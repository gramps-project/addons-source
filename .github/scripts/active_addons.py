#!/usr/bin/env python3
"""Single source of truth for the *active addon* rule (include_in_listing).

An addon is **active** — built and released by ``make.py``, so CI gates on it —
when at least one ``register()`` call in its ``.gpr.py`` file(s) would be listed.
``make.py`` reads each registration's ``include_in_listing`` with a default of
``True`` (``p.get("include_in_listing", True)``), so a plugin is listed unless
its registration explicitly sets ``include_in_listing=False``. An addon whose
EVERY registration sets it to ``False`` is inactive; CI skips it in lint, the
structure check, compile, and the test runners.

This module is the parser behind ``active_addons.sh``'s ``is_active()``; the
shell helper calls ``--list`` once and greps the result. The rule here is:

* **per-register**, matching ``make.py`` — one ``register(..., include_in_listing
  =False)`` does not make the addon inactive if a sibling ``register()`` omits
  the flag (defaults True) or sets it truthy. (The previous grep helper was
  file-granular: any ``include_in_listing=`` with no ``=True`` in the whole file
  read as inactive, disagreeing with make.py on that mixed shape.)
* **comment-proof** — a flag mentioned only in a ``#`` comment is ignored,
  because the source is parsed with ``ast`` rather than grepped.
* **tolerant** — a ``.gpr.py`` that fails to parse, or a dir whose gpr has no
  ``register()`` call at all, counts as ACTIVE. The default never silently drops
  an addon from CI; the worst case is gating one that make.py would not build.

Pure stdlib, no gramps import, never executes the ``.gpr.py`` (ast.parse only).

CLI::

    active_addons.py --list [ROOT]   # active addon dir names, one per line
    active_addons.py --check DIR     # exit 0 if DIR is active, 1 if not
"""

from __future__ import annotations

import argparse
import ast
import glob
import os
import sys


def _register_calls(tree: ast.AST):
    """Yield every ``register(...)`` call node in a parsed .gpr.py."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "register":
                yield node


def _register_is_listed(call: ast.Call) -> bool:
    """Whether one ``register()`` call would be listed by make.py.

    Listed unless it carries ``include_in_listing=`` set to the literal
    ``False``. Omitted → default True → listed. A non-literal value (a variable
    / expression we cannot evaluate statically) is treated as listed, so the
    tolerant default never hides an addon.
    """
    for kw in call.keywords:
        if kw.arg == "include_in_listing":
            value = kw.value
            if isinstance(value, ast.Constant) and value.value is False:
                return False
            return True
    return True  # omitted → make.py default True


def addon_is_active(addon_dir: str) -> bool:
    """Whether an addon directory is active (built/released → CI gates on it)."""
    gprs = sorted(glob.glob(os.path.join(addon_dir, "*.gpr.py")))
    if not gprs:
        return False  # not an addon (no descriptor) — nothing to gate
    saw_register = False
    for gpr in gprs:
        try:
            with open(gpr, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=gpr)
        except (OSError, SyntaxError, ValueError):
            return True  # cannot analyse → tolerant active
        for call in _register_calls(tree):
            saw_register = True
            if _register_is_listed(call):
                return True
    # gpr(s) exist but declared no register() at all → tolerant active;
    # otherwise every register set include_in_listing=False → inactive.
    return not saw_register


def active_addons(root: str) -> list[str]:
    """Sorted names of the active addon directories directly under *root*."""
    names: list[str] = []
    for gpr in sorted(glob.glob(os.path.join(root, "*", "*.gpr.py"))):
        addon_dir = os.path.dirname(gpr)
        name = os.path.basename(addon_dir)
        if name not in names and addon_is_active(addon_dir):
            names.append(name)
    return sorted(names)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--list",
        nargs="?",
        const=".",
        metavar="ROOT",
        help="print active addon dir names under ROOT (default: cwd)",
    )
    group.add_argument(
        "--check",
        metavar="DIR",
        help="exit 0 if the addon DIR is active, 1 if not",
    )
    args = parser.parse_args(argv)

    if args.check is not None:
        return 0 if addon_is_active(args.check) else 1
    print("\n".join(active_addons(args.list)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
