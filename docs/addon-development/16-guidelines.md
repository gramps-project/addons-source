# Rules

[← Previous](15-whats-new.md) · [Index](01-overview.md) · [Next →](17-roadmap.md)

## Summary

Normative reference for addon authors. Conceptual / how-to material lives in the other section pages; this page enumerates the guidelines and is the one to cite in code review.

Rules are stated with RFC 2119 keywords — **MUST** marks a requirement whose violation is a defect, **SHOULD** a strong recommendation you may deviate from with a stated reason, **MAY** an allowance — and where a rule has a known origin, an upstream PR or a maintainer ruling or a Mantis bug, it is cited inline so the rule is auditable rather than folklore. **Repository scope** sets the boundary before any of that: this page governs `addons-source`, not Gramps core, and the two diverge on branch target, test layout, translation tooling, and which static checks are enforced. Where this page is silent, core's rules fill the gap; where it is prescriptive on an addon-specific concern, it wins. Where either disagrees with the authoritative upstream source on the target branch, that source wins.

The rules themselves run through the life of an addon. **Structure** and **Source location** cover the folder, its name, and where the code belongs. **Translation** covers what must be marked and how. **Runtime** is the densest section and the one worth reading in full even if you skim the rest: every database write inside a `DbTxn`, `requires_mod` naming importable modules rather than PyPI distributions, `requires_gi` pins verified against the branch you target, and a firm list of process-global state an addon must not touch — the GTK main loop, screen-wide CSS, `sys.excepthook`, the root logger, `locale.setlocale`, `os.environ`. An addon is a guest in Gramps' process. **Testing** and **Coding style** cover the test layout and the standard inherited from core.

The last three sections are about getting a change accepted rather than written: the **contributor workflow**, the **verification to run before commit**, and **commit messages** — including the Mantis trailer keywords that close a tracker issue automatically, and the separate convention for referencing a bug in an addons-source PR body.

## Repository scope

- **This page applies to the addon repository — [`gramps-project/addons-source`](https://github.com/gramps-project/addons-source).** It does **not** govern Gramps core.
- Core contributions (`gramps-project/gramps`) follow the separate [Core Development — Rules](https://gramps-project.org/wiki/index.php/Gramps_6.1_Wiki_Manual_-_Core_Development_-_Rules) page. The two repositories diverge on branch target, test layout, translation tooling, and which static checks are enforced — do not transfer a rule across without checking it here.
- The full Python coding standard is inherited from core's `../gramps/AGENTS.md`; this page restates the parts addon code review enforces and adds the addon-specific structure, packaging, and translation rules that live outside that file.
- **This page now ships in the repository it governs.** The manual was imported into `addons-source` as `docs/addon-development/` (addons-source PR [994](https://github.com/gramps-project/addons-source/pull/994), merged 2026-07-24, on both `maintenance/gramps60` and `maintenance/gramps61`), and `README.md` / `CONTRIBUTING.md` point at it (PR [995](https://github.com/gramps-project/addons-source/pull/995)). It is no longer only a wiki restatement of upstream practice — upstream carries it.
- **`addons-source/AGENTS.md` and this page split the work deliberately.** The repository's `AGENTS.md` (PR [991](https://github.com/gramps-project/addons-source/pull/991), merged 2026-07-26 on `maintenance/gramps61`) cites `docs/addon-development/16-guidelines.md` for "the normative addon rules — MUST / SHOULD / MAY, with the origin of each rule cited inline" and confines itself to the hands-on workflow around them: `make.py` invocations, how to run the tests, the MSYS2-versus-native-Windows caution, branch selection and fork-PR mechanics. Read `AGENTS.md` for *how to operate the repository*, this page for *what the rules are*. Because the citation runs that way, a contradiction between the two is a defect in upstream's own documentation — report it rather than picking a side.
- **When in doubt, the authoritative source wins and is what to check.** These pages are a convenience restatement. On coding style, core's `../gramps/AGENTS.md` is the source of truth; on addon-specific rules, the authority is upstream `addons-source` — its `CONTRIBUTING.md`, its `AGENTS.md`, and a maintainer's ruling on the PR. Where this page is silent, ambiguous, or disagrees with the authoritative source on the *target branch*, that source wins — verify against it rather than relying on this page from memory.
- **Core stands in where this page doesn't — one way only.** Where this page is not specific or prescriptive on a point, the [Core Development — Rules](https://gramps-project.org/wiki/index.php/Gramps_6.1_Wiki_Manual_-_Core_Development_-_Rules) page (and core's `AGENTS.md`) is the default that fills the gap — addons inherit from core. The fallback runs in this direction only: where this page *is* prescriptive on an addon-specific concern (structure, packaging, branch target, test layout — `tests/` + `test_*.py`, `maintenance/gramps60`), it governs and core does not override it; and the addon guidelines never fill a gap in the core page.

## Conventions

RFC 2119 keywords, with our short forms:

| Keyword | Meaning |
|---------|---------|
| **MUST** / **MUST NOT** | Required; a violation is a defect |
| **SHOULD** / **SHOULD NOT** | Strongly recommended; deviate only with a stated reason |
| **MAY** | Allowed |

Where a rule has a known origin — an upstream PR, a maintainer ruling, a Mantis bug — it's cited inline so the rule is auditable.

## Structure

- **MUST**: the addon's folder name is a valid Python import name (an importable identifier — no spaces). Gramps puts each addon's directory on `sys.path` and addons share code via `import <FolderName>` (see [the upstream Addons development page](https://gramps-project.org/wiki/index.php/Addons_development) → "name your addons with a name appropriate for Python imports"). The folder name need **not** match the `id` in `.gpr.py`: the registration `id` is an independent plugin key and routinely differs (e.g. folder `DeepConnectionsGramplet` ↔ id `Deep Connections Gramplet`), and one folder may register several plugins with unrelated ids.
- **MUST**: `.gpr.py` declares `gramps_target_version` matching the Gramps minor the addon targets.
- **MUST**: `fname` points to an implementation module shipped in the same folder.
- **MUST**: the addon is physically present under the plugin path — a physical copy works on every Gramps version and OS. (Gramps 6.1+ also discovers an addon reached via a symlink, but a physical copy is the portable default.)
- **MUST NOT**: import `register`, `GRAMPLET`, `STABLE`, `_`, or any other name Gramps injects into the `.gpr.py` namespace.
- **SHOULD NOT**: add `__init__.py` to the addon directory itself — keep the addon root a plain directory, with the `__init__.py` marker only in `tests/`. (See [07-testing → Why `tests/__init__.py` exists](07-testing.md#why-tests__init__py-exists).)
  - It does **not** break plugin loading. `PluginManager.import_plugin` inserts the addon's *own* directory at `sys.path[0]` and calls `__import__(mod_name)` — a top-level import — so an addon-root `__init__.py` is never executed on the runtime path (`gramps/gen/plug/_manager.py:300-343`).
  - What it costs is consistency across contexts. Run from the addons-source root, as tests are, the same file is also reachable as `<Addon>.<module>`: two module objects, two copies of every class and module-level global, so identity checks and cached state diverge between the runtime and the test view. The package form also invites `from .module import X`, which fails under the runtime path where that module is top-level — which is exactly why `PostgreSQLEnhanced/__init__.py` needs its `try: from .postgresqlenhanced import … / except ImportError:` `sys.path` fallback.
  - **MAY**, therefore, when an addon genuinely needs to expose a package API (a `DATABASE` backend, say) — provided the module named by `fname` imports by bare name and never relatively.
  - **Not** the [Mantis 12691](https://gramps-project.org/bugs/view.php?id=12691) trap. That one is `from <Addon> import <Addon>` binding the submodule instead of the class, and it comes from the addon dir's *parent* being on `sys.path`; a namespace package binds the submodule identically. `__init__.py` neither causes it nor cures it — the earlier version of this rule cited 12691 in support, which it does not.
  - Seven addons on `maintenance/gramps60` ship one today — `DynamicWeb`, `ExcludeSubtreeFilter`, `GrampyScript`, `PlaceCleanup`, `PostgreSQLEnhanced`, `Query`, `Sqlite` (six of the seven files are empty) — and they work. That is why this is a **SHOULD NOT** and not a **MUST NOT**: a rule seven shipping addons violate without producing a defect does not meet this page's own bar for MUST.
- **MUST** (`TOOL` kind): register an `optionclass` even when the tool takes no options. Gramps refuses to load a `TOOL` without one; an empty `tool.ToolOptions` subclass is sufficient.
- **SHOULD**: ship a `po/` directory with at least `template.pot` if any user-visible string exists. Generate it with `make.py init <Addon>` (see [12-packaging](12-packaging.md)); if it's missing the maintainer creates it on initial check-in.
- **MAY**: ship a `tests/` package with an `__init__.py` marker and at least one test — most existing addons predate addon unit tests. When tests are shipped, the `__init__.py` marker keeps dotted-path loading deterministic and the layout rules under *Testing* apply; a bug fix still **SHOULD** ship a regression test.
- **MAY**: ship multiple plugin kinds from a single addon — multiple `register(...)` calls in one `.gpr.py`, and/or multiple `.gpr.py` files in the addon folder (the loader scans every `*.gpr.py`).

## Source location

- **MUST**: edit addon source in `addons-source/`, never in the live plugin directory. The auto-sync runs source → installed plugin one-way; edits in the live dir are silently overwritten on the next source save.

## Translation

The full how-to (registration setup, `make.py` lifecycle, Glade runtime-override pattern, function reference) lives in [11-internationalization](11-internationalization.md). The rules below are what code review enforces.

- **MUST**: wrap every user-visible string with `_()`.
- **MUST NOT**: `import _` in `.gpr.py` — Gramps' plugin loader injects it. Implementation modules **MUST** bind it explicitly via `_ = glocale.get_addon_translator(__file__).gettext`.
- **SHOULD**: guard that binding so an addon with no compiled catalog still imports:
  ```python
  try:
      _trans = glocale.get_addon_translator(__file__)
  except ValueError:
      _trans = glocale.translation
  _ = _trans.gettext
  ```
  `get_addon_translator` reaches `GrampsLocale._get_translation`, which **raises `ValueError("No usable translations in …")`** when no `.mo` is found for any language in the list and none of them starts with `en` or `C` (`gramps/gen/utils/grampslocale.py:536-540`, unchanged on `maintenance/gramps60` and `master`). An English-locale user never sees it, so the unguarded form passes every test on a developer machine and raises at import time for the first user running a non-English UI against an addon whose `locale/` isn't built yet. Prescribed by upstream [`addons-source/AGENTS.md`](https://github.com/gramps-project/addons-source/blob/maintenance/gramps61/AGENTS.md) → Internationalization.
- **MUST** (multi-file packages): when the addon's code is split across a nested package, bind `_` **once at the addon root** — the directory that holds `locale/`, in a root-level module (e.g. `_i18n.py`) — and import it everywhere else by **bare name** (`from _i18n import _`), **not** a `<Addon>.`-prefixed path: at load time the addon dir *itself* is what Gramps puts on `sys.path`, so `<Addon>` is not an importable name from inside the addon at all (see *Structure* → `__init__.py`), and a root-level module imports directly whereas `from <Addon>.<pkg>.i18n import _` raises `'<Addon>' is not a package` at import time. This holds whether or not the addon root carries an `__init__.py` — the runtime path never has the addon's *parent* on `sys.path`. `get_addon_translator(filename)` derives the catalog dir as `dirname(abspath(filename)) + "/locale"` (`gramps.gen.utils.grampslocale`), so a `get_addon_translator(__file__)` call from a nested module (e.g. `myaddon/views/tab.py`) resolves `myaddon/views/locale/`, which doesn't exist, and a non-English user silently gets the untranslated string. The flat `_ = glocale.get_addon_translator(__file__).gettext` form above is correct only because that module sits at the addon root; from a nested module, anchor the path at the root (e.g. `get_addon_translator(os.path.join(ADDON_ROOT, "_"))` — only `dirname(...)` is read, so the basename is an unused placeholder) instead of passing `__file__`. (NameSuite i18n-anchor fix, 2026-06-25.)
- **SHOULD**: verify an addon translation against an **addon-owned** msgid — one that appears only in the addon's `template.pot`, never a string that also exists in core (e.g. `"Given name"`). `get_addon_translator` returns the **core** translator with the addon catalog only as a *fallback*, so a core string renders translated whether or not the addon binding resolves — it cannot prove the fix. (Same fix: the original check used a core string and demonstrated nothing.)
- **MUST NOT**: wrap an f-string or `.format()` result in a translation function. `xgettext` cannot extract dynamically built strings.
  - **Bad:** `_(f"User {name}")`, `_("User {}".format(name))`
  - **Good:** `_("User %s") % name`
- **MUST** (Glade): translatable strings in `.glade` / `.ui` files are **not** picked up by the addon translation tooling — the extractor only sees Python. For each translatable Glade string, give the widget a meaningful `id`, mark the string with `translatable="yes"` (optionally with a `"context|"` prefix), and override the label at runtime in Python: `self.get_widget("place_name_label").set_label(_("place|Name:"))`.
- **SHOULD**: use `ngettext(singular, plural, n)` for plural forms.
- **SHOULD**: use the pipe-prefix form `_("Context|String")` whenever a word could carry multiple senses (e.g. `_("book|Title")` vs `_("person|Title")`). This is the convention used throughout `addons-source` and is what translators see in the `.po` file. The two-arg form `_(msg, context)` works equivalently. **MUST NOT** call `pgettext` or `sgettext` directly — go through `_`.
- **SHOULD**: use `N_("…")` to mark a string for extraction without translating it at call time (e.g. for module-level constants that are translated later when displayed).

> Addons have no `POTFILES.in` to maintain by hand — the per-addon `po/template.pot` is regenerated by `make.py init <Addon>` (see [12-packaging](12-packaging.md)). Maintaining `po/POTFILES.in` / `POTFILES.skip` is a **core** rule; see the [Core Development — Rules](https://gramps-project.org/wiki/index.php/Gramps_6.1_Wiki_Manual_-_Core_Development_-_Rules) page.

## Runtime

- **MUST**: perform every database write inside a `DbTxn`:
  ```python
  with DbTxn(_("Adding example"), db) as trans:
      db.add_person(person, trans)
  ```
- **MUST**: declare runtime imports in `requires_mod` using the *importable* module name (`PIL`), not the PyPI distribution name (`Pillow`).
- **MUST**: verify each `requires_mod` entry with `importlib.util.find_spec("<name>")` on a system with the package installed before publishing.
- **MUST**: use `requires_gi` for GObject-Introspection bindings, with version strings. The version pin **must match what the code actually imports** at runtime — pins can drift between Gramps minors (e.g. GExiv2 handling was rewritten on `maintenance/gramps61` per addons-source PR 829), so verify the pin against the target branch's related code, not just the previous branch's working declaration.
- **MUST NOT**: mutate process-global state that Gramps' startup owns — run or quit the GTK main loop (`Gtk.main()` / `Gtk.main_quit()`), install screen-wide CSS / retheme the icon theme / change `Gtk.Settings`, replace `sys.excepthook`, call `locale.setlocale` or `gettext.install`, configure the root logger, leave permanent `sys.path` entries, or set `os.environ` keys. An addon is a guest in Gramps' process; the full startup surface with per-item alternatives is [04-fundamentals → The provided environment](04-fundamentals.md#the-provided-environment).
- **SHOULD**: use handles (`PersonHandle`, etc.) for internal traversal; reserve Gramps IDs (`I0001`, …) for user-facing display. Handles are internal and stable; Gramps IDs are user-editable and rewritten in bulk by the Reorder Gramps IDs tool.
- **SHOULD**: import only from `gramps.gen.*`. `gramps.gui.*` and `gramps.plugins.*` are internal to the shipped distribution and break across Gramps versions.
- **SHOULD**: use a module-level logger (`LOG = logging.getLogger(__name__)`); **MUST NOT** use `print()` for diagnostic output.
- **SHOULD**: raise existing exceptions from `gramps.gen.errors` and `gramps.gen.db.exceptions` before inventing a new class.
- **SHOULD**: raise `HandleError` for invalid or missing handles.
- **SHOULD**: compare backlink class names by string. `db.find_backlink_handles(handle)` yields `(class_name, handle)` tuples where `class_name` is `"Person"` / `"Family"` / … as a `str`, not the Python class — `if cls is Person:` always evaluates `False`.
- **MAY**: introduce a new exception class only when none of the existing ones accurately represent the error condition.

## Testing

- **MUST**: use stdlib `unittest` — never `pytest`. Gramps itself standardises on `unittest`, which keeps addon tests contributable upstream.
- **MUST**: name test files `test_*.py` and place them in a `tests/` package alongside the addon module.
- **MUST**: scope platform-specific tests with the correct prefix:

  | Prefix | Where it runs |
  |--------|---------------|
  | `test_*.py`             | All platforms |
  | `test_linux_*.py`       | Linux only |
  | `test_windows_*.py`     | Windows only |
  | `test_integration_*.py` | Linux only — full-pipeline / DB-backed |

- **MUST**: tests run cleanly without the addon's `requires_mod` dependencies installed in the Python that runs them — mock at the import boundary, or skip cleanly with `@unittest.skipUnless(...)`. Mac contributors can't easily install addon deps into the Gramps Python, and there's no Gramps debug-mode on Mac. (Gary Griffin, 2026-05-16.)
- **MUST**: never call `gi.require_version` in addon modules or test files. At runtime Gramps pins Gtk/Gdk before any plugin loads (`gramps/grampsapp.py`, `gramps/gen/constfunc.py`); under test, the pins live once in addons-source's **repo-root** `tests/__init__.py` (addons-source PR 950) — the per-addon `tests/__init__.py` stays empty, and tests run from the repository root so the pinned environment holds. Redundant pins MAY be removed from files already being touched. A module-level pin passes unit tests but breaks inside Gramps as soon as the hardcoded pin and the running version diverge — see [07-testing → The GTK-pin contract](07-testing.md#the-gtk-pin-contract).
- **SHOULD**: ship a regression test with every bug fix that **fails pre-fix and passes post-fix**. Doc-only PRs are the only exception. (At PR level this hardens to a MUST-with-escape — the test, or an explicit "no test because X" rationale; see *Contributor workflow*.)
- **SHOULD**: prefer `example.gramps`-backed tests over mocked DBs for DB-traversal logic — real data has cross-typed backlinks and ID-normalisation shapes that mocks don't reproduce.
- **MAY**: ship mocked unit tests alongside real-DB tests as complementary coverage.

## Coding style

**The coding standard is core's `../gramps/AGENTS.md`, in full — this section lists only the addon deltas.** Black, Python 3.10+ type hints (`X | None`, `list[X]`), Sphinx docstrings, import grouping with comment headers, class-header navigation comments, the `cb_` callback prefix, handle/ID types from `gramps.gen.types` — all are specified there and apply to addon Python unchanged. They are **not** restated below; anything this section is silent on follows core. The deltas are only these:

- **Enforcement is advisory, so the core standard's coding MUSTs read as SHOULDs here.** addons-source runs no `black` / `mypy` / pylint gate — the reviewer weighs the standard; CI does not block on it. You **SHOULD** still run `black --check` before pushing, so the maintainer's cherry-pick forward to gramps61 stays clean.
- **Two rules are not softened — they stay MUST despite the lighter gate:** every new `.py` file carries a GPL-2.0-or-later license header with copyright, and every user-visible string is wrapped with `_()` (§Translation).
- **`gen`-self-containment, reframed.** Core's MUST that `gramps.gen.*` import no other submodule has no direct addon analog, but addon code **SHOULD** uphold the same discipline against itself: factor pure logic into modules that don't import `gramps.gui.*`, so it stays unit-testable without a display.

## Contributor workflow

- **MUST**: one logical fix per PR. Bundling hides mistakes.
- **MUST**: target the right branch — addon changes (`addons-source`) → `maintenance/gramps60`. The maintainer cherry-picks forward to `gramps61`. (Gary Griffin on addons-source PR 915, 2026-05-24.) A reviewer's instruction on a specific PR wins over the default targeting. (e.g. Nick-Hall on gramps#2299.) Core changes target a different branch — see the [Core Development — Rules](https://gramps-project.org/wiki/index.php/Gramps_6.1_Wiki_Manual_-_Core_Development_-_Rules) page.
- **MUST**: branch from `upstream/<base>`, not the fork's tracking copy — fork bases drift (e.g. PRs 2315/2316 carried a stray `AGENTS.md` from the fork).
- **MUST NOT**: bump the addon's `version` field in an addons-source PR. The maintainer manages versions centrally. (Caught on PR 911, bug 12572.)
- **MUST**: a bug-fix PR includes a regression test, or an explicit "no test because X" rationale plus a manual repro. "Add the test later" is not an option.
- **MUST**: open the PR body with a **`**User impact:**`** line (before Root cause), then structure it **Summary / What to look at / Root cause / Fix / Verification**, citing `path:lines` on the branch the PR targets in the Verification "Checked" line (the #106 format).
- **MUST**: when the PR modifies an addon, **call out its current maintainer** — add an `## Affected addon` section to the PR body that **@-mentions the addon's current maintainer**, a heads-up so they are *aware* of the change and don't miss it. This is awareness, not attribution. "Current maintainer" = the addon's `.gpr.py` `maintainers` field when declared, otherwise its `authors` (an addon with no separate maintainer is maintained by its original author — Doug's "original developer (or contributors)" and Nick's "current maintainer" are the same role). The `.gpr.py` records names/emails, not GitHub handles — resolve a handle best-effort from the declared email so the mention notifies, and name the person when no handle resolves. (Raised on addons-source PR #946 — Doug Blank: *"otherwise I could miss fixes to my addons"*; Nick Hall: *"mention the current maintainer if one exists."*)
- **OPTIONAL**: reference the Mantis bug in the PR body **when one exists** — a Mantis reference is optional for addons-source, since many addon fixes have no Mantis ticket (they're tracked as fork GitHub issues, or are ticketless). addons-source also does not use the `Fixes #NNNN` commit-message trailer at all — that is the core convention; see the [Core Development — Rules](https://gramps-project.org/wiki/index.php/Gramps_6.1_Wiki_Manual_-_Core_Development_-_Rules) page.
- **MUST**: keep upstream-repo cross-references out of PR text and fork issues — reference *other* upstream PRs/issues in **plain text** ("upstream PR 949"), never a GitHub URL or `owner/repo#NNN` cross-ref (it back-links/notifies that thread). The `#nnnn` Mantis reference and the PR's own target are exempt. Authoritative: `docs/INTEGRATION.md` §"No upstream-repo links".
- **MUST NOT**: merge across branches. Rebase rather than merge — PRs with merge commits are rejected upstream.
- **MUST NOT**: cosmetically update in-flight upstream PRs. Parity, "rebase is clean," and "branch is behind" are not reasons to force-push. Push only when a specific correctness issue needs fixing.
- **SHOULD**: before writing any fix, check upstream isn't ahead — merged history on the target branch AND `master`, *plus* closed and rejected PRs on the *affected file* (not just the bug number). Closed PRs are signal: a closed-unmerged PR with the same fix shape is the maintainer's "no."
- **SHOULD**: if a PR already exists for the bug, verify it instead of duplicating. Merged → confirm-and-close; open → review and defer to the maintainer; closed → treat as the maintainer's "no."
- **SHOULD**: reproduce against `example.gramps` first — it's the canonical fixture and "couldn't reproduce" is the most common reason a fix stalls in triage.
- **MAY**: open as a draft PR for early review or to publish work-in-progress; mark ready when the change is complete and the author has re-read the diff with fresh eyes.

## Verification before commit

- **MUST**: find a test procedure before committing — local run, dry-run, snippet check. Never commit untested changes.
- **MUST**: treat a green mechanical check (lint, `git cherry-pick` applies, build green, `py_compile` exits 0) as evidence of *that narrow check*, not of correctness. Name what the check verified and what it left unverified.
- **MUST**: after pushing a PR branch, watch the PR's CI checks until they finish (e.g. `gh pr checks <PR#> --watch`). Local pre-commit catches static checks only; test failures surface in CI's actual unit-test run.

## Commit messages

Commit messages are parsed by scripts that update Mantis BT and generate the ChangeLog / News files for releases. Formatting must be followed precisely.

- **MUST**: the first line is a short summary, **≤ 70 characters**.
- **MUST**: the description is separated from the summary by a single blank line, and wrapped at **80 characters**.
- **MUST**: describe the change from the user's perspective. Don't recap the diff — `git diff` exists.
- **SHOULD**: use complete sentences in the description.
- **MUST**: reference another commit by its **full hash**, not a short hash. GitHub auto-hyperlinks full hashes; short hashes in brackets do not link.
- **MUST**: the Mantis trailer is on the **last** line of the commit message, separated from the description by a single blank line.

### Mantis trailer keywords

To **resolve** a bug (closes it on commit):

```
Fixes #12345
Fixed #12345
Resolves #12345
Resolved #12345
Fixes #12345, #67890
```

To **link** to a bug (cross-reference without closing):

```
Bug #12345
Issue #12345
Report #12345
Bugs #12345, #67890
```

Bare numbers (no `#`) and URLs both miss the auto-link — use the `#NNNN` form. Note this is the opposite of the convention *inside* MantisBT itself, where `#NNNN` auto-links to another Mantis issue and bare numbers are preferred; here, inside Git commit messages and GitHub PR bodies, `#NNNN` is what hooks the MantisBT scripts.

For the trailer to wire up on Mantis, the Git **author** or **committer** has to be a developer on the Mantis bug tracker. The Git name must match the Mantis username or real name, or the Git email must match the Mantis email.

### addons-source: bug reference in PR body

addons-source PRs don't use `Fixes #NNNN` in the commit message — that trailer is the core convention. A Mantis bug reference in the PR body is **optional**: include it when the fix has a Mantis ticket, but many addon fixes have none (fork GitHub issue, or ticketless), and those need no reference. A present-but-malformed reference is still wrong.

## See also

- [Overview](01-overview.md)
- [Fundamentals](04-fundamentals.md)
- [Testing](07-testing.md)
- [Code analysis](10-code-analysis.md)
- [Packaging](12-packaging.md)
- `../gramps/AGENTS.md` — the full Python coding standard inherited here.
- [addons-source CONTRIBUTING.md](https://github.com/gramps-project/addons-source/blob/maintenance/gramps60/CONTRIBUTING.md)
- [Committing policies](https://www.gramps-project.org/wiki/index.php/Committing_policies) — upstream's commit-message + Mantis-trailer rules.
