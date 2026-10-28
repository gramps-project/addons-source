#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009 Doug Blank <doug.blank@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""
Deep Connections search, independent of any user interface.

Finds chains of family links (spouse, parent, child, sibling and, optionally,
associations and person links in notes) between two people.  This module has
no GTK or Gramps GUI dependencies: it only calls the read methods of a Gramps
database (``get_person_from_handle``, ``get_family_from_handle`` and
``get_note_from_handle``), so it can run headless, for example in a web
server.  Anything a database returns as ``None`` (missing or hidden by a
privacy proxy) is never passed through.

A path is a linked list of nodes ``(previous_node, step)``.  The step of a
node says how that node's person relates to the person of ``previous_node``,
so a path read from the found person back to the root reads like
"A is the sibling of B, who is a parent of C, ...".  The root node is
``(None, Step(SELF, start_handle))``.
"""

from collections import deque
from typing import NamedTuple, Optional, Tuple

# Relation keys.  They are not translated; a user interface maps them to
# display text.  They are gender-neutral: a family's father and mother
# slots say nothing reliable about gender, so the wording ("father",
# "wife", ...) is chosen from the person's own recorded gender.
SELF = "self"
CHILD = "child"
SPOUSE = "spouse"
SIBLING = "sibling"
PARENT = "parent"
ASSOCIATION = "association"
NOTE = "note"


class Step(NamedTuple):
    """One step of a path: ``handle``'s person is ``relation`` of the next."""

    # One of the relation keys above.
    relation: str
    # The person this step is anchored to (the person the relation is to).
    handle: str
    # The parents of the family the step went through, if any.
    parents: Tuple[Optional[str], ...] = ()
    # Extra text, e.g. the description of an association.
    detail: str = ""


def get_links_from_notes(db, obj, path, person_handle):
    """
    Get anyone mentioned in any note attached to this object.
    """
    retval = []
    for note_handle in obj.get_note_list():
        note = db.get_note_from_handle(note_handle)
        if note:
            for link in note.get_links():
                if link[0] == "gramps" and link[1] == "Person":
                    if link[2] == "handle":
                        retval += [(link[3], (path, Step(NOTE, person_handle)))]
    return retval


def get_relatives(
    db,
    person_handle,
    path,
    start_handle=None,
    follow_associations=True,
    follow_notes=True,
):
    """
    Gets all of the relations of person_handle, as ``(handle, path)`` pairs.

    When ``start_handle`` (the start person) is given, the start person is
    kept out of the body of every produced path (issue 8653) -- see the
    post-processing at the end of this function.
    """
    retval = []
    person = db.get_person_from_handle(person_handle)
    if person is None:
        return []
    for family_handle in person.get_family_handle_list():
        family = db.get_family_from_handle(family_handle)
        if family:
            husband = family.get_father_handle()
            wife = family.get_mother_handle()
            retval.extend(
                (child_ref.ref, (path, Step(CHILD, person_handle, (husband, wife))))
                for child_ref in family.get_child_ref_list()
            )
            if husband and husband != person_handle:
                retval += [(husband, (path, Step(SPOUSE, person_handle)))]
            if wife and wife != person_handle:
                retval += [(wife, (path, Step(SPOUSE, person_handle)))]
            if follow_notes:
                retval += get_links_from_notes(db, family, path, person_handle)

    for family_handle in person.get_parent_family_handle_list():
        family = db.get_family_from_handle(family_handle)
        if family:
            husband = family.get_father_handle()
            wife = family.get_mother_handle()
            retval.extend(
                (
                    child_ref.ref,
                    (path, Step(SIBLING, person_handle, (husband, wife))),
                )
                for child_ref in family.get_child_ref_list()
                if child_ref.ref != person_handle
            )
            if husband and husband != person_handle:
                retval += [(husband, (path, Step(PARENT, person_handle, (wife,))))]
            if wife and wife != person_handle:
                retval += [(wife, (path, Step(PARENT, person_handle, (husband,))))]
            if follow_notes:
                retval += get_links_from_notes(db, family, path, person_handle)

    if follow_associations:
        for assoc in person.get_person_ref_list():
            retval += [
                (
                    assoc.get_reference_handle(),
                    (
                        path,
                        Step(ASSOCIATION, person_handle, detail=assoc.get_relation()),
                    ),
                )
            ]

    if follow_notes:
        retval += get_links_from_notes(db, person, path, person_handle)

    # Issue 8653: the start person is the search origin, so it may appear in a
    # produced path only as its terminal "self" root -- never as, nor as the
    # anchor of, an intermediate relationship step.  Two cases, applied only
    # once the caller has supplied the start handle:
    #   * drop a relative that *is* the start person, so the origin is never
    #     re-entered as an interior node of a path; and
    #   * when the start person itself is being expanded, attach its
    #     relatives straight to the root node (``path`` is that root here)
    #     instead of through a redundant "(relation, start)" step that would
    #     render the start person mid-path (the reporter's
    #     "... / sibling of <Home>" chain).
    if start_handle is not None:
        retval = [item for item in retval if item[0] != start_handle]
        if person_handle == start_handle:
            retval = [(item[0], path) for item in retval]
    return retval


def path_depth(path):
    """Calculate the depth of a relationship path."""
    depth = 0
    while path[0] is not None:
        depth += 1
        path = path[0]
    return depth


def path_steps(path):
    """
    Return the steps of a path as a list, from the found person's step back
    to the root ``SELF`` step.
    """
    steps = []
    while path is not None:
        steps.append(path[1])
        path = path[0]
    return steps


class ConnectionSearch:
    """
    Breadth-first search for paths from a start person to a target person.

    Iterate over :meth:`steps` to run the search one person at a time; a user
    interface can update its display between steps.  Use
    :func:`find_connections` to get only the paths.
    """

    def __init__(
        self,
        db,
        start_handle,
        target_handle,
        follow_associations=True,
        follow_notes=True,
    ):
        self.db = db
        self.start_handle = start_handle
        self.target_handle = target_handle
        self.follow_associations = follow_associations
        self.follow_notes = follow_notes
        self.people_processed = 0
        self.depth = 0
        self.queue = deque([(start_handle, (None, Step(SELF, start_handle)))])
        self.visited = set()
        # Everyone ever queued.  A person already queued would only be
        # skipped when popped again, so queuing them twice is wasted work.
        self.queued = {start_handle}

    @property
    def queue_size(self):
        """Number of people waiting to be processed."""
        return len(self.queue)

    def steps(self):
        """
        Run the search, yielding after each person is processed.

        Yields the path to the target each time one is found, and ``None``
        after each other person is expanded.  Paths are yielded in
        breadth-first order, so shorter paths come first.
        """
        while self.queue:
            current_handle, current_path = self.queue.popleft()
            self.people_processed += 1

            if current_handle == self.target_handle:
                yield current_path
                # The target is the search *target*, not a waypoint:
                # expanding it would feed its own relatives back into the
                # queue, which then re-reach the target and re-emit the
                # connection just reported -- the "same path returned every
                # time you press Continue" of issue 10628.  Skip straight to
                # the next queued candidate so each path is a genuinely
                # different connection; the distinct paths other relatives
                # already queued before the target was found are still
                # reported.
                continue
            if current_handle in self.visited:
                continue

            self.visited.add(current_handle)
            relatives = get_relatives(
                self.db,
                current_handle,
                current_path,
                self.start_handle,
                self.follow_associations,
                self.follow_notes,
            )

            if current_path[0] is not None:
                self.depth = max(self.depth, path_depth(current_path))

            for person_handle, path in relatives:
                if person_handle is None:
                    continue
                # The target is queued once per path to it, so each
                # different connection is still reported.
                if person_handle != self.target_handle:
                    if person_handle in self.queued:
                        continue
                    self.queued.add(person_handle)
                self.queue.append((person_handle, path))

            yield None


def find_connections(
    db,
    start_handle,
    target_handle,
    max_paths=None,
    max_people=None,
    follow_associations=True,
    follow_notes=True,
):
    """
    Yield paths from the start person to the target person.

    Stops after ``max_paths`` paths or after ``max_people`` people have been
    processed, whichever comes first (``None`` means no limit).
    """
    search = ConnectionSearch(
        db, start_handle, target_handle, follow_associations, follow_notes
    )
    found = 0
    for path in search.steps():
        if path is not None:
            yield path
            found += 1
            if max_paths is not None and found >= max_paths:
                return
        if max_people is not None and search.people_processed >= max_people:
            return


# ------------------------------------------------------------------------
#
# In-memory family links
#
# ------------------------------------------------------------------------
#
# The search above reads people and families one at a time, which is fine
# for the gramplet but slow on large trees.  The functions below load all
# family links once (from whatever database they are given, so any
# restrictions that database applies are kept) and search in memory.

# ChildRefType values, inlined so this module needs no Gramps imports.
_BIRTH = 1
_UNKNOWN = 6

# Generations searched for a common ancestor, as in Gramps' relationship
# calculator (whose depth 15 covers ancestors up to 14 generations back).
MAX_GENERATIONS = 14


class SearchLimitReached(Exception):
    """The search stopped at its limit before finding a connection."""


class Link(NamedTuple):
    """One person on a path, and how they relate to the person before."""

    handle: str
    # How this person relates to the person before them (PARENT means this
    # person is a parent of the previous one); SELF for the first person.
    relation: str
    # Whether a parent-child step is a birth relationship (also used for
    # siblings: both are birth children of both parents).
    birth: bool = True
    # The family the step goes through.
    family: Optional[str] = None


class FamilyLinks:
    """
    Who is a parent, child, sibling or spouse of whom, loaded once.

    Built from ``db.get_family_cursor()`` alone, so it holds exactly what
    that database returns: a privacy proxy or other restricted database
    leaves out what it hides, and nothing here knows its rules.
    """

    def __init__(self):
        # family -> (father, mother, children)
        self.families = {}
        # (family, child) -> (relation to the father, to the mother), as
        # ChildRefType values
        self.child_types = {}
        # person -> families where they are a parent / a child
        self.parent_in = {}
        self.child_in = {}

    @classmethod
    def load(cls, db):
        """Load the links of all families ``db`` returns."""
        links = cls()
        with db.get_family_cursor() as cursor:
            for handle, family in cursor:
                links.add_family(
                    handle,
                    family["father_handle"],
                    family["mother_handle"],
                    [
                        (
                            child_ref["ref"],
                            child_ref["frel"]["value"],
                            child_ref["mrel"]["value"],
                        )
                        for child_ref in family["child_ref_list"]
                    ],
                )
        return links

    def add_family(self, handle, father, mother, children):
        """
        Add a family; ``children`` are (handle, relation to the father,
        relation to the mother), as ChildRefType values.
        """
        father = father or None
        mother = mother or None
        self.families[handle] = (father, mother, tuple(c[0] for c in children))
        for parent in (father, mother):
            if parent:
                self.parent_in.setdefault(parent, []).append(handle)
        for child, father_type, mother_type in children:
            self.child_types[(handle, child)] = (father_type, mother_type)
            self.child_in.setdefault(child, []).append(handle)

    def is_birth(self, family, child):
        """(Birth child of the father, birth child of the mother)."""
        father_type, mother_type = self.child_types[(family, child)]
        return father_type == _BIRTH, mother_type == _BIRTH

    def parents(self, handle):
        """Yield (parent, family, birth) for each parent of a person."""
        for family in self.child_in.get(handle, ()):
            father, mother, _children = self.families[family]
            birth_father, birth_mother = self.is_birth(family, handle)
            if father:
                yield father, family, birth_father
            if mother:
                yield mother, family, birth_mother

    def neighbours(self, handle):
        """
        Yield every Link from a person to a relative, birth links first, so
        that among equally short paths a birth relationship tends to win.
        """
        links = []
        for family in self.child_in.get(handle, ()):
            father, mother, children = self.families[family]
            mine = self.is_birth(family, handle)
            for parent, birth in ((father, mine[0]), (mother, mine[1])):
                if parent:
                    links.append(Link(parent, PARENT, birth, family))
            for child in children:
                if child != handle:
                    theirs = self.is_birth(family, child)
                    birth = all(mine) and all(theirs)
                    links.append(Link(child, SIBLING, birth, family))
        for family in self.parent_in.get(handle, ()):
            father, mother, children = self.families[family]
            slot = 0 if handle == father else 1
            for child in children:
                birth = self.is_birth(family, child)[slot]
                links.append(Link(child, CHILD, birth, family))
            for spouse in (father, mother):
                if spouse and spouse != handle:
                    links.append(Link(spouse, SPOUSE, True, family))
        links.sort(key=lambda link: not link.birth)
        return links

    def birth_parents(self, handle):
        """(Birth mother, birth father) of a person, None where unknown."""
        mother = father = None
        for family in self.child_in.get(handle, ()):
            family_father, family_mother, _children = self.families[family]
            birth_father, birth_mother = self.is_birth(family, handle)
            if not mother and birth_mother:
                mother = family_mother
            if not father and birth_father:
                father = family_father
            if mother and father:
                break
        return mother, father

    def non_birth_parents(self, handle):
        """Parents of a person known not to be birth parents."""
        parents = set()
        for family in self.child_in.get(handle, ()):
            family_father, family_mother, _children = self.families[family]
            father_type, mother_type = self.child_types[(family, handle)]
            if mother_type not in (_BIRTH, _UNKNOWN):
                parents.add(family_mother)
            if father_type not in (_BIRTH, _UNKNOWN):
                parents.add(family_father)
        return parents

    def sibling_type(self, calc, orig, other):
        """
        The type of sibling ``other`` is of ``orig``, as the constants of
        Gramps' relationship calculator ``calc``, decided the same way as
        its get_sibling_type().
        """
        mother_orig, father_orig = self.birth_parents(orig)
        mother_other, father_other = self.birth_parents(other)
        if father_orig and mother_orig and father_other and mother_other:
            if father_other == father_orig and mother_other == mother_orig:
                return calc.NORM_SIB
            if father_other == father_orig:
                return calc.HALF_SIB_FATHER
            if mother_other == mother_orig:
                return calc.HALF_SIB_MOTHER
            return calc.STEP_SIB
        # some birth parents are unknown: only step siblings can be known
        orig_non_birth = self.non_birth_parents(orig)
        if father_other and father_other in orig_non_birth:
            if mother_other and mother_other == mother_orig:
                return calc.HALF_SIB_MOTHER
            return calc.STEP_SIB
        if mother_other and mother_other in orig_non_birth:
            if father_other and father_other == father_orig:
                return calc.HALF_SIB_FATHER
            return calc.STEP_SIB
        other_non_birth = self.non_birth_parents(other)
        if father_orig and father_orig in other_non_birth:
            if mother_orig and mother_other == mother_orig:
                return calc.HALF_SIB_MOTHER
            return calc.STEP_SIB
        if mother_orig and mother_orig in other_non_birth:
            if father_other and father_other == father_orig:
                return calc.HALF_SIB_FATHER
            return calc.STEP_SIB
        return calc.UNKNOWN_SIB

    def parent_code(self, parent, family, birth):
        """Gramps path code of a step to a parent: f/m, upper case if not birth."""
        code = "f" if parent == self.families[family][0] else "m"
        return code if birth else code.upper()


def _ancestors(links, handle, max_generations):
    """
    Map each ancestor (and the person) to (generations, previous, Link).

    Breadth first, so each ancestor is reached by a shortest line; among
    equally short lines the one with the fewest non-birth links is kept.
    """
    # -> (gens, previous, link, number of non-birth links)
    found = {handle: (0, None, None, 0)}
    level = [handle]
    for generation in range(1, max_generations + 1):
        found_now = {}
        for person in level:
            non_birth = found[person][3]
            for parent, family, birth in links.parents(person):
                if parent in found:
                    continue
                candidate = (
                    generation,
                    person,
                    Link(parent, PARENT, birth, family),
                    non_birth + (not birth),
                )
                old = found_now.get(parent)
                if old is None or candidate[3] < old[3]:
                    found_now[parent] = candidate
        if not found_now:
            break
        found.update(found_now)
        level = list(found_now)
    return found


def _line(found, ancestor):
    """The Links from a person up to ``ancestor`` (not including the person)."""
    line = []
    person = ancestor
    while found[person][1] is not None:
        line.append(found[person][2])
        person = found[person][1]
    line.reverse()
    return line


def descent_path(links, start, target, max_generations=MAX_GENERATIONS):
    """
    The path from ``start`` up to their nearest common ancestor with
    ``target`` and down to ``target``, or None.

    Among common ancestors at the same total distance, the one reached with
    the fewest non-birth links is preferred.
    """
    up = _ancestors(links, start, max_generations)
    down = _ancestors(links, target, max_generations)
    common = set(up) & set(down)
    if not common:
        return None

    def rank(ancestor):
        return (
            up[ancestor][0] + down[ancestor][0],
            up[ancestor][3] + down[ancestor][3],
            ancestor,
        )

    ancestor = min(common, key=rank)
    path = [Link(start, SELF)] + _line(up, ancestor)
    # Down from the ancestor: walk the target's line backwards, turning each
    # "is parent of" step around into "is child of".
    down_line = _line(down, ancestor)
    people = [target] + [link.handle for link in down_line]
    for i in range(len(down_line) - 1, -1, -1):
        link = down_line[i]
        path.append(Link(people[i], CHILD, link.birth, link.family))
    return path


_REVERSE = {PARENT: CHILD, CHILD: PARENT, SIBLING: SIBLING, SPOUSE: SPOUSE}


def any_path(links, start, target, max_people=None):
    """
    A shortest path from ``start`` to ``target`` over any family link, or
    None if there is none.  Searches from both people at once.  Raises
    SearchLimitReached after ``max_people`` people without an answer.
    """
    if start == target:
        return [Link(start, SELF)]
    # person -> (previous person, Link to the person), one map per side
    seen = ({start: None}, {target: None})
    frontier = ([start], [target])
    while frontier[0] and frontier[1]:
        side = 0 if len(frontier[0]) <= len(frontier[1]) else 1
        mine, other = seen[side], seen[1 - side]
        next_level = []
        meet = None
        for person in frontier[side]:
            for link in links.neighbours(person):
                if link.handle in mine:
                    continue
                mine[link.handle] = (person, link)
                if link.handle in other:
                    meet = link.handle
                    break
                next_level.append(link.handle)
            if meet:
                break
            if max_people is not None and len(seen[0]) + len(seen[1]) > max_people:
                raise SearchLimitReached()
        if meet:
            return _join(seen, start, meet)
        frontier[side][:] = next_level
    return None


def _join(seen, start, meet):
    """Join the two half paths that met at ``meet`` into one from ``start``."""
    path = []
    person = meet
    while seen[0][person] is not None:
        previous, link = seen[0][person]
        path.append(link)
        person = previous
    path.append(Link(start, SELF))
    path.reverse()
    # From the meeting point to the target, each stored Link points away
    # from the target, so turn it around.
    person = meet
    while seen[1][person] is not None:
        previous, link = seen[1][person]
        path.append(Link(previous, _REVERSE[link.relation], link.birth, link.family))
        person = previous
    return path


def shortest_connection(links, start, target, max_people=None):
    """
    How ``target`` is connected to ``start``: through their nearest common
    ancestor if they have one, otherwise by the shortest chain of any family
    links.  Returns a list of Links from ``start`` to ``target``, or None.
    """
    return descent_path(links, start, target) or any_path(
        links, start, target, max_people
    )


# ------------------------------------------------------------------------
#
# Labels
#
# ------------------------------------------------------------------------


def _blood_codes(links, path, previous):
    """
    Gramps path codes (up from the first person, up from the last) for a
    path that only goes up and then down, or None if it doesn't.

    ``previous`` is the person before ``path[0]``.
    """
    up, down = "", ""
    for link in path:
        if link.relation == PARENT and not down:
            up += links.parent_code(link.handle, link.family, link.birth)
        elif link.relation == CHILD:
            down = links.parent_code(previous, link.family, link.birth) + down
        elif link.relation == SIBLING and not down:
            father, mother, _children = links.families[link.family]
            parent = father or mother
            up += links.parent_code(parent, link.family, link.birth)
            down = links.parent_code(parent, link.family, link.birth) + down
        else:
            return None
        previous = link.handle
    return up, down


def _wording(
    links, calc, codes, orig, other, genders, gender_a, in_law_a=False, in_law_b=False
):
    """
    The wording for blood relatives ``orig`` and ``other`` with the given
    path codes; ``gender_a`` is the first person's gender (who may be the
    spouse of ``orig``) and ``genders`` maps handles to genders.
    """
    up, down = codes
    birth = (up + down).islower()
    gender_b = genders[other]
    if len(up) == 1 and len(down) == 1:
        return calc.get_sibling_relationship_string(
            links.sibling_type(calc, orig, other),
            gender_a,
            gender_b,
            in_law_a=in_law_a,
            in_law_b=in_law_b,
        )
    return calc.get_single_relationship_string(
        len(up),
        len(down),
        gender_a,
        gender_b,
        up,
        down,
        only_birth=birth,
        in_law_a=in_law_a,
        in_law_b=in_law_b,
    )


def path_labels(links, path, genders, calc):
    """
    Each person's relationship to the first person along the path, while
    the path goes only up and then down; "" for everyone after that.

    ``genders`` maps handles to Gramps genders and ``calc`` is a Gramps
    relationship calculator (for the wording, in its language).
    """
    labels = [""]
    start = path[0].handle
    for i in range(1, len(path)):
        codes = _blood_codes(links, path[1 : i + 1], start)
        if codes is None:
            return labels + [""] * (len(path) - i)
        labels.append(
            _wording(links, calc, codes, start, path[i].handle, genders, genders[start])
        )
    return labels


def connection_label(links, path, genders, calc):
    """
    The relationship of the last person on the path to the first, if the
    path is a blood relationship or an in-law (one spouse step at either
    end); otherwise "".  A path that is a single spouse step gets "".
    """
    start, target = path[0].handle, path[-1].handle
    if len(path) < 2:
        return ""
    codes = _blood_codes(links, path[1:], start)
    if codes is not None:
        return _wording(links, calc, codes, start, target, genders, genders[start])
    if len(path) > 2 and path[1].relation == SPOUSE:
        # a blood relative of the first person's spouse
        spouse = path[1].handle
        codes = _blood_codes(links, path[2:], spouse)
        if codes is not None:
            return _wording(
                links,
                calc,
                codes,
                spouse,
                target,
                genders,
                genders[start],
                in_law_a=True,
            )
    if len(path) > 2 and path[-1].relation == SPOUSE:
        # the spouse of a blood relative of the first person
        relative = path[-2].handle
        codes = _blood_codes(links, path[1:-1], start)
        if codes is not None:
            # worded as the relative, but with the spouse's gender
            spouse_genders = dict(genders)
            spouse_genders[relative] = genders[target]
            return _wording(
                links,
                calc,
                codes,
                start,
                relative,
                spouse_genders,
                genders[start],
                in_law_b=True,
            )
    return ""
