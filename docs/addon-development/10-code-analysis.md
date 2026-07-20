# Code Analysis

[← Previous](09-troubleshoot.md) · [Index](01-overview.md) · [Next →](11-internationalization.md)

<!--
  Authoritative scraped source:
  ../04 - Technical Documentation/programming-guidelines.md (165L) — PEP 8,
  Black, Pylint scoring rule, cb_ callback prefix, import grouping, class
  header comments.

  Three repos enforce three different combinations; the table at the top
  is the cheat sheet, the per-section detail explains why each is what it
  is. Cross-reference 15-rules for the normative form.
-->

## Overview

What automated checks run against addon code, locally and in CI, and how to keep an addon passing them. The goal is "PR opens green" — every check below catches a class of issue cheaper than a maintainer review round.

The checks vary by repo. Two combinations matter; the cheat sheet:

| Check                                  | gramps core            | addons-source     |
|----------------------------------------|------------------------|-------------------|
| Black formatting (`--check --diff`)    | pre-commit + CI        | —                 |
| `mypy` static types                    | pre-commit + CI        | —                 |
| `ruff` E9 / F63 / F7 / F82             | —                      | pre-commit + CI   |
| `python -m py_compile` / `ast.parse`   | —                      | pre-commit + CI   |
| `msgfmt` on `po/*.po`                  | upstream build         | upstream build    |
| `pylint` ≥ 9 on new files              | manual; not gated      | not enforced      |

`addons-source` does **not** enforce Black today; gramps core does. This is the most common surprise for authors moving between the two. See [Black](#black) below.

## Pre-commit

There is no published upstream `.pre-commit-config.yaml` for `addons-source`; addon authors can install their own locally to mirror the CI gates above (ruff, py_compile), but this is convenience tooling, not an upstream requirement. The authoritative checks live in `addons-source/.github/workflows/ci.yml`; if your local pre-commit and CI disagree, CI wins.

For gramps core, the upstream pre-commit config under the `gramps/` repo covers Black and `mypy`; install with the standard `pre-commit install` flow from the repo root.

## Black

[Black](https://black.readthedocs.io/) is an opinionated Python formatter. Where enforced, the CI lint job is `psf/black@stable --check --diff`; a violation fails the build and blocks merging.

**Where enforced.** gramps core (`maintenance/gramps61` and `master`) — both pre-commit and CI. addons-source does *not* enforce Black today; PRs there go through without formatting checks.

**The trap on gramps core.** Tiny diffs that look harmless trip the gate:

- A mid-module-import blank line.
- A multi-line `.append()` collapsed to one line.

PR 2326 tripped this on `cli/clidbman.py` and a new test file; the fix was a Black-cleaned force-push rebase. Run `black --check` on the changed files before pushing:

```bash
git diff --name-only --diff-filter=ACMR origin/master...HEAD \
  | grep '\.py$' \
  | xargs --no-run-if-empty black --check --diff
```

## `mypy`

Gramps core's CI runs `mypy` against the tree; type errors block the build. `*.gpr.py` plugin registration files are excluded (they run in the injected-name scope and would otherwise complain about `register`, `_`, etc.).

This applies to gramps core only. addons-source PRs don't run `mypy`; addon Python doesn't ship type hints by default. Where an addon does add type hints, prefer the 3.10+ shape (`X | None`, `list[X]`) per [16-guidelines → Coding style](16-guidelines.md#coding-style).

## `ruff` E9 / F63 / F7 / F82

addons-source's pre-commit and CI run `ruff` with a tight rule selection:

| Code  | Catches                                                                |
|-------|------------------------------------------------------------------------|
| `E9*` | Syntax errors                                                          |
| `F63` | Comparison and membership operator mistakes (`is not` vs `not is`)     |
| `F7`  | Imports inside dead code, syntax-level structural issues               |
| `F82` | Undefined names                                                        |

It's a syntax-and-undefined-names net, not a style enforcer — the goal is "code that *imports*", which is what gets you past the plugin-discovery gate.

Local invocation:

```bash
ruff check --select E9,F63,F7,F82 <Addon>/
```

The undefined-name rule (`F82`) is the most useful single check for addon authors — `Pillow` typo'd as `Pilllow`, `gramps.gen.plugin` typo'd as `plugn`, the kind of typo that produces a silent skip in the plugin manager and no traceback. `ruff F82` catches them.

A lint flag is a symptom, not the bug. Don't just add a `# noqa` or a defensive import to silence `F82` — read the enclosing function first. An undefined name in shipping code usually means dead or broken code.

## `python -m py_compile` / `ast.parse`

Both pre-commit and addons-source CI compile every changed `.py`:

```bash
python -m py_compile <Addon>/*.py
```

`ast.parse` is the more lenient check (won't import code, just parses); both exist because a file that compiles can still fail to import (`NameError` at module-level, missing dep). The compile pass is the absolute floor — failing it means the addon can't even register.

## `msgfmt` on `po/*.po`

Per-addon `.po` files have to compile to `.mo` cleanly for translations to take effect at runtime. A malformed catalog — mismatched `%s` substitutions, unclosed plural-form expression — silently falls back to English on the platform where compilation fails. Run `msgfmt -c` on every per-addon catalog before publishing.

Local check:

```bash
make.py gramps60 compile <Addon>
```

`make.py compile` wraps `msgfmt` with the right paths; a failure prints the offending file and line. See [12-packaging → The localisation flow](12-packaging.md#the-localisation-flow).

[Mantis 14234](https://gramps-project.org/bugs/view.php?id=14234) (lxml `ngettext` newline fix; addons-source PR 907) is the canonical example — a single misplaced newline in a plural form, caught by a `msgfmt -c` pass.

## `pylint`

Gramps' programming guidelines call for pylint ≥ 9 on new files and "changes to existing files shall not reduce the pylint score" — but this is **not** gated by CI. It's developer guidance, not a hard check.

`pylint` doesn't run on addon code by default. When you do run it locally:

```bash
pylint --disable=missing-docstring <Addon>/<Addon>.py
```

Run from the addon's parent directory so `pylint`'s import resolution finds it as a package.

## Verifying `requires_mod`

`requires_mod` takes the **importable** module name, not the PyPI distribution name (see [09-troubleshoot → `requires_mod` declares `Pillow`…](09-troubleshoot.md#requires_mod-declares-pillow-but-gramps-says-its-missing)). Before pushing, on a system with the dependency installed:

```python
from importlib.util import find_spec
for mod in ["PIL", "lxml", "dateutil"]:
    assert find_spec(mod) is not None, mod
```

This is a manual check, not a CI gate. It's listed here because the failure mode it catches — silent skip in the plugin manager — looks exactly like a `ruff F82` symptom but happens at a different layer.

## Coding-standard rules worth running locally

The full standard lives in `../gramps/AGENTS.md` and applies to all Gramps-related Python. The mechanical checks above cover formatting and syntax; the rules below need a manual pass.

### Import grouping

Three sections, each with a comment header:

```python
# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
import os
import logging

# -------------------------------------------------------------------------
#
# GTK/Gnome modules
#
# -------------------------------------------------------------------------
from gi.repository import Gtk

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.db.base import DbReadBase
from .mymodule import MyClass
```

Existing code that doesn't follow this stays as-is; new code does.

### Callback names

Callbacks are prefixed `cb_`:

```python
def cb_save(self, *args):
    ...
```

`pylint` also avoids the `W0613: Unused argument` warning for `cb_*`-prefixed methods, which is convenient for GTK signal handlers that receive arguments they don't use.

### Class headers

Every class — including `unittest.TestCase` subclasses — carries a navigation comment header:

```python
# ------------------------------------------------------------
#
# MyClass
#
# ------------------------------------------------------------
class MyClass:
    ...
```

This is for finding the class when multiple classes share a file, not for documentation. Sphinx-style docstrings handle the documentation.

### Member-name conventions

- `__private` (two underscores) — class-only access.
- `_protected` (one underscore) — class and subclass access.

PEP 8 with one local addition: a space after every comma.

### TAB stops

No TABs in Python. Indentation is 4 spaces. Where TABs are unavoidable (Makefiles), they're at columns 9, 17, 25, … (equivalent to 8 spaces). Don't set your editor's TAB stops to 4 — that "fixes" indentation by making TABs invisible and produces files that look right but parse wrong.

## Running everything locally before pushing

A pragmatic checklist before opening a PR:

```bash
# Addons-source PRs:
ruff check --select E9,F63,F7,F82 <Addon>/
python -m py_compile <Addon>/*.py
make.py gramps60 compile <Addon>                  # exercises msgfmt
python -m unittest discover -s <Addon>/tests -t . # tests

# Gramps core PRs add:
black --check --diff <changed-files>.py
mypy
GRAMPS_RESOURCES=. python3 -m unittest discover -p "*_test.py"
```

See [12-packaging](12-packaging.md) for `make.py` setup and [07-testing](07-testing.md) for the test-loading conventions.

## See also

- [04-fundamentals](04-fundamentals.md) — the conventions the static checks verify.
- [07-testing](07-testing.md) — the runtime checks that complement static analysis.
- [09-troubleshoot → "PR's pre-commit passed but CI is red"](09-troubleshoot.md#prs-pre-commit-passed-but-ci-is-red) — the most common code-analysis-related symptom.
- [12-packaging](12-packaging.md) — `make.py` invocations.
- [16-guidelines → Coding style](16-guidelines.md#coding-style), [16-guidelines → Verification before commit](16-guidelines.md#verification-before-commit) — normative rules.
- [Programming guidelines](https://gramps-project.org/wiki/index.php/Programming_guidelines) — the standalone wiki page; primary scraped source.
- `../gramps/AGENTS.md` — the full Python coding standard, inherited from gramps core.
