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

import pytest

# Gramps is imported by the module under test.
pytest.importorskip("gramps")


# ---------------------------------------------------------------------------
# Make the addon importable and ensure GRAMPS_RESOURCES is set
# ---------------------------------------------------------------------------
ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

if "GRAMPS_RESOURCES" not in os.environ:
    import gramps

    os.environ["GRAMPS_RESOURCES"] = os.path.dirname(
        os.path.dirname(gramps.__file__)
    )


# ------------------------
# Module under test
# ------------------------
import gramps.gui.dialog as gramps_dialog  # noqa: E402

from DataEntryGramplet import DataEntryGramplet  # noqa: E402


# ---------------------------------------------------------------------------
# Lightweight stubs — enough surface for the guard paths under test
# ---------------------------------------------------------------------------
class _FakeDbState:
    def __init__(self, is_open=True):
        self._is_open = is_open

    def is_open(self):
        return self._is_open


class _FakeEntry:
    def __init__(self, text=""):
        self._text = text

    def get_text(self):
        return self._text


class _FakeCombo:
    def __init__(self, active=0):
        self._active = active

    def get_active(self):
        return self._active


def _make_gramplet(
    *,
    db_open=True,
    np_name="",
    np_gender=2,  # UNKNOWN
    np_relation=DataEntryGramplet.NO_REL,
    dirty=False,
):
    """Return an instance skipping ``__init__`` so no GTK is required."""
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


@pytest.fixture
def captured_errors(monkeypatch):
    """Replace gramps.gui.dialog.ErrorDialog so tests can inspect calls."""
    shown: list[tuple[str, str]] = []

    def _fake(title, body="", *args, **kwargs):
        shown.append((str(title), str(body)))

    monkeypatch.setattr(gramps_dialog, "ErrorDialog", _fake)
    return shown


# ---------------------------------------------------------------------------
# Bug 12691 — closed Family Tree must not crash
# ---------------------------------------------------------------------------
def test_add_data_entry_with_closed_db_shows_error(captured_errors):
    """Pressing *Add* with no tree open surfaces an ErrorDialog, not a crash."""
    stub = _make_gramplet(db_open=False, np_name="Doe, Jane")

    stub.add_data_entry(None)

    assert captured_errors, "ErrorDialog was not displayed"
    title, body = captured_errors[0]
    assert "Family Tree" in title
    assert "open" in body.lower()


def test_save_data_edit_with_closed_db_shows_error(captured_errors):
    """Pressing *Save* while dirty with no tree open must not invoke DbTxn."""
    stub = _make_gramplet(db_open=False, dirty=True)

    stub.save_data_edit(None)

    assert captured_errors, "ErrorDialog was not displayed"
    title, _body = captured_errors[0]
    assert "Family Tree" in title


def test_save_data_edit_noop_when_not_dirty(captured_errors):
    """A *Save* click with nothing pending should be a silent no-op."""
    stub = _make_gramplet(db_open=True, dirty=False)

    stub.save_data_edit(None)

    assert captured_errors == []
    assert stub._dirty is False


# ---------------------------------------------------------------------------
# Pre-existing guards — lock them in against regressions
# ---------------------------------------------------------------------------
def test_add_data_entry_requires_name(captured_errors):
    """Empty name with a valid tree should surface the name-required error."""
    stub = _make_gramplet(db_open=True, np_name="")

    stub.add_data_entry(None)

    assert captured_errors
    title, _body = captured_errors[0]
    assert "name" in title.lower()


def test_add_data_entry_parent_without_active_person(captured_errors):
    """Adding as a parent without an active person surfaces a clear error."""
    stub = _make_gramplet(
        db_open=True,
        np_name="Doe, Jane",
        np_relation=DataEntryGramplet.AS_PARENT,
    )

    stub.add_data_entry(None)

    assert captured_errors
    _title, body = captured_errors[0]
    assert "parent" in body.lower()


# ---------------------------------------------------------------------------
# Plugin registration — catch metadata breakage early
# ---------------------------------------------------------------------------
def test_gpr_registration_metadata():
    """The .gpr.py file must register a single gramplet with expected keys."""
    gpr_path = os.path.join(ADDON_DIR, "DataEntryGramplet.gpr.py")
    calls: list[tuple[tuple, dict]] = []

    namespace = {
        "register": lambda *args, **kwargs: calls.append((args, kwargs)),
        "GRAMPLET": "GRAMPLET",
        "STABLE": "STABLE",
        "EXPERT": "EXPERT",
        "_": lambda s: s,
    }
    with open(gpr_path, encoding="utf-8") as handle:
        exec(compile(handle.read(), gpr_path, "exec"), namespace)

    assert len(calls) == 1, "expected exactly one register() call"
    args, kwargs = calls[0]
    assert args == ("GRAMPLET",)
    assert kwargs["id"] == "Data Entry Gramplet"
    assert kwargs["gramplet"] == "DataEntryGramplet"
    assert kwargs["fname"] == "DataEntryGramplet.py"
    assert kwargs["gramps_target_version"] == "6.0"
    assert kwargs["status"] == "STABLE"
    # Navigation type must stay Person — the active object is fetched that way.
    assert kwargs["navtypes"] == ["Person"]
