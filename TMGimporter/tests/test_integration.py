"""Integration tests for the TMG importer using the real RELPH SQZ file.

Runs the full import pipeline against the real backup and asserts expected
counts and specific known records.

Run with:
    python3 -m unittest tests.test_integration -v

The SQZ path is read from the environment variable TMG_TEST_SQZ.  If not set
it defaults to the RELPH backup used during development.  Tests are skipped
automatically when the file is not present.
"""

import os
import sys
import shutil
import tempfile
import unittest
import zipfile

# The TMGimporter module imports Gtk at module load — skip the whole file if
# gi/Gtk aren't available (headless-without-GTK environments). On systems
# where both GTK3 and GTK4 are present, pin Gtk to 3.0 before any gramps
# import (mirrors what gramps.grampsapp does at startup); otherwise
# PyGObject loads GTK4 and the gramps.gui import chain crashes on
# Gtk.IconSize.MENU (a GTK3-only enum).
try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
except (ImportError, ValueError, AttributeError) as err:
    raise unittest.SkipTest("GTK 3.0 / PyGObject not available: %s" % err)


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SQZ_PATH = os.environ.get(
    'TMG_TEST_SQZ',
    os.path.join(_TESTS_DIR, 'integration_test.sqz'),
)
DATASET_ID = 1


def _find_pjc(root):
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if fn.lower().endswith('.pjc'):
                return os.path.join(dirpath, fn)
    raise FileNotFoundError("No .pjc file found under " + root)


@unittest.skipUnless(os.path.exists(SQZ_PATH), f'SQZ not found: {SQZ_PATH}')
class TestFullPipelineRelph(unittest.TestCase):
    """Run the complete import pipeline once for the whole class, then assert."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp(prefix='tmg_inttest_')
        with zipfile.ZipFile(SQZ_PATH) as z:
            z.extractall(cls._tmpdir)

        pjc_path = _find_pjc(cls._tmpdir)
        pjc_dir  = os.path.dirname(pjc_path) + os.sep

        import libtmg
        from gramps.gen.db.utils import make_database

        cls.db = make_database("sqlite")
        cls.db.load(":memory:", None)

        projecttables = libtmg.TmgTable(pjc_dir)
        libtmg.map_dbfs_to_tables(projecttables.tablemap())
        libtmg.tmg_import_pipeline(cls.db, DATASET_ID, user=None,
                                    sqzfilename=SQZ_PATH)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Record counts
    # ------------------------------------------------------------------

    def test_people_count(self):
        # 1649 persons in dataset 1
        self.assertEqual(self.db.get_number_of_people(), 1649)

    def test_events_count(self):
        # 5818 dsid=1 events minus 132 Note-type (etype 1078) = 5686
        self.assertEqual(self.db.get_number_of_events(), 5686)

    def test_places_count(self):
        # All 1040 dsid=1 place records have ppv parts so all should import
        self.assertEqual(self.db.get_number_of_places(), 1040)

    def test_sources_count(self):
        # 158 active sources in dataset 1
        self.assertEqual(self.db.get_number_of_sources(), 158)

    def test_repositories_count(self):
        # 15 repositories in dataset 1
        self.assertEqual(self.db.get_number_of_repositories(), 15)

    def test_citations_count(self):
        # 7804 total, 7 skipped (majsource not in active source map) = 7797
        self.assertEqual(self.db.get_number_of_citations(), 7797)

    # ------------------------------------------------------------------
    # Known person: nper=1 — George Thomas RELPH, male
    # ------------------------------------------------------------------

    def _person_by_name(self, surname, given):
        """Return the first Person whose primary name matches."""
        for handle in self.db.get_person_handles():
            p = self.db.get_person_from_handle(handle)
            n = p.get_primary_name()
            if (n.get_first_name() == given and
                    n.get_surname() == surname):
                return p
        return None

    def test_person_1_exists(self):
        # nper=1 → synthetic name "FAMILY1, Person1"
        p = self._person_by_name('FAMILY1', 'Person1')
        self.assertIsNotNone(p, "Person nper=1 (FAMILY1, Person1) not found")

    def test_person_1_is_male(self):
        from gramps.gen.lib import Person
        p = self._person_by_name('FAMILY1', 'Person1')
        self.assertEqual(p.get_gender(), Person.MALE)

    def test_person_3_is_female(self):
        # nper=3 is female in source data
        from gramps.gen.lib import Person
        p = self._person_by_name('FAMILY3', 'Person3')
        self.assertIsNotNone(p, "Person nper=3 (FAMILY3, Person3) not found")
        self.assertEqual(p.get_gender(), Person.FEMALE)

    def test_person_2_exists(self):
        p = self._person_by_name('FAMILY2', 'Person2')
        self.assertIsNotNone(p, "Person nper=2 (FAMILY2, Person2) not found")

    # ------------------------------------------------------------------
    # Known source: majnum=1
    # ------------------------------------------------------------------

    def test_source_1_title(self):
        # majnum=1 → synthetic title "Source1"
        found = any(
            self.db.get_source_from_handle(h).get_title() == 'Source1'
            for h in self.db.get_source_handles()
        )
        self.assertTrue(found, "Source with title 'Source1' not found")

    # ------------------------------------------------------------------
    # Notes from Note-type events contain expected text
    # ------------------------------------------------------------------

    def test_notes_from_note_events(self):
        """132 Note-type events → 132 person notes; placeholder text is present."""
        self.assertGreaterEqual(self.db.get_number_of_notes(), 132)
        found = any(
            'Note text' in self.db.get_note_from_handle(h).get()
            for h in self.db.get_note_handles()
        )
        self.assertTrue(found, "No note with placeholder 'Note text' found")

    # ------------------------------------------------------------------
    # Events are not created for Note-type tags
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Families
    # ------------------------------------------------------------------

    def test_families_count(self):
        # 691 families derived from parent-child relationships in dataset 1
        self.assertEqual(self.db.get_number_of_families(), 691)

    def test_family_has_children(self):
        """At least one family must have children linked."""
        found = any(
            len(self.db.get_family_from_handle(h).get_child_ref_list()) > 0
            for h in self.db.get_family_handles()
        )
        self.assertTrue(found, "No family has children")

    # ------------------------------------------------------------------
    # Person event refs
    # ------------------------------------------------------------------

    def test_person_1_has_event_refs(self):
        p = self._person_by_name('FAMILY1', 'Person1')
        self.assertIsNotNone(p)
        self.assertGreater(len(p.get_event_ref_list()), 0)

    def test_person_1_has_birth_ref(self):
        p = self._person_by_name('FAMILY1', 'Person1')
        self.assertIsNotNone(p)
        self.assertIsNotNone(p.get_birth_ref(),
                             "Person1 should have a birth ref set")

    # ------------------------------------------------------------------
    # Repositories
    # ------------------------------------------------------------------

    def test_repository_1_exists(self):
        found = any(
            self.db.get_repository_from_handle(h).get_name() == 'Repository1'
            for h in self.db.get_repository_handles()
        )
        self.assertTrue(found, "Repository with name 'Repository1' not found")

    # ------------------------------------------------------------------
    # Events are not created for Note-type tags
    # ------------------------------------------------------------------

    def test_no_event_with_note_type(self):
        """No Gramps event should have a type name of 'Note'."""
        for handle in self.db.get_event_handles():
            ev = self.db.get_event_from_handle(handle)
            self.assertNotEqual(str(ev.get_type()), 'Note',
                                "Found an event with type 'Note' — should be a Note object")
