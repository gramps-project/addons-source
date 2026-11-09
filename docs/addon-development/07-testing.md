# Testing

[← Previous](06-api-reference.md) · [Index](01-overview.md) · [Next →](08-debug.md)

<!--
  Sources:
    - per-OS filename prefixes from addons-source ci.yml
    - dotted-path loading from upstream ci.yml
    - example.gramps vs mocks
    - requires_mod no-deps rule (Gary Griffin, 2026-05-16)
    - tests/__init__.py convention (Gary Griffin's PR 930)
    - GTK-pin contract: pins live at the REPOSITORY root's
      tests/__init__.py (addons-source PR 950); per-addon
      tests/__init__.py stays empty (Eduard, 2026-07-20)
  Cross-link to 08-debug for repro scripts, 09-troubleshoot for what
  these tests catch.
-->

## Summary

How to test an addon without launching the GUI on every iteration — the test framework, the layout conventions, the fixtures that work, and the platform-aware rules that keep tests portable across Linux, Windows, and Mac.

A working test suite is what makes an addon **maintainable across Gramps releases**. The matrix of (Gramps version × OS) makes manual testing impossible at scale; the per-OS prefix conventions below let a single CI matrix verify your addon against every supported combination automatically.

The page starts with the ground rules: the framework is **stdlib `unittest`** and nothing else — no pytest, no third-party runner — plus the class-header convention and the `tests/` **layout** each addon follows, including why the per-addon `tests/__init__.py` exists and why it must stay empty. Two sections then cover the mechanics that are easy to get wrong: the **GTK-pin contract** (Gramps pins the GObject-introspection versions once at startup, so an addon module must never call `gi.require_version` itself — the pin belongs in the addons-source repo-root `tests/__init__.py`, and copying it into a module produces the works-in-tests, breaks-in-Gramps failure) and **loading by dotted path** rather than by filesystem path or `unittest discover`, which is what keeps the namespace-package semantics intact.

The middle of the page is about writing tests that hold up. **Mocked versus `example.gramps`-backed** weighs the two fixture styles and says when each is the right call — a mock is fast and precise, the shipped example tree is realistic and catches assumptions a mock would rubber-stamp. **Tests must run without `requires_mod` dependencies** covers keeping a suite green on a machine that lacks your addon's optional imports, by mocking at the import boundary or skipping cleanly. **What to test** and **what the test catches that the GUI doesn't** are the judgement calls: what is worth asserting, and why a passing manual click-through is weaker evidence than it feels. The closing section is the concrete commands for **running tests locally**, per addon and for the whole suite.

One convention on the page belongs to CI rather than to your own runs: the **filename prefixes**. Test files are `test_*.py`, and the `test_linux_*`, `test_windows_*`, and `test_integration_*` variants scope a file to where it can actually run — which is what lets one CI matrix cover both Linux and Windows without either runner failing on tests that were never meant for it.

## Framework: stdlib `unittest`

Use stdlib `unittest`. Don't use pytest.

Gramps itself standardises on `unittest` (subclasses of `unittest.TestCase`), which keeps addon tests contributable upstream without a framework-conversion step. Mixing pytest features (fixtures, parametrise, plugins) breaks contribution upstream where pytest isn't installed.

```python
import unittest


class MyAddonTests(unittest.TestCase):
    def test_handles_empty_input(self):
        # ...
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
```

### Class header convention

The "class header navigation comment" rule from gramps' AGENTS.md is unconditional — it applies to `unittest.TestCase` subclasses too. PR 2326 round 2 caught the omission:

```python
# ------------------------------------------------------------
#
# MyAddonTests
#
# ------------------------------------------------------------
class MyAddonTests(unittest.TestCase):
    ...
```

## Layout

Each addon ships its tests in a `tests/` subpackage:

```
MyAddon/
├── MyAddon.gpr.py
├── MyAddon.py
└── tests/
    ├── __init__.py            # marker — see below
    └── test_myaddon.py
```

### Why `tests/__init__.py` exists

The marker is **hygiene, not a bug fix**. Python 3.3+'s implicit namespace packages (PEP 420) mean a directory without `__init__.py` is still importable; dotted-path loading (`python3 -m unittest MyAddon.tests.test_myaddon`) works either way. But:

1. **Explicit beats implicit.** "It works" is currently true by accident of invocation. The same code breaks the moment something uses `discover` or assumes regular packages.
2. **Explicit — and empty.** Suite-wide test setup (the GI version pins, warning filters) lives at the *repository* root's `tests/__init__.py`, not per addon — see the next section. The per-addon marker stays empty; it is packaging hygiene, and a home for genuinely addon-local setup only if one ever appears.

The convention crystallises as: every addon's `tests/` **should** have an `__init__.py`; the addon directory itself **should not**.

The asymmetry matters, though not for the reason it is often given. Gramps' plugin loader puts the addon dir itself on `sys.path` and imports the `fname` module as a *top-level* name, so an addon-root `__init__.py` never runs at load time and does not break the addon — seven addons on `maintenance/gramps60` ship one and work. What it does is make the same file importable under two names (top-level at runtime, `<Addon>.<module>` from the repo root under test), which yields two module objects and two copies of everything in them. Keeping the addon root a plain directory keeps the two views identical; the `tests/` subfolder has no such concern, so making it an explicit package is free. See [16-guidelines → Structure](16-guidelines.md#structure) for the full rule and the one legitimate exception.

This is what [addons-source PR 930](https://github.com/gramps-project/addons-source/pull/930) (Gary Griffin) is moving toward.

## The GTK-pin contract

Gramps establishes the GObject-introspection environment **once, at startup, before any plugin loads**: `gi.require_version("Gtk", "3.0")` and `gi.require_version("Gdk", "3.0")` run in `gramps/grampsapp.py` and `gramps/gen/constfunc.py`. Every addon module therefore does `from gi.repository import Gtk` into an already-pinned namespace — inside Gramps, the pin is never the addon's job.

**The trap.** Run that module under bare `unittest` and the import warns (or resolves a different GTK) because nothing has pinned yet. The tempting fix is to copy the `gi.require_version` call into the addon module or the test file. Tests now pass — but the pin also executes inside Gramps, where it is redundant at best and a hard failure the moment the hardcoded pin and the version Gramps runs diverge: `gi.require_version` raises `ValueError` once the namespace is already loaded at a different version. That is the *works-in-tests, breaks-in-Gramps* failure mode, and it is invisible to CI because CI only runs the tests.

**The contract**, in two halves:

1. **Modules never pin.** No `gi.require_version` in the addon module or in any test file — the environment is provided *to* them, in both contexts. Redundant pins are safe to remove from files you are already touching (the Themes addon's `tests/__init__.py` cleanup is the precedent), but don't churn files you aren't otherwise changing.
2. **The repository root provides what Gramps provides.** addons-source carries the pins **once**, in the repo-root `tests/__init__.py` (addons-source PR [950](https://github.com/gramps-project/addons-source/pull/950)): the repo-root suite run and the CI runners import that package before any test module, pinning the whole suite to the GTK 3 / GDK 3 stack a real Gramps session uses (it also silences the locale warnings that uncompiled source-tree addons legitimately emit). The per-addon `MyAddon/tests/__init__.py` stays **empty** — see the previous section.

The one thing a GUI-touching test module may still need is a presence guard for hosts with no PyGObject at all:

```python
try:
    import gi
except ImportError as err:
    raise unittest.SkipTest("PyGObject not available: %s" % err)
```

**The corollary: run from the repository root.** The pins execute when the root `tests` package loads — the repo-root suite run and CI's per-addon runners do that. Run your own invocations from the addons-source root too (the dotted-path form below), and never run a test file by filesystem path (`python3 MyAddon/tests/test_myaddon.py`) — the shortcut that pushes pins back into the modules, and that bypasses the namespace-package semantics the loading section below relies on.

The GI pins are one instance of a wider rule: everything process-global that Gramps' startup owns — locale, the root logger, `sys.path`, the GTK main loop, `sys.excepthook`, environment variables — follows the same contract. The full startup surface, with the per-item temptations and alternatives, is tabulated in [04-fundamentals → The provided environment](04-fundamentals.md#the-provided-environment).

## Filename conventions (addons-source CI)

addons-source's CI workflow filters tests by **filename prefix** to scope them per platform:

| Prefix                  | Where it runs                                  |
|-------------------------|------------------------------------------------|
| `test_*.py`             | All platforms (Linux + Windows)                |
| `test_linux_*.py`       | Linux only                                     |
| `test_windows_*.py`     | Windows only                                   |
| `test_integration_*.py` | Linux only — full-pipeline / DB-backed         |

The Ubuntu runner skips `test_windows_*`; the Windows runner skips both `test_linux_*` and `test_integration_*`. Both runners include the platform-neutral `test_*.py` files.

**Pick the prefix that matches the test's portability**, not the platform you happen to be developing on. A test that exercises POSIX file paths goes under `test_linux_*`; a test that exercises win32 locale handling goes under `test_windows_*`; everything else, the plain `test_*.py` prefix.

CI's workflow file is authoritative: [addons-source/.github/workflows/ci.yml](https://github.com/gramps-project/addons-source/blob/maintenance/gramps60/.github/workflows/ci.yml).

## Loading: dotted path, not `discover`

Upstream CI loads tests by **dotted path**:

```bash
python3 -m unittest MyAddon.tests.test_myaddon
```

Not by `discover` from inside an addon's `tests/` directory, and never by filesystem path. Dotted-path loading from the repo root surfaces the namespace-package trap. Bug 12691 — `from <Addon> import <Addon>` binding the submodule instead of the class — only shows up under dotted-path loading. `discover`-based loading walks files by *filename*, hiding the import-resolution issue. Mirroring CI's invocation locally catches what CI catches.

Locally, from the `addons-source` root, the same invocation works:

```bash
# Run one test module
python3 -m unittest MyAddon.tests.test_myaddon

# Run every test in the addon's tests/ package
python3 -m unittest discover -s MyAddon/tests -t .
```

The discover form here works because the addon directory is the import root — the namespace-package trap shows up only when an *individual addon module* mis-imports itself.

## Mocked vs `example.gramps`-backed tests

Two complementary strategies. They're not alternatives.

### Mocked unit tests

Fast, no DB on disk, suitable for tight branch-coverage of pure logic. Substitute the database with a stub that returns fixed objects:

```python
import unittest
from unittest.mock import MagicMock


class HappyPathTests(unittest.TestCase):
    def test_skips_people_without_birth(self):
        person = MagicMock()
        person.get_birth_ref.return_value = None

        result = pure_logic(person)

        self.assertEqual(result, expected)
```

The MagicMock approach has a built-in failure mode: it returns something for *every* method call, so a typo'd method name appears to work. Real DB code that fails on the next call will pass the mocked test. This is the bug the next strategy catches.

### `example.gramps`-backed tests

`example.gramps` ships with the Gramps source under `example/gramps/example.gramps`. It's the canonical fixture triage and developers reproduce against; loading it produces a real populated database with the cross-typed backlinks, ID normalisations, and absent optional fields that real users hit.

```python
import os
import unittest
from gramps.gen.db.utils import open_database


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = open_database(
            os.path.expanduser("~/path/to/gramps/example/gramps/example.gramps")
        )

    def test_handles_real_data(self):
        result = code_under_test(self.db)
        self.assertGreater(len(result), 0)
```

Name these `test_integration_*.py` so CI scopes them to Linux only (loading a real DB is heavier, and Windows CI's Gramps setup is separately constrained — see [14-compatibility → Windows toolchain migrated to UCRT64](14-compatibility.md#windows-toolchain-migrated-to-ucrt64)).

### Choosing between them

| Use the mock when                                 | Use `example.gramps` when                                 |
|---------------------------------------------------|-----------------------------------------------------------|
| The function under test takes pure inputs         | The function traverses the DB                             |
| You're covering many input shapes (loop / branch) | You're verifying *one* real-world scenario                |
| You need sub-millisecond turnaround               | You need real-data shape (backlinks, IDs, optional refs)  |

The lesson, learned the hard way: mocked tests can pass while real-DB tests fail, because the mock doesn't model what production data looks like.

## Tests must run without `requires_mod` deps

A hard constraint, set by Gary Griffin (2026-05-16): addon tests must run cleanly without the addon's `requires_mod` dependencies installed in the Python that runs them. Mac contributors can't easily install addon deps into the Gramps Python on macOS, and there's no Gramps debug-mode equivalent on Mac to work around it.

Two ways to honour this:

### Mock at the import boundary

```python
import sys
from unittest.mock import MagicMock

# Stand in for an optional dep before importing the addon.
sys.modules.setdefault("PIL", MagicMock())
sys.modules.setdefault("PIL.Image", MagicMock())

from MyAddon.MyAddon import code_under_test
```

Cleaner than try/except, and the test asserts the addon's behaviour **with the dep present** — what almost every real user sees.

### Skip cleanly

When mocking is impractical (e.g. the dep is core to the function under test), skip without erroring:

```python
import unittest
from importlib.util import find_spec


@unittest.skipUnless(find_spec("PIL"), "Pillow not installed")
class PhotoTaggingTests(unittest.TestCase):
    def test_loads_jpeg(self):
        ...
```

A failed import at module load — instead of a `skipUnless` — turns into a test error on the Mac runner, blocking the CI suite.

## What to test

Mandatory:

- **The bug a fix closes.** Every bug fix ships with a test that fails pre-fix and passes post-fix. At PR level this is a [16-guidelines MUST](16-guidelines.md#contributor-workflow): the regression test, or an explicit "no test because X" rationale plus a manual repro — "add the test later" is not an option. Doc-only PRs are the only exception.

Strongly recommended:

- **One happy-path call** through the addon's main entry point. The smoke test that catches the next breakage.
- **One real-data scenario** against `example.gramps` for any DB-traversal code.

Optional but valuable:

- **Edge cases** the function explicitly handles: empty DB, missing optional fields, IDs at the boundaries of normalisation.

What *not* to test:

- The Gramps API itself. If `db.get_person_from_handle(h)` returns `None` for a missing handle, that's Gramps' contract; your test exercises that **your code handles `None`**, not that Gramps returns it.

## What the test catches that the GUI doesn't

A test surfaces failure modes the GUI cycle hides:

- **The namespace-package trap** (bug 12691) — surfaces under dotted-path loading.
- **`requires_mod` typos** — `from <pypi-name> import …` would fail import; surfaces immediately at test load.
- **DB-shape assumptions** — the cross-typed-backlinks / ID-norm issues that mocked tests miss.
- **Per-OS regressions** — running on both runners.

See [09-troubleshoot](09-troubleshoot.md) for the symptoms-to-cause mapping for these classes of failure.

## Running tests locally

From the `addons-source` checkout root:

```bash
# Run one addon's tests
python3 -m unittest discover -s MyAddon/tests -t .

# Or invoke a single test module by dotted path (mirrors CI's invocation)
python3 -m unittest MyAddon.tests.test_myaddon
```

Run from the addons-source root, and never invoke a test file by filesystem path — see [the GTK-pin contract](#the-gtk-pin-contract).

The Python that runs the tests needs `gramps` importable. The simplest setup is `PYTHONPATH=/path/to/gramps python3 -m unittest …`; if Gramps is installed system-wide, the import resolves without `PYTHONPATH`.

On Windows, run from the MSYS2 UCRT64 shell against a UCRT64-installed Gramps — the AIO build for Gramps 6.1+ targets UCRT64; Gramps 6.0 isn't Windows-tested upstream. See [14-compatibility → Windows toolchain migrated to UCRT64](14-compatibility.md#windows-toolchain-migrated-to-ucrt64).

## See also

- [04-fundamentals → Logging](04-fundamentals.md#logging) — `LOG` setup that tests assert against.
- [05-data-access → Testing data access](05-data-access.md#testing-data-access) — DB-API patterns to exercise.
- [08-debug](08-debug.md) — turning a repro script into a test.
- [09-troubleshoot](09-troubleshoot.md) — the symptoms these tests catch in CI rather than production.
- [10-code-analysis](10-code-analysis.md) — what the static checkers verify before tests run.
- [16-guidelines → Testing](16-guidelines.md#testing) — normative rules.
- [Mantis 12691](https://gramps-project.org/bugs/view.php?id=12691) — the canonical namespace-package trap that motivates dotted-path loading.
- [addons-source PR 930](https://github.com/gramps-project/addons-source/pull/930) — `tests/__init__.py` convention.
