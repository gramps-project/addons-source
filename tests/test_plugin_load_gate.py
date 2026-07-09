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
Regression test for the addon plugin-load *gating* decision (PR #820, R-C).

``TestPluginLoading.test_load_all_addon_modules`` once named ``hard_failures``
but only ``LOG.warning``-ed them, so a genuine non-dependency load failure
passed silently — its sole assertion was ``assertGreater(len(plugins), 0)``.
These cases drive that **production method itself**, with a synthetic addon
injected at its load seams, and assert that a non-dependency hard failure now
fails the test (``self.fail``) like the sibling smoke tests.

Why a dedicated module rather than a case inside
``tests/test_plugin_registration.py`` (the brief's named test file): the C4
runner executes the *whole* selected test module. Running
``test_plugin_registration`` there pulls in the real, registry-backed
``test_load_all_addon_modules``, which — now that it gates — fails on purely
environmental addon-load gaps in a minimal CI image (e.g. a missing GTK icon
theme: "Icon 'stock_link' not present"). That conflates this fix with the
image's addon completeness and is flaky run-to-run. Isolating the regression
here keeps the gate's verification deterministic while still exercising the
real production code path (the production change itself lives in
``tests/test_plugin_registration.py`` exactly as the brief directs).

Import-light: this module imports the production module (``gramps.gen``-level,
no ``gi``/``gramps.gui`` at load) but runs only the mocked path — no Gramps
plugin registry is booted.
"""

# ------------------------
# Python modules
# ------------------------
from types import SimpleNamespace
from unittest import mock
import os
import unittest

# ------------------------
# Gramps specific
# ------------------------
# NOTE: import the production module, *not* its TestCase classes by name. A bare
# ``from … import TestPluginLoading`` would bind that heavy, registry-backed class
# into this module's namespace, and ``python3 -m unittest tests.test_plugin_load_gate``
# would then collect and run its real ``test_load_all_addon_modules`` here (booting
# the full plugin load). Reaching the class through ``prod`` keeps only this file's
# own cases discoverable while still driving the real production method.
from tests import test_plugin_registration as prod


# ------------------------------------------------------------
#
# TestPluginLoadingGate
#
# ------------------------------------------------------------
class TestPluginLoadingGate(unittest.TestCase):
    """The load check must *gate* on non-dependency failures, not just log them.

    Each case constructs a real :class:`TestPluginLoading` instance and calls
    its production method ``test_load_all_addon_modules`` with one synthetic
    addon injected at the load seams (``_get_addon_plugins`` /
    ``_check_dependencies`` / ``subprocess.run`` in the production module's own
    namespace) — not a copy of the logic and not just the extracted helper — so
    the ``self.fail`` wiring is proven end-to-end on the real code path. Plain
    :class:`unittest.TestCase`: the registry is stubbed out, so nothing boots.
    """

    @staticmethod
    def _fake_plugin() -> SimpleNamespace:
        """A minimal :class:`PluginData` stand-in with no declared dependencies."""
        return SimpleNamespace(
            id="synthetic_broken_addon",
            fpath=os.path.join(prod.ADDONS_ROOT, "SyntheticBrokenAddon"),
            include_in_listing=True,
            requires_mod=[],
            requires_exe=[],
            requires_gi=[],
        )

    def _run_load_test_with(
        self,
        run_result: SimpleNamespace,
        missing_deps: list | None = None,
        strict: bool = False,
    ):
        """Drive ``test_load_all_addon_modules`` with one synthetic plugin.

        ``subprocess.run`` is stubbed to ``run_result`` to simulate a chosen load
        outcome; ``_check_dependencies`` returns ``missing_deps`` (empty by
        default, so the plugin is not skipped). ``GRAMPS_ADDON_TEST_STRICT`` is
        pinned — to ``"1"`` when ``strict`` else ``""`` — so the outcome never
        depends on the ambient environment. Returns the exception the production
        method raised, or ``None`` if it returned without raising.
        """
        loader = prod.TestPluginLoading("test_load_all_addon_modules")
        with mock.patch.object(
            prod, "_get_addon_plugins", return_value=[self._fake_plugin()]
        ), mock.patch.object(
            prod, "_check_dependencies", return_value=(missing_deps or [])
        ), mock.patch.object(
            prod.subprocess, "run", return_value=run_result
        ), mock.patch.dict(
            os.environ, {"GRAMPS_ADDON_TEST_STRICT": "1" if strict else ""}
        ), mock.patch.object(
            # Silence the production advisory logger: every warning here is about
            # the synthetic fixture, so it must not leak next to the real tree's
            # warnings in the test output.
            prod,
            "LOG",
        ):
            try:
                loader.test_load_all_addon_modules()
            except Exception as exc:  # noqa: BLE001 - asserted on by type below
                return exc
        return None

    def test_hard_failure_gates_the_load_test(self) -> None:
        """A synthetic non-dependency load failure must fail the load test.

        With the silent-warning behaviour the production method returned
        normally; the gate must instead raise the test's ``failureException``
        (``self.fail``), so this case is red until the gate exists.
        """
        outcome = self._run_load_test_with(
            SimpleNamespace(
                returncode=1,
                stderr="ModuleNotFoundError: No module named 'totally_missing_dep'",
            )
        )
        self.assertIsInstance(
            outcome,
            prod.TestPluginLoading.failureException,
            "a non-dependency load failure must gate the run (self.fail), "
            "not pass silently",
        )
        self.assertIn("synthetic_broken_addon", str(outcome))
        self.assertIn("failed to load", str(outcome))

    def test_clean_load_does_not_gate(self) -> None:
        """A plugin that loads cleanly must not fail the load test."""
        outcome = self._run_load_test_with(SimpleNamespace(returncode=0, stderr=""))
        self.assertIsNone(
            outcome, f"a clean load must not gate, but raised: {outcome!r}"
        )

    def test_strict_mode_gates_missing_dependency(self) -> None:
        """In strict mode a declared-but-missing dependency must gate.

        By default a dependency skip is advisory; with
        ``GRAMPS_ADDON_TEST_STRICT=1`` the full-runtime gate must promote it to a
        hard failure. ``subprocess.run`` is never reached (the plugin is skipped
        before load), so the outcome is driven purely by the missing dependency.
        """
        clean = SimpleNamespace(returncode=0, stderr="")
        missing = ["gi:GExiv2-0.10"]

        default = self._run_load_test_with(clean, missing_deps=missing, strict=False)
        self.assertIsNone(
            default, "a dependency skip must stay advisory in default mode"
        )

        strict = self._run_load_test_with(clean, missing_deps=missing, strict=True)
        self.assertIsInstance(
            strict,
            prod.TestPluginLoading.failureException,
            "strict mode must gate on a missing declared dependency",
        )
        self.assertIn("synthetic_broken_addon", str(strict))
        self.assertIn("unmet dependency", str(strict))

    def test_strict_mode_gates_environmental_failure(self) -> None:
        """In strict mode an environment-classified load failure must gate.

        A GTK/display init failure is advisory by default (it names a known
        environmental signature); strict mode promotes it to a hard failure,
        since a full runtime should provide the display/GTK stack.
        """
        env_fail = SimpleNamespace(
            returncode=1, stderr="RuntimeError: Gtk couldn't be initialized"
        )

        default = self._run_load_test_with(env_fail, strict=False)
        self.assertIsNone(
            default, "an environmental failure must stay advisory in default mode"
        )

        strict = self._run_load_test_with(env_fail, strict=True)
        self.assertIsInstance(
            strict,
            prod.TestPluginLoading.failureException,
            "strict mode must gate on an environment-classified failure",
        )
        self.assertIn("synthetic_broken_addon", str(strict))
        self.assertIn("environmental", str(strict))


if __name__ == "__main__":
    unittest.main()
