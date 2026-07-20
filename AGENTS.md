# Agent Guidelines for gramps-project/addons-source

This document specifies rules and conventions that agents should follow when
making changes to this repository.

For the normative addon rules — MUST / SHOULD / MAY, with the origin of
each rule (upstream PR, maintainer ruling, Mantis id) cited inline — see
[docs/addon-development/16-guidelines.md](docs/addon-development/16-guidelines.md)
from the Addon Development manual (PR 994). This document covers the
hands-on agent workflow around those rules.

## Repository Overview

`addons-source` holds the source code for third-party Gramps addons —
gramplets, views, tools, reports, importers/exporters, filter rules, database
backends, and other plugins that are not part of Gramps core. It is one of
three tightly-linked repositories:

- **`gramps`** — Gramps core (the application these addons plug into).
- **`addons-source`** (this repo) — addon source code, developed here.
- **`addons`** — built `.addon.tgz` packages and listing JSON consumed by the
  in-app Plugin Manager. Populated from this repo via `make.py`; not edited
  by hand except by the maintainer doing a release build.

There is no unified build or CI pipeline for the whole repo (the checked-in
`.travis.yml` is stale/unused) — each addon is largely independent.

## Branch Model

Branches are per Gramps release, e.g. `maintenance/gramps60`,
`maintenance/gramps61`. **Almost all addon work should target the maintenance
branch matching the current released Gramps version**, not `master`. Only use
`master` for an addon that depends on unreleased Gramps-core features.

Pick the branch carefully:
- When creating a new addon or fixing an existing one, branch from
  `origin/maintenance/gramps6X` (the current release line), not from a local
  tracking branch that may carry unrelated WIP commits.
- When opening the PR, target that same branch on
  `gramps-project/addons-source`.
- Before pushing, sync/rebase against upstream (`git pull --rebase`) so the
  PR applies cleanly.

All PRs must come from a personal fork, never from a branch pushed directly
to `gramps-project/addons-source` (see `CONTRIBUTING.md`, "Commit Your
Changes": "you want to put your changes into _your_ fork, _not_ the upstream
`gramps-project/addons-source` repository").

Weblate translation PRs are the one exception where commits must **not** be
squashed on merge; everything else can be merged/rebased normally.

## Repository Layout

Each addon is a single top-level directory, CamelCase-named to match its
Python import name (e.g. `FilterRules/`, `DataEntryGramplet/`). A directory
typically contains:

- `AddonName.py` — the implementation.
- `AddonName.gpr.py` — the Gramps plugin registration file (required; see
  below).
- `po/` — translation `.po` files, managed by `make.py`.
- `tests/` — optional unit tests (see Testing below).
- `MANIFEST` — optional; lists extra files (docs, data) to include in the
  built package beyond the default `*.py`, `*.glade`, `*.xml`, `*.txt`,
  `locale/*/LC_MESSAGES/*.mo`.
- `locale/` — generated `.mo` files; not something you hand-edit.

Addon directories generally have **no `__init__.py`** (they rely on Python 3
namespace packages) so that Gramps can add each one to `sys.path` at load
time and other addons can `import AddonName` directly.

## Commands

Addon packaging/translation tasks go through `make.py`, run from the repo
root. Point `GRAMPSPATH` at wherever *your* local Gramps checkout lives (it
defaults to `../../..`, i.e. it assumes `make.py` is being invoked from one
level inside a sibling-layout workspace — don't rely on that default, always
set it explicitly), and set `LANGUAGE=en_US.UTF-8`:

```bash
GRAMPSPATH=/path/to/your/gramps LANGUAGE=en_US.UTF-8 python3 make.py gramps61 build AddonDirectory
```

Common subcommands (first positional arg is the branch/version tag, e.g.
`gramps61`):

- `init AddonDirectory [lang]` — scaffold dirs / `.pot` for a new addon, or
  an initial `po/<lang>-local.po`.
- `update AddonDirectory <lang>` — refresh a language `.po` from the `.pot`.
- `compile [AddonDirectory|all]` — compile `.po` → `.mo`.
- `build [AddonDirectory|all]` — produce the downloadable `.addon.tgz`.
- `listing [AddonDirectory|all]` — generate/update the Plugin Manager
  listing JSON.
- `clean AddonDirectory` — strip generated files (`locale/`, `*.pot`, etc.)
  before committing.
- `manifest-check` — validate `MANIFEST` files.
- `as-needed` — build/list/clean only what's out of date, repo-wide.

Unlike `GRAMPSPATH`, the `build`/`listing`/`check` subcommands write to a
**hardcoded relative path**, `../addons/<version>/...` — this isn't a
convention, it's how `make.py` itself resolves the output location, so it
only works if you've cloned the `addons` repo as a sibling of
`addons-source` (see `MAINTAINERS.md` for the recommended three-repo
workspace layout: `gramps` / `addons` / `addons-source` side by side). You
don't need that sibling checkout at all unless you're packaging/publishing
an addon.

You do not need `make.py` just to write/test an addon's Python code — only
when packaging, translating, or updating the listing.

## Testing

Not every addon has tests, but when adding or fixing one, add regression
tests under `AddonName/tests/`, mirroring existing examples (`Form/tests/`,
`DataEntryGramplet/tests/`, `Sqlite/tests/`, `FilterRules/tests/`).

Conventions here differ from Gramps core:

- Test files are named `test_*.py` (pytest-style), **not** the `*_test.py`
  suffix core Gramps uses — `unittest discover` here is invoked per-addon or
  from the repo root without the core `-p "*_test.py"` pattern.
- Still use the `unittest` framework (`unittest.TestCase`), not `pytest`
  APIs, even though filenames follow the `test_*.py` convention.
- `AddonName/tests/__init__.py` should be **empty**. Do not add
  `gi.require_version(...)` pinning there or in individual test modules —
  see GTK/GDK below.
- Because the addon directory has no `__init__.py`, test modules need a
  `sys.path` hack to import it as a namespace package:

  ```python
  ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  if ADDON_DIR not in sys.path:
      sys.path.insert(0, ADDON_DIR)
  ```

  then `from AddonName.addonmodule import SomeClass`.
- Build test data programmatically against a real (temp-dir) database rather
  than relying on fixtures that don't exist in this repo:

  ```python
  from gramps.gen.db.utils import make_database
  from gramps.gen.db import DbTxn

  db = make_database("sqlite")
  db.load(tempfile.mkdtemp(prefix="myaddon_"))
  with DbTxn("build test db", db) as txn:
      ...
  ```
- If a test needs `gramps.gen.filters.CustomFilters`, call
  `reload_custom_filters()` **before** importing the `CustomFilters` name
  from `gramps.gen.filters` — that function rebinds the module-level global
  rather than mutating it in place, so importing the name first leaves you
  with a stale `None`.

### GTK / GDK version pinning

The repo-root `tests/__init__.py` pins `gi.require_version("Gtk", "3.0")` and
`gi.require_version("Gdk", "3.0")` for the whole test suite (added in PR
#950). `gi.require_version` sets process-global state, so **individual addon
test files should not re-pin GTK/GDK** — that's now redundant. A new test
module that imports something pulling in `gramps.gui.*` (which happens at
import time for most GUI-facing addons) only needs a guard for hosts with no
PyGObject at all:

```python
try:
    import gi
except ImportError as err:
    raise unittest.SkipTest("PyGObject not available: %s" % err)
```

Do not add `gi.require_version(...)` calls back into new test files — if you
see them in an addon you're touching, they're safe to remove as redundant
(see the `Themes` addon's `tests/__init__.py` cleanup for precedent), but
don't remove them from files you aren't otherwise changing.

### Running tests

```bash
export GRAMPS_RESOURCES=/path/to/gramps/build/share   # built Gramps checkout
export GDK_BACKEND=-
python3 -m unittest AddonName.tests.test_something -v
```

Run from the `addons-source` repo root so the addon's namespace package
resolves.

## Code Style

- Every new `.py` file needs the same GPL-2.0-or-later header with copyright
  used throughout Gramps core.
- Group imports under comment-banner sections (`Standard Python modules`,
  `GTK/Gnome modules`, `Gramps modules`), matching the style already used
  across this repo (e.g. `FilterRules/isfamilyfiltermatchevent.py`).
- Format with [Black](https://black.readthedocs.io/) — not enforced by a
  checked-in CI workflow here, but the existing codebase is Black-formatted
  and new/changed files should be too (`black <file>`).
- Docstrings: concise; full Sphinx `:param:`/`:returns:` style only when the
  parameters aren't already obvious from the signature.

## Internationalization

Addons manage their own translations, separately from Gramps core. At the
top of an addon's main module:

```python
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
```

(`get_addon_translator` raises `ValueError` if the addon has no
`locale/` translations yet — fall back to the core translator rather than
letting the import crash.) Use `ngettext(singular, plural, n)` instead of a
single `_()` call for any string that counts a noun, for the same reason as
Gramps core: many languages have plural rules English doesn't, and only
`ngettext` lets gettext apply the target language's actual rule.

## Plugin Registration (`.gpr.py`)

Every addon needs an `AddonName.gpr.py` alongside `AddonName.py`:

```python
register(
    RULE,  # or TOOL, GRAMPLET, REPORT, VIEW, GENERAL, IMPORT, EXPORT, ...
    id="uniqueid",
    name=_("Human-Readable Name"),
    description=_("What it does."),
    version="1.0.0",
    gramps_target_version="6.1",
    status=STABLE,  # or UNSTABLE
    fname="AddonName.py",
    authors=["Author Name"],
    authors_email=["author@example.com"],
    help_url="Addon:WikiPageName",
    ...  # PTYPE-specific attributes, e.g. ruleclass/namespace for RULE
)
```

`gramps_target_version` and `version` are required. `help_url` should point
at the addon's Gramps wiki page (`Addon:PageName`), not a GitHub URL.

> **Do not manually change `version` in a PR.** The `MAJOR.MINOR.PATCH`
> version in `.gpr.py` is bumped automatically by the `addons` repo's
> packaging build (`make.py`) when a change is released — the patch
> component increments on its own. Hand-editing it in a source PR just
> creates spurious diffs and can conflict with what the release build
> assigns; leave it as-is unless you're intentionally doing a MAJOR/MINOR
> bump for a breaking addon change.

## Bug Reports and Commit Messages

Bugs against addons are tracked in two places: the shared
[Gramps Mantis BT](https://gramps-project.org/bugs/view_all_bug_page.php)
and, informally, the [Gramps Discourse forum](https://gramps.discourse.group/)
— many addon issues start as a discourse thread rather than a Mantis report.
Unlike Gramps core, this repo has no automated changelog tooling parsing
commit messages, so there's no required `Fixes #N` keyword syntax — just
describe *why* the change was made, and link whatever report (Mantis bug or
discourse URL) motivated it if one exists. Don't invent a Mantis bug number
if you only have a discourse link or user report — link what you actually
have.
