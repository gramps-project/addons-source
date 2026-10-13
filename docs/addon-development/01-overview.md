# Addon Development

[Index](01-overview.md) · [Next →](02-tutorials.md)

## Summary

A Gramps **addon** extends the application without modifying core. You add a feature, ship it on your own schedule, and users install it from the in-app Plugin Manager — no fork of Gramps, no waiting on a core release to put new functionality in front of people. An addon is just a folder of Python on the plugin path, so the barrier to entry is low; the trade-off is that you build against Gramps' API and track it across versions. This is how most of Gramps' reports, tools, and gramplets are delivered, and the same door is open to you.

**What you actually write.** Two files are the minimum: a registration file, `<Addon>.gpr.py`, that declares the addon to Gramps, and an implementation module that Gramps imports the first time the addon is used. Optional `po/` and `tests/` directories sit alongside them. Gramps scans every `.gpr.py` at startup and builds its plugin catalog from the `register(...)` calls; implementation modules load **lazily**. There is no build step and no manifest beyond the registration file — [see below](#anatomy-of-an-addon).

**What you can extend.** Gramps has no single "addon" shape: sixteen registration kinds each plug in at a different extension point — Gramplets, Views, Reports, Tools, Importers, Exporters, Quick Views, Docgens, Sidebars, Map services, Relationship calculators, filter Rules, Database backends, Thumbnailers, citation formatters, and a catch-all `GENERAL` kind for shared libraries. The kind you pick determines the registration fields, the base class you subclass, and where the addon surfaces in the UI. The full catalogue is [Addon Kinds](03-addon-kinds.md); [the addon list](https://gramps-project.org/wiki/index.php/6.0_Addons) shows what already ships.

**What you build against.** An addon targets one Gramps minor version, declared as `gramps_target_version` in the registration — "6.0" means the 6.0 API on the `maintenance/gramps60` branch. Addons import from `gramps.gen.*`, the headless core; `gramps.gui.*` is available to GUI kinds but is a less stable surface. The API you may rely on is curated in [API Reference](06-api-reference.md), and what shifts between versions is in [Compatibility](14-compatibility.md) and [What's New](15-whats-new.md).

**How it reaches users.** Three levels of ambition, and you can stop at any of them. Keep the addon in your own plugin directory and it is yours alone. Hand someone the folder and they drop it into theirs. Or submit it to the `addons-source` repository upstream, where `make.py` packages it into an `.addon.tgz` in the `addons` repository and refreshes the listing JSON that the in-app Plugin Manager fetches over HTTPS — at which point every Gramps user on that version can find and install it. That pipeline is [Packaging](12-packaging.md); what happens afterwards — the addon-list entry, the wiki page, the support duty — is [Community](13-community.md).

**What is expected of you.** The bar is deliberately lower than for core, but two rules never soften: every new `.py` file carries a GPL-2.0-or-later license header with a copyright line, and every user-visible string is wrapped in `_()` so it can be translated. Beyond that: a test where the change is testable, code that passes the static checks, and — counter-intuitively — *not* touching the `version` field in a submission, since the release build manages it. All of it is written out, MUST by MUST, in [Rules](16-guidelines.md).

**Who this is for.** Anyone writing or maintaining a Gramps addon — from a one-file Gramplet for personal use to a published addon with translations and a maintainer. If you are changing Gramps itself rather than extending it, you want the Core Development section instead.

This page is the **start point** for the section: first a map to every other page, then everything a first-time author needs to go from "Gramps is installed" to "my addon shows up in the menu" — anatomy, prerequisites, and a minimal working Gramplet. The normative MUST / SHOULD rules every addon is held to live in [Rules](16-guidelines.md).

## The section at a glance

**New to addon development?** Work through this page, then read in order — from your first loaded addon to a tested, rules-compliant one:

*this page* → [Addon Kinds](03-addon-kinds.md) → [Fundamentals](04-fundamentals.md) → [Data access](05-data-access.md) → [Testing](07-testing.md) → [Rules](16-guidelines.md)

**Looking for something specific?** Jump straight to it:

| If you want to… | Go to |
|-----------------|-------|
| Install the tooling and see your first addon load | *this page, below* |
| Follow an end-to-end walkthrough for your addon kind | [Tutorials](02-tutorials.md) |
| Choose which kind of addon to build | [Addon Kinds](03-addon-kinds.md) |
| Learn the cross-cutting basics — `.gpr.py`, discovery, `_()`, logging, lifecycle | [Fundamentals](04-fundamentals.md) |
| Read from or write to the database | [Data access](05-data-access.md) |
| Look up the `gramps.gen` API an addon may import | [API Reference](06-api-reference.md) |
| Write and run tests | [Testing](07-testing.md) |
| Debug an addon that isn't behaving | [Debug](08-debug.md) |
| Diagnose a common failure mode | [Troubleshoot](09-troubleshoot.md) |
| Pass the static checks (Black, ruff) | [Code Analysis](10-code-analysis.md) |
| Translate your addon's strings | [Internationalization](11-internationalization.md) |
| Package and submit your addon | [Packaging](12-packaging.md) |
| List, announce, and support your published addon | [Community](13-community.md) |
| Port across Gramps versions | [Compatibility](14-compatibility.md) |
| See per-version changes that affect addons | [What's New](15-whats-new.md) |
| Know the rules to follow — and to cite in review | [Rules](16-guidelines.md) |
| See what's planned, or propose a change | [Roadmap](17-roadmap.md) |

The one page to bookmark is [Rules](16-guidelines.md) — the normative MUST / SHOULD / MAY reference every addon is held to.

## What an addon can extend (at a glance)

Almost every part of the Gramps UI is a plugin point. The common kinds:

| Kind | Adds | Shows up in |
|------|------|-------------|
| **Gramplet** | a lightweight widget over the current selection | Dashboard / sidebar |
| **View** | a full alternative way to browse the tree | main view area |
| **Report** | text or graphical output (PDF, HTML, ODF, …) | Reports menu |
| **Tool** | an operation over the database | Tools menu |
| **Importer / Exporter** | reading or writing an external format | File → Import / Export |
| **Quick View** | a one-call report on a selected object | right-click menus |

…plus filter rules, sidebars, map providers, relationship calculators, citation formatters, docgen output backends, and more. The full catalogue — with the registration fields and base class each kind needs — is [Addon Kinds](03-addon-kinds.md).

## Anatomy of an addon

An addon is a folder under Gramps' user plugin directory — one folder per addon — holding at minimum a registration file and an implementation module:

| File | Purpose |
|------|---------|
| `<Addon>.gpr.py` | Registration: id, name, version, Gramps target, kind, entry point |
| `<Addon>.py` | The implementation Gramps loads on demand |
| `po/` | Translation catalogs (optional) |
| `tests/` | Unit tests (optional, recommended) |

At startup Gramps scans every `.gpr.py` and builds a metadata catalog from the `register(...)` call(s); the implementation module named by `fname` loads **lazily**, on first use. The consequence to remember: an error in `.gpr.py` hides the addon entirely, while an error in the implementation only surfaces when the addon is invoked.

The registration declares the Gramps version it targets (`gramps_target_version`) — an addon on `maintenance/gramps60` expects the 6.0 API; see [Compatibility](14-compatibility.md) for cross-version concerns.

What you build next depends on the **kind** — Gramplet, View, Report, Tool, Importer/Exporter, Quick View, and more — each adding its own registration fields and base class. Choose one in [Addon Kinds](03-addon-kinds.md); the full `.gpr.py` field reference and the discovery model are in [Fundamentals](04-fundamentals.md).

## Prerequisites

| Requirement | Why |
|-------------|-----|
| Gramps 6.0 installed and runnable | The target you're developing against |
| Python 3.10+ | Matches Gramps 6.0's minimum |
| A text editor or IDE | Any will do; Gramps doesn't impose one |
| Familiarity with Python imports and packages | Addons are Python modules |

You do **not** need to build Gramps from source for addon work. Addons load from the user plugin directory and are picked up at next start.

## Where addons live

Each addon is a folder under Gramps' user plugin directory, one folder per addon. The exact path is platform-specific; see [the Addons page](https://gramps-project.org/wiki/index.php/6.0_Addons) for the canonical locations. The folder name must be a valid Python import name (no spaces — addons share code via `import <FolderName>`); it need **not** match the registration `id`, which is an independent plugin key ([Rules](16-guidelines.md) → Structure).

On Gramps 6.0, plugin discovery does **not** follow symlinks — the addon must be physically present under the plugin path, so the development loop is copying (or `rsync`ing) from your working tree on save.

**Changed in 6.1**: plugin discovery follows symlinks (with realpath-based dedup against symlink loops), so you can `ln -s <working-tree>/<Addon>` into the user plugin directory and edit in place. Windows users: the 6.1 symlink test is skipped on Windows because the platform's symlink behavior is inconsistent without elevated privileges; the `rsync`/copy loop remains the safe default there. (gramps commit `9443dcbb30` on `maintenance/gramps61`.)

## Your first addon: a minimal Gramplet

A *Gramplet* is the lightest-weight addon kind — a sidebar widget. Two files are enough.

### 1. Create the addon folder

Make a folder named `HelloGramplet` under the user plugin directory.

### 2. Add the registration file

Save this as `HelloGramplet/HelloGramplet.gpr.py`:

```python
register(
    GRAMPLET,
    id="HelloGramplet",
    name=_("Hello Gramplet"),
    description=_("A minimal example Gramplet"),
    version="1.0.0",
    gramps_target_version="6.0",
    status=STABLE,
    fname="hellogramplet.py",
    gramplet="HelloGramplet",
    gramplet_title=_("Hello"),
)
```

The `id` is the addon's stable identifier. `fname` is the implementation module. `gramplet` is the class inside it that Gramps will instantiate.

### 3. Add the implementation

Save this as `HelloGramplet/hellogramplet.py`:

```python
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.plug import Gramplet

_ = glocale.get_addon_translator(__file__).gettext


class HelloGramplet(Gramplet):
    def init(self):
        self.set_text(_("Hello from your first Gramplet!"))
```

`init()` is the construction hook — Gramps calls it once when the Gramplet is first shown. The `_ = glocale...` line binds the translation function for this module — see [Translation](#translation) below.

### 4. Restart Gramps

Plugin discovery happens at startup. After the restart, the new Gramplet appears under *View → Sidebar* (or the Dashboard, depending on view).

## Reload / test cycle

There is no hot-reload for addons. The development loop is:

1. Edit the source.
2. Sync the change into the plugin directory (or work directly there).
3. Restart Gramps.
4. Observe.

For faster iteration on non-GUI logic, write a `unittest`-based test alongside the addon and run it without launching Gramps — see [Testing](07-testing.md) for the conventions.

## Translation

Wrap every user-visible string in `_()` so it can be translated:

```python
self.set_text(_("Hello from your first Gramplet!"))
```

`_` is set up differently in the two files. In `.gpr.py` it is injected by the plugin loader — just use it, never import it. In the implementation module nothing is injected: bind it explicitly at the top of the file, as the walkthrough's `hellogramplet.py` does:

```python
from gramps.gen.const import GRAMPS_LOCALE as glocale

_ = glocale.get_addon_translator(__file__).gettext
```

Translation catalogues live in a per-addon `po/` directory — optional for a first experiment, required for an addon you intend to share; [Internationalization](11-internationalization.md) covers the workflow.

## Next steps

- [Tutorials](02-tutorials.md) — end-to-end walkthroughs per addon kind; read a similar addon's source as your second tutorial ([6.0 Addons](https://gramps-project.org/wiki/index.php/6.0_Addons) lists what exists).
- [Addon Kinds](03-addon-kinds.md) — choose the kind of addon to build; registration fields and base class per kind.
- [Fundamentals](04-fundamentals.md) — every `.gpr.py` field, the discovery model, and the lifecycle hooks the implementation overrides.
- [Testing](07-testing.md) — unit-test conventions and the `tests/` package layout.
- [Addons development](https://gramps-project.org/wiki/index.php/Addons_development) — cross-version porting notes and the wider development reference.
