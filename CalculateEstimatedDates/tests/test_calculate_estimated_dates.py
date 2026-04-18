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
Tests for the Calculate Estimated Dates tool — locks in the error
handling added in response to ``gramps-project/bugs#7898`` (ancestry
loops surfaced as ``DatabaseError`` from ``probably_alive_range``
were tearing down the whole tool).

The tool's ``__init__`` pulls in the full Gramps GUI stack, so these
tests build stub instances via ``__new__`` and exercise the isolated
helpers plus the ``.gpr.py`` registration.
"""

# ------------------------
# Python modules
# ------------------------
import os
import sys

import pytest

# Gramps is imported transitively by the module under test.
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
# Gramps modules
# ------------------------
from gramps.gen.errors import DatabaseError  # noqa: E402
from gramps.gen.lib import Date  # noqa: E402


# ---------------------------------------------------------------------------
# Lazy module loader — the addon pulls in the full Gramps GUI stack at
# import time, so on environments where GTK is missing or version-mismatched
# the import fails. Importing inside a fixture lets pytest collection succeed
# (and skip cleanly per-test) instead of hanging the entire collection phase.
# ---------------------------------------------------------------------------
@pytest.fixture
def ced_module():
    try:
        from CalculateEstimatedDates import CalculateEstimatedDates as mod
    except Exception as err:  # pragma: no cover - environment guard
        pytest.skip(f"CalculateEstimatedDates module unavailable: {err}")
    return mod


# ---------------------------------------------------------------------------
# Lightweight stubs — enough surface for the helper paths under test
# ---------------------------------------------------------------------------
class _FakeOptionsHandler:
    def __init__(self, dates=0):
        self.options_dict = {"dates": dates}


class _FakeOptions:
    def __init__(self, dates=0):
        self.handler = _FakeOptionsHandler(dates=dates)


def _make_tool(ced_module, *, dates=0):
    """Return a CalcToolManagedWindow skipping ``__init__`` (no GTK required)."""
    cls = ced_module.CalcToolManagedWindow
    stub = cls.__new__(cls)
    stub.options = _FakeOptions(dates=dates)
    stub.db = object()
    stub.MAX_SIB_AGE_DIFF = 20
    stub.MAX_AGE_PROB_ALIVE = 110
    stub.AVG_GENERATION_GAP = 20
    return stub


# ---------------------------------------------------------------------------
# get_modifier — pure logic, four branches
# ---------------------------------------------------------------------------
def test_get_modifier_birth_about_when_dates_zero(ced_module):
    """dates=0 + birth → MOD_ABOUT (the 'approximate' case)."""
    tool = _make_tool(ced_module, dates=0)
    assert tool.get_modifier("birth") == Date.MOD_ABOUT


def test_get_modifier_birth_after_when_dates_nonzero(ced_module):
    """dates=1 + birth → MOD_AFTER (the 'extremes' case)."""
    tool = _make_tool(ced_module, dates=1)
    assert tool.get_modifier("birth") == Date.MOD_AFTER


def test_get_modifier_death_about_when_dates_zero(ced_module):
    """dates=0 + death → MOD_ABOUT."""
    tool = _make_tool(ced_module, dates=0)
    assert tool.get_modifier("death") == Date.MOD_ABOUT


def test_get_modifier_death_before_when_dates_nonzero(ced_module):
    """dates=1 + death → MOD_BEFORE (upper-bound estimate)."""
    tool = _make_tool(ced_module, dates=1)
    assert tool.get_modifier("death") == Date.MOD_BEFORE


# ---------------------------------------------------------------------------
# calc_estimates — bug 7898: DatabaseError must propagate so run() can catch
# it per-person instead of letting one loop kill the whole tool.
# ---------------------------------------------------------------------------
def test_calc_estimates_returns_probably_alive_range_result(
    ced_module, monkeypatch
):
    """Happy path — the helper is a pass-through to probably_alive_range."""
    tool = _make_tool(ced_module)
    person = object()
    expected = (Date(), Date(), "explain", None)

    calls = []

    def _fake(person_arg, db_arg, max_sib, max_age, avg_gap):
        calls.append((person_arg, db_arg, max_sib, max_age, avg_gap))
        return expected

    monkeypatch.setattr(ced_module, "probably_alive_range", _fake)

    result = tool.calc_estimates(person)

    assert result == expected
    assert calls == [(person, tool.db, 20, 110, 20)]


def test_calc_estimates_propagates_database_error(ced_module, monkeypatch):
    """
    When ``probably_alive_range`` raises ``DatabaseError`` (e.g. an
    ancestry loop), ``calc_estimates`` must let it escape so the
    per-person handler in ``run()`` can log and skip.
    """
    tool = _make_tool(ced_module)

    def _boom(*_args, **_kwargs):
        raise DatabaseError("loop in Test, Abel's descendants")

    monkeypatch.setattr(ced_module, "probably_alive_range", _boom)

    with pytest.raises(DatabaseError, match="loop"):
        tool.calc_estimates(object())


# ---------------------------------------------------------------------------
# Plugin registration — catch metadata breakage early
# ---------------------------------------------------------------------------
def test_gpr_registration_metadata():
    """The .gpr.py file must register a single TOOL with expected keys."""
    gpr_path = os.path.join(ADDON_DIR, "CalculateEstimatedDates.gpr.py")
    calls: list[tuple[tuple, dict]] = []

    namespace = {
        "register": lambda *args, **kwargs: calls.append((args, kwargs)),
        "TOOL": "TOOL",
        "STABLE": "STABLE",
        "UNSTABLE": "UNSTABLE",
        "TOOL_DBPROC": "TOOL_DBPROC",
        "TOOL_MODE_GUI": "TOOL_MODE_GUI",
        "_": lambda s: s,
    }
    with open(gpr_path, encoding="utf-8") as handle:
        exec(compile(handle.read(), gpr_path, "exec"), namespace)

    assert len(calls) == 1, "expected exactly one register() call"
    args, kwargs = calls[0]
    assert args == ("TOOL",)
    assert kwargs["id"] == "calculateestimateddates"
    assert kwargs["fname"] == "CalculateEstimatedDates.py"
    assert kwargs["gramps_target_version"] == "6.0"
    assert kwargs["status"] == "STABLE"
    assert kwargs["toolclass"] == "CalcToolManagedWindow"
    assert kwargs["optionclass"] == "CalcEstDateOptions"
    assert kwargs["category"] == "TOOL_DBPROC"
    assert kwargs["tool_modes"] == ["TOOL_MODE_GUI"]
