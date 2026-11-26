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
Engine for the undeclared-``depends_on`` detector (Mantis 13707 class).

This module holds the *detector logic* — the ``.gpr.py`` exec-shim, the
addon index, the isolated-load subprocess, the failure classifier, and
the parallel load runner. It is import-light **by design**: it imports
no ``gi`` and no ``gramps.gui``, so the runtime fix it carries can be
exercised under a plain, headless ``python3 -m unittest`` (the test that
drives it lives in ``tests/test_addon_dependencies.py``).

Detect addons that USE another addon without declaring it in
``depends_on``. This is the bug class behind Mantis 13707: the
WebConnect packs imported ``libwebconnect`` at module load without
declaring it, so installing a pack without libwebconnect already present
failed.

The detector is INDEPENDENT of Gramps' plugin loader by design:

* it reads ``.gpr.py`` with an exec-shim of its own (no
  ``gramps.gen.plug._pluginreg`` import, no PluginManager, no
  PluginRegister), because using Gramps' loader would test addons
  through the very dependency resolver whose leniency lets the bug
  ship — and would tie the test to Gramps' internal, unstable API;
* it loads each registered module in a fresh subprocess with
  ``sys.path`` scoped to that addon's directory plus the directories
  of its declared ``depends_on`` (so a real missing dep blows up the
  way it would on a clean install), and parses the resulting
  exception to classify it.

The Gramps runtime is allowed to be importable from the subprocess —
addons do ``from gi.repository import Gtk`` and ``from gramps.gen.lib
import X`` at load time. The isolation being enforced is addon-from-
addon, not addon-from-Gramps.

RUNTIME (Mantis FR-9393 review finding R-F):
With ~144 registered addons this used to spawn one 30s-timeout
subprocess **per module, serially**, inside the already-heavy
integration job — potentially many minutes of wall-clock. The loads
are independent and I/O-bound (each child blocks on its own import),
so :func:`run_isolated_loads` runs them through a bounded thread pool;
the per-load timeout still caps any single child. Worker count defaults
to ``min(2*cpu, n_tasks)`` and is overridable with the
``ADDON_DEP_LOAD_WORKERS`` environment variable.

LIMITATION (important):
This catches undeclared addon dependencies that manifest at LOAD time
(top-level imports). It MISSES lazily-imported deps — e.g. a sibling
addon imported inside a function that is not called at module load.
No false positives, but not exhaustive — do not let it be mistaken
for one.

Failures are bucketed:

a. ``undeclared_addon_dep`` — the import error names a module that
   another addon in this tree provides AND that this addon does not
   declare in ``depends_on``. This is a FINDING and fails the test.
b. ``missing_requires_mod`` — the import error names a module the
   addon declares in ``requires_mod`` (e.g. ``litellm``). That is an
   environment concern, not a dependency-declaration bug; ignored.
c. ``other`` — any other isolated-load failure. Logged so the
   information is not lost, but NOT a finding and NOT a test failure.
   Examples: GI namespace mismatches, host-environment library issues,
   addon import-time side effects requiring full GUI state.
"""

# ------------------------
# Python modules
# ------------------------
import logging
import os
import re
import subprocess
import sys
import textwrap
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

LOG = logging.getLogger(__name__)

ADDONS_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------
# .gpr.py exec shim
# ------------------------
class _GprSentinel:
    """Stands in for any unresolved plugin-type/category constant.

    The shim does not need real enum values — only kwargs captured by
    a fake ``register()`` call. Attribute access, calls, and arithmetic
    on the sentinel all return the sentinel so common patterns inside
    ``.gpr.py`` files do not raise.
    """

    def __repr__(self) -> str:
        return "<gpr-shim>"

    def __getattr__(self, name: str) -> "_GprSentinel":
        return self

    def __call__(self, *args: Any, **kwargs: Any) -> "_GprSentinel":
        return self


_SENT = _GprSentinel()


class _PermissiveGlobals(dict):
    """Globals dict that returns a sentinel for any unknown plain name.

    CPython's ``LOAD_GLOBAL`` opcode calls ``__getitem__`` (and hence
    ``__missing__``) on ``dict`` subclasses, so unresolved plugin-type
    constants (``GRAMPLET``, ``REPORT``, ``CATEGORY_TEXT``, …) do not
    raise ``NameError`` inside the exec. Dunder names still miss so
    Python's own machinery behaves normally.
    """

    def __missing__(self, key: str) -> Any:
        if key.startswith("__"):
            raise KeyError(key)
        return _SENT


def _exec_gpr(gpr_path: str) -> list[dict]:
    """Exec one ``.gpr.py`` with a fake ``register()`` and return its kwargs.

    :param gpr_path: Absolute path to a ``*.gpr.py`` file.
    :returns: One dict per ``register()`` call, with the kwargs verbatim
              plus ``_ptype`` for the positional plugin type.
    """
    plugins: list[dict] = []

    def register(ptype: Any, **kwargs: Any) -> None:
        kwargs["_ptype"] = ptype
        plugins.append(kwargs)

    env = _PermissiveGlobals(
        {
            "__builtins__": __builtins__,
            "__file__": gpr_path,
            "__name__": "_gpr_shim",
            "register": register,
            "_": lambda s, *a, **k: s,
        }
    )
    with open(gpr_path, "r", encoding="utf-8") as f:
        src = f.read()
    exec(compile(src, gpr_path, "exec"), env)
    return plugins


def _index_addons(
    addons_root: str,
) -> tuple[dict[str, dict], set[str], list[tuple[str, str]]]:
    """Walk ``addons_root`` and build the addon metadata index.

    :returns: ``(id_to_addon, all_modules, skipped)`` where
        ``id_to_addon[plugin_id]`` is
        ``{directory, modules, depends_on, requires_mod, gpr_files}``,
        ``all_modules`` is the set of registered module names across
        the whole tree, and ``skipped`` is a list of
        ``(gpr_path, error)`` tuples for files whose exec raised.
    """
    id_to_addon: dict[str, dict] = {}
    all_modules: set[str] = set()
    skipped: list[tuple[str, str]] = []

    for dirname in sorted(os.listdir(addons_root)):
        addon_dir = os.path.join(addons_root, dirname)
        if not os.path.isdir(addon_dir):
            continue
        if dirname.startswith("."):
            continue
        gpr_files = sorted(
            os.path.join(addon_dir, f)
            for f in os.listdir(addon_dir)
            if f.endswith(".gpr.py")
        )
        if not gpr_files:
            continue
        for gpr in gpr_files:
            try:
                plugins = _exec_gpr(gpr)
            except BaseException as exc:  # noqa: BLE001
                skipped.append((gpr, f"{type(exc).__name__}: {exc}"))
                continue
            for plugin in plugins:
                pid = plugin.get("id")
                fname = plugin.get("fname")
                if not isinstance(pid, str) or not isinstance(fname, str):
                    continue
                module = re.sub(r"\.py$", "", fname)
                rec = id_to_addon.setdefault(
                    pid,
                    {
                        "directory": addon_dir,
                        "modules": [],
                        "depends_on": [],
                        "requires_mod": [],
                        "gpr_files": [],
                    },
                )
                if module not in rec["modules"]:
                    rec["modules"].append(module)
                for dep in plugin.get("depends_on") or []:
                    if isinstance(dep, str) and dep not in rec["depends_on"]:
                        rec["depends_on"].append(dep)
                for req in plugin.get("requires_mod") or []:
                    if isinstance(req, str) and req not in rec["requires_mod"]:
                        rec["requires_mod"].append(req)
                if gpr not in rec["gpr_files"]:
                    rec["gpr_files"].append(gpr)
                all_modules.add(module)
    return id_to_addon, all_modules, skipped


# ------------------------
# Isolated-load subprocess
# ------------------------
_LOADER = textwrap.dedent("""
    import sys, importlib, traceback
    # Strip the implicit "" CWD entry. Without this, if the subprocess
    # is run from a directory that contains addon subdirectories, PEP
    # 420 implicit namespace packages let sibling addons import as
    # empty packages — which silently defeats the isolation we are
    # trying to enforce. The caller also chdirs to a neutral directory,
    # but stripping "" makes the isolation independent of CWD.
    sys.path[:] = [p for p in sys.path if p not in ("", ".")]
    # Pin the GI namespace versions Gramps itself pins before loading
    # any plugin, so addons whose top-level `from gi.repository import X`
    # is version-sensitive do not generate false (c) failures from
    # ambiguous GI defaults. This is NOT Gramps' loader; it is matching
    # the runtime conditions an addon is loaded under.
    try:
        import gi
        for ns, ver in (
            ("Gtk", "3.0"),
            ("PangoCairo", "1.0"),
            ("OsmGpsMap", "1.0"),
            ("GExiv2", "0.10"),
            ("Gspell", "1"),
            ("GeocodeGlib", "1.0"),
        ):
            try:
                gi.require_version(ns, ver)
            except (ValueError, AttributeError):
                pass
    except ImportError:
        pass
    target_dir = {target_dir!r}
    dep_dirs = {dep_dirs!r}
    sys.path[:0] = [target_dir] + list(dep_dirs)
    try:
        importlib.import_module({module!r})
    except BaseException:
        traceback.print_exc()
        sys.exit(2)
    sys.exit(0)
    """)


def _isolated_load(
    target_dir: str, dep_dirs: list[str], module: str, timeout: int = 30
) -> tuple[int, str]:
    """Spawn a subprocess that tries to import ``module`` in isolation.

    The subprocess is run from a neutral CWD (the system temp dir) and
    with ``PYTHONPATH`` stripped from the environment, so neither the
    parent's working directory nor a stray ``PYTHONPATH`` can leak
    sibling-addon paths into the child's ``sys.path``.

    :returns: ``(returncode, stderr)``. Returncode ``-1`` indicates
              the subprocess timed out.
    """
    code = _LOADER.format(target_dir=target_dir, dep_dirs=dep_dirs, module=module)
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/tmp",
            env=env,
        )
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    return proc.returncode, proc.stderr


_MISSING_NAME_RE = re.compile(r"No module named ['\"]([^'\"]+)['\"]")


def _classify(
    stderr: str,
    declared_dep_modules: set[str],
    requires_mod: set[str],
    all_addon_modules: set[str],
) -> tuple[str, str]:
    """Bucket a failed isolated-load.

    A given failure may name multiple missing modules. Bucket (a) wins
    over (b) wins over (c), so the highest-signal finding is reported.
    """
    missing = [m.split(".")[0] for m in _MISSING_NAME_RE.findall(stderr)]
    for name in missing:
        if name in all_addon_modules and name not in declared_dep_modules:
            return ("a_undeclared_addon_dep", name)
    for name in missing:
        if name in requires_mod:
            return ("b_requires_mod", name)
    last_lines = stderr.strip().split("\n")[-5:]
    return ("c_other", last_lines[-1] if last_lines else "")


# ------------------------
# Parallel load runner (review finding R-F)
# ------------------------
# One isolated-load unit of work. The directories and declared-module
# sets are resolved up-front (by :func:`build_load_tasks`) so the worker
# pool only has to fire subprocesses and classify their output.
LoadTask = namedtuple(
    "LoadTask",
    "pid module target_dir dep_dirs declared_modules requires_mod",
)

# Signature of the per-task loader: (target_dir, dep_dirs, module) -> (rc, stderr).
LoadFn = Callable[[str, list[str], str], tuple[int, str]]


def build_load_tasks(id_to_addon: dict[str, dict]) -> list[LoadTask]:
    """Flatten the addon index into one :class:`LoadTask` per module.

    Each task carries the directories its isolated load may see (the
    addon's own directory plus the directories of its declared
    ``depends_on``) and the module/dep names needed to classify a
    failure — resolved here, deterministically, so the parallel runner
    needs no shared mutable state.
    """
    tasks: list[LoadTask] = []
    for pid in sorted(id_to_addon):
        rec = id_to_addon[pid]
        target_dir = rec["directory"]
        dep_dirs: list[str] = []
        declared_modules: set[str] = set()
        for dep_id in rec["depends_on"]:
            dep_rec = id_to_addon.get(dep_id)
            if dep_rec is None:
                continue
            if dep_rec["directory"] not in dep_dirs:
                dep_dirs.append(dep_rec["directory"])
            declared_modules.update(dep_rec["modules"])
        requires_mod_set = set(rec["requires_mod"])
        for module in rec["modules"]:
            tasks.append(
                LoadTask(
                    pid=pid,
                    module=module,
                    target_dir=target_dir,
                    dep_dirs=list(dep_dirs),
                    declared_modules=set(declared_modules),
                    requires_mod=set(requires_mod_set),
                )
            )
    return tasks


def default_workers(n_tasks: int) -> int:
    """Worker count for the load pool.

    ``ADDON_DEP_LOAD_WORKERS`` overrides; otherwise ``2*cpu`` (the loads
    are I/O-bound — each child blocks on its own import), bounded to the
    number of tasks and at least 1.
    """
    override = os.environ.get("ADDON_DEP_LOAD_WORKERS")
    if override:
        try:
            requested = int(override)
        except ValueError:
            requested = 0
        if requested > 0:
            return max(1, min(requested, n_tasks)) if n_tasks else requested
    cpu = os.cpu_count() or 2
    return max(1, min(cpu * 2, n_tasks)) if n_tasks else 1


def run_isolated_loads(
    tasks: list[LoadTask],
    all_addon_modules: set[str],
    *,
    max_workers: int | None = None,
    load_fn: LoadFn = _isolated_load,
) -> tuple[dict[str, int], list[str], list[str]]:
    """Run every task's isolated load through a bounded thread pool.

    The loads are independent and each blocks on a subprocess, so a
    thread pool collapses the serial wall-clock to roughly
    ``ceil(n / workers)`` slow loads instead of ``n`` (review finding
    R-F). Results are classified in the *original* task order so output
    is deterministic regardless of completion order.

    :param load_fn: the per-task loader; defaults to the real
        :func:`_isolated_load` subprocess. Injectable so the runtime
        behaviour can be tested without spawning subprocesses.
    :returns: ``(counts, findings_a, findings_c)``.
    """
    if max_workers is None:
        max_workers = default_workers(len(tasks))
    max_workers = max(1, max_workers)

    def _do(task: LoadTask) -> tuple[LoadTask, int, str]:
        rc, err = load_fn(task.target_dir, task.dep_dirs, task.module)
        return task, rc, err

    counts = {"pass": 0, "a": 0, "b": 0, "c": 0}
    findings_a: list[str] = []
    findings_c: list[str] = []

    if not tasks:
        return counts, findings_a, findings_c

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        # executor.map preserves input order, so classification stays
        # deterministic even though loads finish out of order.
        for task, rc, err in pool.map(_do, tasks):
            if rc == 0:
                counts["pass"] += 1
                continue
            bucket, detail = _classify(
                err, task.declared_modules, task.requires_mod, all_addon_modules
            )
            if bucket == "a_undeclared_addon_dep":
                counts["a"] += 1
                findings_a.append(
                    f"  {task.pid} (module {task.module}) — undeclared addon "
                    f"dep: {detail}"
                )
            elif bucket == "b_requires_mod":
                counts["b"] += 1
            else:
                counts["c"] += 1
                findings_c.append(f"  {task.pid} (module {task.module}) — {detail}")

    return counts, findings_a, findings_c
