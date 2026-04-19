#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Eduard Ralph
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
Tests for the Data Entry Gramplet — covers
``gramps-project/gramps#12691`` (``AttributeError: 'DummyDb' object
has no attribute 'get_undodb'`` when the user presses *Add* or *Save*
without a Family Tree loaded).

The Gramplet subclass requires a live Gramps GUI to instantiate, so
these tests build a minimal stub via ``__new__`` and invoke the
mutating callbacks directly. That keeps the tests fast and avoids
spinning up GTK, while still exercising the real guard code paths.
"""

# ------------------------
# Python modules
# ------------------------
import os
import sys
import unittest
from typing import Any
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
# Addon root goes on sys.path so ``from DataEntryGramplet import
# DataEntryGramplet`` resolves the module-level class. The unittest
# discovery entrypoint (tests/) lacks an __init__.py, so this
# ``__file__``-based hack is still the right way to make the addon
# importable during local and CI runs.
ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    import gramps
except ImportError as err:
    raise unittest.SkipTest("gramps package not available: %s" % err)

if "GRAMPS_RESOURCES" not in os.environ:
    os.environ["GRAMPS_RESOURCES"] = os.path.dirname(
        os.path.dirname(gramps.__file__)
    )

# ------------------------
# Gramps specific
# ------------------------
# The addon module pulls in the full Gramps GUI stack at import time. On
# environments where GTK is missing or version-mismatched the import
# fails; skip the whole module cleanly in that case so collection does
# not surface spurious errors.
try:
    import gramps.gui.dialog as gramps_dialog  # noqa: E402
    from DataEntryGramplet import DataEntryGramplet  # noqa: E402
except Exception as err:  # noqa: BLE001 — environment guard
    raise unittest.SkipTest("DataEntryGramplet module unavailable: %s" % err)


# ------------------------------------------------------------
#
# _FakeDbState
#
# ------------------------------------------------------------
class _FakeDbState:
    """Stub for ``Gramplet.dbstate`` — only ``is_open()`` is consulted
    by the guards under test."""

    def __init__(self, is_open: bool = True) -> None:
        """
        :param is_open: Value returned from ``is_open()``.
        :type is_open: bool
        """
        self._is_open = is_open

    def is_open(self) -> bool:
        """Return the configured open state."""
        return self._is_open


# ------------------------------------------------------------
#
# _FakeEntry
#
# ------------------------------------------------------------
class _FakeEntry:
    """Stub for ``Gtk.Entry`` — exposes only ``get_text()``."""

    def __init__(self, text: str = "") -> None:
        """
        :param text: Value returned from ``get_text()``.
        :type text: str
        """
        self._text = text

    def get_text(self) -> str:
        """Return the configured text."""
        return self._text


# ------------------------------------------------------------
#
# _FakeCombo
#
# ------------------------------------------------------------
class _FakeCombo:
    """Stub for ``Gtk.ComboBox`` — exposes only ``get_active()``."""

    def __init__(self, active: int = 0) -> None:
        """
        :param active: Value returned from ``get_active()``.
        :type active: int
        """
        self._active = active

    def get_active(self) -> int:
        """Return the configured active index."""
        return self._active


def _make_gramplet(
    *,
    db_open: bool = True,
    np_name: str = "",
    np_gender: int = 2,  # UNKNOWN
    np_relation: int = DataEntryGramplet.NO_REL,
    dirty: bool = False,
) -> Any:
    """
    Build a ``DataEntryGramplet`` via ``__new__`` so its ``__init__``
    (which pulls in GTK) does not run, then attach just enough state
    for the isolated guards to execute.

    :param db_open: Whether ``dbstate.is_open()`` reports an open tree.
    :type db_open: bool
    :param np_name: Value stored in the Name entry.
    :type np_name: str
    :param np_gender: Value stored in the Gender combo (UNKNOWN by default).
    :type np_gender: int
    :param np_relation: Value stored in the Relation combo.
    :type np_relation: int
    :param dirty: Value of the private ``_dirty`` flag.
    :type dirty: bool
    :returns: A stub instance with the minimum attributes set.
    :rtype: DataEntryGramplet
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
    # save_data_edit falls through to self.update() even on the guarded path.
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

        stub.add_data_entry(None)

        self.assertTrue(self.captured_errors, "ErrorDialog was not displayed")
        title, body = self.captured_errors[0]
        self.assertIn("Family Tree", title)
        self.assertIn("open", body.lower())

    def test_save_data_edit_with_closed_db_shows_error(self) -> None:
        """*Save* while dirty with no tree open must not invoke DbTxn."""
        stub = _make_gramplet(db_open=False, dirty=True)

        stub.save_data_edit(None)

        self.assertTrue(self.captured_errors, "ErrorDialog was not displayed")
        title, _body = self.captured_errors[0]
        self.assertIn("Family Tree", title)

    def test_save_data_edit_noop_when_not_dirty(self) -> None:
        """A *Save* click with nothing pending should be a silent no-op."""
        stub = _make_gramplet(db_open=True, dirty=False)

        stub.save_data_edit(None)

        self.assertEqual(self.captured_errors, [])
        self.assertFalse(stub._dirty)


# ------------------------------------------------------------
#
# TestInputGuards
#
# ------------------------------------------------------------
class TestInputGuards(_ErrorDialogTestCase):
    """Lock in the pre-existing input validators so future refactors
    cannot silently weaken the guardrails around ``add_data_entry``."""

    def test_add_data_entry_requires_name(self) -> None:
        """Empty name with a valid tree should surface the name-required error."""
        stub = _make_gramplet(db_open=True, np_name="")

        stub.add_data_entry(None)

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

        stub.add_data_entry(None)

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
        self.assertEqual(kwargs["gramps_target_version"], "6.0")
        self.assertEqual(kwargs["status"], "STABLE")
        # Navigation type must stay Person — the active object is fetched that way.
        self.assertEqual(kwargs["navtypes"], ["Person"])


if __name__ == "__main__":
    unittest.main()
