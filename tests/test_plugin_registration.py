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
Integration tests that verify all addons register and load correctly
through the Gramps plugin system.

These tests use the real Gramps ``PluginRegister`` and ``BasePluginManager`` to:

1. Scan every addon's ``.gpr.py``.
2. Verify all plugins registered successfully.
3. Attempt to load each plugin module (catching missing dependencies).
4. Validate plugin metadata (version, target version, entry points).
"""

# ------------------------
# Python modules
# ------------------------
import ast
import glob
import importlib
import logging
import os
import subprocess
import sys
import unittest
from types import SimpleNamespace
from typing import Any

# ------------------------
# Gramps modules
# ------------------------
from gramps.gen.plug._pluginreg import EXPORT, GRAMPLET, IMPORT, REPORT, TOOL
from gramps.gen.utils.requirements import Requirements
from gramps.version import VERSION_TUPLE

# ------------------------
# Gramps specific
# ------------------------
from tests.gramps_test_env import ADDONS_ROOT, HAS_GTK, GrampsTestCase, strict_mode

LOG = logging.getLogger(__name__)


def _get_addon_plugins(registry: Any, include_unlisted: bool = False) -> list[Any]:
    """Return all :class:`PluginData` objects whose ``fpath`` is inside the addons tree.

    By default, plugins whose ``.gpr.py`` declares ``include_in_listing=False``
    are filtered out: those addons are not built or released by ``make.py``,
    so this CI does not gate on their state (per Gary Griffin's discussion on
    PR #820). Pass ``include_unlisted=True`` to inspect them anyway.

    :param registry: A :class:`PluginRegister` instance.
    :param include_unlisted: If ``True``, also return plugins whose
                             ``include_in_listing`` field is ``False``.
    :type include_unlisted: bool
    :returns: List of :class:`PluginData` entries belonging to this repository.
    """
    return [
        pdata
        for pdata in registry._PluginRegister__plugindata
        if pdata.fpath
        and ADDONS_ROOT in pdata.fpath
        and (include_unlisted or pdata.include_in_listing)
    ]


# Gramps' own requirement checker, shared for the whole run so its positive
# caches survive across the ~200 plugins probed. Reused rather than
# re-implemented so this test agrees with what Gramps does at runtime — in
# particular a `requires_gi` version may be a comma-separated list of
# acceptable versions ("0.10,0.12"), any one of which satisfies it.
_REQUIREMENTS = Requirements()


def _check_dependencies(pdata: Any) -> list[str]:
    """Return a list of missing dependency descriptions for a plugin, or empty.

    Only *probes* for each declared requirement — via :func:`find_spec`,
    ``gi.require_version`` and a ``PATH`` lookup — to decide whether attempting
    the load is fair. The addon itself is imported later, in the isolated
    subprocess of :meth:`TestPluginLoading.test_load_all_addon_modules`.

    :param pdata: The plugin's :class:`PluginData` record.
    :returns: Human-readable strings describing each unmet requirement.
    """
    missing: list[str] = []
    for mod in pdata.requires_mod or []:
        if not _REQUIREMENTS.check_mod(mod):
            missing.append(f"mod:{mod}")
    for exe in pdata.requires_exe or []:
        if not _REQUIREMENTS.check_exe(exe):
            missing.append(f"exe:{exe}")
    for gi_mod, gi_ver in pdata.requires_gi or []:
        if not _REQUIREMENTS.check_gi((gi_mod, gi_ver)):
            missing.append(f"gi:{gi_mod}-{gi_ver}")
            continue
        # check_gi() resolves the typelib version but does not import it. Probe
        # the binding too, so a typelib that resolves yet fails to import is a
        # dependency skip here rather than a hard failure blamed on the addon
        # (only Gtk/Gdk namespace errors are in _ENV_LOAD_SIGNATURES).
        try:
            importlib.import_module(f"gi.repository.{gi_mod}")
        except (ImportError, ValueError):
            missing.append(f"gi:{gi_mod}-{gi_ver}")
    return missing


# Signatures of a load failure caused by the *environment* (no display server,
# no icon theme, a GTK namespace missing) rather than the addon — the same
# class as a GTK signal crash: advisory, not a hard failure. Each entry is
# specific enough that it would not appear in a normal addon exception message;
# broad words ("DISPLAY", "load_icon") are deliberately avoided so a real
# defect cannot be misclassified as environmental (false green).
_ENV_LOAD_SIGNATURES = (
    "Gtk couldn't be initialized",  # GTK init with no display
    "could not open display",
    "cannot open display",
    "Cannot open display",
    "gtk-icon-theme-error-quark",  # headless icon theme (ClipboardGramplet, GError)
    "object has no attribute 'load_icon'",  # same, when the lookup returns None
    "Namespace Gtk not available",  # GTK typelib missing from the image
    "Namespace Gdk not available",
)


def _is_env_load_failure(stderr: str) -> bool:
    """Whether ``stderr`` is a display/GTK-environment load failure.

    Anchored so a signature only counts on an actual error/log line, not on an
    indented traceback frame or a source snippet echoed inside the traceback —
    a real addon defect that merely quotes one of these strings in its code
    must not be demoted to advisory.
    """
    for raw in (stderr or "").splitlines():
        # Traceback "File ..." frames and echoed source lines are indented;
        # exception messages and GLib/GTK warnings sit at column 0.
        if not raw or raw[0].isspace():
            continue
        if any(sig in raw for sig in _ENV_LOAD_SIGNATURES):
            return True
    return False


# Per-plugin isolated-load timeout. Each subprocess re-registers the whole
# plugin tree before loading one addon, so the wall-clock cost scales with the
# machine and filesystem. A timeout while still scanning the registry is
# advisory (slow setup); a timeout *after* REGISTRY_READY is a real import
# hang and gates. The value is generous so only a genuine hang trips it.
_LOAD_TIMEOUT = 120


# ------------------------------------------------------------
#
# TestPluginRegistration
#
# ------------------------------------------------------------
class TestPluginRegistration(GrampsTestCase):
    """Verify every addon registers through the Gramps plugin system."""

    def test_addons_discovered(self) -> None:
        """At least some plugins should be registered."""
        all_types = [IMPORT, EXPORT, REPORT, TOOL, GRAMPLET]
        total = sum(len(self.plugin_registry.type_plugins(t)) for t in all_types)
        self.assertGreater(total, 0, "No addon plugins were registered")

    def test_all_plugins_have_valid_metadata(self) -> None:
        """Every registered plugin must have id, name, and version."""
        for pdata in self.plugin_registry.type_plugins(None) or []:
            self.assertTrue(pdata.id, f"Plugin missing id: {pdata}")
            self.assertTrue(pdata.name, f"Plugin {pdata.id} missing name")
            self.assertTrue(pdata.version, f"Plugin {pdata.id} missing version")

    def test_target_version_matches_gramps_install(self) -> None:
        """All listed addons must target the Gramps series they're running against.

        The expected prefix is derived from the installed Gramps' version
        (``gramps.version.VERSION_TUPLE``), so the same assertion works on
        every maintenance branch — gramps60 expects "6.0", gramps61 expects
        "6.1", etc.
        """
        expected_prefix = f"{VERSION_TUPLE[0]}.{VERSION_TUPLE[1]}"
        issues: list[str] = []
        for pdata in _get_addon_plugins(self.plugin_registry):
            if not pdata.gramps_target_version.startswith(expected_prefix):
                issues.append(f"{pdata.id}: targets {pdata.gramps_target_version}")
        if issues:
            self.fail(
                f"Addons not targeting Gramps {expected_prefix}:\n"
                + "\n".join(issues)
            )


# ------------------------------------------------------------
#
# TestPluginLoading
#
# ------------------------------------------------------------
class TestPluginLoading(GrampsTestCase):
    """Attempt to load every addon plugin module through Gramps.

    Each plugin is loaded in a subprocess to isolate crashes (e.g. segfaults
    from missing GI typelibs) from the test runner.
    """

    def test_load_all_addon_modules(self) -> None:
        """Load every addon plugin; gate on non-dependency load failures.

        Failures are collected rather than failing fast, then classified. A
        non-dependency *hard* load failure always fails the test (``self.fail``)
        — as does an import that hangs past the timeout — so this is a real gate,
        like the sibling smoke tests (:class:`TestImportPluginSmoke`,
        :class:`TestExportPluginSmoke`), not an always-pass that merely warns.

        The remaining categories depend on the mode
        (``GRAMPS_ADDON_TEST_STRICT`` — see :func:`strict_mode`):

        * **default** — dependency skips (unmet ``requires_mod``/``gi``/``exe``),
          display/GTK-environment failures, and slow registry-scan timeouts are
          advisory and only logged; the test can still pass.
        * **strict** — dependency skips and environment failures are promoted to
          hard failures (a full runtime should provide those). Only slow
          registry-scan timeouts stay advisory (performance, not correctness).
        """
        plugins = _get_addon_plugins(self.plugin_registry)
        self.assertGreater(len(plugins), 0, "No addon plugins found to test")

        hard_failures: list[str] = []
        dep_skips: list[str] = []
        env_failures: list[str] = []
        timeouts: list[str] = []

        for pdata in plugins:
            missing = _check_dependencies(pdata)
            if missing:
                dep_skips.append(f"{pdata.id} (missing: {', '.join(missing)})")
                continue

            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        # Print REGISTRY_READY *after* registration, *before*
                        # the addon import, so a timeout can tell the two apart
                        # (see the TimeoutExpired handler).
                        f"import sys; sys.path.insert(0, {ADDONS_ROOT!r});"
                        f"from gramps.gen.plug import BasePluginManager;"
                        f"from gramps.gen.const import PLUGINS_DIR;"
                        f"pmgr = BasePluginManager.get_instance();"
                        f"pmgr.reg_plugins(PLUGINS_DIR, None, None);"
                        f"pmgr.reg_plugins({ADDONS_ROOT!r}, None, None);"
                        f"print('REGISTRY_READY', flush=True);"
                        # Neutralise blocking modal dialogs (e.g. an addon that
                        # pops ErrorDialog(...).run() at import when an optional
                        # dep is missing) so the load can't hang or show UI.
                        f"from tests.gramps_test_env import neutralize_gui_dialogs;"
                        f"neutralize_gui_dialogs();"
                        f"from gramps.gen.plug import PluginRegister;"
                        f"preg = PluginRegister.get_instance();"
                        f"pdata = preg.get_plugin({pdata.id!r});"
                        f"mod = pmgr.load_plugin(pdata);"
                        f"sys.exit(0 if mod else 1)",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=_LOAD_TIMEOUT,
                    env={**os.environ, "PYTHONPATH": ADDONS_ROOT},
                )
            except subprocess.TimeoutExpired as exc:
                partial = exc.stdout or ""
                if isinstance(partial, bytes):
                    partial = partial.decode("utf-8", "replace")
                if "REGISTRY_READY" in partial:
                    # Registration finished; the process hung inside the
                    # addon's own import. That is a real defect, not slow
                    # setup — gate on it.
                    hard_failures.append(
                        f"{pdata.id} (hung during import, >{_LOAD_TIMEOUT}s)"
                    )
                else:
                    # Still scanning the registry when the cap hit — cost of
                    # the per-plugin full re-registration on a slow machine or
                    # filesystem. Advisory, and it must never abort the test.
                    timeouts.append(
                        f"{pdata.id} (registry scan >{_LOAD_TIMEOUT}s)"
                    )
                continue
            if result.returncode < 0:
                # Killed by a signal — usually GTK aborting with no display.
                # Advisory by default, since a headless abort often prints no
                # useful stderr. In strict mode a crash with NO display/GTK
                # signature is treated as a real native crash and gates.
                sig = -result.returncode
                if strict_mode() and not _is_env_load_failure(result.stderr or ""):
                    hard_failures.append(
                        f"{pdata.id} (native crash, signal {sig}, "
                        "no display/GTK signature)"
                    )
                else:
                    env_failures.append(f"{pdata.id} (signal {sig})")
            elif result.returncode != 0:
                err = (
                    result.stderr.strip().split("\n")[-1]
                    if result.stderr
                    else "unknown"
                )
                # A GTK/display-init failure that surfaces as a Python
                # exception is the same environmental class as a signal crash;
                # classify it the same way rather than only failing this half.
                if _is_env_load_failure(result.stderr):
                    env_failures.append(f"{pdata.id} ({err})")
                else:
                    hard_failures.append(f"{pdata.id} ({err})")

        total = len(plugins)

        if strict_mode():
            # Full-runtime gate: a complete runtime (Xvfb + every GI typelib +
            # all declared deps) leaves no room for these to be "environmental",
            # so promote them to hard failures — matching the make.py docs. Only
            # slow registry-scan timeouts stay advisory (performance, not
            # correctness); genuine import hangs are already hard failures.
            hard_failures += [f"{s} (unmet dependency)" for s in dep_skips]
            hard_failures += [
                f"{s} (environmental — a full runtime should provide this)"
                for s in env_failures
            ]
            dep_skips = []
            env_failures = []

        # Advisory categories are always logged, so a *passing* run still
        # surfaces them.
        if dep_skips:
            LOG.warning("Skipped for unmet dependencies (%d):\n  %s",
                        len(dep_skips), "\n  ".join(dep_skips))
        if env_failures:
            LOG.warning(
                "Failed for environmental reasons — signal crash or GTK/"
                "display init, likely need a display server (%d):\n  %s",
                len(env_failures), "\n  ".join(env_failures))
        if timeouts:
            LOG.warning(
                "Timed out during isolated load — slow machine/filesystem, "
                "each load re-scans the full registry (%d):\n  %s",
                len(timeouts), "\n  ".join(timeouts))

        if hard_failures:
            # Communicate the situation clearly: list ONLY the hard failures
            # (what actually gates the test and needs fixing), then one line
            # per advisory category saying what it means and what to do. Full
            # advisory lists stay in the warning log above so the failure isn't
            # a wall of text.
            lines = [
                f"{len(hard_failures)} of {total} addon(s) failed to load. "
                "These are real load failures and must be fixed:",
                "",
                *(f"  ✗ {x}" for x in hard_failures),
            ]
            advisory: list[str] = []
            if env_failures:
                advisory.append(
                    f"  {len(env_failures)} could not initialise GTK/a display "
                    "— run under Xvfb to load these; not an addon bug"
                )
            if timeouts:
                advisory.append(
                    f"  {len(timeouts)} timed out (>{_LOAD_TIMEOUT}s) — slow "
                    "machine/filesystem; not an addon bug"
                )
            if dep_skips:
                advisory.append(
                    f"  {len(dep_skips)} skipped for an unmet optional "
                    "dependency (requires_mod/gi/exe)"
                )
            if advisory:
                lines += [
                    "",
                    "Not failing this test (advisory only; full lists in the "
                    "log above):",
                    *advisory,
                ]
            self.fail("\n".join(lines))


# ------------------------------------------------------------
#
# TestImportPluginSmoke
#
# ------------------------------------------------------------
class TestImportPluginSmoke(GrampsTestCase):
    """Verify import plugins have a callable ``import_function`` attribute."""

    def test_import_plugins_have_callable(self) -> None:
        """Each listed IMPORT plugin must reference a callable import function."""
        import_plugins = [
            p
            for p in self.plugin_registry.type_plugins(IMPORT)
            if p.fpath and ADDONS_ROOT in p.fpath and p.include_in_listing
        ]
        issues: list[str] = []
        for pdata in import_plugins:
            if _check_dependencies(pdata):
                continue
            mod = self.plugin_manager.load_plugin(pdata)
            if mod is None:
                # Dependencies are satisfied yet the module did not load — a
                # real failure, not a skip. Import plugins are headless-safe
                # (no GUI at import), so this is not a display artifact.
                issues.append(f"{pdata.id}: failed to load (no module)")
                continue
            func = getattr(mod, pdata.import_function, None)
            if not callable(func):
                issues.append(f"{pdata.id}: {pdata.import_function} is not callable")
        if issues:
            self.fail(
                f"{len(issues)} of {len(import_plugins)} import plugin(s) failed "
                "to load or lack a callable import_function:\n  "
                + "\n  ".join(issues)
            )


# ------------------------------------------------------------
#
# TestExportPluginSmoke
#
# ------------------------------------------------------------
class TestExportPluginSmoke(GrampsTestCase):
    """Verify export plugins have a callable ``export_function`` attribute."""

    def test_export_plugins_have_callable(self) -> None:
        """Each listed EXPORT plugin must reference a callable export function."""
        export_plugins = [
            p
            for p in self.plugin_registry.type_plugins(EXPORT)
            if p.fpath and ADDONS_ROOT in p.fpath and p.include_in_listing
        ]
        issues: list[str] = []
        for pdata in export_plugins:
            if _check_dependencies(pdata):
                continue
            mod = self.plugin_manager.load_plugin(pdata)
            if mod is None:
                # Dependencies are satisfied yet the module did not load — a
                # real failure, not a skip. Export plugins are headless-safe
                # (no GUI at import), so this is not a display artifact.
                issues.append(f"{pdata.id}: failed to load (no module)")
                continue
            func = getattr(mod, pdata.export_function, None)
            if not callable(func):
                issues.append(f"{pdata.id}: {pdata.export_function} is not callable")
        if issues:
            self.fail(
                f"{len(issues)} of {len(export_plugins)} export plugin(s) failed "
                "to load or lack a callable export_function:\n  "
                + "\n  ".join(issues)
            )


# Individual plugin registrations intentionally not listed for release (a
# ``register(...)`` call with ``include_in_listing=False``), keyed
# ``"<directory>:<plugin id>"``. These are excluded from the load / version /
# dependency gates, so nothing else notices if one is dropped — and a *source*
# declaration is the right thing to freeze, because an unlisted plugin may never
# reach the runtime registry (e.g. MongoDB is UNSTABLE and dropped before
# registration). Keying per-registration (not per-directory) catches a mixed
# directory — e.g. TMGimporter also ships the *listed* ``im_sqz`` — flipping one
# of its listed plugins to unlisted. Any drift fails the test, forcing a choice.
#
# Branch-specific: this is the gramps60 set; the gramps61 copy carries its own.
# Update with a one-line reason when you intentionally change a listing.
_EXPECTED_UNLISTED = {
    "CheckPlaceTitles:checkplacetitle": "maintenance/QA helper, not a release feature",
    "DetId:deterministicid": "developer deterministic-id utility",
    "FaceDetection:Face Detection": "experimental, heavy optional deps",
    "HtmlView:htmlview": "deprecated HTML view",
    "MongoDB:mongodb": "unstable experimental database backend",
    "PhpGedView:PhpGedView": "niche import integration",
    "Query:Query Gramplet": "developer query tooling",
    "Query:Query Quickview": "developer query tooling",
    "SourceIndex:BirthIndex": "helper index gramplet, not standalone",
    "SourceIndex:CensusIndex": "helper index gramplet, not standalone",
    "SourceIndex:DeathIndex": "helper index gramplet, not standalone",
    "SourceIndex:MarriageIndex": "helper index gramplet, not standalone",
    "SourceIndex:Index": "helper index gramplet, not standalone",
    "SourceIndex:Witness": "helper gramplet, not standalone",
    "SourceReferences:Source References": "helper gramplet, superseded",
    "SurnameMappingGramplet:Surname Mapping": "niche/legacy gramplet",
    "TMGimporter:im_pjc": "conditional TMG PJC-format importer",
    "TMGimporter:im_tmg": "conditional TMG-format importer",
    "TMGimporter:im_ver": "conditional TMG VER-format importer",
    "WordleGramplet:Wordle Gramplet": "demo/experimental gramplet",
}


def _unlisted_registrations(addons_root: str) -> set[str]:
    """Return ``{"<dir>:<id>"}`` for every ``register(include_in_listing=False)``.

    Parses each ``.gpr.py`` with :mod:`ast` (no code execution) and inspects
    every ``register(...)`` call — including those inside conditionals, which
    are still declarations worth guarding. A call whose ``id`` is not a literal
    is keyed ``"<dir>:<unknown>"`` so it is not silently dropped.

    :param addons_root: The addons-source root directory.
    :returns: Set of ``"<directory>:<plugin id>"`` keys.
    """
    found: set[str] = set()
    for gpr in glob.glob(os.path.join(addons_root, "*", "*.gpr.py")):
        directory = os.path.basename(os.path.dirname(gpr))
        try:
            with open(gpr, encoding="utf-8", errors="ignore") as handle:
                tree = ast.parse(handle.read(), gpr)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "register"
            ):
                continue
            kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
            inc = kwargs.get("include_in_listing")
            if isinstance(inc, ast.Constant) and inc.value is False:
                pid = kwargs.get("id")
                pid_val = pid.value if isinstance(pid, ast.Constant) else "<unknown>"
                found.add(f"{directory}:{pid_val}")
    return found


# ------------------------------------------------------------
#
# TestAddonListingManifest
#
# ------------------------------------------------------------
class TestAddonListingManifest(unittest.TestCase):
    """Guard which plugins opt out of the gates via ``include_in_listing=False``.

    Source-based and per-registration: scans every ``register()`` call in every
    ``.gpr.py``, so it catches unlisted plugins that never register *and* a
    single plugin flipping inside an otherwise-listed directory.
    """

    def test_unlisted_registrations_match_manifest(self) -> None:
        """Unlisted ``register()`` calls must match :data:`_EXPECTED_UNLISTED`.

        The gates skip unlisted plugins, so one slipping to
        ``include_in_listing=False`` would silently leave every gate. Fail on any
        drift — a new unlisting or a re-listing — so the change is deliberate.
        """
        declared = _unlisted_registrations(ADDONS_ROOT)
        expected = set(_EXPECTED_UNLISTED)
        newly = sorted(declared - expected)
        relisted = sorted(expected - declared)
        problems: list[str] = []
        if newly:
            problems.append(
                "Newly unlisted (include_in_listing=False) — now excluded from "
                "the load/version/dependency gates. If intentional, add each to "
                "_EXPECTED_UNLISTED with a reason:\n  " + "\n  ".join(newly)
            )
        if relisted:
            problems.append(
                "No longer declaring include_in_listing=False (now listed, or "
                "removed) — drop each from _EXPECTED_UNLISTED:\n  "
                + "\n  ".join(relisted)
            )
        if problems:
            self.fail("\n\n".join(problems))


# ------------------------------------------------------------
#
# TestEnvLoadClassifier
#
# ------------------------------------------------------------
class TestEnvLoadClassifier(unittest.TestCase):
    """Unit tests for :func:`_is_env_load_failure` (no Gramps needed).

    Guards the false-green risk: an environmental failure must be recognised,
    but a real addon defect that merely quotes a signature must not be.
    """

    def test_gtk_init_failure_is_environmental(self) -> None:
        stderr = (
            "Traceback (most recent call last):\n"
            '  File "addon.py", line 3, in <module>\n'
            "    from gi.repository import Gtk\n"
            "RuntimeError: Gtk couldn't be initialized. "
            "Use Gtk.init_check() if you want to handle this case."
        )
        self.assertTrue(_is_env_load_failure(stderr))

    def test_icon_theme_gerror_is_environmental(self) -> None:
        stderr = (
            "gi.repository.GLib.GError: gtk-icon-theme-error-quark: "
            "Icon 'stock_link' not present in theme Yaru (0)"
        )
        self.assertTrue(_is_env_load_failure(stderr))

    def test_none_load_icon_is_environmental(self) -> None:
        # The ClipboardGramplet headless case as it surfaces on some builds:
        # the icon lookup returns None, then `.load_icon` is called on it.
        self.assertTrue(
            _is_env_load_failure(
                "AttributeError: 'NoneType' object has no attribute 'load_icon'"
            )
        )

    def test_missing_typelib_is_environmental(self) -> None:
        self.assertTrue(
            _is_env_load_failure("ValueError: Namespace Gtk not available")
        )

    def test_real_defect_is_not_environmental(self) -> None:
        stderr = (
            "Traceback (most recent call last):\n"
            "ModuleNotFoundError: No module named 'requests'"
        )
        self.assertFalse(_is_env_load_failure(stderr))

    def test_signature_only_in_source_frame_is_not_environmental(self) -> None:
        # The addon's own code quotes a signature, but the actual exception is
        # unrelated. The indented source line must not trigger a match.
        stderr = (
            "Traceback (most recent call last):\n"
            '  File "addon.py", line 9, in build\n'
            '    raise ValueError("cannot open display later")\n'
            "ValueError: bad config"
        )
        self.assertFalse(_is_env_load_failure(stderr))

    def test_dropped_broad_words_do_not_match(self) -> None:
        # "DISPLAY" and the bare word "load_icon" were removed as over-broad;
        # only the specific NoneType-load_icon phrase counts, so a real error
        # merely naming them must not be misclassified.
        self.assertFalse(_is_env_load_failure("KeyError: 'DISPLAY'"))
        self.assertFalse(
            _is_env_load_failure("NameError: name 'load_icon' is not defined")
        )

    def test_empty_stderr_is_not_environmental(self) -> None:
        self.assertFalse(_is_env_load_failure(""))


# ------------------------------------------------------------
#
# TestDependencyCheck
#
# ------------------------------------------------------------
@unittest.skipUnless(HAS_GTK, "needs PyGI with a Gtk 3.0 typelib")
class TestDependencyCheck(unittest.TestCase):
    """Unit tests for :func:`_check_dependencies` (no registry boot).

    Guards the false-skip risk. A ``requires_gi`` version may be a *comma-
    separated list of acceptable versions* — Gramps' ``Requirements.check_gi()``
    splits on "," and takes the first that resolves — so an addon declaring
    ``("GExiv2", "0.10,0.12,0.14,0.16")`` must not be reported missing on a host
    that has GExiv2 0.10. Passing the raw string to ``gi.require_version()``
    raises :exc:`ValueError` and reports a satisfied dependency as unmet: an
    advisory skip by default, and a false *failure* under
    :func:`~tests.gramps_test_env.strict_mode`.
    """

    @staticmethod
    def _pdata(**requirements: Any) -> SimpleNamespace:
        """A :class:`PluginData` stand-in declaring only the given requirements."""
        spec: dict[str, Any] = {
            "requires_mod": [],
            "requires_exe": [],
            "requires_gi": [],
        }
        spec.update(requirements)
        return SimpleNamespace(**spec)

    def test_comma_separated_gi_version_satisfied_by_any_member(self) -> None:
        # Gtk stands in for the real cases (GExiv2 "0.10,0.12,0.14,0.16",
        # GooCanvas "2.0,3.0"): it is the one typelib this suite already needs,
        # so the assertion holds on any host that can run these tests.
        self.assertEqual(
            _check_dependencies(self._pdata(requires_gi=[("Gtk", "3.0,4.0")])), []
        )
        # Order must not matter: the resolvable version is not always first.
        self.assertEqual(
            _check_dependencies(self._pdata(requires_gi=[("Gtk", "4.0,3.0")])), []
        )

    def test_single_gi_version_still_resolves(self) -> None:
        self.assertEqual(
            _check_dependencies(self._pdata(requires_gi=[("Gtk", "3.0")])), []
        )

    def test_absent_gi_namespace_is_reported_missing(self) -> None:
        # No member of the list resolves — the whole spec is unmet, and the
        # message quotes the spec as declared.
        self.assertEqual(
            _check_dependencies(
                self._pdata(requires_gi=[("NoSuchNamespace", "1.0,2.0")])
            ),
            ["gi:NoSuchNamespace-1.0,2.0"],
        )

    def test_absent_module_and_executable_are_reported_missing(self) -> None:
        self.assertEqual(
            _check_dependencies(
                self._pdata(
                    requires_mod=["totally_missing_module"],
                    requires_exe=["totally-missing-executable"],
                )
            ),
            ["mod:totally_missing_module", "exe:totally-missing-executable"],
        )


if __name__ == "__main__":
    unittest.main()
