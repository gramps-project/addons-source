# Troubleshoot

[← Previous](08-debug.md) · [Index](01-overview.md) · [Next →](10-code-analysis.md)

<!--
  Symptom-first guide. Each entry: what you see → why → what to do.
  Cross-link the originating bug / PR / triage note where one exists.

  This chapter is largely original — failure modes observed while
  triaging Mantis bugs and reviewing addons-source PRs. There is no
  parallel scraped wiki page; the closest is some overlap with
  debugging-gramps.md, but that page is technique-first (pdb / gdb /
  trace), this one is symptom-first.
-->

## Summary

The failure modes that bite first-time addon authors, organised by symptom. Each entry is "what you see → why → what to do." Read this sideways: jump to the symptom that matches what you're seeing, follow the link out to the relevant chapter for the fix in depth.

The entries are grouped into six families, roughly in the order an addon meets them. **Loading and discovery** — the addon doesn't appear anywhere, edits vanish on restart, or the folder is present but ignored — is where most first-day problems land, and the cause is usually the plugin path, a `.gpr.py` error swallowing the whole addon, or the symlink rule. **Imports and Python namespace traps** covers the ones that look like Python bugs rather than Gramps bugs: `from <Addon> import <Addon>` binding the submodule instead of the class, `requires_mod` naming the PyPI distribution instead of the importable module, and a `requires_gi` declaration that is valid on 6.0 and broken on 6.1.

**Database access** covers the errors that only appear on real data — a `KeyError` partway through an iteration, backlinks returning a class *name* rather than a class, and the mocked test that passes while `example.gramps` fails. **Translation and locale** covers the two classic reports: strings marked with `_()` that never translate, and an addon that translates on one platform but not another. **Testing** covers the gap between your machine and CI, and between the pre-commit hook and the CI run — they check different things, so green locally is not green upstream. **Pull-request shape** covers what gets a submission bounced rather than reviewed: a rejected version bump, a duplicate, or a PR that simply sits.

If nothing here matches, the problem is probably not a known pattern — go to [08-debug](08-debug.md) for the technique-level coverage (log levels, repro scripts, pdb, gdb, profilers) and work it from the evidence. For the normative rules an addon must satisfy, see [16-guidelines](16-guidelines.md).

## Loading and discovery

### "My addon doesn't appear in any menu."

The addon failed to register. Three usual causes, in order of likelihood:

1. **`.gpr.py` raised at import.** Plugin discovery executes every `.gpr.py` at startup; a `SyntaxError` or import failure there silently drops the addon from the catalog. Launch from a terminal to see the traceback on stderr, or check the Gramps log window (Help → Log) for the failure entry.

2. **`gramps_target_version` mismatch.** A `6.0` addon won't load in 6.1, and vice versa. Plugin discovery silently skips the registration entry. See [14-compatibility → `gramps_target_version` semantics](14-compatibility.md#gramps_target_version-semantics).

3. **`id` doesn't match the folder name.** The addon's folder name and the `id` argument to `register(...)` must be identical. Gramps does not match by content — it matches by folder name and verifies against `id`. A mismatch silently drops the entry.

The fastest check: in a Python REPL with `gramps` on `sys.path`, `exec(open("MyAddon/MyAddon.gpr.py").read())`. If it raises, you have your cause; if it returns silently and there's no entry, your `register()` call is being filtered out.

### "My edits to the plugin file disappeared on restart."

The user plugin directory (`~/.local/share/gramps/gramps60/plugins/…`) is the auto-sync **target**. Edits there are silently overwritten on the next save from `addons-source/`.

**The fix.** Edit in `addons-source/<Addon>/` and let the sync flow do its job — see [12-packaging → Editing `addons-source/`, not the live plugin directory](12-packaging.md#editing-addons-source-not-the-live-plugin-directory).

On Gramps 6.1+ Linux/macOS, symlinking the working tree into the user plugin directory once eliminates the copy step (commit `9443dcbb30`); on Gramps 6.0 and on Windows generally, the copy / `rsync` loop remains.

### "The addon's folder is there but Gramps doesn't load it."

The most common variants of the previous symptom, when ruled out:

- **6.0 only**: the folder is reached via a symlink. Gramps 6.0 plugin discovery does **not** follow symlinks; use a physical copy or upgrade to 6.1+. (See [14-compatibility → Plugin discovery follows symlinks](14-compatibility.md#plugin-discovery-follows-symlinks).)
- **Windows, any version**: same as above — the 6.1 symlink test is skipped on Windows because the platform's symlink behaviour is inconsistent without elevated privileges. Physical copy.
- **`.gpr.py` not at top level of folder**: the registration file has to be `<Addon>/<Addon>.gpr.py`, not in a subfolder.

## Imports and Python namespace traps

### "`from <Addon> import <Addon>` binds the submodule, not the class."

The classic Gramps namespace-package trap.

The addon folder is a *namespace package* (PEP 420), so importing `<Addon>` gives you the package, not the class inside the like-named module. Code that worked under `discover`-based test loading breaks under dotted-path loading because the resolution path is different.

**The fix.** Use the explicit submodule form:

```python
# Wrong: binds the package (silently — until you try to use the class)
from MyAddon import MyAddon

# Right: binds the class inside the module
from MyAddon.MyAddon import MyAddon
```

Mantis bug [12691](https://gramps-project.org/bugs/view.php?id=12691) is the canonical case. Upstream CI loads addon tests by dotted path rather than `discover` exactly to surface this trap; see [07-testing](07-testing.md).

### "`requires_mod` declares `Pillow` but Gramps says it's missing."

`requires_mod` takes the **importable** module name, not the PyPI distribution name:

| PyPI name      | Importable name |
|----------------|-----------------|
| `Pillow`       | `PIL`           |
| `PyYAML`       | `yaml`          |
| `lxml`         | `lxml`          |
| `python-dateutil` | `dateutil`   |
| `Beautifulsoup4` | `bs4`         |

**The check.** Before pushing, verify on a system with the package installed:

```python
from importlib.util import find_spec
assert find_spec("PIL") is not None
```

If `find_spec` returns `None`, the name in `requires_mod` is wrong.

### "`requires_gi` declaration is fine on 6.0, broken on 6.1."

GExiv2's version handling was rewritten on `maintenance/gramps61` only (addons-source PR [829](https://github.com/gramps-project/addons-source/pull/829)). An addon with `requires_gi=[("GExiv2", "0.10")]` that works on 6.0 may need a different pin on 6.1.

**The fix.** Read the EditExifMetadata addon's GExiv2 code on the target branch before assuming a pin transfers. See [14-compatibility → GExiv2 version handling rewritten](14-compatibility.md#gexiv2-version-handling-rewritten).

## Database access

### "My addon iterates the DB but raises `KeyError` halfway through."

The DB contains a reference to a handle that no longer resolves. This happens in real-world data; mocked tests don't exhibit it because mocks always return the same fixed set.

**The fix.** Always guard handle dereferences:

```python
event = db.get_event_from_handle(handle)
if event is None:
    continue   # silently skip dangling reference
```

See [05-data-access → Reading: one object at a time](05-data-access.md#reading-one-object-at-a-time) for the pattern. The same shape applies to every `get_<type>_from_handle` call.

### "Backlinks return `(class_name, handle)` not `(class, handle)`."

`db.find_backlink_handles(handle)` yields tuples whose first element is the **class name as a string** (`"Person"`, `"Family"`, …), not the Python class itself. The most common bug here is `isinstance` checks that never match.

```python
# Wrong:
for cls, h in db.find_backlink_handles(handle):
    if cls is Person:   # always False — cls is "Person"
        ...

# Right:
for type_name, h in db.find_backlink_handles(handle):
    if type_name == "Person":
        ...
```

### "The fix worked in my mocked test but breaks on `example.gramps`."

Real data has shapes the mock doesn't model:

- **Cross-typed backlinks** — a Source can be backlinked from a Person, a Family, an Event, a Place, a Media, a Note, a Citation, and a Repository. Mocks tend to model only the type the test author was focused on.
- **ID normalisation** — `I0001` vs `I0021` vs `I12345`. A regex that matches the mock's 4-digit IDs misses the real data's variable-width IDs.
- **Optional fields actually being absent** — `person.get_birth_ref()` returns `None` in real data far more often than in mocks.

**The fix.** Add an `example.gramps`-backed test alongside the mock. See [05-data-access → Testing data access](05-data-access.md#testing-data-access) and [07-testing](07-testing.md).

## Translation and locale

### "My addon translates fine on Linux, not on Windows" (or vice versa).

The two platforms set up the locale differently:

- **Linux** — needs `locale-gen` for the language and the `LANGUAGE` env var set (not just `LANG`).
- **Windows** — reads `LANG` directly via `win32locale.py`, no OS locale config needed.

**The fix in repro scripts.** Sidestep both by instantiating `GrampsLocale(localedir, languages)` directly — see [08-debug → Reproduction scripts that bypass the GUI](08-debug.md#reproduction-scripts-that-bypass-the-gui).

**The fix in production.** Make sure the per-addon `.po` files compile cleanly on both platforms (`make.py compile <Addon>` in addons-source). A `.mo` file that's missing or malformed will silently fall back to English on whichever platform fails to load it.

### "Strings I marked with `_()` aren't translated."

You've forgotten to bind `_` to the addon's catalog. At the top of the implementation module:

```python
from gramps.gen.const import GRAMPS_LOCALE as glocale

_ = glocale.get_addon_translator(__file__).gettext
```

Without that line, `_()` falls back to Gramps' core catalog rather than the addon's own `<Addon>/po/` translations. The strings stay English regardless of UI language. See [04-fundamentals → Translation](04-fundamentals.md#translation).

## Testing

### "Tests pass locally, fail in CI."

Three common causes:

1. **Filename prefix wrong for the platform.** `test_linux_*.py` is skipped on the Windows runner, `test_windows_*.py` is skipped on Linux. A test you intended as cross-platform but accidentally named with a prefix runs only where the prefix points. See [07-testing → Filename conventions](07-testing.md#filename-conventions-addons-source-ci).

2. **`requires_mod` deps assumed in tests.** Addon tests must be runnable without the addon's `requires_mod` dependencies installed in the test Python — Mac contributors can't easily install addon deps into the Gramps Python (Gary Griffin, 2026-05-16). Mock at the import boundary or skip cleanly.

3. **Test loaded by dotted path surfaces the namespace trap.** Local `discover` from `tests/` would hide the `from <Addon> import <Addon>` bug; CI loads by dotted path (`<Addon>.tests.<module>`), which exposes it. See bug 12691.

### "`CustomFilters` is `None` in my test."

`gramps.gen.filters` initialises `CustomFilters = None` at import and only populates it when `reload_custom_filters()` runs — and that function **rebinds the module global** rather than mutating an object in place (`gramps/gen/filters/__init__.py:24`, `:38-41`):

```python
def reload_custom_filters():
    global CustomFilters
    CustomFilters = FilterList(CUSTOM_FILTERS)
    CustomFilters.load()
```

So importing the *name* first captures the `None` and never sees the replacement:

```python
# Wrong — binds None for good
from gramps.gen.filters import CustomFilters, reload_custom_filters
reload_custom_filters()

# Right — reload, then import the name
from gramps.gen.filters import reload_custom_filters
reload_custom_filters()
from gramps.gen.filters import CustomFilters
```

Inside Gramps the view manager calls it during startup, which is why this only bites under test. Core's own suites do the same thing at module import time (`gramps/test/test_util.py:41`, `gramps/gen/filters/rules/test/person_rules_test.py:34`). Called out in upstream [`addons-source/AGENTS.md`](https://github.com/gramps-project/addons-source/blob/maintenance/gramps61/AGENTS.md) → Testing.

### "PR's pre-commit passed but CI is red."

Pre-commit catches static checks only. Test failures (e.g. an import that breaks at module load) surface in CI's actual unit-test run, not in pre-commit. After pushing, watch the PR's checks until they finish:

```bash
gh pr checks <PR#> --watch
```

See [16-guidelines → Verification before commit](16-guidelines.md#verification-before-commit).

## Pull-request shape

### "`.gpr.py` version bump rejected on PR."

addons-source PRs do **not** bump the addon's `version` field. The maintainer manages versions centrally. Leave the `version = "…"` line in `.gpr.py` untouched. (Tripped on addons-source PR 911.)

### "PR sits without review."

Two things to check:

1. **Branch target.** `addons-source` PRs target `maintenance/gramps60`, not `master`. Gary cherry-picks forward to `gramps61`. Core PRs target `maintenance/gramps61`. A PR against the wrong branch may sit untouched waiting for retargeting. See [16-guidelines → Contributor workflow](16-guidelines.md#contributor-workflow).

2. **PR body shape.** Reviewers expect a **`**User impact:**`** opener (before Root cause), then *Summary / What to look at / Root cause / Fix / Verification* (the #106 format). A PR body that leads with internals instead of the user-visible effect often returns without a substantive review until it conforms.

### "PR was rejected as duplicate."

You wrote a fix without checking that upstream already had one in flight. The pre-flight check is [16-guidelines → Contributor workflow](16-guidelines.md#contributor-workflow) — the bullets about "check upstream isn't ahead" and "if a PR already exists, VERIFY it, do not duplicate." Searching by **affected file path**, not just the bug number, is the part that catches the most duplicates.

## See also

- [08-debug](08-debug.md) — technique-level coverage for reproducing what these symptoms describe.
- [07-testing](07-testing.md) — the test conventions that catch many of these symptoms before they reach a user.
- [12-packaging](12-packaging.md) — the source-to-distribution flow, where the "edits disappeared" trap lives.
- [14-compatibility](14-compatibility.md) — the 6.0 vs 6.1 deltas behind several entries here.
- [16-guidelines](16-guidelines.md) — normative reference; this chapter describes what *goes wrong*, that chapter describes what *must hold*.
- [Mantis bug tracker](https://gramps-project.org/bugs) — where the recurring failures get filed.
