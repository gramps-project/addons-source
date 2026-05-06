"""Unit tests for libtmg.py

Run with:
    python -m pytest tests/
or:
    python -m unittest discover -s tests

Gramps must be installed.  The DBF-dependent import functions are tested by
patching the module-level table globals so no real .dbf files are needed.
"""

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



import sys
import os
import tempfile
import unittest

# Make sure libtmg is importable from the parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import libtmg

from gramps.gen.lib import Date, Event, NoteType, Person, Place, Source
from gramps.gen.db.utils import make_database
from gramps.gen.db import DbTxn


# ---------------------------------------------------------------------------
# Helpers shared across test cases
# ---------------------------------------------------------------------------

class _Rec:
    """Minimal fake DBF record — set any field via keyword arguments."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _table(records):
    """Return an object that behaves like a dbf.Table used as a context manager.

    libtmg uses tables in two ways:
        with tmgFoo:
            for record in tmgFoo:   # iterates over context-managed table
    """
    class _FakeTable:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def __iter__(self):
            return iter(records)
    return _FakeTable()


def _make_db():
    """Return a fresh in-memory Gramps database."""
    db = make_database("sqlite")
    db.load(":memory:", None)
    return db


def _add_person(db):
    """Add an empty Person to db and return (db, handle)."""
    p = Person()
    with DbTxn("setup", db) as t:
        db.add_person(p, t)
    return db, p.get_handle()


# ---------------------------------------------------------------------------
# Pure function: _strip_tmg_codes
# ---------------------------------------------------------------------------

class TestStripTmgCodes(unittest.TestCase):

    def test_none_returns_none(self):
        self.assertIsNone(libtmg._strip_tmg_codes(None))

    def test_empty_string_returns_empty(self):
        self.assertEqual(libtmg._strip_tmg_codes(''), '')

    def test_plain_text_unchanged(self):
        self.assertEqual(libtmg._strip_tmg_codes('Hello World'), 'Hello World')

    def test_italic_codes_removed(self):
        self.assertEqual(libtmg._strip_tmg_codes('[:ITAL:]text[:ITAL:]'), 'text')

    def test_cr_code_removed(self):
        self.assertEqual(libtmg._strip_tmg_codes('line1[:CR:]line2'), 'line1line2')

    def test_bold_codes_removed(self):
        self.assertEqual(libtmg._strip_tmg_codes('[BOLD:]text[BOLD:]'), 'text')

    def test_mixed_codes_all_removed(self):
        result = libtmg._strip_tmg_codes('[BOLD:][:ITAL:]hello[:ITAL:][BOLD:]')
        self.assertEqual(result, 'hello')

    def test_whitespace_stripped(self):
        self.assertEqual(libtmg._strip_tmg_codes('  hello  '), 'hello')


# ---------------------------------------------------------------------------
# Pure function: tmg_date_to_gramps_date
# ---------------------------------------------------------------------------

def _raw(date1='19000615', mod='3', date2='00000000', uncertain='0'):
    """Build a 21-char TMG date string.

    Layout:  [0] type-flag  [1:9] date1  [9] old-style  [10] modifier
             [11:19] date2  [19] old-style2  [20] uncertain
    """
    return '1' + date1 + '0' + mod + date2 + '0' + uncertain


class TestTmgDateToGrampsDate(unittest.TestCase):

    def test_none_returns_none(self):
        self.assertIsNone(libtmg.tmg_date_to_gramps_date(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(libtmg.tmg_date_to_gramps_date(''))

    def test_type_flag_zero_returns_none(self):
        # datefieldtype '0' means no date
        self.assertIsNone(libtmg.tmg_date_to_gramps_date('0' + '0' * 20))

    def test_all_zero_date_returns_none(self):
        # type=1 but all date digits zero → effectively empty
        self.assertIsNone(libtmg.tmg_date_to_gramps_date(_raw(date1='00000000')))

    def test_exact_date_fields(self):
        d = libtmg.tmg_date_to_gramps_date(_raw())
        self.assertEqual(d.get_year(),  1900)
        self.assertEqual(d.get_month(), 6)
        self.assertEqual(d.get_day(),   15)

    def test_before_modifier(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='0'))
        self.assertEqual(d.get_modifier(), Date.MOD_BEFORE)

    def test_say_modifier_maps_to_about(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='1'))
        self.assertEqual(d.get_modifier(), Date.MOD_ABOUT)

    def test_circa_modifier_maps_to_about(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='2'))
        self.assertEqual(d.get_modifier(), Date.MOD_ABOUT)

    def test_exact_modifier(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='3'))
        self.assertEqual(d.get_modifier(), Date.MOD_NONE)

    def test_after_modifier(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='4'))
        self.assertEqual(d.get_modifier(), Date.MOD_AFTER)

    def test_range_modifier(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='5', date2='19501231'))
        self.assertEqual(d.get_modifier(), Date.MOD_RANGE)
        self.assertEqual(d.get_year(),      1900)
        self.assertEqual(d.get_stop_year(), 1950)

    def test_or_modifier_maps_to_range(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='6', date2='19501231'))
        self.assertEqual(d.get_modifier(), Date.MOD_RANGE)

    def test_span_modifier(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='7', date2='19501231'))
        self.assertEqual(d.get_modifier(), Date.MOD_SPAN)

    def test_uncertain_sets_estimated_quality(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(uncertain='1'))
        self.assertEqual(d.get_quality(), Date.QUAL_ESTIMATED)

    def test_say_sets_estimated_quality(self):
        # "Say" (mod=1) also triggers QUAL_ESTIMATED regardless of uncertain flag
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='1'))
        self.assertEqual(d.get_quality(), Date.QUAL_ESTIMATED)

    def test_exact_certain_has_no_quality(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='3', uncertain='0'))
        self.assertEqual(d.get_quality(), Date.QUAL_NONE)


# ---------------------------------------------------------------------------
# import_notes — patches the module-level DBF table globals
# ---------------------------------------------------------------------------

class TestImportNotes(unittest.TestCase):

    def _patch(self, tagtypes_records, events_records):
        """Patch libtmg globals and return a context manager."""
        import unittest.mock as mock
        patches = [
            mock.patch.object(libtmg, 'tmgTagTypes', _table(tagtypes_records)),
            mock.patch.object(libtmg, 'tmgEvents',   _table(events_records)),
        ]
        return patches

    def _run(self, tagtypes_records, events_records, per_no_map, dataset=1, db=None):
        import unittest.mock as mock
        if db is None:
            db = _make_db()
        with mock.patch('libtmg.tmgTagTypes', _table(tagtypes_records), create=True), \
             mock.patch('libtmg.tmgEvents',   _table(events_records),   create=True):
            libtmg.import_notes(db, dataset, per_no_map)
        return db

    def test_no_per_no_map_is_noop(self):
        """Passing per_no_map=None must not touch any table."""
        import unittest.mock as mock
        db = _make_db()
        mock_table = mock.MagicMock()
        with mock.patch('libtmg.tmgTagTypes', mock_table, create=True), \
             mock.patch('libtmg.tmgEvents',   mock_table, create=True):
            libtmg.import_notes(db, 1, per_no_map=None)
        mock_table.__enter__.assert_not_called()

    def test_note_attached_to_person(self):
        db, phandle = _add_person(_make_db())
        per_no_map = {42: phandle}
        self._run(
            tagtypes_records=[_Rec(dsid=1, etypenum=77, etypename='Note')],
            events_records=[_Rec(dsid=1, etype=77, per1=42, recno=1,
                                 efoot='Born in London')],
            per_no_map=per_no_map, db=db,
        )
        person = db.get_person_from_handle(phandle)
        self.assertEqual(len(person.get_note_list()), 1)

    def test_note_text_stored(self):
        db, phandle = _add_person(_make_db())
        per_no_map = {1: phandle}
        self._run(
            tagtypes_records=[_Rec(dsid=1, etypenum=10, etypename='Note')],
            events_records=[_Rec(dsid=1, etype=10, per1=1, recno=1,
                                 efoot='  Some note text  ')],
            per_no_map=per_no_map, db=db,
        )
        person = db.get_person_from_handle(phandle)
        note = db.get_note_from_handle(person.get_note_list()[0])
        self.assertEqual(note.get(), 'Some note text')

    def test_note_type_is_person(self):
        db, phandle = _add_person(_make_db())
        per_no_map = {1: phandle}
        self._run(
            tagtypes_records=[_Rec(dsid=1, etypenum=77, etypename='Note')],
            events_records=[_Rec(dsid=1, etype=77, per1=1, recno=1,
                                 efoot='hello')],
            per_no_map=per_no_map, db=db,
        )
        person = db.get_person_from_handle(phandle)
        note = db.get_note_from_handle(person.get_note_list()[0])
        self.assertEqual(note.get_type(), NoteType.PERSON)

    def test_tmg_codes_stripped_from_note(self):
        db, phandle = _add_person(_make_db())
        per_no_map = {1: phandle}
        self._run(
            tagtypes_records=[_Rec(dsid=1, etypenum=77, etypename='Note')],
            events_records=[_Rec(dsid=1, etype=77, per1=1, recno=1,
                                 efoot='[:ITAL:]italicised[:ITAL:]')],
            per_no_map=per_no_map, db=db,
        )
        person = db.get_person_from_handle(phandle)
        note = db.get_note_from_handle(person.get_note_list()[0])
        self.assertEqual(note.get(), 'italicised')

    def test_empty_note_text_skipped(self):
        db, phandle = _add_person(_make_db())
        per_no_map = {1: phandle}
        self._run(
            tagtypes_records=[_Rec(dsid=1, etypenum=77, etypename='Note')],
            events_records=[_Rec(dsid=1, etype=77, per1=1, recno=1,
                                 efoot='')],
            per_no_map=per_no_map, db=db,
        )
        person = db.get_person_from_handle(phandle)
        self.assertEqual(len(person.get_note_list()), 0)

    def test_unknown_person_skipped(self):
        db = _make_db()
        self._run(
            tagtypes_records=[_Rec(dsid=1, etypenum=77, etypename='Note')],
            events_records=[_Rec(dsid=1, etype=77, per1=99, recno=1,
                                 efoot='orphan note')],
            per_no_map={}, db=db,
        )
        self.assertEqual(db.get_number_of_notes(), 0)

    def test_non_note_etype_ignored(self):
        db, phandle = _add_person(_make_db())
        per_no_map = {1: phandle}
        self._run(
            tagtypes_records=[_Rec(dsid=1, etypenum=77, etypename='Note')],
            # etype=10 is not a Note type
            events_records=[_Rec(dsid=1, etype=10, per1=1, recno=1,
                                 efoot='should be ignored')],
            per_no_map=per_no_map, db=db,
        )
        self.assertEqual(db.get_number_of_notes(), 0)

    def test_wrong_dataset_ignored(self):
        db, phandle = _add_person(_make_db())
        per_no_map = {1: phandle}
        self._run(
            tagtypes_records=[_Rec(dsid=1, etypenum=77, etypename='Note')],
            events_records=[_Rec(dsid=2, etype=77, per1=1, recno=1,
                                 efoot='wrong dataset')],
            per_no_map=per_no_map, dataset=1, db=db,
        )
        self.assertEqual(db.get_number_of_notes(), 0)

    def test_multiple_notes_for_one_person(self):
        db, phandle = _add_person(_make_db())
        per_no_map = {1: phandle}
        self._run(
            tagtypes_records=[_Rec(dsid=1, etypenum=77, etypename='Note')],
            events_records=[
                _Rec(dsid=1, etype=77, per1=1, recno=1, efoot='first'),
                _Rec(dsid=1, etype=77, per1=1, recno=2, efoot='second'),
            ],
            per_no_map=per_no_map, db=db,
        )
        person = db.get_person_from_handle(phandle)
        self.assertEqual(len(person.get_note_list()), 2)

    def test_no_note_tag_type_defined(self):
        """If the dataset has no 'Note' tag type, nothing is imported."""
        db, phandle = _add_person(_make_db())
        per_no_map = {1: phandle}
        self._run(
            tagtypes_records=[],   # no tag types at all
            events_records=[_Rec(dsid=1, etype=77, per1=1, recno=1,
                                 efoot='orphan')],
            per_no_map=per_no_map, db=db,
        )
        self.assertEqual(db.get_number_of_notes(), 0)


# ---------------------------------------------------------------------------
# trial_events — event import and Note-etype skip
# ---------------------------------------------------------------------------

# A minimal raw date string for an exact date (1900-06-15)
_EXACT_DATE = '1' + '19000615' + '0' + '3' + '00000000' + '0' + '0'
_EMPTY_DATE = ''


class TestTrialEvents(unittest.TestCase):

    def _run(self, tagtypes_records, events_records, dataset=1):
        import unittest.mock as mock
        db = _make_db()
        with mock.patch('libtmg.tmgTagTypes', _table(tagtypes_records), create=True), \
             mock.patch('libtmg.tmgEvents',   _table(events_records),   create=True):
            handle_map = libtmg.import_events(db, dataset)
        return db, handle_map

    def test_regular_event_creates_db_entry(self):
        _tagtypes = [_Rec(dsid=1, etypenum=10, etypename='Birth')]
        _events   = [_Rec(dsid=1, recno=1, etype=10, per1=1, per2=0,
                          placenum=0, edate=_EMPTY_DATE, efoot='')]
        db, hmap = self._run(_tagtypes, _events)
        self.assertEqual(db.get_number_of_events(), 1)
        self.assertIn(1, hmap)

    def test_handle_map_tuple_has_four_elements(self):
        _tagtypes = [_Rec(dsid=1, etypenum=10, etypename='Birth')]
        _events   = [_Rec(dsid=1, recno=5, etype=10, per1=3, per2=0,
                          placenum=7, edate=_EMPTY_DATE, efoot='')]
        _, hmap = self._run(_tagtypes, _events)
        entry = hmap[5]
        self.assertEqual(len(entry), 4)
        _handle, per1, per2, placenum = entry
        self.assertEqual(per1, 3)
        self.assertEqual(per2, 0)
        self.assertEqual(placenum, 7)

    def test_note_etype_event_not_in_handle_map(self):
        _tagtypes = [_Rec(dsid=1, etypenum=77, etypename='Note')]
        _events   = [_Rec(dsid=1, recno=1, etype=77, per1=1, per2=0,
                          placenum=0, edate=_EMPTY_DATE, efoot='a note')]
        db, hmap = self._run(_tagtypes, _events)
        self.assertEqual(db.get_number_of_events(), 0)
        self.assertNotIn(1, hmap)

    def test_event_memo_stored_as_description(self):
        _tagtypes = [_Rec(dsid=1, etypenum=10, etypename='Birth')]
        _events   = [_Rec(dsid=1, recno=1, etype=10, per1=1, per2=0,
                          placenum=0, edate=_EMPTY_DATE, efoot='born here')]
        db, hmap = self._run(_tagtypes, _events)
        event = db.get_event_from_handle(hmap[1][0])
        self.assertEqual(event.get_description(), 'born here')

    def test_event_memo_tmg_codes_stripped(self):
        _tagtypes = [_Rec(dsid=1, etypenum=10, etypename='Birth')]
        _events   = [_Rec(dsid=1, recno=1, etype=10, per1=1, per2=0,
                          placenum=0, edate=_EMPTY_DATE,
                          efoot='[:CR:]born here')]
        db, hmap = self._run(_tagtypes, _events)
        event = db.get_event_from_handle(hmap[1][0])
        self.assertEqual(event.get_description(), 'born here')

    def test_event_date_set(self):
        _tagtypes = [_Rec(dsid=1, etypenum=10, etypename='Birth')]
        _events   = [_Rec(dsid=1, recno=1, etype=10, per1=1, per2=0,
                          placenum=0, edate=_EXACT_DATE, efoot='')]
        db, hmap = self._run(_tagtypes, _events)
        event = db.get_event_from_handle(hmap[1][0])
        d = event.get_date_object()
        self.assertEqual(d.get_year(), 1900)
        self.assertEqual(d.get_month(), 6)

    def test_wrong_dataset_skipped(self):
        _tagtypes = [_Rec(dsid=1, etypenum=10, etypename='Birth')]
        _events   = [_Rec(dsid=2, recno=1, etype=10, per1=1, per2=0,
                          placenum=0, edate=_EMPTY_DATE, efoot='')]
        db, hmap = self._run(_tagtypes, _events, dataset=1)
        self.assertEqual(db.get_number_of_events(), 0)

    def test_mixed_note_and_regular_events(self):
        _tagtypes = [
            _Rec(dsid=1, etypenum=77, etypename='Note'),
            _Rec(dsid=1, etypenum=10, etypename='Birth'),
        ]
        _events = [
            _Rec(dsid=1, recno=1, etype=77, per1=1, per2=0,
                 placenum=0, edate=_EMPTY_DATE, efoot='a note'),
            _Rec(dsid=1, recno=2, etype=10, per1=1, per2=0,
                 placenum=0, edate=_EMPTY_DATE, efoot=''),
        ]
        db, hmap = self._run(_tagtypes, _events)
        self.assertEqual(db.get_number_of_events(), 1)
        self.assertNotIn(1, hmap)
        self.assertIn(2, hmap)


# ---------------------------------------------------------------------------
# import_sources — info-field parsing and author/publication split
# ---------------------------------------------------------------------------

class TestImportSources(unittest.TestCase):

    def _run(self, src_components, src_repo_links, sources_records,
             repo_handle_map=None, dataset=1):
        import unittest.mock as mock
        db = _make_db()
        with mock.patch('libtmg.tmgSourceComponents',      _table(src_components),  create=True), \
             mock.patch('libtmg.tmgSourceRepositoryLinks', _table(src_repo_links),  create=True), \
             mock.patch('libtmg.tmgSources',               _table(sources_records), create=True):
            smap = libtmg.import_sources(db, dataset, repo_handle_map)
        return db, smap

    def _source_rec(self, **kw):
        defaults = dict(dsid=1, majnum=1, mactive=True,
                        title='Test Source', abbrev='', info='',
                        text='', fform='', sform='', bform='', reminders='')
        defaults.update(kw)
        return _Rec(**defaults)

    def test_source_created(self):
        db, smap = self._run([], [], [self._source_rec()])
        self.assertEqual(db.get_number_of_sources(), 1)
        self.assertIn(1, smap)

    def test_title_set(self):
        db, smap = self._run([], [], [self._source_rec(title='My Source')])
        src = db.get_source_from_handle(smap[1])
        self.assertEqual(src.get_title(), 'My Source')

    def test_abbreviation_set(self):
        db, smap = self._run([], [], [self._source_rec(abbrev='MySrc')])
        src = db.get_source_from_handle(smap[1])
        self.assertEqual(src.get_abbreviation(), 'MySrc')

    def test_inactive_source_skipped(self):
        db, smap = self._run([], [], [self._source_rec(mactive=False)])
        self.assertEqual(db.get_number_of_sources(), 0)

    def test_wrong_dataset_skipped(self):
        db, smap = self._run([], [], [self._source_rec(dsid=2)], dataset=1)
        self.assertEqual(db.get_number_of_sources(), 0)

    def test_author_element_sets_author(self):
        # recno 1 → position 0 in $!& split
        components = [_Rec(recno=1, element='[AUTHOR]')]
        rec = self._source_rec(info='John Smith')
        db, smap = self._run(components, [], [rec])
        src = db.get_source_from_handle(smap[1])
        self.assertEqual(src.get_author(), 'John Smith')

    def test_non_author_element_sets_publication_info(self):
        components = [_Rec(recno=1, element='[TITLE]')]
        rec = self._source_rec(info='Some Title')
        db, smap = self._run(components, [], [rec])
        src = db.get_source_from_handle(smap[1])
        self.assertIn('TITLE', src.get_publication_info())
        self.assertIn('Some Title', src.get_publication_info())

    def test_multiple_authors_joined_with_semicolon(self):
        # positions 0 and 1 → recno 1 and 2
        components = [
            _Rec(recno=1, element='[AUTHOR]'),
            _Rec(recno=2, element='[EDITOR]'),
        ]
        rec = self._source_rec(info='Alice$!&Bob')
        db, smap = self._run(components, [], [rec])
        src = db.get_source_from_handle(smap[1])
        self.assertEqual(src.get_author(), 'Alice; Bob')

    def test_empty_info_position_skipped(self):
        # position 0 empty, position 1 filled → recno 2 = [AUTHOR]
        components = [
            _Rec(recno=1, element='[TITLE]'),
            _Rec(recno=2, element='[AUTHOR]'),
        ]
        rec = self._source_rec(info='$!&Jane Doe')
        db, smap = self._run(components, [], [rec])
        src = db.get_source_from_handle(smap[1])
        self.assertEqual(src.get_author(), 'Jane Doe')
        self.assertEqual(src.get_publication_info(), '')

    def test_note_fields_become_notes(self):
        rec = self._source_rec(text='original text', fform='', sform='', bform='')
        db, smap = self._run([], [], [rec])
        src = db.get_source_from_handle(smap[1])
        self.assertEqual(len(src.get_note_list()), 1)
        note = db.get_note_from_handle(src.get_note_list()[0])
        self.assertIn('original text', note.get())

    def test_multiple_note_fields_each_become_a_note(self):
        rec = self._source_rec(text='txt', fform='fn', sform='', bform='')
        db, smap = self._run([], [], [rec])
        src = db.get_source_from_handle(smap[1])
        self.assertEqual(len(src.get_note_list()), 2)


# ---------------------------------------------------------------------------
# import_places — name reconstruction, type resolution, note parts
# ---------------------------------------------------------------------------

class TestImportPlaces(unittest.TestCase):

    def _run(self, part_types, place_dict, ppv_records, places_records, dataset=1):
        import unittest.mock as mock
        db = _make_db()
        with mock.patch('libtmg.tmgPlacePartType',  _table(part_types),      create=True), \
             mock.patch('libtmg.tmgPlaceDictionary', _table(place_dict),      create=True), \
             mock.patch('libtmg.tmgPlacePartValue',  _table(ppv_records),     create=True), \
             mock.patch('libtmg.tmgPlaces',          _table(places_records),  create=True):
            pmap = libtmg.import_places(db, dataset)
        return db, pmap

    # Convenience: build part_type, place_dict, ppv records for a single place
    def _setup(self, recno, parts, dataset=1, comment='', shortplace=''):
        """
        parts: list of (label, value)  e.g. [('City','London'),('Country','UK')]
        Returns (part_type_recs, place_dict_recs, ppv_recs, place_recs)
        """
        part_type_recs = []
        place_dict_recs = []
        ppv_recs = []
        for i, (label, value) in enumerate(parts):
            type_id = i + 1
            uid = i + 100
            part_type_recs.append(_Rec(type=type_id, value=label))
            place_dict_recs.append(_Rec(uid=uid,     value=value))
            ppv_recs.append(_Rec(dsid=dataset, recno=recno, type=type_id, uid=uid))
        place_recs = [_Rec(dsid=dataset, recno=recno,
                           shortplace=shortplace, comment=comment)]
        return part_type_recs, place_dict_recs, ppv_recs, place_recs

    def test_city_only_name_and_type(self):
        pt, pd, ppv, pl = self._setup(1, [('City', 'London')])
        db, pmap = self._run(pt, pd, ppv, pl)
        self.assertIn(1, pmap)
        place = db.get_place_from_handle(pmap[1])
        self.assertEqual(place.get_name().get_value(), 'London')
        from gramps.gen.lib import PlaceType
        self.assertEqual(place.get_type().value, PlaceType.CITY)

    def test_country_only_name_and_type(self):
        pt, pd, ppv, pl = self._setup(1, [('Country', 'France')])
        db, pmap = self._run(pt, pd, ppv, pl)
        place = db.get_place_from_handle(pmap[1])
        from gramps.gen.lib import PlaceType
        self.assertEqual(place.get_type().value, PlaceType.COUNTRY)

    def test_city_state_country_name_order(self):
        pt, pd, ppv, pl = self._setup(1, [
            ('City', 'Paris'), ('State', 'Île-de-France'), ('Country', 'France')
        ])
        db, pmap = self._run(pt, pd, ppv, pl)
        place = db.get_place_from_handle(pmap[1])
        # GEO_ORDER: Addressee, Detail, City, County, State, Country
        self.assertEqual(place.get_name().get_value(),
                         'Paris, Île-de-France, France')

    def test_most_specific_type_wins(self):
        # City is more specific than Country in _GEO_ORDER
        pt, pd, ppv, pl = self._setup(1, [
            ('City', 'Berlin'), ('Country', 'Germany')
        ])
        db, pmap = self._run(pt, pd, ppv, pl)
        place = db.get_place_from_handle(pmap[1])
        from gramps.gen.lib import PlaceType
        self.assertEqual(place.get_type().value, PlaceType.CITY)

    def test_empty_place_skipped(self):
        # No parts and no shortplace → nothing imported
        place_recs = [_Rec(dsid=1, recno=1, shortplace='', comment='')]
        db, pmap = self._run([], [], [], place_recs)
        self.assertEqual(db.get_number_of_places(), 0)
        self.assertNotIn(1, pmap)

    def test_shortplace_fallback(self):
        # No parts but shortplace set → use it
        place_recs = [_Rec(dsid=1, recno=1, shortplace='Somewhere', comment='')]
        db, pmap = self._run([], [], [], place_recs)
        self.assertIn(1, pmap)
        place = db.get_place_from_handle(pmap[1])
        self.assertEqual(place.get_name().get_value(), 'Somewhere')

    def test_note_parts_go_to_note(self):
        pt, pd, ppv, pl = self._setup(1, [
            ('City', 'Rome'), ('Postal', '00100')
        ])
        db, pmap = self._run(pt, pd, ppv, pl)
        place = db.get_place_from_handle(pmap[1])
        self.assertEqual(len(place.get_note_list()), 1)
        note = db.get_note_from_handle(place.get_note_list()[0])
        self.assertIn('Postal', note.get())
        self.assertIn('00100', note.get())

    def test_comment_goes_to_note(self):
        pt, pd, ppv, pl = self._setup(1, [('City', 'Rome')], comment='see also')
        db, pmap = self._run(pt, pd, ppv, pl)
        place = db.get_place_from_handle(pmap[1])
        note = db.get_note_from_handle(place.get_note_list()[0])
        self.assertIn('see also', note.get())

    def test_wrong_dataset_skipped(self):
        pt, pd, ppv, pl = self._setup(1, [('City', 'Oslo')], dataset=2)
        db, pmap = self._run(pt, pd, ppv, pl, dataset=1)
        self.assertEqual(db.get_number_of_places(), 0)

    def test_returns_recno_to_handle_map(self):
        pt, pd, ppv, pl = self._setup(42, [('City', 'Vienna')])
        db, pmap = self._run(pt, pd, ppv, pl)
        self.assertIn(42, pmap)


# ---------------------------------------------------------------------------
# link_event_places — event gets its place handle set
# ---------------------------------------------------------------------------

class TestLinkEventPlaces(unittest.TestCase):

    def _make_event(self, db):
        from gramps.gen.db import DbTxn
        ev = Event()
        with DbTxn("setup", db) as t:
            db.add_event(ev, t)
        return ev.get_handle()

    def _make_place(self, db):
        from gramps.gen.db import DbTxn
        pl = Place()
        with DbTxn("setup", db) as t:
            db.add_place(pl, t)
        return pl.get_handle()

    def test_place_linked_to_event(self):
        db = _make_db()
        ev_handle = self._make_event(db)
        pl_handle  = self._make_place(db)
        event_handle_map = {1: (ev_handle, 1, 0, 7)}
        place_handle_map = {7: pl_handle}
        libtmg.link_event_places(db, event_handle_map, place_handle_map)
        event = db.get_event_from_handle(ev_handle)
        self.assertEqual(event.get_place_handle(), pl_handle)

    def test_zero_placenum_skipped(self):
        db = _make_db()
        ev_handle = self._make_event(db)
        event_handle_map = {1: (ev_handle, 1, 0, 0)}
        place_handle_map = {0: self._make_place(db)}
        libtmg.link_event_places(db, event_handle_map, place_handle_map)
        event = db.get_event_from_handle(ev_handle)
        self.assertEqual(event.get_place_handle(), '')

    def test_unknown_placenum_skipped(self):
        db = _make_db()
        ev_handle = self._make_event(db)
        event_handle_map = {1: (ev_handle, 1, 0, 99)}
        libtmg.link_event_places(db, event_handle_map, {})
        event = db.get_event_from_handle(ev_handle)
        self.assertEqual(event.get_place_handle(), '')

    def test_empty_maps_noop(self):
        db = _make_db()
        libtmg.link_event_places(db, {}, {})   # must not raise
        libtmg.link_event_places(db, None, None)


# ---------------------------------------------------------------------------
# Pure functions: num_to_month, num_to_date, parse_date
# ---------------------------------------------------------------------------

class TestNumToMonth(unittest.TestCase):

    def test_january(self):
        self.assertEqual(libtmg.num_to_month('01'), 'Jan')

    def test_september(self):
        self.assertEqual(libtmg.num_to_month('09'), 'Sep')

    def test_december(self):
        self.assertEqual(libtmg.num_to_month('12'), 'Dec')

    def test_integer_input(self):
        self.assertEqual(libtmg.num_to_month(6), 'Jun')


class TestNumToDate(unittest.TestCase):

    def test_full_date(self):
        self.assertEqual(libtmg.num_to_date('20130920'), '20 Sep 2013')

    def test_year_only(self):
        self.assertEqual(libtmg.num_to_date('20130000'), '2013')

    def test_month_year_only(self):
        self.assertEqual(libtmg.num_to_date('20130900'), 'Sep 2013')

    def test_all_zeros_returns_none(self):
        self.assertIsNone(libtmg.num_to_date('00000000'))

    def test_day_month_only(self):
        # YYYY=0000 MM=09 DD=20 → "20 Sep"
        self.assertEqual(libtmg.num_to_date('00000920'), '20 Sep')

    def test_day_only(self):
        self.assertEqual(libtmg.num_to_date('00000020'), '20')

    def test_month_only(self):
        self.assertEqual(libtmg.num_to_date('00000900'), 'Sep')


class TestParseDate(unittest.TestCase):

    def _d(self, date1='19000615', mod='3', date2='00000000', uncertain='0'):
        """Build a TMG date string (same layout as the _raw helper above)."""
        return '1' + date1 + '0' + mod + date2 + '0' + uncertain

    def test_exact_date(self):
        self.assertEqual(libtmg.parse_date(self._d()), '15 Jun 1900')

    def test_before_modifier(self):
        result = libtmg.parse_date(self._d(mod='0'))
        self.assertTrue(result.startswith('Before '))

    def test_say_modifier(self):
        result = libtmg.parse_date(self._d(mod='1'))
        self.assertTrue(result.startswith('Say '))

    def test_circa_modifier(self):
        result = libtmg.parse_date(self._d(mod='2'))
        self.assertTrue(result.startswith('Circa '))

    def test_after_modifier(self):
        result = libtmg.parse_date(self._d(mod='4'))
        self.assertTrue(result.startswith('After '))

    def test_between_modifier(self):
        result = libtmg.parse_date(self._d(mod='5', date2='19501231'))
        self.assertIn('Between', result)
        self.assertIn('1900', result)
        self.assertIn('1950', result)

    def test_or_modifier(self):
        result = libtmg.parse_date(self._d(mod='6', date2='19501231'))
        self.assertIn(' or ', result)

    def test_from_to_modifier(self):
        result = libtmg.parse_date(self._d(mod='7', date2='19501231'))
        self.assertTrue(result.startswith('From '))
        self.assertIn(' to ', result)

    def test_uncertain_flag_adds_question_mark(self):
        result = libtmg.parse_date(self._d(uncertain='1'))
        self.assertTrue(result.endswith('?'))

    def test_certain_flag_no_question_mark(self):
        result = libtmg.parse_date(self._d(uncertain='0'))
        self.assertFalse(result.endswith('?'))

    def test_irregular_date_code_returns_raw(self):
        # type '0' → return the 28-char raw value after the type flag
        raw = '0' + 'about 1900' + ' ' * 18
        result = libtmg.parse_date(raw[:29])
        self.assertEqual(result, raw[1:29])


# ---------------------------------------------------------------------------
# Pure functions: _repo_type_from_name, _url_from_name
# ---------------------------------------------------------------------------

class TestRepoTypeFromName(unittest.TestCase):

    def _t(self, name):
        return libtmg._repo_type_from_name(name)

    def test_website_by_domain(self):
        from gramps.gen.lib import RepositoryType
        self.assertEqual(self._t('ancestry.com'), RepositoryType.WEBSITE)

    def test_website_by_keyword(self):
        from gramps.gen.lib import RepositoryType
        self.assertEqual(self._t('My Online Genealogy Website'), RepositoryType.WEBSITE)

    def test_archive(self):
        from gramps.gen.lib import RepositoryType
        self.assertEqual(self._t('National Archives'), RepositoryType.ARCHIVE)

    def test_library(self):
        from gramps.gen.lib import RepositoryType
        self.assertEqual(self._t('City Library'), RepositoryType.LIBRARY)

    def test_cemetery(self):
        from gramps.gen.lib import RepositoryType
        self.assertEqual(self._t('St John Cemetery'), RepositoryType.CEMETERY)

    def test_church(self):
        from gramps.gen.lib import RepositoryType
        self.assertEqual(self._t('St Mary Parish Church'), RepositoryType.CHURCH)

    def test_default_is_library(self):
        from gramps.gen.lib import RepositoryType
        self.assertEqual(self._t('Unknown Place Name'), RepositoryType.LIBRARY)


class TestUrlFromName(unittest.TestCase):

    def test_bare_domain(self):
        self.assertEqual(libtmg._url_from_name('ancestry.com'),
                         'https://www.ancestry.com')

    def test_www_prefix_preserved(self):
        self.assertEqual(libtmg._url_from_name('www.familysearch.org'),
                         'https://www.familysearch.org')

    def test_no_domain_returns_none(self):
        self.assertIsNone(libtmg._url_from_name('Some Local Library'))

    def test_gov_domain(self):
        url = libtmg._url_from_name('records.gov')
        self.assertEqual(url, 'https://www.records.gov')

    def test_domain_embedded_in_name(self):
        url = libtmg._url_from_name('Ancestry (ancestry.com) family trees')
        self.assertEqual(url, 'https://www.ancestry.com')


# ---------------------------------------------------------------------------
# Lookup helpers: short_place_name, tag_type_name
# ---------------------------------------------------------------------------

class TestShortPlaceName(unittest.TestCase):

    def _run(self, places_records, placenum, dataset=1):
        import unittest.mock as mock
        db = _make_db()
        with mock.patch('libtmg.tmgPlaces', _table(places_records), create=True):
            return libtmg.short_place_name(db, placenum, dataset)

    def test_returns_shortplace(self):
        rec = _Rec(dsid=1, recno=5, shortplace='New York  ', styleid=1, comment='')
        self.assertEqual(self._run([rec], placenum=5), 'New York')

    def test_trailing_whitespace_stripped(self):
        rec = _Rec(dsid=1, recno=1, shortplace='London   ', styleid=1, comment='')
        self.assertEqual(self._run([rec], placenum=1), 'London')

    def test_wrong_recno_returns_none(self):
        rec = _Rec(dsid=1, recno=1, shortplace='Paris', styleid=1, comment='')
        self.assertIsNone(self._run([rec], placenum=99))

    def test_wrong_dataset_returns_none(self):
        rec = _Rec(dsid=2, recno=1, shortplace='Berlin', styleid=1, comment='')
        self.assertIsNone(self._run([rec], placenum=1, dataset=1))


class TestTagTypeName(unittest.TestCase):

    def _run(self, tagtypes_records, eventtype, dataset=1):
        import unittest.mock as mock
        db = _make_db()
        with mock.patch('libtmg.tmgTagTypes', _table(tagtypes_records), create=True):
            return libtmg.tag_type_name(db, eventtype, dataset)

    def test_returns_name(self):
        rec = _Rec(dsid=1, etypenum=2, etypename='Birth   ')
        self.assertEqual(self._run([rec], eventtype=2), 'Birth')

    def test_trailing_whitespace_stripped(self):
        rec = _Rec(dsid=1, etypenum=3, etypename='Death  ')
        self.assertEqual(self._run([rec], eventtype=3), 'Death')

    def test_wrong_eventtype_returns_none(self):
        rec = _Rec(dsid=1, etypenum=2, etypename='Birth')
        self.assertIsNone(self._run([rec], eventtype=99))

    def test_wrong_dataset_returns_none(self):
        rec = _Rec(dsid=2, etypenum=2, etypename='Birth')
        self.assertIsNone(self._run([rec], eventtype=2, dataset=1))


# ---------------------------------------------------------------------------
# import_people — name parsing, gender, dataset filter
# ---------------------------------------------------------------------------

class TestImportPeople(unittest.TestCase):

    def _run(self, names_records, people_records, dataset=1):
        import unittest.mock as mock
        db = _make_db()
        with mock.patch('libtmg.tmgNames',  _table(names_records),  create=True), \
             mock.patch('libtmg.tmgPeople', _table(people_records), create=True):
            per_no_map = libtmg.import_people(db, dataset)
        return db, per_no_map

    def _name_rec(self, **kw):
        defaults = dict(dsid=1, nper=1, primary=True, srnamedisp='SMITH, John')
        defaults.update(kw)
        return _Rec(**defaults)

    def _person_rec(self, **kw):
        defaults = dict(dsid=1, per_no=1, sex='M')
        defaults.update(kw)
        return _Rec(**defaults)

    def test_person_created(self):
        db, pmap = self._run([self._name_rec()], [self._person_rec()])
        self.assertEqual(db.get_number_of_people(), 1)

    def test_returns_per_no_map(self):
        db, pmap = self._run([self._name_rec(nper=5)], [self._person_rec(per_no=5)])
        self.assertIn(5, pmap)

    def test_surname_parsed(self):
        db, pmap = self._run([self._name_rec(nper=1, srnamedisp='JONES, Alice')],
                             [self._person_rec(per_no=1)])
        p = db.get_person_from_handle(pmap[1])
        self.assertEqual(p.get_primary_name().get_surname(), 'JONES')

    def test_given_name_parsed(self):
        db, pmap = self._run([self._name_rec(nper=1, srnamedisp='JONES, Alice')],
                             [self._person_rec(per_no=1)])
        p = db.get_person_from_handle(pmap[1])
        self.assertEqual(p.get_primary_name().get_first_name(), 'Alice')

    def test_male_gender(self):
        db, pmap = self._run([self._name_rec()], [self._person_rec(sex='M')])
        p = db.get_person_from_handle(pmap[1])
        self.assertEqual(p.get_gender(), Person.MALE)

    def test_female_gender(self):
        db, pmap = self._run([self._name_rec()], [self._person_rec(sex='F')])
        p = db.get_person_from_handle(pmap[1])
        self.assertEqual(p.get_gender(), Person.FEMALE)

    def test_unknown_gender(self):
        db, pmap = self._run([self._name_rec()], [self._person_rec(sex='?')])
        p = db.get_person_from_handle(pmap[1])
        self.assertEqual(p.get_gender(), Person.UNKNOWN)

    def test_non_primary_name_skipped(self):
        db, pmap = self._run(
            [self._name_rec(primary=False, srnamedisp='ALT, Name')],
            [self._person_rec()]
        )
        self.assertEqual(db.get_number_of_people(), 0)

    def test_wrong_dataset_skipped(self):
        db, pmap = self._run([self._name_rec(dsid=2)], [self._person_rec(dsid=2)],
                             dataset=1)
        self.assertEqual(db.get_number_of_people(), 0)

    def test_no_comma_surname_only(self):
        # srnamedisp with no comma → surname=full string, given=''
        db, pmap = self._run([self._name_rec(srnamedisp='SMITH')],
                             [self._person_rec()])
        p = db.get_person_from_handle(pmap[1])
        self.assertEqual(p.get_primary_name().get_surname(), 'SMITH')
        self.assertEqual(p.get_primary_name().get_first_name(), '')


# ---------------------------------------------------------------------------
# link_person_events — EventRefs, birth/death special refs
# ---------------------------------------------------------------------------

class TestLinkPersonEvents(unittest.TestCase):

    def _make_typed_event(self, db, event_type_int):
        from gramps.gen.lib import EventType
        ev = Event()
        ev.set_type(EventType(event_type_int))
        with DbTxn("setup", db) as t:
            db.add_event(ev, t)
        return ev.get_handle()

    def test_individual_event_linked_to_person(self):
        from gramps.gen.lib import EventType
        db, phandle = _add_person(_make_db())
        ev_handle = self._make_typed_event(db, EventType.OCCUPATION)
        libtmg.link_person_events(db,
                                  per_no_map={1: phandle},
                                  event_handle_map={1: (ev_handle, 1, 0, 0)})
        p = db.get_person_from_handle(phandle)
        self.assertEqual(len(p.get_event_ref_list()), 1)

    def test_couple_event_not_linked_to_person(self):
        from gramps.gen.lib import EventType
        db, phandle = _add_person(_make_db())
        ev_handle = self._make_typed_event(db, EventType.MARRIAGE)
        libtmg.link_person_events(db,
                                  per_no_map={1: phandle},
                                  event_handle_map={1: (ev_handle, 1, 2, 0)})
        p = db.get_person_from_handle(phandle)
        self.assertEqual(len(p.get_event_ref_list()), 0)

    def test_birth_event_sets_birth_ref(self):
        from gramps.gen.lib import EventType
        db, phandle = _add_person(_make_db())
        ev_handle = self._make_typed_event(db, EventType.BIRTH)
        libtmg.link_person_events(db,
                                  per_no_map={1: phandle},
                                  event_handle_map={1: (ev_handle, 1, 0, 0)})
        p = db.get_person_from_handle(phandle)
        self.assertIsNotNone(p.get_birth_ref())
        self.assertEqual(p.get_birth_ref().ref, ev_handle)

    def test_death_event_sets_death_ref(self):
        from gramps.gen.lib import EventType
        db, phandle = _add_person(_make_db())
        ev_handle = self._make_typed_event(db, EventType.DEATH)
        libtmg.link_person_events(db,
                                  per_no_map={1: phandle},
                                  event_handle_map={1: (ev_handle, 1, 0, 0)})
        p = db.get_person_from_handle(phandle)
        self.assertIsNotNone(p.get_death_ref())

    def test_unknown_person_skipped(self):
        from gramps.gen.lib import EventType
        db = _make_db()
        ev_handle = self._make_typed_event(db, EventType.BIRTH)
        # Must not raise even when per1 has no entry in per_no_map
        libtmg.link_person_events(db,
                                  per_no_map={},
                                  event_handle_map={1: (ev_handle, 1, 0, 0)})

    def test_empty_maps_noop(self):
        db = _make_db()
        libtmg.link_person_events(db, None, None)
        libtmg.link_person_events(db, {}, {})


# ---------------------------------------------------------------------------
# import_families — parent-child grouping, couple events, rel type
# ---------------------------------------------------------------------------

class TestImportFamilies(unittest.TestCase):

    def _run(self, tagtypes, pc_rels, per_no_by_gender, event_handle_map=None,
             dataset=1):
        """Create persons from per_no_by_gender={per_no: gender}, run import."""
        import unittest.mock as mock
        db = _make_db()
        pmap = {}
        for per_no, gender in per_no_by_gender.items():
            p = Person()
            p.set_gender(gender)
            with DbTxn("setup", db) as t:
                db.add_person(p, t)
            pmap[per_no] = p.get_handle()
        with mock.patch('libtmg.tmgTagTypes',                _table(tagtypes), create=True), \
             mock.patch('libtmg.tmgParentChildRelationships', _table(pc_rels),  create=True):
            libtmg.import_families(db, dataset, pmap, event_handle_map)
        return db, pmap

    def _pc(self, parent, child, ptype, primary=True, pnote='', dsid=1):
        return _Rec(dsid=dsid, parent=parent, child=child,
                    ptype=ptype, primary=primary, pnote=pnote)

    def _father_type(self, num=1):
        return _Rec(dsid=1, etypenum=num, etypename='Father-Biological')

    def _mother_type(self, num=2):
        return _Rec(dsid=1, etypenum=num, etypename='Mother-Biological')

    def test_father_child_creates_family(self):
        db, pmap = self._run([self._father_type()],
                             [self._pc(1, 2, ptype=1)],
                             {1: Person.MALE, 2: Person.UNKNOWN})
        self.assertEqual(db.get_number_of_families(), 1)
        fam = db.get_family_from_handle(list(db.get_family_handles())[0])
        self.assertEqual(fam.get_father_handle(), pmap[1])

    def test_mother_child_creates_family(self):
        db, pmap = self._run([self._mother_type()],
                             [self._pc(1, 2, ptype=2)],
                             {1: Person.FEMALE, 2: Person.UNKNOWN})
        fam = db.get_family_from_handle(list(db.get_family_handles())[0])
        self.assertEqual(fam.get_mother_handle(), pmap[1])

    def test_father_and_mother_same_family(self):
        db, pmap = self._run(
            [self._father_type(1), self._mother_type(2)],
            [self._pc(1, 3, ptype=1), self._pc(2, 3, ptype=2)],
            {1: Person.MALE, 2: Person.FEMALE, 3: Person.UNKNOWN},
        )
        self.assertEqual(db.get_number_of_families(), 1)
        fam = db.get_family_from_handle(list(db.get_family_handles())[0])
        self.assertEqual(fam.get_father_handle(), pmap[1])
        self.assertEqual(fam.get_mother_handle(), pmap[2])

    def test_child_added_to_family(self):
        db, pmap = self._run([self._father_type()],
                             [self._pc(1, 2, ptype=1)],
                             {1: Person.MALE, 2: Person.UNKNOWN})
        fam = db.get_family_from_handle(list(db.get_family_handles())[0])
        self.assertEqual(len(fam.get_child_ref_list()), 1)
        self.assertEqual(fam.get_child_ref_list()[0].ref, pmap[2])

    def test_child_ref_type_biological(self):
        from gramps.gen.lib import ChildRefType
        db, pmap = self._run([self._father_type()],
                             [self._pc(1, 2, ptype=1)],
                             {1: Person.MALE, 2: Person.UNKNOWN})
        fam = db.get_family_from_handle(list(db.get_family_handles())[0])
        self.assertEqual(fam.get_child_ref_list()[0].get_father_relation(),
                         ChildRefType.BIRTH)

    def test_wrong_dataset_skipped(self):
        db, _ = self._run([self._father_type()],
                          [self._pc(1, 2, ptype=1, dsid=2)],
                          {1: Person.MALE, 2: Person.UNKNOWN}, dataset=1)
        self.assertEqual(db.get_number_of_families(), 0)

    def test_no_per_no_map_is_noop(self):
        import unittest.mock as mock
        db = _make_db()
        with mock.patch('libtmg.tmgTagTypes',                _table([]), create=True), \
             mock.patch('libtmg.tmgParentChildRelationships', _table([]), create=True):
            libtmg.import_families(db, 1, per_no_map=None)
        self.assertEqual(db.get_number_of_families(), 0)

    def test_marriage_event_sets_rel_type_married(self):
        from gramps.gen.lib import EventType, FamilyRelType
        import unittest.mock as mock

        db = _make_db()
        pmap = {}
        for per_no, gender in {1: Person.MALE, 2: Person.FEMALE, 3: Person.UNKNOWN}.items():
            p = Person()
            p.set_gender(gender)
            with DbTxn("s", db) as t:
                db.add_person(p, t)
            pmap[per_no] = p.get_handle()

        ev = Event()
        ev.set_type(EventType(EventType.MARRIAGE))
        with DbTxn("s", db) as t:
            db.add_event(ev, t)

        tagtypes = [self._father_type(1), self._mother_type(2)]
        pc = [self._pc(1, 3, ptype=1), self._pc(2, 3, ptype=2)]
        event_handle_map = {99: (ev.get_handle(), 1, 2, 0)}

        with mock.patch('libtmg.tmgTagTypes',                _table(tagtypes), create=True), \
             mock.patch('libtmg.tmgParentChildRelationships', _table(pc),       create=True):
            libtmg.import_families(db, 1, pmap, event_handle_map)

        fam = db.get_family_from_handle(list(db.get_family_handles())[0])
        self.assertEqual(fam.get_relationship(), FamilyRelType.MARRIED)
        self.assertEqual(len(fam.get_event_ref_list()), 1)


# ---------------------------------------------------------------------------
# import_repositories — name, type inference, URL, notes
# ---------------------------------------------------------------------------

class TestImportRepositories(unittest.TestCase):

    def _run(self, repo_records, per_no_map=None, dataset=1):
        import unittest.mock as mock
        db = _make_db()
        with mock.patch('libtmg.tmgRepositories', _table(repo_records), create=True):
            repo_map = libtmg.import_repositories(db, dataset, per_no_map)
        return db, repo_map

    def _repo_rec(self, **kw):
        defaults = dict(dsid=1, recno=1, name='City Library',
                        abbrev='', rnote='', rperno=0)
        defaults.update(kw)
        return _Rec(**defaults)

    def test_repository_created(self):
        db, rmap = self._run([self._repo_rec()])
        self.assertEqual(db.get_number_of_repositories(), 1)
        self.assertIn(1, rmap)

    def test_name_set(self):
        db, rmap = self._run([self._repo_rec(name='National Archives')])
        repo = db.get_repository_from_handle(rmap[1])
        self.assertEqual(repo.get_name(), 'National Archives')

    def test_wrong_dataset_skipped(self):
        db, rmap = self._run([self._repo_rec(dsid=2)], dataset=1)
        self.assertEqual(db.get_number_of_repositories(), 0)

    def test_type_inferred_from_name(self):
        from gramps.gen.lib import RepositoryType
        db, rmap = self._run([self._repo_rec(name='ancestry.com')])
        repo = db.get_repository_from_handle(rmap[1])
        self.assertEqual(repo.get_type().value, RepositoryType.WEBSITE)

    def test_url_added_for_web_repo(self):
        db, rmap = self._run([self._repo_rec(name='familysearch.org')])
        repo = db.get_repository_from_handle(rmap[1])
        urls = repo.get_url_list()
        self.assertEqual(len(urls), 1)
        self.assertIn('familysearch', urls[0].get_path())

    def test_no_url_for_non_web_repo(self):
        db, rmap = self._run([self._repo_rec(name='Local Parish Church')])
        repo = db.get_repository_from_handle(rmap[1])
        self.assertEqual(len(repo.get_url_list()), 0)

    def test_blank_name_falls_back_to_abbrev(self):
        db, rmap = self._run([self._repo_rec(name='', abbrev='TNA')])
        repo = db.get_repository_from_handle(rmap[1])
        self.assertEqual(repo.get_name(), 'TNA')

    def test_note_added_when_rnote_set(self):
        db, rmap = self._run([self._repo_rec(rnote='Open Mon-Fri')])
        repo = db.get_repository_from_handle(rmap[1])
        self.assertEqual(len(repo.get_note_list()), 1)
        note = db.get_note_from_handle(repo.get_note_list()[0])
        self.assertIn('Open Mon-Fri', note.get())

    def test_returns_recno_to_handle_map(self):
        db, rmap = self._run([self._repo_rec(recno=42)])
        self.assertIn(42, rmap)


# ---------------------------------------------------------------------------
# import_citations — creation and attachment to events / persons
# ---------------------------------------------------------------------------

class TestImportCitations(unittest.TestCase):

    def _run(self, citation_records, names_records=None, pc_records=None,
             source_handle_map=None, event_handle_map=None, per_no_map=None,
             dataset=1, db=None):
        import unittest.mock as mock
        if db is None:
            db = _make_db()
        with mock.patch('libtmg.tmgCitations',                _table(citation_records),    create=True), \
             mock.patch('libtmg.tmgNames',                    _table(names_records or []), create=True), \
             mock.patch('libtmg.tmgParentChildRelationships', _table(pc_records or []),    create=True):
            libtmg.import_citations(db, dataset,
                                    source_handle_map=source_handle_map,
                                    event_handle_map=event_handle_map,
                                    per_no_map=per_no_map)
        return db

    def _cit_rec(self, **kw):
        defaults = dict(dsid=1, recno=1, majsource=1, stype='E', refrec=1,
                        exclude=False, subsource='', citref='', citmemo='',
                        sdsure='', snsure='', sssure='', spsure='', sfsure='')
        defaults.update(kw)
        return _Rec(**defaults)

    def test_no_source_map_is_noop(self):
        db = self._run([self._cit_rec()])
        self.assertEqual(db.get_number_of_citations(), 0)

    def test_citation_created(self):
        db = _make_db()
        src = Source()
        with DbTxn("s", db) as t:
            db.add_source(src, t)
        db = self._run([self._cit_rec()],
                       source_handle_map={1: src.get_handle()}, db=db)
        self.assertEqual(db.get_number_of_citations(), 1)

    def test_excluded_citation_skipped(self):
        db = _make_db()
        src = Source()
        with DbTxn("s", db) as t:
            db.add_source(src, t)
        db = self._run([self._cit_rec(exclude=True)],
                       source_handle_map={1: src.get_handle()}, db=db)
        self.assertEqual(db.get_number_of_citations(), 0)

    def test_wrong_dataset_skipped(self):
        db = _make_db()
        src = Source()
        with DbTxn("s", db) as t:
            db.add_source(src, t)
        db = self._run([self._cit_rec(dsid=2)],
                       source_handle_map={1: src.get_handle()}, db=db, dataset=1)
        self.assertEqual(db.get_number_of_citations(), 0)

    def test_unknown_source_skipped(self):
        db = _make_db()
        db = self._run([self._cit_rec(majsource=99)],
                       source_handle_map={1: 'some_handle'}, db=db)
        self.assertEqual(db.get_number_of_citations(), 0)

    def test_citation_attached_to_event(self):
        db = _make_db()
        src = Source()
        ev = Event()
        with DbTxn("s", db) as t:
            db.add_source(src, t)
            db.add_event(ev, t)
        ev_handle = ev.get_handle()

        db = self._run([self._cit_rec(stype='E', refrec=7)],
                       source_handle_map={1: src.get_handle()},
                       event_handle_map={7: (ev_handle, 1, 0, 0)},
                       db=db)
        event = db.get_event_from_handle(ev_handle)
        self.assertEqual(len(event.get_citation_list()), 1)

    def test_citation_attached_to_person_via_name(self):
        db = _make_db()
        src = Source()
        p = Person()
        with DbTxn("s", db) as t:
            db.add_source(src, t)
            db.add_person(p, t)
        phandle = p.get_handle()

        # name recno=3 maps to nper=5; per_no_map routes nper=5 to phandle
        db = self._run(
            [self._cit_rec(stype='N', refrec=3)],
            names_records=[_Rec(dsid=1, recno=3, nper=5)],
            source_handle_map={1: src.get_handle()},
            per_no_map={5: phandle},
            db=db,
        )
        person = db.get_person_from_handle(phandle)
        self.assertEqual(len(person.get_citation_list()), 1)

    def test_subsource_becomes_page(self):
        db = _make_db()
        src = Source()
        with DbTxn("s", db) as t:
            db.add_source(src, t)
        db = self._run([self._cit_rec(subsource='p.42')],
                       source_handle_map={1: src.get_handle()}, db=db)
        cit_handle = list(db.get_citation_handles())[0]
        cit = db.get_citation_from_handle(cit_handle)
        self.assertEqual(cit.get_page(), 'p.42')



# ── TmgProject._read_pjc_config ──────────────────────────────────────────

def _make_minimal_sqz(tmp_dir, pjc_content):
    """Create a minimal .SQZ zip containing only a PJC file."""
    import zipfile as _zf
    pjc_path = os.path.join(tmp_dir, 'test.pjc')
    sqz_path = os.path.join(tmp_dir, 'test.sqz')
    with open(pjc_path, 'w', encoding='latin-1') as f:
        f.write(pjc_content)
    with _zf.ZipFile(sqz_path, 'w') as zf:
        zf.write(pjc_path, 'test.pjc')
    return sqz_path


class _MockUser:
    """Minimal stand-in for the Gramps user object used in importData."""
    def __init__(self):
        self.error_shown = False
        self.error_message = None
        self.uistate = None

    def notify_error(self, title, message=''):
        self.error_shown = True
        self.error_message = message

    def begin_progress(self, *a, **kw): pass
    def end_progress(self): pass
    def step_progress(self): pass


class TestReadPjcConfig(unittest.TestCase):
    """Tests for TmgProject._read_pjc_config PJC parsing."""

    _MINIMAL_PJC = (
        "[Stamp]\n"
        "PjcVersion=11.0\n"
        "[Researcher]\n"
        "Name=Test User\n"
    )

    def _make_project(self, pjc_content, tmp_path):
        pjc_file = os.path.join(tmp_path, "test.pjc")
        with open(pjc_file, 'w', encoding='latin-1') as f:
            f.write(pjc_content)
        return libtmg.TmgProject(pjc_file)

    def test_well_formed_pjc_returns_version(self):
        """A clean PJC file parses successfully and version() returns a float."""
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(self._MINIMAL_PJC, tmp)
            self.assertEqual(project.version(), 11.0)

    def test_malformed_section_header_does_not_raise(self):
        """Lines like '[Exho' (no closing bracket) are silently dropped."""
        pjc = (
            "[Stamp]\n"
            "PjcVersion=11.0\n"
            "[Exho\n"                  # malformed — the crash trigger
            "SomeGarbage\n"
            "[Researcher]\n"
            "Name=Test User\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(pjc, tmp)
            # Must not raise; must still find [Stamp]
            self.assertEqual(project.version(), 11.0)

    def test_null_bytes_stripped(self):
        """NUL bytes in the PJC file are stripped before parsing."""
        pjc = "[Stamp]\x00\nPjcVersion=11.0\n"
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(pjc, tmp)
            self.assertEqual(project.version(), 11.0)

    def test_parse_error_returns_partial_config(self):
        """If configparser still raises after filtering, a warning is logged
        and a (possibly empty) config object is returned rather than crashing."""
        import logging
        # Feed content that survives the filter but still breaks configparser:
        # a key=value line before any section header is technically invalid.
        pjc = "orphan_key=value\n[Stamp]\nPjcVersion=11.0\n"
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(pjc, tmp)
            with self.assertLogs('.TMGImport', level=logging.WARNING) as cm:
                cfg = project._read_pjc_config()
            self.assertTrue(any('parse error' in m.lower() or 'parsing' in m.lower()
                                for m in cm.output))
            # Config object is returned (not None), even if incomplete
            self.assertIsNotNone(cfg)

    def test_version_too_old_notifies_user(self):
        """A PJC version < 11.0 calls user.notify_error and aborts import."""
        pjc = "[Stamp]\nPjcVersion=10.0\n"  # TMG 9.01 or earlier
        with tempfile.TemporaryDirectory() as tmp:
            sqz = _make_minimal_sqz(tmp, pjc)
            db = _make_db()
            user = _MockUser()
            libtmg.importData(db, sqz, user)
        self.assertTrue(user.error_shown,
                        "notify_error should have been called for old version")
        self.assertIn('9.05', user.error_message or '',
                      "Error message should mention TMG 9.05")

    def test_missing_pjc_version_notifies_user(self):
        """A PJC with no [Stamp]/PjcVersion calls user.notify_error."""
        pjc = "[OtherSection]\nSomeKey=value\n"  # no [Stamp] at all
        with tempfile.TemporaryDirectory() as tmp:
            sqz = _make_minimal_sqz(tmp, pjc)
            db = _make_db()
            user = _MockUser()
            libtmg.importData(db, sqz, user)
        self.assertTrue(user.error_shown,
                        "notify_error should have been called for missing version")

if __name__ == '__main__':
    unittest.main()
