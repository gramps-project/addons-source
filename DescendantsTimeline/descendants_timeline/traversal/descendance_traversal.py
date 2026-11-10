"""Parcours DFS de la descendance.

Le module travaille uniquement sur ``RawGenealogyData``. Il ne réalise
aucune inférence temporelle et aucun calcul graphique.

Deux sorties complémentaires sont produites :
- ``rows`` : ordre logique des personnes à afficher ;
- ``family_occurrences`` : état de chaque famille rencontrée dans le parcours.

Cette séparation permet notamment de représenter correctement une personne
ayant plusieurs familles, dont certaines ont déjà été développées et
d'autres non.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from descendants_timeline.model.child_ref import ChildRelation
from descendants_timeline.model.genealogy import RawGenealogyData


class DescendanceMode(str, Enum):
    """Politique d'inclusion des relations enfant-parent dans le DFS."""

    BIOLOGICAL_ONLY = "BIOLOGICAL_ONLY"
    EXTENDED = "EXTENDED"


@dataclass(frozen=True, slots=True)
class TraversalOptions:
    """Options du parcours de descendance."""

    mode: DescendanceMode = DescendanceMode.BIOLOGICAL_ONLY

    def __post_init__(self) -> None:
        if not isinstance(self.mode, DescendanceMode):
            raise TypeError("mode must be a DescendanceMode")


class TraversalRole(str, Enum):
    """Rôle d'une ligne-personne dans le résultat du parcours."""

    ROOT = "ROOT"
    DESCENDANT = "DESCENDANT"
    SPOUSE = "SPOUSE"


class FamilyTraversalState(str, Enum):
    """État d'une occurrence de famille dans le DFS."""

    EXPLORED = "EXPLORED"
    ALREADY_DESCRIBED = "ALREADY_DESCRIBED"


@dataclass(frozen=True, slots=True)
class TraversalRow:
    """Une ligne logique représentant une personne.

    ``generation`` appartient à l'occurrence dans le parcours et non à
    l'objet Person. Une même personne peut donc apparaître avec des
    générations différentes selon la branche parcourue.
    """

    person_id: str
    generation: int
    role: TraversalRole
    family_id: str | None
    spouse_of_person_id: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.person_id, str) or not self.person_id.strip():
            raise ValueError("person_id must be a non-empty string")

        if not isinstance(self.generation, int) or self.generation < 1:
            raise ValueError("generation must be an integer >= 1")

        if not isinstance(self.role, TraversalRole):
            raise TypeError("role must be a TraversalRole")

        if self.family_id is not None:
            if not isinstance(self.family_id, str) or not self.family_id.strip():
                raise ValueError("family_id must be a non-empty string or None")

        if self.spouse_of_person_id is not None:
            if (
                not isinstance(self.spouse_of_person_id, str)
                or not self.spouse_of_person_id.strip()
            ):
                raise ValueError(
                    "spouse_of_person_id must be a non-empty string or None"
                )

        if self.role is TraversalRole.SPOUSE:
            if self.family_id is None:
                raise ValueError("a SPOUSE row must reference a family_id")
            if self.spouse_of_person_id is None:
                raise ValueError(
                    "a SPOUSE row must reference spouse_of_person_id"
                )


@dataclass(frozen=True, slots=True)
class TraversalFamilyOccurrence:
    """Décrit une famille telle qu'elle est rencontrée dans le parcours.

    ``referenced_row_index`` est un index Python (base 0) vers la ligne du
    descendant qui avait développé cette famille lors de sa première
    occurrence. Il vaut ``None`` pour une famille explorée pour la première fois.
    """

    family_id: str
    descendant_person_id: str
    descendant_row_index: int
    spouse_person_id: str | None
    spouse_row_index: int | None
    state: FamilyTraversalState
    referenced_row_index: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.family_id, str) or not self.family_id.strip():
            raise ValueError("family_id must be a non-empty string")

        if (
            not isinstance(self.descendant_person_id, str)
            or not self.descendant_person_id.strip()
        ):
            raise ValueError("descendant_person_id must be a non-empty string")

        if (
            not isinstance(self.descendant_row_index, int)
            or self.descendant_row_index < 0
        ):
            raise ValueError("descendant_row_index must be an integer >= 0")

        if self.spouse_person_id is None:
            if self.spouse_row_index is not None:
                raise ValueError(
                    "spouse_row_index must be None when spouse_person_id is None"
                )
        else:
            if (
                not isinstance(self.spouse_person_id, str)
                or not self.spouse_person_id.strip()
            ):
                raise ValueError(
                    "spouse_person_id must be a non-empty string or None"
                )
            if (
                not isinstance(self.spouse_row_index, int)
                or self.spouse_row_index < 0
            ):
                raise ValueError(
                    "spouse_row_index must be an integer >= 0 when a spouse exists"
                )

        if not isinstance(self.state, FamilyTraversalState):
            raise TypeError("state must be a FamilyTraversalState")

        if self.state is FamilyTraversalState.EXPLORED:
            if self.referenced_row_index is not None:
                raise ValueError(
                    "an EXPLORED family must not have referenced_row_index"
                )

        if self.state is FamilyTraversalState.ALREADY_DESCRIBED:
            if (
                not isinstance(self.referenced_row_index, int)
                or self.referenced_row_index < 0
            ):
                raise ValueError(
                    "an ALREADY_DESCRIBED family must reference a previous row"
                )


@dataclass(frozen=True, slots=True)
class TraversalResult:
    """Résultat immuable du parcours DFS."""

    root_person_id: str
    rows: tuple[TraversalRow, ...]
    family_occurrences: tuple[TraversalFamilyOccurrence, ...]


class DescendanceTraversal:
    """Construit l'ordre logique d'une descendance par parcours DFS."""

    def traverse(
        self,
        data: RawGenealogyData,
        root_person_id: str,
        options: TraversalOptions | None = None,
    ) -> TraversalResult:
        if not isinstance(data, RawGenealogyData):
            raise TypeError("data must be RawGenealogyData")

        if not isinstance(root_person_id, str) or not root_person_id.strip():
            raise ValueError("root_person_id must be a non-empty string")

        if root_person_id not in data.persons:
            raise ValueError("root_person_id must reference a person present in data")

        if options is None:
            options = TraversalOptions()

        if not isinstance(options, TraversalOptions):
            raise TypeError("options must be TraversalOptions")

        rows: list[TraversalRow] = []
        occurrences: list[TraversalFamilyOccurrence] = []

        # family_id -> index de la ligne descendant ayant développé
        # cette famille lors de sa première rencontre.
        first_family_row: dict[str, int] = {}

        def visit_person(
            person_id: str,
            generation: int,
            role: TraversalRole,
            parent_family_id: str | None,
        ) -> None:
            person = data.persons[person_id]

            descendant_row_index = len(rows)
            rows.append(
                TraversalRow(
                    person_id=person_id,
                    generation=generation,
                    role=role,
                    family_id=parent_family_id,
                    spouse_of_person_id=None,
                )
            )

            for family_id in person.family_ids:
                family = data.families[family_id]

                if family.parent1_id == person_id:
                    spouse_id = family.parent2_id
                    parent_position = 1
                elif family.parent2_id == person_id:
                    spouse_id = family.parent1_id
                    parent_position = 2
                else:
                    raise ValueError(
                        f"Person {person_id} references family {family_id} "
                        "but is not one of its parents"
                    )

                spouse_row_index: int | None = None

                # Même pour une famille déjà développée, le conjoint est affiché
                # afin de conserver la structure du couple dans la vue.
                if spouse_id is not None:
                    spouse_row_index = len(rows)
                    rows.append(
                        TraversalRow(
                            person_id=spouse_id,
                            generation=generation,
                            role=TraversalRole.SPOUSE,
                            family_id=family_id,
                            spouse_of_person_id=person_id,
                        )
                    )

                if family_id in first_family_row:
                    occurrences.append(
                        TraversalFamilyOccurrence(
                            family_id=family_id,
                            descendant_person_id=person_id,
                            descendant_row_index=descendant_row_index,
                            spouse_person_id=spouse_id,
                            spouse_row_index=spouse_row_index,
                            state=FamilyTraversalState.ALREADY_DESCRIBED,
                            referenced_row_index=first_family_row[family_id],
                        )
                    )
                    continue

                first_family_row[family_id] = descendant_row_index

                occurrences.append(
                    TraversalFamilyOccurrence(
                        family_id=family_id,
                        descendant_person_id=person_id,
                        descendant_row_index=descendant_row_index,
                        spouse_person_id=spouse_id,
                        spouse_row_index=spouse_row_index,
                        state=FamilyTraversalState.EXPLORED,
                        referenced_row_index=None,
                    )
                )

                for child_ref in family.child_refs:
                    relation = (
                        child_ref.relation_to_parent1
                        if parent_position == 1
                        else child_ref.relation_to_parent2
                    )

                    if self._include_relation(relation, options.mode):
                        visit_person(
                            person_id=child_ref.person_id,
                            generation=generation + 1,
                            role=TraversalRole.DESCENDANT,
                            parent_family_id=family_id,
                        )

        visit_person(
            person_id=root_person_id,
            generation=1,
            role=TraversalRole.ROOT,
            parent_family_id=None,
        )

        return TraversalResult(
            root_person_id=root_person_id,
            rows=tuple(rows),
            family_occurrences=tuple(occurrences),
        )

    @staticmethod
    def _include_relation(
        relation: ChildRelation,
        mode: DescendanceMode,
    ) -> bool:
        if mode is DescendanceMode.BIOLOGICAL_ONLY:
            return relation is ChildRelation.BIRTH

        if mode is DescendanceMode.EXTENDED:
            return relation in {
                ChildRelation.BIRTH,
                ChildRelation.ADOPTED,
                ChildRelation.SPONSORED,
            }

        raise ValueError(f"Unsupported DescendanceMode: {mode}")
