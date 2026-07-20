# Addon Kinds

[← Previous](02-tutorials.md) · [Index](01-overview.md) · [Next →](04-fundamentals.md)

<!--
  Index page over the addon kinds. Each kind gets:
    - the registration constant
    - where the kind shows up in the UI
    - the base class (if any) and entry-point shape
    - the minimum-viable shape of the implementation module
    - a pointer onward (tutorial, similar live addon, the kind's wiki page)

  Source of truth for the constants:
  ../gramps/gramps/gen/plug/_pluginreg.py (PTYPE_STR block, ~L82-L98).
  The numeric values aren't author-facing; cite by name.
-->

## Overview

Gramps doesn't have one "addon" shape — it has 14 of them, each registered with a different `register(KIND, …)` constant and each plugged in at a different extension point. This page is the index over all of them, with the registration constant, the UI location, the base class to subclass, and a pointer onward. Use it to answer the first question every prospective addon author asks: **which kind of thing am I writing?**

Source of truth for the constants: [`gramps/gen/plug/_pluginreg.py`](https://github.com/gramps-project/gramps/blob/maintenance/gramps60/gramps/gen/plug/_pluginreg.py).

![Fig. 1 — Where each addon kind plugs into the Gramps UI. Menu-anchored kinds (REPORT, TOOL, IMPORT/EXPORT) appear inline with the menu item that hosts them; panel-anchored kinds (SIDEBAR, VIEW, GRAMPLET, QUICKVIEW, MAPSERVICE, RULE) carry callouts to their surface. The six kinds with no direct UI surface — DOCGEN, DATABASE, RELCALC, THUMBNAILER, CITE, GENERAL — are listed separately. Schematic; relative positions match Gramps 6.0's default layout but are not pixel-accurate.](_media/addon-kinds-ui-map.svg)

## Kinds at a glance

| Constant       | Where it shows up                | Typical use                                                                  |
|----------------|----------------------------------|------------------------------------------------------------------------------|
| `GRAMPLET`     | Dashboard, sidebar, bottombar    | Lightweight widget over the current selection                                |
| `VIEW`         | Main view area                   | A full alternative way to browse the tree                                    |
| `REPORT`       | Reports menu                     | Text / graphical output (PDF, HTML, ODF, …) using the docgen interface       |
| `TOOL`         | Tools menu                       | Operates on the database, optionally writing inside a transaction            |
| `IMPORT`       | File → Import                    | Reads an external format into the tree                                       |
| `EXPORT`       | File → Export                    | Writes the tree to an external format                                        |
| `DOCGEN`       | Report output backends           | Adds a new output format / paper backend used by reports                     |
| `QUICKVIEW`    | Right-click context menus        | Single-call short report on a selected object (formerly `QUICKREPORT`)       |
| `SIDEBAR`      | Sidebar navigator                | Adds a new sidebar category                                                  |
| `MAPSERVICE`   | Geography view                   | Adds a new map tile provider                                                 |
| `RELCALC`      | Relationships view               | Per-locale relationship calculator                                           |
| `RULE`         | Filter editor                    | Adds a new filter rule for an object type                                    |
| `DATABASE`     | New tree backend selection       | Adds support for another database backend                                    |
| `THUMBNAILER`  | Media handling                   | Adds a thumbnail generator for an additional media format                    |
| `CITE`         | Source citations                 | Adds a citation formatter style                                              |
| `GENERAL`      | (varies)                         | Catch-all for libraries / pluggable categories (`WEBSTUFF`, `Filters`, …)    |

`QUICKREPORT` is the legacy name for `QUICKVIEW`; the integer constant is identical (`gramps/gen/plug/_pluginreg.py` line 83). New addons use `QUICKVIEW`; existing ones continue to work.

## Per-kind notes

The notes below cover the kinds an addon author is likely to write. Kinds with deeper conventions get their own section; the rest are summarised in one paragraph each. For full attribute lists per kind, the authoritative reference is the `expand_*` functions in `_pluginreg.py`.

### `GRAMPLET`

**Where it shows up:** docked in the Dashboard, sidebar, or bottombar of any view; can be detached into a floating window.

**Base class:** subclass `gramps.gen.plug.Gramplet`. Override `init()` (constructor hook, runs once), `main()` (re-run on update), `db_changed()` (called when the active database changes), and `active_changed()` (called when the active person / family / etc. changes).

**Minimum-viable shape:**

```python
from gramps.gen.plug import Gramplet

class MyGramplet(Gramplet):
    def init(self):
        self.set_text(_("Hello"))
```

**Registration:** see [01-overview → Add the registration file](01-overview.md#2-add-the-registration-file) for the full call. Required Gramplet-specific fields are `gramplet` (the class name) and `gramplet_title` (the user-visible tab title).

**Tutorial:** [02-tutorials → A live Gramplet](02-tutorials.md#a-live-gramplet).

### `REPORT`

**Where it shows up:** Reports menu, organised by category.

**Base class:** subclass `gramps.gen.plug.report.Report`. Override `write_report()` to emit content. Pair with an options class that subclasses `gramps.gen.plug.report.MenuReportOptions` and overrides `add_menu_options()` (to define user-adjustable options) and `make_default_style()` (to define paragraph and font styles).

**Categories** (`_pluginreg.py` L141–L149): `CATEGORY_TEXT`, `CATEGORY_DRAW`, `CATEGORY_CODE`, `CATEGORY_WEB`, `CATEGORY_BOOK`, `CATEGORY_GRAPHVIZ`, `CATEGORY_TREE`. Text and Draw reports go through the docgen abstraction, so the same report can emit PDF / HTML / ODF without per-format code.

**Report modes** (`report_modes` field): `REPORT_MODE_GUI` (dialog-driven), `REPORT_MODE_BKI` (book item), `REPORT_MODE_CLI` (command line). Most addons combine GUI + CLI.

**Tutorial:** [02-tutorials → A text Report](02-tutorials.md#a-text-report).

### `TOOL`

**Where it shows up:** Tools menu, optionally categorised.

**Base class:** subclass a class from `gramps.gui.plug.tool` (typically `Tool` or `BatchTool`). Override the constructor — Gramps passes `(dbstate, user, options_class, name, callback=None)`. Tools that mutate the database **must** do so inside a `DbTxn`.

**Categories** (`_pluginreg.py` L154–L159): `TOOL_DEBUG`, `TOOL_ANAL`, `TOOL_DBPROC`, `TOOL_DBFIX`, `TOOL_REVCTL`, `TOOL_UTILS`. Choose the one that matches what the tool actually does — `TOOL_DBFIX` for repairs, `TOOL_ANAL` for read-only analysis, `TOOL_UTILS` for generic utilities.

**Tool modes** (`tool_modes` field, `_pluginreg.py` L183–L184): `TOOL_MODE_GUI` and `TOOL_MODE_CLI`. A pure-data tool should support both so a power user can scriptit.

**Tutorial:** [02-tutorials → A simple Tool](02-tutorials.md#a-simple-tool).

### `QUICKVIEW`

**Where it shows up:** right-click context menus on the selected object in views and editors.

**Entry point:** a `run(database, document, person_or_family_or_…)` function declared in the implementation module and pointed to by the `runfunc` field. No class subclassing required.

**Categories** (`_pluginreg.py` L163–L174): `CATEGORY_QR_PERSON`, `CATEGORY_QR_FAMILY`, `CATEGORY_QR_EVENT`, `CATEGORY_QR_SOURCE`, `CATEGORY_QR_PLACE`, `CATEGORY_QR_REPOSITORY`, `CATEGORY_QR_NOTE`, `CATEGORY_QR_DATE`, `CATEGORY_QR_MEDIA`, `CATEGORY_QR_CITATION`, `CATEGORY_QR_SOURCE_OR_CITATION`, `CATEGORY_QR_MISC`. The category determines which context menu the entry appears in.

Quick Views are deliberately the shortest path to a usable report — written against the `gramps.gen.simple` API (`SimpleAccess`, `SimpleDoc`), they hide most of the docgen complexity. Reach for a full `REPORT` only when you need styles, paragraph layout, or multiple output formats.

**Tutorial:** [02-tutorials → A Quick View](02-tutorials.md#a-quick-view).

### `RULE`

**Where it shows up:** the Add Rule dialog when the user composes a custom filter from the Filter Editor; available wherever filters are.

**Base class:** subclass the right rule base from `gramps.gen.filters.rules` — pick the namespace-specific base (`gramps.gen.filters.rules.person.Rule`, `…family.Rule`, etc.) that matches the object type your rule applies to. Set the class attributes `name`, `description`, `category`, and `labels` (the user-prompted arguments); implement `apply(db, obj)` to return `True` / `False`.

**Tutorial:** [02-tutorials → A custom filter Rule](02-tutorials.md#a-custom-filter-rule).

### `VIEW`

**Where it shows up:** the main view area; available from the navigator once registered.

**Base class:** subclass an appropriate view from `gramps.gui.views` (`NavigationView`, `ListView`, `PageView`). Views are the heaviest addon kind — they own the entire display surface and the keyboard / mouse interaction. Most addons should reach for `GRAMPLET` instead and only graduate to `VIEW` when the gramplet outgrows its container.

**Live examples:** `CombinedView`, `LifeLineChartView`, `QuiltView` — read one before writing your own.

### `IMPORT` / `EXPORT`

**Where they show up:** File → Import / Export, with the new format appearing in the format dropdown.

**Entry point:** a module-level function. Importers receive `(database, filename, user)`; exporters receive `(database, filename, error_dialog, option_box, callback)` (signatures vary slightly by Gramps minor; the safest move is to read a live importer/exporter and copy the shape).

**Live examples:** the GEDCOM (`gramps/plugins/importer/importgedcom.py`, `…/exporter/exportgedcom.py`) and JSON importers/exporters in core are the canonical references.

### `DOCGEN`

**Where it shows up:** as a new output format in any Report's options dialog; not user-launched on its own.

**Base class:** subclass `gramps.gen.plug.docgen.BaseDoc` (or the text/draw subclasses depending on what kind of output you generate). A DocGen implements the *primitives* — paragraphs, tables, drawing commands — that the abstract Report classes call into. Authors usually only write a new DocGen to add a new output format (e.g. a new word-processor file type); it's a relatively rare addon kind.

### `SIDEBAR`

**Where it shows up:** the navigator on the left of the main window; each `SIDEBAR` plugin adds one category.

**Base class:** subclass `gramps.gui.sidebar.Sidebar`. Core categories (People, Families, Events, …) are themselves implemented this way, so the canonical examples ship in core under `gramps/gui/sidebar/`.

### `MAPSERVICE`

**Where it shows up:** the Geography views' map-source dropdown.

**Base class:** subclass `gramps.plugins.lib.maps.osmgps.MapService` and implement the URL / tile-fetch protocol for your provider. Pure tile adapters — no UI changes — so most are very small.

### `RELCALC`

**Where it shows up:** wherever Gramps computes a relationship string (Relationships view, person editor, reports). One `RELCALC` plugin per locale.

**Base class:** subclass `gramps.gen.relationship.RelationshipCalculator`. The base class supplies all the English-language logic; subclasses override the localised strings and any kinship rules specific to the culture being modelled.

### `DATABASE`

**Where it shows up:** the database-backend dropdown in tree creation.

Adds a fully alternative storage backend implementing the `DbReadBase` / `DbWriteBase` interfaces. By far the heaviest kind — the only current in-tree examples are the BSDDB and SQLite backends themselves. Treat the existence of this kind as "yes, it is possible," not "you should consider writing one."

### `THUMBNAILER`

**Where it shows up:** wherever Gramps generates a media thumbnail.

Adds a generator for one additional media format. Pure-function shape: input file → thumbnail image. Use this when a media type Gramps recognises doesn't have a working thumbnailer in your environment.

### `CITE`

**Where it shows up:** the citation style chooser in source / citation editors and reports.

Adds an alternative citation formatter (Chicago, MLA, Evidence Explained, …). Implements the formatting protocol expected by the source / citation code; cite an existing core formatter (`gramps/plugins/cite/`) for the exact shape on the branch you're targeting.

### `GENERAL`

**Where it shows up:** nowhere directly — `GENERAL` is the escape hatch for plugin code that doesn't fit any other kind. Two main uses:

- **Shared libraries** — code reused across multiple addons. Set `load_on_reg=True` and the file gets imported at startup; everything in it becomes importable to other plugins as `import <addon-id>`. The `libwebconnect` addon, depended on by every Web Connect Pack, is the archetype.
- **Pluggable categories** — `GENERAL` plugins can declare a `category` string; other code can then ask the plugin manager for all `GENERAL` plugins of category `WEBSTUFF` (CSS stylesheets for the narrative website report) or `Filters` (filter-rule providers). New categories are rare; the published ones are documented in [addons-development](https://gramps-project.org/wiki/index.php/Addons_development#Registered_GENERAL_Categories).

The category `WEBSTUFF` is the one most addon authors meet: addons that ship a stylesheet for the narrative website register as `GENERAL, category="WEBSTUFF"` and the website report picks them up automatically.

**The plugin-data API.** Three registration fields drive the category machinery. A plugin contributes data either statically (`data = [...]` right in the `.gpr.py`) or dynamically — if the implementation module defines a function named `load_on_reg(dbstate, uistate, plugin)`, Gramps calls it at registration and its return value becomes the plugin's data. A `process = "function_name"` field names a function applied over the accumulated data when a consumer asks for it. Consumers query by category through the plugin manager:

```python
from gramps.gui.pluginmanager import GuiPluginManager

plugman = GuiPluginManager.get_instance()
plugman.get_plugin_data("WEBSTUFF")       # all data from WEBSTUFF plugins
plugman.process_plugin_data("WEBSTUFF")   # same, run through the process function
```

Note there is **no automatic loading** of `GENERAL` plugins beyond this: without `load_on_reg=True` the module sits unimported until something imports it explicitly.

## Multiple kinds in one addon

A single `.gpr.py` can call `register(...)` more than once. The classic case is a report that also registers a Quick View entry for the same underlying logic (`gramps/plugins/quickview/all_events.py` does this for events). Each `register()` call is independent; only the addon folder / `id` and the implementation file(s) are shared.

## See also

- [01-overview](01-overview.md) — what an addon is, file roles, first Gramplet end-to-end.
- [02-tutorials](02-tutorials.md) — per-kind walkthroughs.
- [04-fundamentals](04-fundamentals.md) — the cross-cutting concepts every kind relies on, including [the provided environment](04-fundamentals.md#the-provided-environment) every kind inherits from Gramps' startup.
- [`gramps/gen/plug/_pluginreg.py`](https://github.com/gramps-project/gramps/blob/maintenance/gramps60/gramps/gen/plug/_pluginreg.py) — the authoritative definition of all the constants and `expand_*` attribute lists per kind.
- [6.0 Addons](https://gramps-project.org/wiki/index.php/6.0_Addons) — the canonical catalogue of what already exists per kind; reading a similar addon's source is your fastest second tutorial.
