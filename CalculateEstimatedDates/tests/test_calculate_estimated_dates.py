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
Tests for the Calculate Estimated Dates tool — lock in the error
handling added in response to ``gramps-project/bugs#7898`` (ancestry
loops surfaced as ``DatabaseError`` from ``probably_alive_range`` were
tearing down the whole tool).

The tool's ``__init__`` pulls in the full Gramps GUI stack, so these
tests build stub instances via ``__new__`` and exercise the isolated
helpers plus the ``.gpr.py`` registration.
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
# addons-source/ goes on sys.path so ``from CalculateEstimatedDates import
# CalculateEstimatedDates`` resolves package→submodule. With the addon
# directory itself on sys.path instead, ``CalculateEstimatedDates`` binds
# to ``CalculateEstimatedDates.py`` directly, and the submodule lookup
# fails. ADDON_DIR is retained for the ``.gpr.py`` path in the registration
# test.
ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDONS_SOURCE_DIR = os.path.dirname(ADDON_DIR)
if ADDONS_SOURCE_DIR not in sys.path:
    sys.path.insert(0, ADDONS_SOURCE_DIR)

try:
    import gramps
except ImportError as err:
    raise unittest.SkipTest("gramps package not available: %s" % err)

if "GRAMPS_RESOURCES" not in os.environ:
    os.environ["GRAMPS_RESOURCES"] = os.path.dirname(
        os.path.dirname(gramps.__file__)
    )

from gramps.gen.errors import DatabaseError  # noqa: E402
from gramps.gen.lib import Date  # noqa: E402

# ------------------------
# Gramps specific
# ------------------------
# The addon module pulls in the full Gramps GUI stack at import time. On
# environments where GTK is missing or version-mismatched the import
# fails; skip the whole module cleanly in that case so collection does
# not surface spurious errors.
try:
    from CalculateEstimatedDates import CalculateEstimatedDates as ced_module
except Exception as err:  # noqa: BLE001 — environment guard
    raise unittest.SkipTest(
        "CalculateEstimatedDates module unavailable: %s" % err
    )


# ------------------------------------------------------------
#
# _FakeOptionsHandler
#
# ------------------------------------------------------------
class _FakeOptionsHandler:
    """Stub for ``CalcToolManagedWindow.options.handler`` — exposes only
    ``options_dict``, which is all the paths under test read."""

    def __init__(self, dates: int = 0) -> None:
        """
        :param dates: Value stored under ``options_dict["dates"]``.
        :type dates: int
        """
        self.options_dict: dict[str, int] = {"dates": dates}


# ------------------------------------------------------------
#
# _FakeOptions
#
# ------------------------------------------------------------
class _FakeOptions:
    """Stub for ``CalcToolManagedWindow.options`` with a ``handler`` attribute."""

    def __init__(self, dates: int = 0) -> None:
        """
        :param dates: Value propagated into the handler's ``options_dict``.
        :type dates: int
        """
        self.handler = _FakeOptionsHandler(dates=dates)


def _make_tool(dates: int = 0) -> Any:
    """
    Build a ``CalcToolManagedWindow`` via ``__new__`` so its ``__init__``
    (which pulls in GTK) does not run, then attach just enough state for
    the isolated helpers to execute.

    :param dates: Value stored on the fake options handler.
    :type dates: int
    :returns: A stub instance with the minimum attributes set.
    :rtype: CalcToolManagedWindow
    """
    cls = ced_module.CalcToolManagedWindow
    stub = cls.__new__(cls)
    stub.options = _FakeOptions(dates=dates)
    stub.db = object()
    stub.MAX_SIB_AGE_DIFF = 20
    stub.MAX_AGE_PROB_ALIVE = 110
    stub.AVG_GENERATION_GAP = 20
    return stub


# ------------------------------------------------------------
#
# TestGetModifier
#
# ------------------------------------------------------------
class TestGetModifier(unittest.TestCase):
    """Pure-logic coverage for ``get_modifier`` across its four branches."""

    def test_birth_about_when_dates_zero(self) -> None:
        """dates=0 + birth → MOD_ABOUT (the 'approximate' case)."""
        tool = _make_tool(dates=0)
        self.assertEqual(tool.get_modifier("birth"), Date.MOD_ABOUT)

    def test_birth_after_when_dates_nonzero(self) -> None:
        """dates=1 + birth → MOD_AFTER (the 'extremes' case)."""
        tool = _make_tool(dates=1)
        self.assertEqual(tool.get_modifier("birth"), Date.MOD_AFTER)

    def test_death_about_when_dates_zero(self) -> None:
        """dates=0 + death → MOD_ABOUT."""
        tool = _make_tool(dates=0)
        self.assertEqual(tool.get_modifier("death"), Date.MOD_ABOUT)

    def test_death_before_when_dates_nonzero(self) -> None:
        """dates=1 + death → MOD_BEFORE (upper-bound estimate)."""
        tool = _make_tool(dates=1)
        self.assertEqual(tool.get_modifier("death"), Date.MOD_BEFORE)


# ------------------------------------------------------------
#
# TestCalcEstimates
#
# ------------------------------------------------------------
class TestCalcEstimates(unittest.TestCase):
    """Regression coverage for bug 7898 — ``calc_estimates`` must let
    ``DatabaseError`` from ``probably_alive_range`` escape so the
    per-person handler in ``run()`` can log and skip instead of tearing
    down the whole tool."""

    def test_returns_probably_alive_range_result(self) -> None:
        """Happy path — the helper is a pass-through to ``probably_alive_range``."""
        tool = _make_tool()
        person = object()
        expected = (Date(), Date(), "explain", None)
        calls: list[tuple] = []

        def _fake(person_arg: Any, db_arg: Any, max_sib: int, max_age: int, avg_gap: int) -> tuple:
            calls.append((person_arg, db_arg, max_sib, max_age, avg_gap))
            return expected

        with mock.patch.object(ced_module, "probably_alive_range", _fake):
            result = tool.calc_estimates(person)

        self.assertEqual(result, expected)
        self.assertEqual(calls, [(person, tool.db, 20, 110, 20)])

    def test_propagates_database_error(self) -> None:
        """
        When ``probably_alive_range`` raises ``DatabaseError`` (e.g. an
        ancestry loop), ``calc_estimates`` must let it escape so the
        per-person handler in ``run()`` can log and skip.
        """
        tool = _make_tool()

        def _boom(*_args: Any, **_kwargs: Any) -> Any:
            raise DatabaseError("loop in Test, Abel's descendants")

        with mock.patch.object(ced_module, "probably_alive_range", _boom):
            with self.assertRaisesRegex(DatabaseError, "loop"):
                tool.calc_estimates(object())


# ------------------------------------------------------------
#
# TestGprRegistration
#
# ------------------------------------------------------------
class TestGprRegistration(unittest.TestCase):
    """Catch metadata breakage in the plugin registration file early."""

    def test_gpr_registration_metadata(self) -> None:
        """The .gpr.py file must register a single TOOL with expected keys."""
        gpr_path = os.path.join(ADDON_DIR, "CalculateEstimatedDates.gpr.py")
        calls: list[tuple[tuple, dict]] = []

        namespace: dict[str, Any] = {
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

        self.assertEqual(len(calls), 1, "expected exactly one register() call")
        args, kwargs = calls[0]
        self.assertEqual(args, ("TOOL",))
        self.assertEqual(kwargs["id"], "calculateestimateddates")
        self.assertEqual(kwargs["fname"], "CalculateEstimatedDates.py")
        self.assertEqual(kwargs["gramps_target_version"], "6.1")
        self.assertEqual(kwargs["status"], "STABLE")
        self.assertEqual(kwargs["toolclass"], "CalcToolManagedWindow")
        self.assertEqual(kwargs["optionclass"], "CalcEstDateOptions")
        self.assertEqual(kwargs["category"], "TOOL_DBPROC")
        self.assertEqual(kwargs["tool_modes"], ["TOOL_MODE_GUI"])


if __name__ == "__main__":
    unittest.main()
