#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Eduard Ralph
# Copyright (C) 2026  Brian McCullough
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
Tests for the Data Entry Gramplet.

Covers ``gramps-project/gramps#12691`` (``AttributeError: 'DummyDb' object
has no attribute 'get_undodb'`` when the user presses *Add* or *Save*
without a Family Tree loaded), the event type menus and their ``.ini``
file, the Enter Sources / Select Citation radio group, and adding people
and events to a real (temporary) database.

The Gramplet subclass requires a live Gramps GUI to instantiate, so
these tests build a minimal stub via ``__new__`` with fake widgets and
invoke the callbacks directly. That keeps the tests fast and avoids
spinning up GTK, while still exercising the real code paths.
"""

# ------------------------
# Python modules
# ------------------------
import importlib
import os
import shutil
import sys
import tempfile
import unittest
from typing import Any, Callable
from unittest import mock

# The addon imports Gtk at module load — skip cleanly if gi/Gtk are not
# available. On systems where both GTK3 and GTK4 are present, pin Gtk to
# 3.0 before any gramps import (mirrors what gramps.grampsapp does at
# startup); otherwise PyGObject loads GTK4 and the gramps.gui import
# chain crashes on Gtk.IconSize.MENU (a GTK3-only enum).
try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
except (ImportError, ValueError, AttributeError) as err:
    raise unittest.SkipTest("GTK 3.0 / PyGObject not available: %s" % err)

# ------------------------
# Gramps modules
# ------------------------
# Addon root goes on sys.path so ``DataEntryGramplet.DataEntryGramplet``
# resolves to the addon module. The fully-qualified form matters: when
# unittest loads this file as ``DataEntryGramplet.tests.test_...``, the
# outer ``DataEntryGramplet`` is already a namespace package in
# ``sys.modules``, so a bare ``from DataEntryGramplet import
# DataEntryGramplet`` would bind the submodule instead of the class. The
# ``tests/`` directory lacks an __init__.py, so this ``__file__``-based
# hack is still the right way to make the addon importable during local
# and CI runs.
ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    import gramps
except ImportError as err:
    raise unittest.SkipTest("gramps package not available: %s" % err)

if "GRAMPS_RESOURCES" not in os.environ:
    os.environ["GRAMPS_RESOURCES"] = os.path.dirname(os.path.dirname(gramps.__file__))

# ------------------------
# Gramps specific
# ------------------------
# The addon module pulls in the full Gramps GUI stack at import time. On
# environments where GTK is missing or version-mismatched the import
# fails; skip the whole module cleanly in that case so collection does
# not surface spurious errors.
try:
    import gramps.gui.dialog as gramps_dialog  # noqa: E402
    from gramps.gen.db import DbTxn  # noqa: E402
    from gramps.gen.errors import ValidationError  # noqa: E402
    from gramps.gen.lib import (  # noqa: E402
        Citation,
        Date,
        EventType,
        Person,
        Source,
    )
    from gramps.gen.utils.configmanager import ConfigManager  # noqa: E402
    from gramps.version import major_version  # noqa: E402

    addon = importlib.import_module("DataEntryGramplet.DataEntryGramplet")
    DataEntryGramplet = addon.DataEntryGramplet
except Exception as err:  # noqa: BLE001 — environment guard
    raise unittest.SkipTest("DataEntryGramplet module unavailable: %s" % err)


# ------------------------------------------------------------
#
# Fakes
#
# ------------------------------------------------------------
class _FakeDbState:
    """Stub for ``Gramplet.dbstate``: an open/closed flag and an optional db."""

    def __init__(self, is_open: bool = True, db: Any = None) -> None:
        """
        :param is_open: Value returned from ``is_open()``.
        :param db: The database behind ``dbstate.db``.
        """
        self._is_open = is_open
        self.db = db

    def is_open(self) -> bool:
        """Return the configured open state."""
        return self._is_open


class _FakeEntry:
    """Stub for ``Gtk.Entry`` (text only)."""

    def __init__(self, text: str = "") -> None:
        """
        :param text: The initial text.
        """
        self._text = text

    def get_text(self) -> str:
        """Return the text."""
        return self._text

    def set_text(self, text: str) -> None:
        """Set the text."""
        self._text = text

    def hide(self) -> None:
        """Ignore (visibility is not tested)."""

    def show(self) -> None:
        """Ignore (visibility is not tested)."""

    def set_visible(self, _visible: bool) -> None:
        """Ignore (visibility is not tested)."""


class _FakeCombo:
    """Stub for ``Gtk.ComboBox`` (active index only)."""

    def __init__(self, active: int = 0) -> None:
        """
        :param active: The initially active index.
        """
        self._active = active
        self.handlers: list[Callable[..., None]] = []

    def get_active(self) -> int:
        """Return the active index."""
        return self._active

    def set_active(self, active: int) -> None:
        """Set the active index."""
        self._active = active

    def connect(self, _signal: str, handler: Callable[..., None]) -> None:
        """Remember a handler (not called by this stub)."""
        self.handlers.append(handler)


class _FakeRadio:
    """
    Stub for a ``Gtk.RadioButton`` group member.

    Like the real widget, activating one member deactivates whatever other
    member of its group was active, firing that member's own ``toggled``
    handlers too (see :meth:`_FakeRadio.new_group`).
    """

    def __init__(self, active: bool = False) -> None:
        """
        :param active: The initial state.
        """
        self._active = active
        self.handlers: list[Callable[..., None]] = []
        self.tooltip = None
        self.group: list["_FakeRadio"] = [self]

    @classmethod
    def new_group(cls, *active_flags: bool) -> tuple["_FakeRadio", ...]:
        """
        Build several instances that share one exclusivity group.

        :param active_flags: Initial state of each member, in order.
        :returns: The members, sharing a common group.
        """
        members = tuple(cls(active) for active in active_flags)
        group = list(members)
        for member in members:
            member.group = group
        return members

    def connect(self, _signal: str, handler: Callable[..., None]) -> None:
        """Remember a handler for the ``toggled`` signal."""
        self.handlers.append(handler)

    def get_active(self) -> bool:
        """Return the state."""
        return self._active

    def set_active(self, active: bool) -> None:
        """
        Change the state and emit ``toggled`` if it changed.

        Activating a member deactivates any active sibling first, exactly
        like ``Gtk.RadioButton``.
        """
        if active == self._active:
            return
        self._active = active
        if active:
            for sibling in self.group:
                if sibling is not self and sibling._active:
                    sibling.set_active(False)
        for handler in list(self.handlers):
            handler(self)

    def set_tooltip_text(self, text: Any) -> None:
        """Remember the tooltip."""
        self.tooltip = text

    def hide(self) -> None:
        """Ignore (visibility is not tested)."""

    def show(self) -> None:
        """Ignore (visibility is not tested)."""

    def set_visible(self, _visible: bool) -> None:
        """Ignore (visibility is not tested)."""


class _FakeLabel(_FakeEntry):
    """Stub for ``Gtk.Label`` (text and tooltip)."""

    def __init__(self, text: str = "") -> None:
        """
        :param text: The initial text.
        """
        super().__init__(text)
        self.tooltip = None

    def set_tooltip_text(self, text: Any) -> None:
        """Remember the tooltip."""
        self.tooltip = text

    def set_use_markup(self, _markup: bool) -> None:
        """Ignore (markup is not tested)."""


class _FakeSelector:
    """Stand-in for the Citation selector class returned by SelectorFactory."""

    result: Any = None
    opened = 0

    def __init__(self, *_args: Any) -> None:
        """Count how often the selector was opened."""
        type(self).opened += 1

    def run(self) -> Any:
        """Return what the "user" chose (an object or ``None``)."""
        return type(self).result


def _make_gramplet(
    *,
    db_open: bool = True,
    np_name: str = "",
    np_gender: int = 2,  # UNKNOWN
    np_relation: int = DataEntryGramplet.NO_REL,
    dirty: bool = False,
) -> Any:
    """
    Build a ``DataEntryGramplet`` via ``__new__`` so its ``init``
    (which pulls in GTK) does not run, then attach just enough state
    for the isolated guards to execute.

    :param db_open: Whether ``dbstate.is_open()`` reports an open tree.
    :param np_name: Value stored in the Name entry.
    :param np_gender: Value stored in the Gender combo (UNKNOWN by default).
    :param np_relation: Value stored in the Relation combo.
    :param dirty: Value of the private ``_dirty`` flag.
    :returns: A stub instance with the minimum attributes set.
    """
    stub = DataEntryGramplet.__new__(DataEntryGramplet)
    stub.dbstate = _FakeDbState(db_open)
    stub._dirty = dirty
    stub._dirty_person = None
    stub.de_widgets = {
        "NPName": _FakeEntry(np_name),
        "NPGender": _FakeCombo(np_gender),
        "NPRelation": _FakeCombo(np_relation),
    }
    # cb_save_data_edit falls through to self.update() even on the guarded path.
    stub.update = lambda: None
    stub.get_active_object = lambda _type: None
    return stub


# ------------------------------------------------------------
#
# _ErrorDialogTestCase
#
# ------------------------------------------------------------
class _ErrorDialogTestCase(unittest.TestCase):
    """Base class that patches ``gramps.gui.dialog.ErrorDialog`` so
    tests can inspect calls without opening any GTK dialogs."""

    def setUp(self) -> None:
        """Install the ErrorDialog capture and reset the buffer."""
        self.captured_errors: list[tuple[str, str]] = []

        def _fake(title: Any, body: Any = "", *_args: Any, **_kwargs: Any) -> None:
            self.captured_errors.append((str(title), str(body)))

        patcher = mock.patch.object(gramps_dialog, "ErrorDialog", _fake)
        patcher.start()
        self.addCleanup(patcher.stop)


# ------------------------------------------------------------
#
# TestBug12691ClosedDb
#
# ------------------------------------------------------------
class TestBug12691ClosedDb(_ErrorDialogTestCase):
    """Regression coverage for bug 12691 — pressing *Add* or *Save*
    with no tree open must surface an ErrorDialog instead of crashing
    inside ``DbTxn`` with ``AttributeError: 'DummyDb' ... get_undodb``."""

    def test_add_data_entry_with_closed_db_shows_error(self) -> None:
        """*Add* with no tree open surfaces an ErrorDialog, not a crash."""
        stub = _make_gramplet(db_open=False, np_name="Doe, Jane")

        stub.cb_add_data_entry(None)

        self.assertTrue(self.captured_errors, "ErrorDialog was not displayed")
        title, body = self.captured_errors[0]
        self.assertIn("Family Tree", title)
        self.assertIn("open", body.lower())

    def test_save_data_edit_with_closed_db_shows_error(self) -> None:
        """*Save* while dirty with no tree open must not invoke DbTxn."""
        stub = _make_gramplet(db_open=False, dirty=True)

        stub.cb_save_data_edit(None)

        self.assertTrue(self.captured_errors, "ErrorDialog was not displayed")
        title, _body = self.captured_errors[0]
        self.assertIn("Family Tree", title)

    def test_save_data_edit_noop_when_not_dirty(self) -> None:
        """A *Save* click with nothing pending should be a silent no-op."""
        stub = _make_gramplet(db_open=True, dirty=False)

        stub.cb_save_data_edit(None)

        self.assertEqual(self.captured_errors, [])
        self.assertFalse(stub._dirty)


# ------------------------------------------------------------
#
# TestInputGuards
#
# ------------------------------------------------------------
class TestInputGuards(_ErrorDialogTestCase):
    """Lock in the pre-existing input validators so future refactors
    cannot silently weaken the guardrails around ``cb_add_data_entry``."""

    def test_add_data_entry_requires_name(self) -> None:
        """Empty name with a valid tree should surface the name-required error."""
        stub = _make_gramplet(db_open=True, np_name="")

        stub.cb_add_data_entry(None)

        self.assertTrue(self.captured_errors)
        title, _body = self.captured_errors[0]
        self.assertIn("name", title.lower())

    def test_add_data_entry_parent_without_active_person(self) -> None:
        """Adding as a parent without an active person surfaces a clear error."""
        stub = _make_gramplet(
            db_open=True,
            np_name="Doe, Jane",
            np_relation=DataEntryGramplet.AS_PARENT,
        )

        stub.cb_add_data_entry(None)

        self.assertTrue(self.captured_errors)
        _title, body = self.captured_errors[0]
        self.assertIn("parent", body.lower())


# ------------------------------------------------------------
#
# TestGprRegistration
#
# ------------------------------------------------------------
class TestGprRegistration(unittest.TestCase):
    """Catch metadata breakage in the plugin registration file early."""

    def test_gpr_registration_metadata(self) -> None:
        """The .gpr.py file must register a single gramplet with expected keys."""
        gpr_path = os.path.join(ADDON_DIR, "DataEntryGramplet.gpr.py")
        calls: list[tuple[tuple, dict]] = []

        namespace: dict[str, Any] = {
            "register": lambda *args, **kwargs: calls.append((args, kwargs)),
            "GRAMPLET": "GRAMPLET",
            "STABLE": "STABLE",
            "EXPERIMENTAL": "EXPERIMENTAL",
            "EXPERT": "EXPERT",
            "_": lambda s: s,
        }
        with open(gpr_path, encoding="utf-8") as handle:
            exec(compile(handle.read(), gpr_path, "exec"), namespace)

        self.assertEqual(len(calls), 1, "expected exactly one register() call")
        args, kwargs = calls[0]
        self.assertEqual(args, ("GRAMPLET",))
        self.assertEqual(kwargs["id"], "Data Entry Gramplet")
        self.assertEqual(kwargs["gramplet"], "DataEntryGramplet")
        self.assertEqual(kwargs["fname"], "DataEntryGramplet.py")
        self.assertEqual(kwargs["gramps_target_version"], major_version)
        self.assertEqual(kwargs["status"], "STABLE")
        # Navigation type must stay Person — the active object is fetched that way.
        self.assertEqual(kwargs["navtypes"], ["Person"])

    def test_plugin_id_matches_gpr(self) -> None:
        """PLUGIN_ID (stamped into the .ini) must equal the registered id."""
        self.assertEqual(addon.PLUGIN_ID, "Data Entry Gramplet")


# ------------------------------------------------------------
#
# TestEventTypeTokens
#
# ------------------------------------------------------------
class TestEventTypeTokens(unittest.TestCase):
    """The ``number:Name`` tokens stored in the .ini."""

    def test_round_trip(self) -> None:
        """Every event type the menus offer survives token -> value."""
        stub = _make_gramplet()
        for _name, value in stub.event_type_choices():
            token = addon.event_type_token(value)
            self.assertEqual(addon.parse_event_type_token(token), value, token)

    def test_token_has_number_and_english_name(self) -> None:
        """The name part is the locale-independent one."""
        token = addon.event_type_token(EventType.BIRTH)
        self.assertEqual(token, "%d:Birth" % EventType.BIRTH)

    def test_mismatched_name_is_rejected(self) -> None:
        """A right number with the wrong name means the list has changed."""
        self.assertIsNone(addon.parse_event_type_token("%d:Death" % EventType.BIRTH))

    def test_unknown_number_is_rejected(self) -> None:
        """A number Gramps does not know is rejected, whatever the name."""
        self.assertIsNone(addon.parse_event_type_token("9999:Unknown"))

    def test_unknown_and_custom_are_rejected(self) -> None:
        """Unknown and Custom are not usable menu choices."""
        for value in (EventType.UNKNOWN, EventType.CUSTOM):
            self.assertIsNone(
                addon.parse_event_type_token(addon.event_type_token(value))
            )

    def test_garbage_is_rejected(self) -> None:
        """Anything that is not ``number:Name`` gives ``None``."""
        for token in (None, 42, "", "abc", "12", "x:Birth", ":Birth"):
            self.assertIsNone(addon.parse_event_type_token(token), repr(token))


# ------------------------------------------------------------
#
# TestConfigFile
#
# ------------------------------------------------------------
class TestConfigFile(unittest.TestCase):
    """DataEntryGramplet.ini: location, [meta] block, migration, fallback."""

    def setUp(self) -> None:
        """Use a temporary .ini instead of the real one."""
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.ini = os.path.join(self.tmpdir, "DataEntryGramplet.ini")

    def _load(self) -> ConfigManager:
        """Run ``_load_config`` against the temporary file."""
        manager = ConfigManager(self.ini)
        with mock.patch.object(
            addon.global_config, "register_manager", return_value=manager
        ):
            return addon._load_config()

    def test_real_ini_is_next_to_the_module(self) -> None:
        """The module's own ConfigManager writes into the addon folder."""
        filename = str(addon.CONFIG.filename)
        self.assertEqual(
            os.path.dirname(os.path.abspath(filename)),
            os.path.dirname(os.path.abspath(str(addon.__file__))),
        )
        self.assertEqual(os.path.basename(filename), "DataEntryGramplet.ini")

    def test_new_file_gets_a_live_meta_block(self) -> None:
        """A new .ini names the addon and its format version (uncommented)."""
        self._load()
        with open(self.ini, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("[meta]", text)
        self.assertIn("\nplugin_id='Data Entry Gramplet'\n", text)
        self.assertIn("\nschema_version='2'\n", text)

    def test_schema_1_file_is_migrated(self) -> None:
        """Bare numbers under event_type_N become ``number:Name`` tokens."""
        with open(self.ini, "w", encoding="utf-8") as handle:
            handle.write(
                "[gramplet]\nevent_type_2=%d\n\n"
                "[meta]\nplugin_id='Data Entry Gramplet'\nschema_version='1'\n"
                % EventType.CENSUS
            )
        manager = self._load()
        self.assertEqual(
            manager.get("gramplet.event_type_row2"),
            addon.event_type_token(EventType.CENSUS),
        )
        self.assertEqual(manager.get("meta.schema_version"), "2")
        with open(self.ini, encoding="utf-8") as handle:
            self.assertNotIn("event_type_2=", handle.read())

    def test_invalid_stored_types_fall_back_per_row(self) -> None:
        """A stale row falls back to its default; the other rows are kept."""
        manager = self._load()
        manager.set("gramplet.event_type_row1", "%d:Wrong" % EventType.BIRTH)
        manager.set(
            "gramplet.event_type_row2", addon.event_type_token(EventType.CENSUS)
        )
        stub = _make_gramplet()
        stub.de_widgets.update(
            {p + "Type": _FakeCombo() for p in DataEntryGramplet.EVENT_PREFIXES}
        )
        with mock.patch.object(addon, "CONFIG", manager):
            stub.on_load()
        selected = [
            stub.selected_event_type(p) for p in DataEntryGramplet.EVENT_PREFIXES
        ]
        self.assertEqual(
            selected,
            [EventType.BIRTH, EventType.CENSUS, EventType.DEATH, EventType.BURIAL],
        )

    def test_choices_are_saved_and_restored(self) -> None:
        """save_event_types writes tokens that on_load reads back."""
        manager = self._load()
        stub = _make_gramplet()
        stub.de_widgets.update(
            {p + "Type": _FakeCombo() for p in DataEntryGramplet.EVENT_PREFIXES}
        )
        wanted = [
            EventType.BAPTISM,
            EventType.CENSUS,
            EventType.BURIAL,
            EventType.CREMATION,
        ]
        for prefix, value in zip(DataEntryGramplet.EVENT_PREFIXES, wanted):
            stub.select_event_type(prefix, value)
        with mock.patch.object(addon, "CONFIG", manager):
            stub.save_event_types()
            again = _make_gramplet()
            again.de_widgets.update(
                {p + "Type": _FakeCombo() for p in DataEntryGramplet.EVENT_PREFIXES}
            )
            again.on_load()
        restored = [
            again.selected_event_type(p) for p in DataEntryGramplet.EVENT_PREFIXES
        ]
        self.assertEqual(restored, wanted)


# ------------------------------------------------------------
#
# _DbTestCase
#
# ------------------------------------------------------------
class _DbTestCase(_ErrorDialogTestCase):
    """Base class with a real temporary database and a form of fake widgets."""

    def setUp(self) -> None:
        """Create the database and the stub gramplet."""
        super().setUp()
        try:
            from gramps.plugins.db.dbapi.sqlite import SQLite

            self.tmpdir = tempfile.mkdtemp()
            self.db = SQLite()
            self.db.load(self.tmpdir, None)
        except Exception as err:  # noqa: BLE001 — environment guard
            raise unittest.SkipTest("cannot create a test database: %s" % err)
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.addCleanup(self.db.close)
        self.stub = self._make_form()
        self.active: Any = None
        self.stub.get_active_object = lambda _type: self.active

    def _make_form(self) -> Any:
        """Return a stub gramplet whose widgets are fakes."""
        stub = DataEntryGramplet.__new__(DataEntryGramplet)
        stub.dbstate = _FakeDbState(True, self.db)
        stub._dirty = False
        stub._dirty_person = None
        stub._citation_handle = None
        stub.uistate = None
        stub.track = []
        stub.update = lambda: None
        show_sources, show_citation, show_none = _FakeRadio.new_group(
            True, False, False
        )
        widgets: dict[str, Any] = {
            "NPName": _FakeEntry(),
            "NPGender": _FakeCombo(Person.UNKNOWN),
            "NPRelation": _FakeCombo(DataEntryGramplet.NO_REL),
            "NPSource": _FakeEntry(),
            "Active person": _FakeLabel(),
            "Active person:Edit person": _FakeEntry(),
            "Active person:Edit family": _FakeEntry(),
            "Active person:Edit family:Label": _FakeEntry(),
            "APName": _FakeEntry(),
            "APGender": _FakeCombo(Person.UNKNOWN),
            "APSource": _FakeEntry(),
            "APBirth": _FakeEntry(),
            "APBirthSource": _FakeEntry(),
            "APDeath": _FakeEntry(),
            "APDeathSource": _FakeEntry(),
            "Active person:Show sources": show_sources,
            "Active person:Show citation": show_citation,
            "Active person:Show none": show_none,
            "Citation:Info": _FakeLabel(),
        }
        for prefix in DataEntryGramplet.EVENT_PREFIXES:
            widgets[prefix] = _FakeEntry()
            widgets[prefix + "Source"] = _FakeEntry()
            widgets[prefix + "Type"] = _FakeCombo()
        for key in DataEntryGramplet.SOURCE_KEYS:
            widgets[key + ":Citation"] = _FakeRadio(False)
        stub.de_widgets = widgets
        for prefix, default in zip(
            DataEntryGramplet.EVENT_PREFIXES, DataEntryGramplet.EVENT_DEFAULTS
        ):
            stub.select_event_type(prefix, default)
        widgets["Active person:Show sources"].connect("toggled", stub.cb_toggle_sources)
        widgets["Active person:Show citation"].connect(
            "toggled", stub.cb_toggle_citation
        )
        return stub

    def add_person(self, first: str, last: str, gender: int) -> Person:
        """Add a person to the database directly and return it."""
        with DbTxn("test setup", self.db) as trans:
            person = self.stub.make_person(first, last, gender)
            self.db.add_person(person, trans)
        return person

    def add_citation(
        self, page: str, date: Any = None, title: str = "Register"
    ) -> Citation:
        """Add a source with one citation and return the citation."""
        with DbTxn("test setup", self.db) as trans:
            source = Source()
            source.set_title(title)
            self.db.add_source(source, trans)
            citation = Citation()
            citation.set_reference_handle(source.get_handle())
            citation.set_page(page)
            if date is not None:
                citation.set_date_object(date)
            self.db.add_citation(citation, trans)
        return citation

    def fill(
        self, name: str, relation: int, gender: int, events: tuple[str, ...] = ()
    ) -> None:
        """Fill the New person block."""
        widgets = self.stub.de_widgets
        widgets["NPName"].set_text(name)
        widgets["NPRelation"].set_active(relation)
        widgets["NPGender"].set_active(gender)
        for prefix, text in zip(DataEntryGramplet.EVENT_PREFIXES, events):
            widgets[prefix].set_text(text)

    def person_named(self, first: str) -> Person:
        """Return the person with a given first name."""
        for handle in self.db.get_person_handles():
            person = self.db.get_person_from_handle(handle)
            if person.get_primary_name().get_first_name() == first:
                return person
        raise AssertionError("no person named %s" % first)

    def counts(self) -> tuple[int, ...]:
        """People, families, events, places, sources and citations."""
        return (
            self.db.get_number_of_people(),
            self.db.get_number_of_families(),
            self.db.get_number_of_events(),
            self.db.get_number_of_places(),
            self.db.get_number_of_sources(),
            self.db.get_number_of_citations(),
        )

    def event_types(self, person: Person) -> list[int]:
        """The types of a person's events, in order."""
        return [
            int(self.db.get_event_from_handle(ref.ref).get_type())
            for ref in person.get_event_ref_list()
        ]


# ------------------------------------------------------------
#
# TestSaveDataEdit
#
# ------------------------------------------------------------
class TestSaveDataEdit(_DbTestCase):
    """Saving the Active person block, including per-field citation use."""

    def setUp(self) -> None:
        """Route the selector to a fake."""
        super().setUp()
        patcher = mock.patch.object(
            addon.gramps_selectors, "SelectorFactory", lambda _name: _FakeSelector
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_citation_attaches_only_to_checked_fields(self) -> None:
        """Save attaches the chosen citation only where its box is checked."""
        person = self.add_person("Al", "Grand", Person.MALE)
        citation = self.add_citation("p. 1")
        _FakeSelector.result = citation
        widgets = self.stub.de_widgets
        self.stub._dirty_person = person
        widgets["APName"].set_text("Grand, Al")
        widgets["APGender"].set_active(Person.MALE)
        widgets["APBirth"].set_text("1900")
        widgets["APDeath"].set_text("")
        widgets["Active person:Show citation"].set_active(True)
        widgets["APBirthSource:Citation"].set_active(True)
        self.stub._dirty = True
        self.stub.cb_save_data_edit(None)
        birth = self.db.get_event_from_handle(person.get_birth_ref().ref)
        self.assertEqual(birth.get_citation_list(), [citation.get_handle()])
        self.assertEqual(person.get_citation_list(), [])

    def test_use_citation_is_a_one_shot_flag(self) -> None:
        """The checked box does not survive the refresh after Save."""
        person = self.add_person("Al", "Grand", Person.MALE)
        citation = self.add_citation("p. 1")
        _FakeSelector.result = citation
        widgets = self.stub.de_widgets
        self.stub._dirty_person = person
        widgets["APName"].set_text("Grand, Al")
        widgets["APGender"].set_active(Person.MALE)
        widgets["APBirth"].set_text("1900")
        widgets["APDeath"].set_text("")
        widgets["Active person:Show citation"].set_active(True)
        widgets["APBirthSource:Citation"].set_active(True)
        self.stub._dirty = True
        self.stub.cb_save_data_edit(None)
        self.active = person
        self.stub.main()
        self.assertFalse(widgets["APBirthSource:Citation"].get_active())


# ------------------------------------------------------------
#
# TestRefusableTxn
#
# ------------------------------------------------------------
class TestRefusableTxn(_DbTestCase):
    """A refused transaction must leave nothing behind."""

    def test_success_commits(self) -> None:
        """Without an exception the transaction is committed."""
        with addon.refusable_txn(DbTxn("ok", self.db)) as trans:
            self.db.add_person(self.stub.make_person("Al", "Grand", Person.MALE), trans)
        self.assertEqual(self.db.get_number_of_people(), 1)
        self.assertEqual(self.captured_errors, [])

    def test_validation_error_rolls_back_and_shows_message(self) -> None:
        """ValidationError(title, body) aborts the txn and opens the dialog."""
        with addon.refusable_txn(DbTxn("refused", self.db)) as trans:
            self.db.add_person(self.stub.make_person("Al", "Grand", Person.MALE), trans)
            raise ValidationError("A title", "A message")
        self.assertEqual(self.db.get_number_of_people(), 0)
        self.assertEqual(self.captured_errors, [("A title", "A message")])

    def test_other_errors_propagate(self) -> None:
        """Only ValidationError is turned into a dialog."""
        with self.assertRaises(RuntimeError):
            with addon.refusable_txn(DbTxn("boom", self.db)):
                raise RuntimeError("boom")
        self.assertEqual(self.captured_errors, [])


# ------------------------------------------------------------
#
# TestAddPeople
#
# ------------------------------------------------------------
class TestAddPeople(_DbTestCase):
    """Adding people and events through the Add button's callback."""

    def test_new_person_with_four_events(self) -> None:
        """Birth and Death become the birth/death references."""
        self.fill(
            "Doe, Jane",
            DataEntryGramplet.NO_REL,
            Person.FEMALE,
            ("1875", "1900 in Texas", "1940", "1941"),
        )
        self.stub.cb_add_data_entry(None)
        person = self.person_named("Jane")
        self.assertEqual(
            self.event_types(person),
            [EventType.BIRTH, EventType.RESIDENCE, EventType.DEATH, EventType.BURIAL],
        )
        self.assertEqual(
            int(self.db.get_event_from_handle(person.get_birth_ref().ref).get_type()),
            EventType.BIRTH,
        )
        self.assertEqual(
            int(self.db.get_event_from_handle(person.get_death_ref().ref).get_type()),
            EventType.DEATH,
        )
        self.assertEqual(self.db.get_number_of_places(), 1)

    def test_empty_event_rows_create_nothing(self) -> None:
        """A row without text makes no event."""
        self.fill(
            "Doe, Jane", DataEntryGramplet.NO_REL, Person.FEMALE, ("", "", "", "")
        )
        self.stub.cb_add_data_entry(None)
        self.assertEqual(self.event_types(self.person_named("Jane")), [])

    def test_only_the_first_birth_row_is_the_birth_reference(self) -> None:
        """Two rows set to Birth: the second is a plain event."""
        self.stub.select_event_type("NPEvent2", EventType.BIRTH)
        self.fill("Doe, Twin", DataEntryGramplet.NO_REL, Person.MALE, ("1880", "1881"))
        self.stub.cb_add_data_entry(None)
        person = self.person_named("Twin")
        birth = self.db.get_event_from_handle(person.get_birth_ref().ref)
        self.assertEqual(str(birth.get_date_object()), "1880-00-00")
        self.assertEqual(len(person.get_event_ref_list()), 2)

    def test_event_type_follows_the_menu(self) -> None:
        """Changing a menu changes the type of the event that is created."""
        self.stub.select_event_type("NPEvent1", EventType.BAPTISM)
        self.fill("Doe, Jane", DataEntryGramplet.NO_REL, Person.FEMALE, ("1876",))
        self.stub.cb_add_data_entry(None)
        person = self.person_named("Jane")
        self.assertEqual(self.event_types(person), [EventType.BAPTISM])
        self.assertIsNone(person.get_birth_ref())

    def test_add_child_creates_the_family(self) -> None:
        """A child of a person with no family gets a new family."""
        self.active = self.add_person("Al", "Grand", Person.MALE)
        self.fill("Grand, Bob", DataEntryGramplet.AS_CHILD, Person.MALE)
        self.stub.cb_add_data_entry(None)
        bob = self.person_named("Bob")
        family = self.db.get_family_from_handle(bob.get_parent_family_handle_list()[0])
        self.assertEqual(family.get_father_handle(), self.active.get_handle())
        self.assertEqual(self.db.get_number_of_families(), 1)

    def test_source_text_creates_a_citation(self) -> None:
        """Enter Sources selected: the title in a Source field is cited."""
        self.fill("Doe, Jane", DataEntryGramplet.NO_REL, Person.FEMALE, ("1876",))
        self.stub.de_widgets["NPEvent1Source"].set_text("Family Bible")
        self.stub.cb_add_data_entry(None)
        event = self.db.get_event_from_handle(
            self.person_named("Jane").get_event_ref_list()[0].ref
        )
        citation = self.db.get_citation_from_handle(event.get_citation_list()[0])
        source = self.db.get_source_from_handle(citation.get_reference_handle())
        self.assertEqual(source.get_title(), "Family Bible")

    def test_none_selected_creates_no_citation(self) -> None:
        """None selected: a filled Source field is ignored, nothing is cited."""
        self.stub.de_widgets["Active person:Show none"].set_active(True)
        self.fill("Doe, Jane", DataEntryGramplet.NO_REL, Person.FEMALE, ("1876",))
        self.stub.de_widgets["NPEvent1Source"].set_text("Family Bible")
        self.stub.cb_add_data_entry(None)
        event = self.db.get_event_from_handle(
            self.person_named("Jane").get_event_ref_list()[0].ref
        )
        self.assertEqual(event.get_citation_list(), [])
        self.assertEqual(self.db.get_number_of_sources(), 0)

    def test_chosen_citation_is_attached_where_use_citation_is_checked(self) -> None:
        """Citation mode attaches the citation only where its box is checked."""
        citation = self.add_citation("p. 42")
        with mock.patch.object(_FakeSelector, "result", citation):
            with mock.patch.object(
                addon.gramps_selectors, "SelectorFactory", lambda _name: _FakeSelector
            ):
                self.stub.de_widgets["Active person:Show citation"].set_active(True)
        self.stub.de_widgets["NPSource:Citation"].set_active(True)
        self.stub.de_widgets["NPEvent1Source:Citation"].set_active(True)
        self.fill(
            "Doe, Jane",
            DataEntryGramplet.NO_REL,
            Person.FEMALE,
            ("1875", "1900", "1940", "1941"),
        )
        self.stub.cb_add_data_entry(None)
        person = self.person_named("Jane")
        self.assertEqual(person.get_citation_list(), [citation.get_handle()])
        refs = person.get_event_ref_list()
        birth_event = self.db.get_event_from_handle(refs[0].ref)
        self.assertEqual(birth_event.get_citation_list(), [citation.get_handle()])
        for ref in refs[1:]:
            event = self.db.get_event_from_handle(ref.ref)
            self.assertEqual(event.get_citation_list(), [])

    def test_citation_mode_without_use_citation_attaches_nothing(self) -> None:
        """A chosen citation with every "Use citation" box left unchecked."""
        citation = self.add_citation("p. 42")
        with mock.patch.object(_FakeSelector, "result", citation):
            with mock.patch.object(
                addon.gramps_selectors, "SelectorFactory", lambda _name: _FakeSelector
            ):
                self.stub.de_widgets["Active person:Show citation"].set_active(True)
        self.fill(
            "Doe, Jane",
            DataEntryGramplet.NO_REL,
            Person.FEMALE,
            ("1875", "1900", "1940", "1941"),
        )
        self.stub.cb_add_data_entry(None)
        person = self.person_named("Jane")
        self.assertEqual(person.get_citation_list(), [])
        for ref in person.get_event_ref_list():
            event = self.db.get_event_from_handle(ref.ref)
            self.assertEqual(event.get_citation_list(), [])

    def test_use_citation_checkboxes_reset_on_clear(self) -> None:
        """Clear resets checked "Use citation" boxes (a one-shot flag)."""
        widgets = self.stub.de_widgets
        widgets["NPSource:Citation"].set_active(True)
        widgets["NPEvent1Source:Citation"].set_active(True)
        self.stub.cb_clear_data_entry(None)
        self.assertFalse(widgets["NPSource:Citation"].get_active())
        self.assertFalse(widgets["NPEvent1Source:Citation"].get_active())


# ------------------------------------------------------------
#
# TestRefusedAdds
#
# ------------------------------------------------------------
class TestRefusedAdds(_DbTestCase):
    """Checks that fail after the new person was added must roll back."""

    before: tuple[int, ...] = ()

    def _assert_refused_without_trace(self, title: str) -> None:
        """Nothing was saved and the right dialog was shown once."""
        self.assertEqual(self.counts(), self.before)
        self.assertEqual([t for t, _b in self.captured_errors], [title])

    def test_child_of_a_parent_with_unknown_gender(self) -> None:
        """The child, its event, place and source are not left behind."""
        self.active = self.add_person("Al", "Grand", Person.UNKNOWN)
        self.before = self.counts()
        self.fill(
            "Grand, Bob", DataEntryGramplet.AS_CHILD, Person.MALE, ("1900 in Ohio",)
        )
        self.stub.de_widgets["NPEvent1Source"].set_text("Bible")
        self.stub.cb_add_data_entry(None)
        self._assert_refused_without_trace("Please set gender on Active person.")

    def test_retry_after_fixing_the_gender_adds_it_once(self) -> None:
        """No duplicate person appears when the user corrects and retries."""
        self.active = self.add_person("Al", "Grand", Person.UNKNOWN)
        self.fill("Grand, Bob", DataEntryGramplet.AS_CHILD, Person.MALE)
        self.stub.cb_add_data_entry(None)
        self.active.set_gender(Person.MALE)
        with DbTxn("fix", self.db) as trans:
            self.db.commit_person(self.active, trans)
        self.stub.cb_add_data_entry(None)
        self.assertEqual(self.db.get_number_of_people(), 2)
        self.assertEqual(self.db.get_number_of_families(), 1)

    def test_spouse_with_the_same_gender(self) -> None:
        """Same-gender partners are refused and nothing is saved."""
        self.active = self.add_person("Al", "Grand", Person.MALE)
        self.before = self.counts()
        self.fill("Grand, Ben", DataEntryGramplet.AS_SPOUSE, Person.MALE)
        self.stub.cb_add_data_entry(None)
        self._assert_refused_without_trace("Same genders on Active and new person.")


# ------------------------------------------------------------
#
# TestCitationRadio
#
# ------------------------------------------------------------
class TestCitationRadio(_DbTestCase):
    """Selecting Select Citation opens the selector; the choice is shown and used."""

    def setUp(self) -> None:
        """Route the selector to a fake and remember what it opens."""
        super().setUp()
        _FakeSelector.opened = 0
        _FakeSelector.result = None
        patcher = mock.patch.object(
            addon.gramps_selectors, "SelectorFactory", lambda _name: _FakeSelector
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        widgets = self.stub.de_widgets
        self.sources = widgets["Active person:Show sources"]
        self.citation = widgets["Active person:Show citation"]
        self.none = widgets["Active person:Show none"]

    def test_cancel_reverts_to_sources_silently(self) -> None:
        """No choice: selection reverts to Enter Sources, no dialog appears."""
        _FakeSelector.result = None
        self.citation.set_active(True)
        self.assertFalse(self.citation.get_active())
        self.assertTrue(self.sources.get_active())
        self.assertEqual(self.captured_errors, [])
        self.assertEqual(_FakeSelector.opened, 1)

    def test_source_row_is_not_a_citation(self) -> None:
        """Picking a Source row counts as no valid choice."""
        source = Source()
        source.set_title("A source")
        _FakeSelector.result = source
        self.citation.set_active(True)
        self.assertFalse(self.citation.get_active())
        self.assertEqual(self.captured_errors, [])

    def test_closed_tree_reverts_to_sources(self) -> None:
        """Without an open tree there is nothing to choose from."""
        self.stub.dbstate = _FakeDbState(False, self.db)
        self.citation.set_active(True)
        self.assertFalse(self.citation.get_active())
        self.assertEqual(_FakeSelector.opened, 0)

    def test_valid_choice_is_shown_and_excludes_sources(self) -> None:
        """The description shows Date; Volume/Page; Source title."""
        citation = self.add_citation("Vol 3, p. 42", Date(1900, 6, 1), "1900 Census")
        _FakeSelector.result = citation
        self.citation.set_active(True)
        self.assertTrue(self.citation.get_active())
        self.assertFalse(self.sources.get_active())
        self.assertEqual(
            self.stub.de_widgets["Citation:Info"].get_text(),
            "1900-06-01; Vol 3, p. 42; 1900 Census",
        )

    def test_empty_parts_are_left_out(self) -> None:
        """A citation without a date shows only page and title."""
        _FakeSelector.result = self.add_citation("p. 7", None, "Register")
        self.citation.set_active(True)
        self.assertEqual(self.stub.describe_citation(), "p. 7; Register")

    def test_selecting_sources_forgets_the_citation(self) -> None:
        """Selecting Enter Sources: the citation and its description are cleared."""
        _FakeSelector.result = self.add_citation("p. 1")
        self.citation.set_active(True)
        self.sources.set_active(True)
        self.assertIsNone(self.stub._citation_handle)
        self.assertEqual(self.stub.de_widgets["Citation:Info"].get_text(), "")

    def test_selecting_sources_deselects_citation(self) -> None:
        """Enter Sources and Select Citation exclude each other in both directions."""
        _FakeSelector.result = self.add_citation("p. 1")
        self.citation.set_active(True)
        self.sources.set_active(True)
        self.assertFalse(self.citation.get_active())
        self.assertIsNone(self.stub._citation_handle)

    def test_none_deselects_sources_and_citation(self) -> None:
        """Selecting None deselects whichever of the other two was active."""
        self.none.set_active(True)
        self.assertFalse(self.sources.get_active())
        self.assertFalse(self.citation.get_active())

    def test_none_forgets_a_chosen_citation(self) -> None:
        """Selecting None deselects Select Citation and forgets its choice."""
        _FakeSelector.result = self.add_citation("p. 1")
        self.citation.set_active(True)
        self.none.set_active(True)
        self.assertFalse(self.citation.get_active())
        self.assertIsNone(self.stub._citation_handle)
        self.assertEqual(self.stub.de_widgets["Citation:Info"].get_text(), "")

    def test_selecting_sources_deselects_none(self) -> None:
        """Enter Sources and None exclude each other too."""
        self.none.set_active(True)
        self.sources.set_active(True)
        self.assertFalse(self.none.get_active())
        self.assertTrue(self.sources.get_active())

    def test_deleted_citation_reverts_to_sources(self) -> None:
        """If the chosen citation is deleted elsewhere, selection reverts."""
        citation = self.add_citation("p. 1")
        _FakeSelector.result = citation
        self.citation.set_active(True)
        self.stub.cb_citation_deleted([citation.get_handle()])
        self.assertFalse(self.citation.get_active())
        self.assertTrue(self.sources.get_active())

    def test_copy_puts_the_citation_date_in_the_residence_row(self) -> None:
        """Copy Active Data flows the citation date into Residence."""
        widgets = self.stub.de_widgets
        widgets["APBirth"].set_text("1850 in Ohio")
        widgets["APDeath"].set_text("1910")
        _FakeSelector.result = self.add_citation("p. 1", Date(1900, 6, 1))
        self.citation.set_active(True)
        self.stub.cb_copy_data_entry(None)
        self.assertEqual(widgets["NPEvent1"].get_text(), "1850 in Ohio")
        self.assertEqual(widgets["NPEvent2"].get_text(), "1900-06-01")
        self.assertEqual(widgets["NPEvent3"].get_text(), "1910")

    def test_copy_keeps_residence_when_the_citation_has_no_date(self) -> None:
        """No citation date: the Residence row is left as it is."""
        widgets = self.stub.de_widgets
        widgets["NPEvent2"].set_text("keep me")
        _FakeSelector.result = self.add_citation("p. 1")
        self.citation.set_active(True)
        self.stub.cb_copy_data_entry(None)
        self.assertEqual(widgets["NPEvent2"].get_text(), "keep me")

    def test_copy_without_a_residence_row_skips_the_date(self) -> None:
        """No row is set to Residence: nothing else is overwritten."""
        widgets = self.stub.de_widgets
        self.stub.select_event_type("NPEvent2", EventType.CENSUS)
        _FakeSelector.result = self.add_citation("p. 1", Date(1900, 6, 1))
        self.citation.set_active(True)
        self.stub.cb_copy_data_entry(None)
        self.assertEqual(widgets["NPEvent2"].get_text(), "")

    def test_copy_without_a_citation_copies_only_the_active_person(self) -> None:
        """Select Citation not selected: Residence stays empty."""
        widgets = self.stub.de_widgets
        widgets["APBirth"].set_text("1850")
        self.stub.cb_copy_data_entry(None)
        self.assertEqual(widgets["NPEvent1"].get_text(), "1850")
        self.assertEqual(widgets["NPEvent2"].get_text(), "")


# ------------------------------------------------------------
#
# TestDirtyFlag
#
# ------------------------------------------------------------
class TestDirtyFlag(unittest.TestCase):
    """The dirty flag remembers which fields were edited."""

    def test_fields_are_recorded_and_cleared(self) -> None:
        """cb_mark_dirty records the field; clearing the flag forgets them."""
        stub = _make_gramplet()
        entry = _FakeEntry()
        stub.de_widgets["APBirth"] = entry
        stub.cb_mark_dirty(entry)
        self.assertTrue(stub._dirty)
        self.assertEqual(stub._dirty_fields, ["APBirth"])
        stub._dirty = False
        self.assertEqual(stub._dirty_fields, [])

    def test_abandon_clears_the_flag(self) -> None:
        """Abandon reloads and clears the flag."""
        stub = _make_gramplet(dirty=True)
        updates: list[int] = []
        stub.update = lambda: updates.append(1)
        stub.cb_abandon_data_edit(None)
        self.assertFalse(stub._dirty)
        self.assertEqual(updates, [1])


if __name__ == "__main__":
    unittest.main()
