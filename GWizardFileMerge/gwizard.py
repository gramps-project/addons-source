#
# Gramps - a GTK+/GNOME based genealogy program
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""
Base class and interfaces for the GWizard import framework.
"""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
from __future__ import annotations
import abc
import difflib
import logging
import re
import unicodedata
from typing import Any, NamedTuple

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.db.base import DbWriteBase
from gramps.gen.errors import HandleError
from gramps.gen.types import PersonHandle
from gramps.gen.lib import Person, Event, Name
from gramps.gen.soundex import soundex
from gramps.gen.const import GRAMPS_LOCALE as glocale

# -------------------------------------------------------------------------
#
# Log
#
# -------------------------------------------------------------------------
LOG = logging.getLogger(__name__)

_ = glocale.translation.gettext


# ------------------------------------------------------------
#
# GWizardCompareRow
#
# ------------------------------------------------------------
class GWizardCompareRow(NamedTuple):
    """
    Represent a single side-by-side comparative difference between a source
    and a target person record.
    """

    status: str  # "match", "differ", "source_only", "target_only"
    field: str  # e.g., "Given Name", "Surname", "Birth Date", etc.
    source_val: str  # value in external source (e.g. GEDCOM or FamilySearch)
    target_val: str  # value in main target Gramps DB
    source_date: str = ""
    target_date: str = ""
    field_type: str = ""  # metadata describing field type for apply routing
    extra_data: Any = None  # arbitrary custom data payload (e.g., event references)


# ------------------------------------------------------------
#
# GWizardBase
#
# ------------------------------------------------------------
class GWizardBase(abc.ABC):
    """
    Abstract base class representing the step-by-step wizard workflow (GWizard).

    The workflow sequence is:
    connect -> load -> match -> compare -> apply.
    """

    def __init__(self, db: DbWriteBase) -> None:
        """
        Initialize the GWizard workflow.

        :param db: The target Gramps database instance.
        """
        self.db = db
        self.context: dict[str, Any] = {}
        self.current_step: str = ""

    def get_steps(self) -> list[str]:
        """
        Return the list of step names in the wizard sequence.

        :returns: A list of step identifiers in order.
        :rtype: list[str]
        """
        return ["connect", "load", "match", "compare", "apply"]

    def get_step_title(self, step: str) -> str:
        """
        Return a user-friendly, translatable title for the step.

        :param step: The step identifier.
        :returns: Translatable step title.
        :rtype: str
        """
        titles = {
            "connect": _("Configure Connection"),
            "load": _("Load Data"),
            "match": _("Find Matching Persons"),
            "compare": _("Compare Differences"),
            "apply": _("Apply Changes"),
        }
        return titles.get(step, step)

    def get_step_description(self, step: str) -> str:
        """
        Return a user-friendly, translatable description for the step.

        :param step: The step identifier.
        :returns: Translatable step description.
        :rtype: str
        """
        descriptions = {
            "connect": _("Configure file path or authenticate with online service."),
            "load": _("Load/parse the external genealogy data into memory."),
            "match": _("Search for potential matches in your database."),
            "compare": _("Compare fields side-by-side between the source and target."),
            "apply": _("Merge selected changes or add new records to the database."),
        }
        return descriptions.get(step, step)

    def run_step(self, step: str, **kwargs: Any) -> Any:
        """
        Execute the hook corresponding to the specified step.

        :param step: The step identifier.
        :returns: The result of the step execution.
        """
        self.current_step = step
        LOG.debug("Running GWizard step: %s with args: %s", step, kwargs)

        if step == "connect":
            return self._connect(**kwargs)
        elif step == "load":
            return self._load(**kwargs)
        elif step == "match":
            return self._match(**kwargs)
        elif step == "compare":
            return self._compare(**kwargs)
        elif step == "apply":
            return self._apply(**kwargs)
        else:
            raise ValueError(f"Unknown step: {step}")

    @abc.abstractmethod
    def _connect(self, **kwargs: Any) -> bool:
        """
        Establish connection details.

        :returns: True if successful, False otherwise.
        :rtype: bool
        """

    @abc.abstractmethod
    def _load(self, **kwargs: Any) -> Any:
        """
        Load records from source into the wizard context.

        :returns: Loaded data/records.
        """

    @abc.abstractmethod
    def _match(self, **kwargs: Any) -> list[dict[str, Any]]:
        """
        Find candidates in target db matching source records.

        :returns: List of match candidates.
        :rtype: list[dict[str, Any]]
        """

    @abc.abstractmethod
    def _compare(self, **kwargs: Any) -> list[GWizardCompareRow]:
        """
        Perform a field-by-field comparison of a source person and target person.

        :returns: List of comparison rows.
        :rtype: list[GWizardCompareRow]
        """

    @abc.abstractmethod
    def _apply(self, **kwargs: Any) -> bool:
        """
        Apply selected changes to the target database.

        :returns: True if successful, False otherwise.
        :rtype: bool
        """


# ------------------------------------------------------------
#
# Safe handle lookups
#
# ------------------------------------------------------------
def safe_get(db: Any, handle: str | None, getter_name: str, what: str) -> Any | None:
    """
    Fetch a primary object by handle, returning None instead of raising.

    ``DbReadBase.get_*_from_handle`` raises :class:`HandleError` for an
    unknown handle rather than returning None, which makes naive
    ``if not obj: continue`` guards ineffective. Handles held by the
    comparison UI can go stale (a merge may delete or replace the
    counterpart person), so every dereference of a UI-held handle must
    tolerate a dangling reference.

    :param db: The database to look the handle up in.
    :param handle: The handle to resolve, possibly None or empty.
    :param getter_name: Name of the ``get_*_from_handle`` method to call.
    :param what: Human-readable object kind, used for the debug log.
    :returns: The object, or None when the handle is empty or dangling.
    """
    if not handle:
        return None
    try:
        return getattr(db, getter_name)(handle)
    except HandleError:
        LOG.debug("Stale %s handle ignored: %s", what, handle)
        return None


def safe_get_person(db: Any, handle: str | None) -> Person | None:
    """Return the person for handle, or None when it is empty or dangling."""
    return safe_get(db, handle, "get_person_from_handle", "person")


def safe_get_family(db: Any, handle: str | None) -> Any | None:
    """Return the family for handle, or None when it is empty or dangling."""
    return safe_get(db, handle, "get_family_from_handle", "family")


def safe_get_event(db: Any, handle: str | None) -> Event | None:
    """Return the event for handle, or None when it is empty or dangling."""
    return safe_get(db, handle, "get_event_from_handle", "event")


def safe_get_place(db: Any, handle: str | None) -> Any | None:
    """Return the place for handle, or None when it is empty or dangling."""
    return safe_get(db, handle, "get_place_from_handle", "place")


def safe_get_source(db: Any, handle: str | None) -> Any | None:
    """Return the source for handle, or None when it is empty or dangling."""
    return safe_get(db, handle, "get_source_from_handle", "source")


def safe_get_repository(db: Any, handle: str | None) -> Any | None:
    """Return the repository for handle, or None when it is empty or dangling."""
    return safe_get(db, handle, "get_repository_from_handle", "repository")


def vital_event_ref(db: Any, person: Person | None, kind: str) -> Any | None:
    """Return the birth or death EventRef, with a type-scan fallback."""
    if person is None or db is None:
        return None
    try:
        ref = person.get_birth_ref() if kind == "birth" else person.get_death_ref()
    except Exception:
        ref = None
    if ref is not None:
        return ref
    try:
        refs = person.get_event_ref_list() or []
    except Exception:
        return None
    want_birth = kind == "birth"
    for cand in refs:
        try:
            event = safe_get_event(db, getattr(cand, "ref", None))
        except Exception:
            continue
        if event is None:
            continue
        try:
            etype = event.get_type()
        except Exception:
            continue
        try:
            is_match = etype.is_birth() if want_birth else etype.is_death()
        except Exception:
            continue
        if is_match:
            return cand
    return None


# ------------------------------------------------------------
#
# Source matching helpers
#
# ------------------------------------------------------------
SOURCE_MATCHED = "matched"
SOURCE_AMBIGUOUS = "ambiguous"
SOURCE_NEW = "new"

_MARKUP_TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")


def normalize_source_text(text: str | None) -> str:
    """
    Normalize source text for comparison.

    Applies Unicode NFKC, removes simple HTML tags (titles exported from
    FamilySearch carry ``<i>`` markup), collapses whitespace and casefolds.

    :param text: Title, author, publication info or page text, or None.
    :returns: The normalized text, '' for None or empty input.
    """
    text = unicodedata.normalize("NFKC", _MARKUP_TAG_RE.sub("", text or ""))
    return " ".join(text.split()).casefold()


def source_signature(source: Any) -> tuple[str, str, str] | None:
    """
    Return the (title, author, publication info) key used to match sources.

    :param source: A Gramps ``Source``.
    :returns: The normalized key, or None when the source has no title
        (a source without a title is never matched).
    """
    title = normalize_source_text(source.get_title())
    if not title:
        return None
    return (
        title,
        normalize_source_text(source.get_author()),
        normalize_source_text(source.get_publication_info()),
    )


class SourceMatcher:
    """
    Find the source in ``db`` that an incoming source corresponds to.

    Sources match only when title, author and publication info all agree
    after normalization. When several sources in ``db`` share a key the
    result is ambiguous and nothing is matched, so callers add a new
    source instead of guessing. The index over ``db`` is built on first
    use; sources created afterwards must be registered with :meth:`add`.
    """

    def __init__(self, db: Any) -> None:
        self.db = db
        self._index: dict[tuple[str, str, str], list[str]] | None = None

    def _ensure_index(self) -> dict[tuple[str, str, str], list[str]]:
        if self._index is None:
            index: dict[tuple[str, str, str], list[str]] = {}
            for source in self.db.iter_sources():
                signature = source_signature(source)
                if signature is not None:
                    index.setdefault(signature, []).append(source.handle)
            self._index = index
        return self._index

    def find(self, source: Any) -> tuple[str | None, str]:
        """
        Look up the counterpart of ``source`` in the database.

        :returns: ``(handle, SOURCE_MATCHED)`` for exactly one match,
            ``(None, SOURCE_AMBIGUOUS)`` for several, otherwise
            ``(None, SOURCE_NEW)``.
        """
        signature = source_signature(source)
        if signature is None:
            return None, SOURCE_NEW
        handles = self._ensure_index().get(signature, [])
        if len(handles) == 1:
            return handles[0], SOURCE_MATCHED
        if len(handles) > 1:
            return None, SOURCE_AMBIGUOUS
        return None, SOURCE_NEW

    def add(self, source: Any) -> None:
        """Register a source that was just added to the database."""
        signature = source_signature(source)
        if signature is None:
            return
        handles = self._ensure_index().setdefault(signature, [])
        if source.handle not in handles:
            handles.append(source.handle)


def source_match_report(source_db: Any, target_db: Any) -> list[dict[str, str]]:
    """
    Describe how each incoming source would be treated by a merge.

    Read-only; useful for checking a real file against a real tree
    before relying on source matching.

    :returns: One dict per incoming source with ``title``, ``author``,
        ``status`` (matched, ambiguous or new) and ``target_handle``,
        sorted by status then title.
    """
    matcher = SourceMatcher(target_db)
    rows = []
    for source in source_db.iter_sources():
        handle, status = matcher.find(source)
        rows.append(
            {
                "title": source.get_title() or "",
                "author": source.get_author() or "",
                "status": status,
                "target_handle": handle or "",
            }
        )
    rows.sort(key=lambda r: (r["status"], r["title"].casefold()))
    return rows


# ------------------------------------------------------------
#
# Given-name matching helpers
#
# ------------------------------------------------------------
_QUOTED_NICK_RE = re.compile(r'"[^"]*"|\([^)]*\)|\'[^\']*\'')


def _strip_embedded_nickname(given: str) -> str:
    """
    Remove embedded nicknames in quotes or parentheses.
    """
    return _QUOTED_NICK_RE.sub(" ", given)


def _given_tokens(given: str) -> list[str]:
    """
    Split a given-name string into lowercase tokens.
    """
    cleaned = _strip_embedded_nickname(given)
    cleaned = cleaned.replace("-", " ")
    return [tok.lower() for tok in cleaned.split() if tok]


def score_given_names(source_given: str, target_given: str) -> float:
    """
    Score two given-name strings from 0.0 to 1.0.
    """
    s_raw = (source_given or "").strip()
    t_raw = (target_given or "").strip()
    if not s_raw or not t_raw:
        return 0.0
    if s_raw.lower() == t_raw.lower():
        return 1.0
    s_tokens = _given_tokens(s_raw)
    t_tokens = _given_tokens(t_raw)
    if not s_tokens or not t_tokens:
        return 0.0
    if s_tokens == t_tokens:
        return 1.0
    # Reversed / reordered tokens: same set regardless of order
    if sorted(s_tokens) == sorted(t_tokens):
        return 0.9
    # Partial token overlap (e.g. shared middle name only)
    if set(s_tokens) & set(t_tokens):
        return 0.5
    # Fuzzy similarity on the cleaned full strings
    ratio = difflib.SequenceMatcher(
        None, " ".join(s_tokens), " ".join(t_tokens)
    ).ratio()
    if ratio >= 0.8:
        return 0.6
    if s_tokens[0][0] == t_tokens[0][0]:
        return 0.25
    return 0.0


# ------------------------------------------------------------
#
# Name part helpers
#
# ------------------------------------------------------------
def surname_text(name: Name) -> str:
    """
    Return every surname of a name object as one space separated string.

    A name may carry more than one surname (a GEDCOM ``SURN`` with comma
    separated values such as "Hansdotter, Smith"). Joining them keeps the
    multi-surname case visible when two records are compared.

    :param name: The name object to read.
    :returns: Space-separated surnames, e.g. ``"Hansdotter Smith"``.
    :rtype: str
    """
    return " ".join(
        [surn.get_surname() for surn in name.get_surname_list() if surn.get_surname()]
    )


def surname_prefix_text(name: Name) -> str:
    """
    Return every surname prefix of a name object, space separated.

    Prefixes come from the GEDCOM ``SPFX`` tag (for example ``2 SPFX Vrow``)
    and are stored per surname - never inside the surname string itself - so
    comparing surnames alone silently hides them.

    :param name: The name object to read.
    :returns: Space-separated prefixes, e.g. ``"Vrow"`` or ``""``.
    :rtype: str
    """
    return " ".join(
        [surn.get_prefix() for surn in name.get_surname_list() if surn.get_prefix()]
    )


# ------------------------------------------------------------
#
# CandidateMatcher
#
# ------------------------------------------------------------
class CandidateMatcher:
    """
    Match engine to identify potential matches in a Gramps DB for a source person.
    """

    def __init__(self, db: DbWriteBase) -> None:
        """
        Initialize the CandidateMatcher.

        :param db: The database to search for matches in.
        """
        self.db = db

    def get_surnames(self, name: Name) -> str:
        """
        Helper to extract all surnames from a name object as a space-separated string.

        :param name: The name object.
        :returns: Space-separated surnames.
        :rtype: str
        """
        return surname_text(name)

    def get_prefixes(self, name: Name) -> str:
        """
        Helper to extract all surname prefixes from a name object.

        :param name: The name object.
        :returns: Space-separated surname prefixes (empty parts skipped).
        :rtype: str
        """
        return surname_prefix_text(name)

    def score_match(
        self,
        source: Person,
        target: Person,
        source_db: Any | None = None,
    ) -> float:
        """
        Score how closely two Person records match. Returns -1.0 for a complete mismatch,
        otherwise a non-negative float matching score.

        :param source: The source person object.
        :param target: The target person object.
        :param source_db: Database holding the source person (for birth events).
            Defaults to the target database when omitted.
        :returns: The calculated match score or -1.0.
        :rtype: float
        """
        # Gender must match, or be unknown/other in either
        s_gender = source.get_gender()
        t_gender = target.get_gender()
        if s_gender in (Person.MALE, Person.FEMALE) and t_gender in (
            Person.MALE,
            Person.FEMALE,
        ):
            if s_gender != t_gender:
                return -1.0

        score = 0.0

        # Compare surnames via exact and soundex
        s_name = source.get_primary_name()
        t_name = target.get_primary_name()

        s_surnames = self.get_surnames(s_name).strip()
        t_surnames = self.get_surnames(t_name).strip()

        s_lookup_db = source_db if source_db is not None else self.db
        # Given name match (token-aware: reorderings, quoted nicknames,
        # fuzzy similarity, same-initial fallback)
        s_given = s_name.first_name.strip()
        t_given = t_name.first_name.strip()

        given_score = 0.0
        if s_given and t_given:
            given_score = score_given_names(s_given, t_given)
            score += given_score

        # Avoid pairing newcomers on surname alone: when both given
        # names are present but totally dissimilar, cap the surname
        # credit so a shared surname cannot auto-match by itself.
        surname_score = 0.0
        if s_surnames and t_surnames:
            if s_surnames.lower() == t_surnames.lower():
                surname_score = 1.0
            else:
                try:
                    if soundex(s_surnames) == soundex(t_surnames):
                        surname_score = 0.75
                except Exception:
                    pass
            if given_score == 0.0 and s_given and t_given:
                surname_score = min(surname_score, 0.25)
            score += surname_score

        # Birth date match helper (partial-date aware)
        s_birth_ref = vital_event_ref(s_lookup_db, source, "birth")
        t_birth_ref = vital_event_ref(self.db, target, "birth")

        if s_birth_ref and t_birth_ref:
            try:
                s_birth = safe_get_event(s_lookup_db, s_birth_ref.ref)
                t_birth = safe_get_event(self.db, t_birth_ref.ref)
                if s_birth is not None and t_birth is not None:
                    s_date = s_birth.get_date_object()
                    t_date = t_birth.get_date_object()
                    s_year = s_date.get_year()
                    t_year = t_date.get_year()
                    if s_year > 0 and t_year > 0:
                        diff = abs(s_year - t_year)
                        if diff != 0:
                            if diff <= 2:
                                score += 0.5
                            elif diff <= 5:
                                score += 0.25
                        else:
                            s_mon = s_date.get_month()
                            t_mon = t_date.get_month()
                            s_day = s_date.get_day()
                            t_day = t_date.get_day()
                            if s_mon <= 0 or t_mon <= 0:
                                # One side is year-only: same year, partial info
                                score += 0.75
                            elif s_mon != t_mon:
                                score += 0.5
                            elif s_day <= 0 or t_day <= 0:
                                score += 0.85
                            elif s_day != t_day:
                                score += 0.75
                            else:
                                score += 1.0
            except Exception:
                pass

        return score

    def find_matches(
        self,
        source: Person,
        threshold: float = 1.0,
        source_db: Any | None = None,
    ) -> list[tuple[PersonHandle, float]]:
        """
        Search the target database for potential matching candidates.

        :param source: The source person object to find matches for.
        :param threshold: The minimum matching score required to include a candidate.
        :param source_db: Database holding the source person (for birth events).
        :returns: List of tuples containing target person handles and their match scores.
        :rtype: list[tuple[PersonHandle, float]]
        """
        results: list[tuple[PersonHandle, float]] = []

        for handle in self.db.iter_person_handles():
            try:
                target = safe_get_person(self.db, handle)
                if target is None:
                    continue
                score = self.score_match(source, target, source_db=source_db)
                if score >= threshold:
                    results.append((PersonHandle(handle), score))
            except Exception:
                continue

        # Sort descending by score
        results.sort(key=lambda item: item[1], reverse=True)
        return results
