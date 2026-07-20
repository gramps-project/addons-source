# Packaging

[← Previous](11-internationalization.md) · [Index](01-overview.md) · [Next →](13-community.md)

<!--
  This page covers the source-to-distribution PIPELINE only. The normative
  rules for contributors (branch targeting, version-field discipline, PR
  body shape, Mantis trailers, test-with-fix requirement) live in
  [[16-guidelines]] so there is one source of truth — link there, don't restate.

  Authoritative scraped source:
  ../04 - Technical Documentation/addons-development.md (sections
  "Develop your addon" through "List your addon in the Gramps Plugin
  Manager"). The make.py target name in the scrape is shown as
  `gramps``` because the wiki template literal "{{Stable_branch}}"
  didn't render; the real target is gramps60 for our maintenance
  branch and gramps61 for master.
-->

## Overview

From "works on my machine" to "users can install it from the addon manager." This chapter is the source-to-distribution pipeline: how `addons-source` becomes a `.addon.tgz` in `addons`, how the in-app addon manager picks it up, and what to send upstream.

The normative *rules* a submission must satisfy (branch targeting, version-field discipline, PR body shape, Mantis trailers) live in [16-guidelines](16-guidelines.md). This page covers the *workflow* — what to run, what files appear, where they end up.

## The three repositories

![Fig. 1 — The source-to-distribution pipeline. Authors edit in `addons-source/`; `make.py build` packages each addon into `addons/grampsXY/download/<Addon>.addon.tgz` and `make.py listing` refreshes `addons/grampsXY/listings/*.json`; the in-app addon manager fetches both over HTTPS and installs to the user's plugin directory. Edits in the user plugin dir are not pushed back — the flow is one-way only.](_media/packaging-pipeline.svg)

Gramps addons live across three repositories. You'll have all three cloned side-by-side under one base directory:

```
base/
├── gramps/          # gramps-project/gramps — Gramps itself; source of truth for the API
├── addons-source/   # gramps-project/addons-source — addon source code, one folder per addon
└── addons/          # gramps-project/addons — built distribution, one folder per Gramps version
```

| Repo            | What's there                                                                        | You edit?                          |
|-----------------|-------------------------------------------------------------------------------------|------------------------------------|
| `gramps`        | The Gramps source tree; provides `GRAMPSPATH` for the build                         | No (unless writing a core change)  |
| `addons-source` | The addon source: `<Addon>/<Addon>.gpr.py`, `<Addon>/<Addon>.py`, `po/`, `tests/`   | **Yes — author addons here**       |
| `addons`        | Built `.addon.tgz` packages and listing JSON, organised by Gramps minor             | No — `make.py` writes to it        |

`addons` is the **output**. The in-app addon manager hits its HTTPS mirror to fetch listings and downloads. Editing files in `addons` directly does nothing — the next `make.py` run overwrites them.

### Branch directory split inside `addons/`

Inside `addons/`, each Gramps minor gets its own subdirectory:

```
addons/
├── gramps42/
├── gramps50/
├── gramps51/
├── gramps52/
├── gramps60/
│   ├── download/   # <Addon>.addon.tgz files
│   └── listings/   # JSON catalogues fetched by the addon manager
└── gramps61/
    ├── download/
    └── listings/
```

The same addon can ship to multiple minors, each with its own `.addon.tgz` — that's why the addon manager reads only the listing for the running Gramps version.

## Initial clone

```bash
mkdir gramps-addons && cd gramps-addons

git clone https://github.com/gramps-project/gramps.git
git clone https://github.com/gramps-project/addons-source.git
git clone https://github.com/gramps-project/addons.git

cd addons-source
git checkout -b gramps60 origin/maintenance/gramps60     # for 6.0
# or for master/6.1:
# git checkout -b gramps61 origin/master
```

The branch you check out in `addons-source` determines which Gramps minor your built addons target — `make.py` reads the branch name to pick the output directory inside `addons/`.

See [14-compatibility](14-compatibility.md) for branch-targeting guidance per Gramps minor.

## Build prerequisites

`make.py` calls out to two environment things and one OS tool:

- **`GRAMPSPATH`** — absolute path to your `gramps/` clone.
- **`LANGUAGE`** — must be set to `en_US.UTF-8` for the build to run.
- **`intltool`** — `sudo apt-get install intltool` on Debian/Ubuntu.

The standard invocation:

```bash
GRAMPSPATH=/path/to/gramps LANGUAGE='en_US.UTF-8' python3 make.py gramps60 <command> <Addon>
```

Cumbersome to type each time. Set the env vars in your shell startup once; only the `make.py` line varies per command.

In the examples below, `gramps60` is the maintenance/gramps60 target; substitute `gramps61` when you're working on the master branch.

## `make.py` cheat sheet

`make.py` lives at the top of `addons-source` and runs against one addon at a time, or `all` for everything. The commands you'll use most:

| Command                                  | What it does                                                                  |
|------------------------------------------|-------------------------------------------------------------------------------|
| `make.py gramps60 init <Addon>`          | Create `<Addon>/po/template.pot` from extracted strings                       |
| `make.py gramps60 init <Addon> <lang>`   | Create `<Addon>/po/<lang>-local.po` from the template                         |
| `make.py gramps60 update <Addon> <lang>` | Merge new strings from Gramps + the addon into `<lang>-local.po`              |
| `make.py gramps60 compile <Addon>`       | Compile every `<lang>-local.po` into `.mo` files                              |
| `make.py gramps60 build <Addon>`         | Compile translations *and* produce `<Addon>.addon.tgz` in `addons/gramps60/download/` |
| `make.py gramps60 listing <Addon>`       | Refresh `addons/gramps60/listings/*.json` so the addon manager sees it        |
| `make.py gramps60 clean <Addon>`         | Delete generated files (`locale/`, `*.mo`) — run before `git add`             |
| `make.py gramps60 build all`             | Build every addon                                                             |

`build` includes `compile`, so the standard release cycle is `clean` → edit → `build` → `listing` → commit + push to `addons/`.

### What `build` packages

By default `build` includes:

- every `*.py` in the addon folder,
- every `*.glade`, `*.xml`, `*.txt`,
- every `locale/*/LC_MESSAGES/*.mo`.

Anything else — README images, extra data files, help HTML — needs an explicit `MANIFEST` file in the addon's root listing them, **with the addon folder name prefixed on each line**:

```
<Addon>/README.md
<Addon>/help/index.html
<Addon>/data/*
```

The `MANIFEST` mechanism was added in Gramps 5.0 and is the way to ship anything beyond the default file types.

## The localisation flow

Per-addon translations live under `<Addon>/po/`. They are independent of Gramps' core catalogues — Gramps' plugin loader binds `_()` to the addon's own catalog when the implementation module declares:

```python
from gramps.gen.const import GRAMPS_LOCALE as glocale

_ = glocale.get_addon_translator(__file__).gettext
```

See [04-fundamentals → Translation](04-fundamentals.md#translation) for the full opt-in. Without that line, strings fall back to the core catalog regardless of where translators put them.

### Adding a new language

```bash
# 1. Generate (or refresh) the template from extracted strings.
make.py gramps60 init <Addon>

# 2. Initialise a fresh language file from the template.
make.py gramps60 init <Addon> fr

# 3. Translator edits <Addon>/po/fr-local.po manually.

# 4. Recompile so the .mo file lands under <Addon>/locale/fr/LC_MESSAGES/.
make.py gramps60 compile <Addon>

# 5. Commit the .po (NOT the .mo or the generated locale/ tree).
git add <Addon>/po/fr-local.po
git commit -m "Add French translation for <Addon>"
```

### Refreshing an existing language

When you've changed user-visible strings in the addon, every existing `<lang>-local.po` needs new entries merged in:

```bash
make.py gramps60 update <Addon> fr
```

This preserves existing translations and marks new or changed entries as `fuzzy` for the translator to review.

### Editing `template.pot`'s header once

The header of `<Addon>/po/template.pot` carries author, maintainer, and team metadata. Edit it after the first `init` — the values propagate into every per-language file the next time you `init <Addon> <lang>`.

### What to commit, what to skip

Commit:

- `<Addon>/po/template.pot`
- `<Addon>/po/<lang>-local.po` (one per language)

Don't commit:

- `<Addon>/locale/**` — generated by `compile` and `build`. Always run `make.py gramps60 clean <Addon>` (or `rm -rf <Addon>/locale`) before `git add`.
- `<Addon>/*.mo` outside `locale/` — same reason.

## Publishing to `addons/`

`build` writes one `.addon.tgz` per addon; `listing` rebuilds the JSON catalogues the addon manager fetches. Both go into the `addons/` repository and need committing **there**, not in `addons-source/`:

```bash
# In addons-source/, build the package.
make.py gramps60 build <Addon>
make.py gramps60 listing <Addon>

# Switch to the addons/ checkout.
cd ../addons

# Stage the new .tgz and the refreshed listings.
git add gramps60/download/<Addon>.addon.tgz
git add gramps60/listings/*
git commit -m "Add <Addon> for Gramps 6.0"

# Push when you have write access — see [16-guidelines] for the review gate.
```

The in-app addon manager hits the `addons` repo over HTTPS and shows the addon to users on their next "Check for updates" cycle.

## Editing `addons-source/`, not the live plugin directory

During development it's tempting to edit directly in `~/.local/share/gramps/gramps60/plugins/<Addon>/` so a Gramps restart picks up the change without copying. **Don't** — that directory is the auto-sync *target*, and Gramps writes back through it on every save. Edits made there are silently overwritten on the next source save.

Edit in `addons-source/<Addon>/`. The dev loop is one of:

- **Gramps 6.0** — copy / `rsync` the folder into the user plugin directory on each save. Plugin discovery doesn't follow symlinks.
- **Gramps 6.1+ on Linux/macOS** — symlink the working tree into the user plugin directory once, then edit in place. Plugin discovery follows symlinks with realpath-based loop dedup (commit `9443dcbb30`).
- **Windows, any version** — physical copy. The 6.1 symlink test is skipped on Windows because the platform's symlink behaviour is inconsistent without elevated privileges.

See [01-overview → Where addons live](01-overview.md#where-addons-live) for the user plugin directory paths.

## Submitting a new addon

The first time you add an addon to `addons-source/`:

```bash
cd addons-source

# 1. Create the folder and the two required files.
mkdir <Addon>
$EDITOR <Addon>/<Addon>.gpr.py
$EDITOR <Addon>/<Addon>.py

# 2. (Optional, recommended) Translation scaffold + tests.
mkdir <Addon>/po <Addon>/tests
$EDITOR <Addon>/tests/__init__.py    # empty marker — see 07-testing
$EDITOR <Addon>/tests/test_<Addon>.py

# 3. Clean any build artefacts before committing.
make.py gramps60 clean <Addon>

# 4. Commit and push to your fork, then open a PR.
git add <Addon>
git commit -m "Add <Addon>: <one-line description>"
```

Open the PR against the **correct branch** — for an addon targeting Gramps 6.0, that's `maintenance/gramps60`, which the maintainer cherry-picks forward to `gramps61` (see [16-guidelines → Contributor workflow](16-guidelines.md#contributor-workflow) for the full submission shape).

## Update an existing addon

After editing source:

```bash
cd addons-source

# 1. Iterate: edit, restart Gramps, verify behaviour.
# 2. Refresh translations if user-visible strings changed.
make.py gramps60 update <Addon> all
# 3. Compile-check.
make.py gramps60 compile <Addon>
# 4. Clean and commit.
make.py gramps60 clean <Addon>
git add <Addon>
git commit -m "<Addon>: <what changed>"
```

The `version` field in `<Addon>.gpr.py` **stays untouched** in PRs — the maintainer manages versions centrally. (See [16-guidelines](16-guidelines.md#contributor-workflow); this came up on PR 911 where a bump was rejected.)

## See also

- [01-overview](01-overview.md) — what an addon is.
- [04-fundamentals → Translation](04-fundamentals.md#translation) — the `_()` injection that makes per-addon `.po` files load.
- [07-testing](07-testing.md) — what to put in `tests/` before packaging.
- [14-compatibility](14-compatibility.md) — picking the right Gramps minor and branch for your addon.
- [16-guidelines](16-guidelines.md) — the normative rules a PR must satisfy.
- [Addons development](https://gramps-project.org/wiki/index.php/Addons_development) — the standalone wiki page; primary scraped source for this chapter.
- [addons-source CONTRIBUTING.md](https://github.com/gramps-project/addons-source/blob/maintenance/gramps60/CONTRIBUTING.md) — the addons-source-side contributor guide.
