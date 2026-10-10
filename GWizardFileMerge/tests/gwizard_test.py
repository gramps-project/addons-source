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
Unit tests for the GWizard import framework and GEDCOM implementation.
"""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
from __future__ import annotations
import os
import shutil
import sys
import tempfile
import unittest

# Set up test resources environment variables before importing any Gramps module
#
# Gramps needs authors.xml, gramps.png and COPYING at import time. In a source
# checkout they are copied from the repository into a temporary resource
# directory. When this test runs from an installed addon (no source checkout
# anywhere above or beside the ``gramps`` package), the installed Gramps
# already provides them, so the environment is left alone.
_RESOURCE_FILES = (
    ("data", "authors.xml"),
    ("images", "gramps.png"),
    ("COPYING",),
)


def _find_source_root() -> str | None:
    """Return a Gramps source checkout root holding the resources, or None."""
    candidates = [
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..")
        )
    ]
    try:
        import importlib.util

        spec = importlib.util.find_spec("gramps")
        for location in (spec.submodule_search_locations or []) if spec else []:
            candidates.append(os.path.dirname(os.path.abspath(location)))
    except (ImportError, ValueError):
        pass
    for candidate in candidates:
        if all(os.path.isfile(os.path.join(candidate, *f)) for f in _RESOURCE_FILES):
            return candidate
    return None


resource_path = os.environ.get("GRAMPS_RESOURCES")
if not resource_path or not os.path.exists(
    os.path.join(resource_path, "gramps", "authors.xml")
):
    ROOT_DIR = _find_source_root()
    if ROOT_DIR is not None:
        resource_path = tempfile.mkdtemp(prefix="gramps-resources-")
        os.makedirs(os.path.join(resource_path, "gramps", "images"), exist_ok=True)
        os.makedirs(os.path.join(resource_path, "doc", "gramps"), exist_ok=True)
        os.makedirs(os.path.join(resource_path, "locale"), exist_ok=True)

        shutil.copyfile(
            os.path.join(ROOT_DIR, "data", "authors.xml"),
            os.path.join(resource_path, "gramps", "authors.xml"),
        )
        shutil.copyfile(
            os.path.join(ROOT_DIR, "images", "gramps.png"),
            os.path.join(resource_path, "gramps", "images", "gramps.png"),
        )
        shutil.copyfile(
            os.path.join(ROOT_DIR, "COPYING"),
            os.path.join(resource_path, "doc", "gramps", "COPYING"),
        )
        os.environ["GRAMPS_RESOURCES"] = resource_path

os.environ["HOME"] = os.environ.get("HOME") or tempfile.mkdtemp(prefix="gramps-home-")

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.db.base import DbWriteBase
from gramps.gen.db.txn import DbTxn
from gramps.gen.db.utils import make_database
from gramps.gen.errors import HandleError
from gramps.gen.lib import (
    Person,
    Event,
    Place,
    Surname,
    Name,
    Date,
    EventRef,
    EventType,
)
from gramps.gen.types import PersonHandle

# -------------------------------------------------------------------------
#
# Local imports
#
# -------------------------------------------------------------------------
from gwizard import (
    GWizardCompareRow,
    CandidateMatcher,
    safe_get,
    safe_get_event,
    safe_get_family,
    safe_get_person,
    safe_get_place,
    safe_get_source,
    score_given_names,
    surname_prefix_text,
    surname_text,
    vital_event_ref,
)
from gwizardgedcom import GedGWizard


def _find_sample_dir(*names: str) -> str | None:
    """
    Return a directory containing all of the named Gramps sample files.

    ``gramps.gen.const.TEST_DIR`` only exists for a source checkout, so when
    it is missing (installed Gramps, addon run) look in the usual example
    locations instead. Returns None if the files cannot be found.
    """
    candidates = []
    try:
        from gramps.gen.const import TEST_DIR

        candidates.append(TEST_DIR)
    except ImportError:
        pass
    root = globals().get("ROOT_DIR")
    if root:
        candidates.append(os.path.join(root, "example", "gramps"))
    for base in (
        os.environ.get("GRAMPS_RESOURCES"),
        os.path.join(sys.prefix, "share"),
    ):
        if base:
            candidates.append(os.path.join(base, "doc", "gramps", "example", "gramps"))
            candidates.append(os.path.join(base, "gramps", "example", "gramps"))
    try:
        import importlib.util

        spec = importlib.util.find_spec("gramps")
        for location in (spec.submodule_search_locations or []) if spec else []:
            candidates.append(
                os.path.join(
                    os.path.dirname(os.path.abspath(location)), "example", "gramps"
                )
            )
    except (ImportError, ValueError):
        pass
    for candidate in candidates:
        if all(os.path.isfile(os.path.join(candidate, name)) for name in names):
            return candidate
    return None


def _has_gtk_display() -> bool:
    """
    Return True only if a real Gtk display is available.

    Building a widget without one crashes, so those tests must be skipped.
    An X11 backend needs DISPLAY set and cannot run with the CI value of
    GDK_BACKEND; the Windows and macOS backends need neither.
    """
    if sys.platform not in ("win32", "darwin"):
        if not os.environ.get("DISPLAY") or os.environ.get("GDK_BACKEND") == "-":
            return False
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        return bool(Gtk.init_check([])[0])
    except Exception:
        return False


_HAS_GTK_DISPLAY = _has_gtk_display()


# ------------------------------------------------------------
#
# GWizardTest
#
# ------------------------------------------------------------
class GWizardTest(unittest.TestCase):
    """
    Test cases for GWizard core framework, CandidateMatcher, and GedGWizard.
    """

    def setUp(self) -> None:
        """
        Set up the in-memory databases and test entities.
        """
        self.db = make_database("sqlite")
        self.db.load(":memory:")

        # Create basic target person in self.db
        with DbTxn("Add target person", self.db) as trans:
            self.target_person = Person()
            self.target_person.set_gender(Person.MALE)
            name = Name()
            name.first_name = "John"
            s1 = Surname()
            s1.set_surname("Doe")
            name.add_surname(s1)
            self.target_person.set_primary_name(name)
            self.db.add_person(self.target_person, trans)

            # Add Birth Event
            self.birth_event = Event()
            self.birth_event.set_type(EventType.BIRTH)
            d = Date()
            d.set_yr_mon_day(1980, 6, 15)
            self.birth_event.set_date_object(d)

            # Add Birth Place
            self.birth_place = Place()
            self.birth_place.set_title("Springfield")
            self.db.add_place(self.birth_place, trans)
            self.birth_event.set_place_handle(self.birth_place.handle)

            self.db.add_event(self.birth_event, trans)

            eref = EventRef()
            eref.ref = self.birth_event.handle
            self.target_person.set_birth_ref(eref)
            self.db.commit_person(self.target_person, trans)

    def test_compare_flags_generic_event_count_difference(self) -> None:
        """
        Two incoming (GEDCOM) and three target (database) custom events for
        the same person must be surfaced as compare differences.
        """
        source_db = make_database("sqlite")
        source_db.load(":memory:")

        def add_person_with_events(db: DbWriteBase, descriptions: list[str]) -> Person:
            person = Person()
            name = Name()
            name.first_name = "Test"
            surname = Surname()
            surname.set_surname("Person")
            name.add_surname(surname)
            person.set_primary_name(name)
            with DbTxn("Add event set", db) as trans:
                for description in descriptions:
                    event = Event()
                    event.set_type(EventType.CUSTOM)
                    event.set_description(description)
                    db.add_event(event, trans)
                    event_ref = EventRef()
                    event_ref.ref = event.handle
                    person.add_event_ref(event_ref)
                db.add_person(person, trans)
                db.commit_person(person, trans)
            return person

        try:
            source_person = add_person_with_events(
                source_db, ["GED event one", "GED event two"]
            )
            target_person = add_person_with_events(
                self.db,
                ["target event one", "target event two", "target event three"],
            )
            gwizard = GedGWizard(self.db)
            gwizard.context["source_db"] = source_db

            rows = gwizard.run_step(
                "compare",
                source_person_handle=source_person.handle,
                target_person_handle=target_person.handle,
            )

            event_rows = [row for row in rows if row.field_type == "event"]
            self.assertEqual(len(event_rows), 3)
            self.assertEqual(
                [row.status for row in event_rows],
                ["differ", "differ", "target_only"],
            )
            self.assertEqual(event_rows[-1].target_val, "target event three")
        finally:
            source_db.close()

    def tearDown(self) -> None:
        """
        Close the target database connection.
        """
        self.db.close()

    def test_candidate_matcher(self) -> None:
        """
        Verify that CandidateMatcher successfully matches similar records
        and flags gender mismatches.
        """
        matcher = CandidateMatcher(self.db)

        # Create matching person in memory
        source_person = Person()
        source_person.set_gender(Person.MALE)
        name = Name()
        name.first_name = "John"
        s1 = Surname()
        s1.set_surname("Doe")
        name.add_surname(s1)
        source_person.set_primary_name(name)

        # Exact gender & name match
        score = matcher.score_match(source_person, self.target_person)
        self.assertGreater(score, 1.0)

        # Gender mismatch
        source_person.set_gender(Person.FEMALE)
        score = matcher.score_match(source_person, self.target_person)
        self.assertEqual(score, -1.0)

    def test_score_given_names_reordered_tokens(self) -> None:
        """
        Verify reordered given names score as near-exact.
        """
        self.assertEqual(score_given_names("Edna Dorothy", "Dorothy Edna"), 0.9)

    def test_score_given_names_embedded_nickname(self) -> None:
        """
        Verify an embedded quoted nickname is ignored.
        """
        self.assertEqual(score_given_names('Mary "Lizzie"', "Mary"), 1.0)

    def test_score_given_names_partial_overlap(self) -> None:
        """
        Verify a shared token scores partial credit.
        """
        self.assertEqual(score_given_names("Mary Elizabeth", "Mary Ann"), 0.5)

    def test_score_match_newcomer_stays_unmatched(self) -> None:
        """
        Verify a newcomer sharing only a surname does not auto-match.
        """
        matcher = CandidateMatcher(self.db)
        newcomer = Person()
        newcomer.set_gender(Person.MALE)
        name = Name()
        name.first_name = "Zachary"
        surname = Surname()
        surname.set_surname("Doe")
        name.add_surname(surname)
        newcomer.set_primary_name(name)
        score = matcher.score_match(newcomer, self.target_person)
        self.assertLess(score, 0.5)
        matches = matcher.find_matches(newcomer, threshold=0.5)
        self.assertEqual(matches, [])

    def test_surname_text_joins_all_surnames(self) -> None:
        """
        Verify surname_text joins every surname, and skips empty ones.
        """
        name = Name()
        name.first_name = "Anna"
        first = Surname()
        first.set_surname("Hansdotter")
        second = Surname()
        second.set_surname("Smith")
        empty = Surname()
        name.add_surname(first)
        name.add_surname(second)
        name.add_surname(empty)
        self.assertEqual(surname_text(name), "Hansdotter Smith")

    def test_surname_prefix_text_reads_spfx(self) -> None:
        """
        Verify surname_prefix_text exposes the SPFX value, or "" when absent.
        """
        name = Name()
        name.first_name = "Anna"
        prefixed = Surname()
        prefixed.set_surname("Hansdotter")
        prefixed.set_prefix("Vrow")
        name.add_surname(prefixed)
        self.assertEqual(surname_prefix_text(name), "Vrow")

        plain = Name()
        plain.first_name = "Anna"
        plain_surn = Surname()
        plain_surn.set_surname("Hansdotter")
        plain.add_surname(plain_surn)
        self.assertEqual(surname_prefix_text(plain), "")

    def test_compare_surname_prefix_difference(self) -> None:
        """
        Verify a missing SPFX prefix produces a differing prefix row.
        """
        source_db = make_database("sqlite")
        source_db.load(":memory:")
        target_db = make_database("sqlite")
        target_db.load(":memory:")
        try:
            s_handle = None
            t_handle = None
            with DbTxn("Add source person", source_db) as trans:
                s_person = Person()
                s_name = Name()
                s_name.first_name = "Anna"
                s_surn = Surname()
                s_surn.set_surname("Hansdotter")
                s_name.add_surname(s_surn)
                s_person.set_primary_name(s_name)
                source_db.add_person(s_person, trans)
                s_handle = s_person.handle
            with DbTxn("Add target person", target_db) as trans:
                t_person = Person()
                t_name = Name()
                t_name.first_name = "Anna"
                t_surn = Surname()
                t_surn.set_surname("Hansdotter")
                t_surn.set_prefix("Vrow")
                t_name.add_surname(t_surn)
                t_person.set_primary_name(t_name)
                target_db.add_person(t_person, trans)
                t_handle = t_person.handle
            gwizard = GedGWizard(target_db)
            gwizard.context["source_db"] = source_db
            rows = gwizard.run_step(
                "compare",
                source_person_handle=s_handle,
                target_person_handle=t_handle,
            )
            prefix_rows = [r for r in rows if r.field_type == "surname_prefix"]
            self.assertEqual(len(prefix_rows), 1)
            self.assertEqual(prefix_rows[0].status, "target_only")
            self.assertEqual(prefix_rows[0].source_val, "")
            self.assertEqual(prefix_rows[0].target_val, "Vrow")
        finally:
            source_db.close()
            target_db.close()

    def test_vital_event_ref_falls_back_to_type_scan(self) -> None:
        """
        Verify a Birth stored as a plain event ref is still found.
        """
        target_db = make_database("sqlite")
        target_db.load(":memory:")
        try:
            with DbTxn("Add person with unindexed birth", target_db) as trans:
                person = Person()
                name = Name()
                name.first_name = "Kimberly"
                surn = Surname()
                surn.set_surname("White")
                name.add_surname(surn)
                person.set_primary_name(name)
                target_db.add_person(person, trans)
                birth = Event()
                birth.set_type(EventType.BIRTH)
                day = Date()
                day.set_yr_mon_day(1968, 5, 6)
                birth.set_date_object(day)
                target_db.add_event(birth, trans)
                eref = EventRef()
                eref.ref = birth.handle
                person.add_event_ref(eref)
                target_db.commit_person(person, trans)
                self.assertIsNone(person.get_birth_ref())
            stored = target_db.get_person_from_handle(person.handle)
            ref = vital_event_ref(target_db, stored, "birth")
            self.assertIsNotNone(ref)
            event = target_db.get_event_from_handle(ref.ref)
            self.assertEqual(event.get_date_object().get_year(), 1968)
            self.assertIsNone(vital_event_ref(target_db, stored, "death"))
        finally:
            target_db.close()

    def test_compare_prefers_primary_birth_over_first_birth(self) -> None:
        """
        Verify the Birth row uses the primary birth ref, not the first one.
        """
        source_db = make_database("sqlite")
        source_db.load(":memory:")
        target_db = make_database("sqlite")
        target_db.load(":memory:")
        try:
            s_handle = None
            t_handle = None
            with DbTxn("Add source person", source_db) as trans:
                s_person = Person()
                s_name = Name()
                s_name.first_name = "Kimberly"
                s_surn = Surname()
                s_surn.set_surname("White")
                s_name.add_surname(s_surn)
                s_person.set_primary_name(s_name)
                source_db.add_person(s_person, trans)
                s_handle = s_person.handle
            with DbTxn("Add target person", target_db) as trans:
                t_person = Person()
                t_name = Name()
                t_name.first_name = "Kimberly"
                t_surn = Surname()
                t_surn.set_surname("White")
                t_name.add_surname(t_surn)
                t_person.set_primary_name(t_name)
                target_db.add_person(t_person, trans)
                first = Event()
                first.set_type(EventType.BIRTH)
                early = Date()
                early.set_yr_mon_day(1967, 5, 6)
                first.set_date_object(early)
                target_db.add_event(first, trans)
                first_ref = EventRef()
                first_ref.ref = first.handle
                t_person.add_event_ref(first_ref)
                primary = Event()
                primary.set_type(EventType.BIRTH)
                late = Date()
                late.set_yr_mon_day(1968, 5, 6)
                primary.set_date_object(late)
                target_db.add_event(primary, trans)
                primary_ref = EventRef()
                primary_ref.ref = primary.handle
                t_person.set_birth_ref(primary_ref)
                target_db.commit_person(t_person, trans)
                t_handle = t_person.handle
            gwizard = GedGWizard(target_db)
            gwizard.context["source_db"] = source_db
            rows = gwizard.run_step(
                "compare",
                source_person_handle=s_handle,
                target_person_handle=t_handle,
            )
            birth_rows = [r for r in rows if r.field_type == "birth_event"]
            self.assertEqual(len(birth_rows), 2)
            primary_row = [
                r
                for r in birth_rows
                if r.extra_data.get("target_handle") == primary.handle
            ]
            self.assertEqual(len(primary_row), 1)
            self.assertIn("1968", primary_row[0].target_val)
            self.assertNotIn("1967", primary_row[0].target_val)
            extra_row = [
                r
                for r in birth_rows
                if r.extra_data.get("target_handle") == first.handle
            ]
            self.assertEqual(len(extra_row), 1)
            self.assertIn("1967", extra_row[0].target_val)
            self.assertNotIn("1968", extra_row[0].target_val)
        finally:
            source_db.close()
            target_db.close()

    def test_apply_alternate_birth_event_key(self) -> None:
        """
        Verify an alternate Birth merges via its "event:" resolution key.
        """
        source_db = make_database("sqlite")
        source_db.load(":memory:")
        target_db = make_database("sqlite")
        target_db.load(":memory:")
        try:
            s_handle = None
            t_handle = None
            s_birth_handle = None
            with DbTxn("Add source person", source_db) as trans:
                s_person = Person()
                s_name = Name()
                s_name.first_name = "Kimberly"
                s_surn = Surname()
                s_surn.set_surname("White")
                s_name.add_surname(s_surn)
                s_person.set_primary_name(s_name)
                source_db.add_person(s_person, trans)
                primary = Event()
                primary.set_type(EventType.BIRTH)
                primary_day = Date()
                primary_day.set_yr_mon_day(1967, 5, 6)
                primary.set_date_object(primary_day)
                source_db.add_event(primary, trans)
                primary_ref = EventRef()
                primary_ref.ref = primary.handle
                s_person.set_birth_ref(primary_ref)
                birth = Event()
                birth.set_type(EventType.BIRTH)
                day = Date()
                day.set_yr_mon_day(1968, 5, 6)
                birth.set_date_object(day)
                source_db.add_event(birth, trans)
                birth_ref = EventRef()
                birth_ref.ref = birth.handle
                s_person.add_event_ref(birth_ref)
                source_db.commit_person(s_person, trans)
                s_handle = s_person.handle
                s_birth_handle = birth.handle
            with DbTxn("Add target person", target_db) as trans:
                t_person = Person()
                t_name = Name()
                t_name.first_name = "Kimberly"
                t_surn = Surname()
                t_surn.set_surname("White")
                t_name.add_surname(t_surn)
                t_person.set_primary_name(t_name)
                target_db.add_person(t_person, trans)
                t_handle = t_person.handle
            gwizard = GedGWizard(target_db)
            gwizard.context["source_db"] = source_db
            gwizard.run_step(
                "apply",
                source_person_handle=s_handle,
                target_person_handle=t_handle,
                resolutions={f"event:{s_birth_handle}": "source"},
            )
            updated = target_db.get_person_from_handle(t_handle)
            birth_years = set()
            for ref in updated.get_event_ref_list():
                event = target_db.get_event_from_handle(ref.ref)
                if event is not None and event.get_type() == EventType.BIRTH:
                    birth_years.add(event.get_date_object().get_year())
            self.assertIn(1968, birth_years)
        finally:
            source_db.close()
            target_db.close()

    def test_compare_finds_unindexed_target_birth(self) -> None:
        """
        Verify _compare reports target_only when the target birth ref index
        is unset (e.g. Legacy import quirk).
        """
        source_db = make_database("sqlite")
        source_db.load(":memory:")
        target_db = make_database("sqlite")
        target_db.load(":memory:")
        try:
            s_handle = None
            t_handle = None
            with DbTxn("Add source person", source_db) as trans:
                s_person = Person()
                s_name = Name()
                s_name.first_name = "Kimberly"
                s_surn = Surname()
                s_surn.set_surname("White")
                s_name.add_surname(s_surn)
                s_person.set_primary_name(s_name)
                source_db.add_person(s_person, trans)
                s_handle = s_person.handle
            with DbTxn("Add target person", target_db) as trans:
                t_person = Person()
                t_name = Name()
                t_name.first_name = "Kimberly"
                t_surn = Surname()
                t_surn.set_surname("White")
                t_name.add_surname(t_surn)
                t_person.set_primary_name(t_name)
                target_db.add_person(t_person, trans)
                birth = Event()
                birth.set_type(EventType.BIRTH)
                day = Date()
                day.set_yr_mon_day(1968, 5, 6)
                birth.set_date_object(day)
                target_db.add_event(birth, trans)
                eref = EventRef()
                eref.ref = birth.handle
                t_person.add_event_ref(eref)
                target_db.commit_person(t_person, trans)
                t_handle = t_person.handle
            gwizard = GedGWizard(target_db)
            gwizard.context["source_db"] = source_db
            rows = gwizard.run_step(
                "compare",
                source_person_handle=s_handle,
                target_person_handle=t_handle,
            )
            birth_rows = [r for r in rows if r.field_type == "birth_event"]
            self.assertEqual(len(birth_rows), 1)
            self.assertEqual(birth_rows[0].status, "target_only")
            self.assertEqual(birth_rows[0].source_val, "")
            self.assertNotEqual(birth_rows[0].target_val, "")
        finally:
            source_db.close()
            target_db.close()

    def test_apply_surname_prefix_only(self) -> None:
        """
        Verify applying only the prefix row updates the target prefix.
        """
        source_db = make_database("sqlite")
        source_db.load(":memory:")
        target_db = make_database("sqlite")
        target_db.load(":memory:")
        try:
            s_handle = None
            t_handle = None
            with DbTxn("Add source person", source_db) as trans:
                s_person = Person()
                s_name = Name()
                s_name.first_name = "John"
                s_surn = Surname()
                s_surn.set_surname("Doe")
                s_surn.set_prefix("von")
                s_name.add_surname(s_surn)
                s_person.set_primary_name(s_name)
                source_db.add_person(s_person, trans)
                s_handle = s_person.handle
            with DbTxn("Add target person", target_db) as trans:
                t_person = Person()
                t_name = Name()
                t_name.first_name = "John"
                t_surn = Surname()
                t_surn.set_surname("Doe")
                t_name.add_surname(t_surn)
                t_person.set_primary_name(t_name)
                target_db.add_person(t_person, trans)
                t_handle = t_person.handle
            gwizard = GedGWizard(target_db)
            gwizard.context["source_db"] = source_db
            gwizard.run_step(
                "apply",
                source_person_handle=s_handle,
                target_person_handle=t_handle,
                resolutions={"surname_prefix": "source"},
            )
            updated = target_db.get_person_from_handle(t_handle)
            self.assertEqual(
                updated.get_primary_name().get_surname_list()[0].get_prefix(),
                "von",
            )
            self.assertEqual(
                updated.get_primary_name().get_surname_list()[0].get_surname(),
                "Doe",
            )
        finally:
            source_db.close()
            target_db.close()

    def test_score_match_year_only_birth_partial_credit(self) -> None:
        """
        Verify a year-only birth vs a full birth date gets partial credit.
        """
        source_db = make_database("sqlite")
        source_db.load(":memory:")
        try:
            with DbTxn("Add source person", source_db) as trans:
                source_person = Person()
                source_person.set_gender(Person.MALE)
                name = Name()
                name.first_name = "John"
                surname = Surname()
                surname.set_surname("Doe")
                name.add_surname(surname)
                source_person.set_primary_name(name)
                source_db.add_person(source_person, trans)
                birth = Event()
                birth.set_type(EventType.BIRTH)
                year_only = Date()
                year_only.set_year(1980)
                birth.set_date_object(year_only)
                source_db.add_event(birth, trans)
                eref = EventRef()
                eref.ref = birth.handle
                source_person.set_birth_ref(eref)
                source_db.commit_person(source_person, trans)
            matcher = CandidateMatcher(self.db)
            # Target birth is 15 JUN 1980; same year but partial info.
            partial_score = matcher.score_match(
                source_person, self.target_person, source_db=source_db
            )
            self.assertAlmostEqual(partial_score, 2.75)
        finally:
            source_db.close()

    def test_ged_gwizard_flow(self) -> None:
        """
        Test the end-to-end GedGWizard workflow sequence (connect, load, match, compare, apply).
        """
        # Create a simple valid minimal GEDCOM file
        gedcom_data = """0 HEAD
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
2 GIVN John
2 SURN Doe
1 SEX M
1 BIRT
2 DATE 15 JUN 1980
2 PLAC Springfield
0 TRLR
"""
        with tempfile.NamedTemporaryFile(suffix=".ged", mode="w", delete=False) as f:
            f.write(gedcom_data)
            temp_path = f.name

        try:
            gwizard = GedGWizard(self.db)

            # 1. Connect
            self.assertTrue(gwizard.run_step("connect", gedcom_path=temp_path))

            # 2. Load
            people = gwizard.run_step("load")
            self.assertEqual(len(people), 1)
            source_person = people[0]
            self.assertEqual(source_person.get_primary_name().first_name, "John")

            # 3. Match
            matches = gwizard.run_step(
                "match", source_person_handle=source_person.handle
            )
            self.assertEqual(len(matches), 1)
            match = matches[0]
            self.assertEqual(match["handle"], self.target_person.handle)
            self.assertGreater(match["score"], 1.0)

            # 4. Compare
            comparison = gwizard.run_step(
                "compare",
                source_person_handle=source_person.handle,
                target_person_handle=self.target_person.handle,
            )
            self.assertGreater(len(comparison), 0)

            given_name_row = [r for r in comparison if r.field_type == "given_name"][0]
            self.assertEqual(given_name_row.status, "match")
            self.assertEqual(given_name_row.source_val, "John")
            self.assertEqual(given_name_row.target_val, "John")

            # 5. Apply (Merge Overwrite given name with target, add birth)
            resolutions = {
                "given_name": "source",
                "surname": "target",
                "gender": "target",
                "birth_event": "source",
            }
            success = gwizard.run_step(
                "apply",
                source_person_handle=source_person.handle,
                target_person_handle=self.target_person.handle,
                resolutions=resolutions,
            )
            self.assertTrue(success)

            # Verify target person has successfully updated primary details
            updated_person = self.db.get_person_from_handle(self.target_person.handle)
            self.assertEqual(updated_person.get_primary_name().first_name, "John")

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_copy_event_handle_collision_preserves_existing_event(self) -> None:
        """A source event handle collision must not overwrite a target event."""
        existing_event_handle = self.birth_event.handle
        self.birth_event.set_description("Existing event description")
        other_person = Person()
        other_name = Name()
        other_name.first_name = "Other"
        other_person.set_primary_name(other_name)
        other_birth_ref = EventRef()
        other_birth_ref.ref = existing_event_handle
        other_person.set_birth_ref(other_birth_ref)
        with DbTxn("Add another user of the event", self.db) as trans:
            self.db.commit_event(self.birth_event, trans)
            self.db.add_person(other_person, trans)

        source_db = make_database("sqlite")
        source_db.load(":memory:")
        try:
            source_event = Event()
            source_event.set_handle(existing_event_handle)
            source_event.set_type(EventType.BIRTH)
            source_event.set_description("Incoming event description")
            source_person = Person()
            source_name = Name()
            source_name.first_name = "John"
            source_person.set_primary_name(source_name)
            source_birth_ref = EventRef()
            source_birth_ref.ref = existing_event_handle
            source_person.set_birth_ref(source_birth_ref)
            with DbTxn("Add colliding source event", source_db) as trans:
                source_db.add_event(source_event, trans)
                source_db.add_person(source_person, trans)
                source_db.commit_person(source_person, trans)

            self.assertEqual(source_event.handle, existing_event_handle)
            gwizard = GedGWizard(self.db)
            gwizard.context["source_db"] = source_db
            self.assertTrue(
                gwizard.run_step(
                    "apply",
                    source_person_handle=source_person.handle,
                    target_person_handle=self.target_person.handle,
                    resolutions={"birth_event": "source"},
                )
            )

            existing_event = self.db.get_event_from_handle(existing_event_handle)
            self.assertEqual(
                existing_event.get_description(), "Existing event description"
            )
            unchanged_user = self.db.get_person_from_handle(other_person.handle)
            self.assertEqual(unchanged_user.get_birth_ref().ref, existing_event_handle)
            updated_person = self.db.get_person_from_handle(self.target_person.handle)
            incoming_event_handle = updated_person.get_birth_ref().ref
            self.assertNotEqual(incoming_event_handle, existing_event_handle)
            incoming_event = self.db.get_event_from_handle(incoming_event_handle)
            self.assertEqual(
                incoming_event.get_description(), "Incoming event description"
            )
        finally:
            source_db.close()

    def test_ged_gwizard_add_new_clears_source_database_handles(self) -> None:
        """Add as New must not retain links into the temporary source DB."""
        gedcom_data = """0 HEAD
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Alice /Example/
1 BIRT
2 DATE 1 JAN 1980
1 EVEN
2 TYPE Graduation
2 DATE 1 JUN 2000
1 FAMS @F1@
0 @I2@ INDI
1 NAME Partner /Example/
1 FAMS @F1@
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
0 TRLR
"""
        with tempfile.NamedTemporaryFile(suffix=".ged", mode="w", delete=False) as f:
            f.write(gedcom_data)
            temp_path = f.name

        try:
            gwizard = GedGWizard(self.db)
            gwizard.run_step("connect", gedcom_path=temp_path)
            people = gwizard.run_step("load")
            source_person = next(
                person
                for person in people
                if person.get_primary_name().first_name == "Alice"
            )
            self.assertTrue(source_person.get_family_handle_list())
            self.assertGreaterEqual(len(source_person.get_event_ref_list()), 2)

            existing_handles = set(self.db.iter_person_handles())
            self.assertTrue(
                gwizard.run_step(
                    "apply",
                    source_person_handle=source_person.handle,
                    target_person_handle=None,
                    resolutions={},
                )
            )

            added_handles = set(self.db.iter_person_handles()) - existing_handles
            self.assertEqual(len(added_handles), 1)
            added_person = self.db.get_person_from_handle(added_handles.pop())
            self.assertEqual(added_person.get_family_handle_list(), [])
            self.assertEqual(added_person.get_parent_family_handle_list(), [])
            self.assertEqual(added_person.get_person_ref_list(), [])
            for event_ref in added_person.get_event_ref_list():
                self.assertIsNotNone(safe_get_event(self.db, event_ref.ref))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_load_bare_xml_gramps_content(self) -> None:
        """
        Verify bare ``.xml`` files holding Gramps XML load in place.

        Copies the ``imp_sample``/``exp_sample`` Gramps XML pair to
        ``.xml`` temp names and asserts the person counts match the
        ``.gramps`` originals (42 and 52).
        """
        cases = (
            ("imp_sample.gramps", 42),
            ("exp_sample.gramps", 52),
        )
        TEST_DIR = _find_sample_dir(*(name for name, _count in cases))
        if TEST_DIR is None:
            self.skipTest("imp_sample.gramps / exp_sample.gramps not found")

        for source_name, expected_count in cases:
            temp_path = os.path.join(
                tempfile.gettempdir(),
                os.path.splitext(source_name)[0] + "_gwizard_test.xml",
            )
            try:
                shutil.copyfile(
                    os.path.join(TEST_DIR, source_name),
                    temp_path,
                )
                gwizard = GedGWizard(self.db)
                self.assertTrue(gwizard.run_step("connect", gedcom_path=temp_path))
                self.assertTrue(gwizard._is_gramps_xml_file(temp_path))
                people = gwizard.run_step("load")
                self.assertEqual(len(people), expected_count)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

    def test_is_gramps_xml_file_rejects_gedcom(self) -> None:
        """
        Verify GEDCOM content is not sniffed as Gramps XML.
        """
        gedcom_data = """0 HEAD
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
0 TRLR
"""
        with tempfile.NamedTemporaryFile(
            suffix=".xml", mode="w", delete=False
        ) as handle:
            handle.write(gedcom_data)
            temp_path = handle.name
        try:
            gwizard = GedGWizard(self.db)
            self.assertFalse(gwizard._is_gramps_xml_file(temp_path))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_format_diff_line(self) -> None:
        """
        Test the GWizardMergeDialog's static method for rendering
        Pango-highlighted differences between values.
        """
        from gwizardmergedialog import GWizardMergeDialog

        # Exact match (should be plain)
        res = GWizardMergeDialog._format_diff_line(
            "Given Name", "John", "John", show_label=False, is_left=True
        )
        self.assertEqual(res, "John")

        # Differ (one word differs)
        res_diff = GWizardMergeDialog._format_diff_line(
            "Given Name", "John James", "John Paul", show_label=False, is_left=True
        )
        # "James" differs, so it should be bolded, while "John" is matched and just italicized
        self.assertIn("James", res_diff)

        # Show label
        res_label = GWizardMergeDialog._format_diff_line(
            "Given Name", "John", "John", show_label=True, is_left=True
        )
        self.assertEqual(res_label, "Given Name: John")

    def test_ged_gwizard_apply_merge_relationships(self) -> None:
        """
        Test merging complex family relationships (spouse, child, parents)
        where the relative is mapped using best_target_person lookup.
        """
        # Create relative (spouse) in self.db
        with DbTxn("Add spouse and child", self.db) as trans:
            self.spouse_person = Person()
            self.spouse_person.set_gender(Person.FEMALE)
            name = Name()
            name.first_name = "Jane"
            s1 = Surname()
            s1.set_surname("Doe")
            name.add_surname(s1)
            self.spouse_person.set_primary_name(name)
            self.db.add_person(self.spouse_person, trans)

        # GEDCOM data with John Doe having a spouse Jane Doe
        gedcom_data = """0 HEAD
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
2 GIVN John
2 SURN Doe
1 SEX M
1 FAMS @F1@
0 @I2@ INDI
1 NAME Jane /Doe/
2 GIVN Jane
2 SURN Doe
1 SEX F
1 FAMS @F1@
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
0 TRLR
"""
        with tempfile.NamedTemporaryFile(suffix=".ged", mode="w", delete=False) as f:
            f.write(gedcom_data)
            temp_path = f.name

        try:
            gwizard = GedGWizard(self.db)
            gwizard.run_step("connect", gedcom_path=temp_path)
            people = gwizard.run_step("load")
            source_john = [
                p for p in people if p.get_primary_name().first_name == "John"
            ][0]
            source_jane = [
                p for p in people if p.get_primary_name().first_name == "Jane"
            ][0]

            # Merge spouse relation
            resolutions = {
                f"spouse:{source_jane.handle}": "source",
            }
            success = gwizard.run_step(
                "apply",
                source_person_handle=source_john.handle,
                target_person_handle=self.target_person.handle,
                resolutions=resolutions,
            )
            self.assertTrue(success)

            # Verify that John now has a family link in self.db, and Jane is the spouse
            updated_john = self.db.get_person_from_handle(self.target_person.handle)
            self.assertTrue(len(updated_john.get_family_handle_list()) > 0)
            fam_handle = updated_john.get_family_handle_list()[0]
            fam = self.db.get_family_from_handle(fam_handle)
            self.assertIsNotNone(fam)
            self.assertEqual(fam.get_father_handle(), updated_john.handle)
            self.assertEqual(fam.get_mother_handle(), self.spouse_person.handle)

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_ged_gwizard_resolve_dangling_references(self) -> None:
        """
        Verify that dangling references (Notes, Citations, Sources) are
        recursively copied and linked correctly when merging a person or event.
        """
        # GEDCOM file containing nested note, citation, source structure
        gedcom_data = """0 HEAD
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
2 GIVN John
2 SURN Doe
1 SEX M
1 BIRT
2 DATE 15 JUN 1980
2 SOUR @S1@
3 PAGE 42
0 @S1@ SOUR
1 TITL Famous Book of Doe
1 NOTE @N1@
0 @N1@ NOTE This is a linked note for a source.
0 TRLR
"""
        with tempfile.NamedTemporaryFile(suffix=".ged", mode="w", delete=False) as f:
            f.write(gedcom_data)
            temp_path = f.name

        try:
            gwizard = GedGWizard(self.db)
            gwizard.run_step("connect", gedcom_path=temp_path)
            people = gwizard.run_step("load")
            source_person = people[0]

            resolutions = {
                "given_name": "source",
                "surname": "source",
                "gender": "source",
                "birth_event": "source",
            }
            success = gwizard.run_step(
                "apply",
                source_person_handle=source_person.handle,
                target_person_handle=self.target_person.handle,
                resolutions=resolutions,
            )
            self.assertTrue(success)

            # Get the merged birth event from the target database
            updated_person = self.db.get_person_from_handle(self.target_person.handle)
            birth_ref = updated_person.get_birth_ref()
            self.assertIsNotNone(birth_ref)
            birth_event = self.db.get_event_from_handle(birth_ref.ref)
            self.assertIsNotNone(birth_event)

            # Verify that the birth event has a Citation
            citation_handles = birth_event.get_citation_list()
            self.assertTrue(len(citation_handles) > 0)
            citation = self.db.get_citation_from_handle(citation_handles[0])
            self.assertIsNotNone(citation)

            # Verify that the Citation references the correct Source in the target DB
            source_handle = citation.get_reference_handle()
            self.assertIsNotNone(source_handle)
            source = self.db.get_source_from_handle(source_handle)
            self.assertIsNotNone(source)
            self.assertEqual(source.title, "Famous Book of Doe")

            # Verify that the Source references the Note in the target DB
            note_handles = source.get_note_list()
            self.assertTrue(len(note_handles) > 0)
            note = self.db.get_note_from_handle(note_handles[0])
            self.assertIsNotNone(note)
            self.assertIn("linked note", str(note.get_styledtext()))

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @unittest.skipUnless(
        _HAS_GTK_DISPLAY,
        "needs a real Gtk display (run under xvfb-run); "
        "gramps CI sets GDK_BACKEND=- so Gtk.Dialog cannot init.",
    )
    def test_dialog_find_dangling_references(self) -> None:
        """
        Verify that GWizardMergeDialog._find_dangling_references correctly
        detects and categorizes missing references prior to merge.
        """
        from gwizardmergedialog import GWizardMergeDialog

        gedcom_data = """0 HEAD
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
2 GIVN John
2 SURN Doe
1 SEX M
1 BIRT
2 DATE 15 JUN 1980
2 SOUR @S1@
3 PAGE 42
0 @S1@ SOUR
1 TITL Famous Book of Doe
1 NOTE @N1@
0 @N1@ NOTE This is a linked note for a source.
0 TRLR
"""
        with tempfile.NamedTemporaryFile(suffix=".ged", mode="w", delete=False) as f:
            f.write(gedcom_data)
            temp_path = f.name

        try:
            gwizard = GedGWizard(self.db)
            gwizard.run_step("connect", gedcom_path=temp_path)
            people = gwizard.run_step("load")
            source_person = people[0]

            # Construct mock/real DbState
            class MockDbState:
                def __init__(self, db):
                    self.db = db

            # GWizardMergeDialog needs a real display (skipped otherwise).
            dbstate = MockDbState(self.db)
            dialog = GWizardMergeDialog(
                dbstate=dbstate,
                gwizard=gwizard,
                source_handle=source_person.handle,
                target_handle=self.target_person.handle,
            )

            # Select birth event resolution as 'source'
            dialog._resolutions = {
                "birth_event": "source",
            }

            missing = dialog._find_dangling_references()

            # Assert that the dialog correctly finds missing citation, source, and note
            self.assertTrue(len(missing["citation"]) > 0)
            self.assertTrue(len(missing["source"]) > 0)
            self.assertTrue(len(missing["note"]) > 0)

            # If birth_event is not resolved, no missing references should be detected for birth
            dialog._resolutions = {}
            missing_empty = dialog._find_dangling_references()
            self.assertEqual(len(missing_empty["citation"]), 0)
            self.assertEqual(len(missing_empty["source"]), 0)
            self.assertEqual(len(missing_empty["note"]), 0)

            # Cleanup dialog
            dialog.destroy()

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @unittest.skipUnless(
        _HAS_GTK_DISPLAY,
        "needs a real Gtk display (run under xvfb-run); "
        "gramps CI sets GDK_BACKEND=- so Gtk.Dialog cannot init.",
    )
    def test_dialog_rejects_dangling_source_handle(self) -> None:
        """
        Opening the merge dialog with a handle that no longer resolves
        must raise HandleError instead of failing later with an
        AttributeError on a None person.
        """
        from gwizardmergedialog import GWizardMergeDialog

        class MockDbState:
            def __init__(self, db):
                self.db = db

        gedcom_data = """0 HEAD
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Solo /Person/
2 GIVN Solo
2 SURN Person
0 TRLR
"""
        with tempfile.NamedTemporaryFile(suffix=".ged", mode="w", delete=False) as f:
            f.write(gedcom_data)
            temp_path = f.name

        try:
            gwizard = GedGWizard(self.db)
            gwizard.run_step("connect", gedcom_path=temp_path)

            with self.assertRaises(HandleError):
                GWizardMergeDialog(
                    dbstate=MockDbState(self.db),
                    gwizard=gwizard,
                    source_handle="0000006e0000006e",
                    target_handle=None,
                )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @unittest.skipUnless(
        _HAS_GTK_DISPLAY,
        "needs a real Gtk display (run under xvfb-run); "
        "gramps CI sets GDK_BACKEND=- so Gtk.Dialog cannot init.",
    )
    def test_dialog_opens_in_add_as_new_mode(self) -> None:
        """
        With no target handle the dialog must still build, since the
        compare window opens it that way for unmatched people.
        """
        from gwizardmergedialog import GWizardMergeDialog

        gedcom_data = """0 HEAD
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Solo /Person/
2 GIVN Solo
2 SURN Person
0 TRLR
"""
        with tempfile.NamedTemporaryFile(suffix=".ged", mode="w", delete=False) as f:
            f.write(gedcom_data)
            temp_path = f.name

        try:
            gwizard = GedGWizard(self.db)
            gwizard.run_step("connect", gedcom_path=temp_path)
            people = gwizard.run_step("load")
            source_person = people[0]

            class MockDbState:
                def __init__(self, db):
                    self.db = db

            dialog = GWizardMergeDialog(
                dbstate=MockDbState(self.db),
                gwizard=gwizard,
                source_handle=source_person.handle,
                target_handle=None,
            )
            # The rows are populated, and every one must carry a key.
            self.assertTrue(dialog._row_index > 0)
            dialog.destroy()
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


# ------------------------------------------------------------
#
# GWizardSafeLookupTest
#
# ------------------------------------------------------------
class GWizardSafeLookupTest(unittest.TestCase):
    """
    Test the safe handle lookup helpers.

    ``DbReadBase.get_*_from_handle`` raises ``HandleError`` for an unknown
    handle rather than returning None, so a bare ``if not obj`` guard does
    not protect a dereference. The comparison UI holds handles that a
    merge can invalidate, so every one of these must return None instead
    of propagating the exception.
    """

    class _RaisingDb:
        """Stand-in database that always reports a dangling handle."""

        def get_person_from_handle(self, handle):
            raise HandleError("Handle %s not found" % handle)

        def get_family_from_handle(self, handle):
            raise HandleError("Handle %s not found" % handle)

        def get_event_from_handle(self, handle):
            raise HandleError("Handle %s not found" % handle)

        def get_place_from_handle(self, handle):
            raise HandleError("Handle %s not found" % handle)

        def get_source_from_handle(self, handle):
            raise HandleError("Handle %s not found" % handle)

    def test_safe_get_returns_none_for_dangling_handle(self):
        """A dangling handle yields None instead of raising HandleError."""
        db = GWizardSafeLookupTest._RaisingDb()
        self.assertIsNone(safe_get_person(db, "0000006e0000006e"))
        self.assertIsNone(safe_get_family(db, "0000006e0000006e"))
        self.assertIsNone(safe_get_event(db, "0000006e0000006e"))
        self.assertIsNone(safe_get_place(db, "0000006e0000006e"))
        self.assertIsNone(safe_get_source(db, "0000006e0000006e"))

    def test_safe_get_short_circuits_empty_handle(self):
        """An empty or None handle never reaches the database."""
        db = GWizardSafeLookupTest._RaisingDb()
        for handle in (None, ""):
            self.assertIsNone(safe_get_person(db, handle))
        # No exception means the getter was never invoked.

    def test_safe_get_returns_object_when_present(self):
        """A live handle still resolves to the object."""
        person = Person()
        person.set_handle("handle1")

        class _Db:
            def get_person_from_handle(self, handle):
                return person

        self.assertIs(safe_get_person(_Db(), "handle1"), person)

    def test_safe_get_dispatches_by_getter_name(self):
        """The generic helper forwards to the named getter method."""
        sentinel = object()
        db = GWizardSafeLookupTest._RaisingDb()
        db.get_note_from_handle = lambda handle: sentinel
        self.assertIs(safe_get(db, "h", "get_note_from_handle", "note"), sentinel)
        # An unknown getter still surfaces its own error rather than
        # being silently swallowed.
        with self.assertRaises(AttributeError):
            safe_get(db, "h", "get_nonsense_from_handle", "nonsense")

    def test_safe_get_propagates_non_handle_errors(self):
        """Real database errors are not masked as a missing object."""

        class _Broken:
            def get_person_from_handle(self, handle):
                raise RuntimeError("database is locked")

        with self.assertRaises(RuntimeError):
            safe_get_person(_Broken(), "handle1")
