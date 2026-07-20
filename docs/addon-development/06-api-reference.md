# API Reference

[← Previous](05-data-access.md) · [Index](01-overview.md) · [Next →](07-testing.md)

<!--
  Curated reference. Two principles:
    1. Anything an addon may import lives under gramps.gen.*. gen is
       self-contained (cannot import from gui / plugins) — see
       AGENTS.md "Submodule Import Rules".
    2. This page is a NAVIGATOR. For exhaustive signatures, read the
       source of the module referenced (or the upstream Sphinx docs).
       Adding signatures here would have us chasing version drift.

  Scraped sources:
    - report-api.md (93L) — TextDoc / DrawDoc / GVDoc structure trees
    - report-generation.md (88L) — Text / Draw / Graphviz / Web categorisation
-->

## Overview

The curated `gramps.gen.*` surface addons are allowed to import. `gen` is the self-contained core submodule (it must not import from `gui` or `plugins`); importing only from `gen` keeps an addon portable across UI variants and testable without a display.

This page is a navigator, not a generated API dump. For exhaustive signatures, read the source of the module referenced — the [upstream Sphinx docs](https://gramps-project.org/docs/) carry the same information formatted for browsing.

## Allowed surface

### Database

| Module / class                            | Notes                                                              |
|-------------------------------------------|--------------------------------------------------------------------|
| `gramps.gen.db.base.DbReadBase`           | Read-only DB interface — what addon code typically receives        |
| `gramps.gen.db.base.DbWriteBase`          | Mutation interface; reach via `db` after `with DbTxn(...) as trans`|
| `gramps.gen.db.txn.DbTxn`                 | Transaction context manager — required for every write             |
| `gramps.gen.db.utils.open_database`       | Open a tree by path; used in repro scripts and tests               |
| `gramps.gen.db.exceptions`                | DB-layer exception hierarchy                                       |

See [05-data-access](05-data-access.md) for the addon-facing patterns that use this surface.

### Object model

| Module                              | Notes                                                                  |
|-------------------------------------|------------------------------------------------------------------------|
| `gramps.gen.lib`                    | Every primary class: `Person`, `Family`, `Event`, `Place`, `Source`, `Citation`, `Repository`, `Media`, `Note`, `Tag`. Plus value classes (`Name`, `Date`, `Address`, `Surname`, `EventRef`, …). |
| `gramps.gen.lib.person.Person`      | The gender constants (`Person.MALE`, `Person.FEMALE`, `Person.UNKNOWN`) are class attributes |

The full inventory is large; the cheapest reference is the source under [`gramps/gen/lib/`](https://github.com/gramps-project/gramps/tree/maintenance/gramps60/gramps/gen/lib). Every primary class has matching `get_*` / `set_*` accessors; relationships are exposed as handle lists (`get_family_handle_list`) or ref lists (`get_event_ref_list`, `get_child_ref_list`).

### Types and IDs

| Module                | Notes                                                                                       |
|-----------------------|---------------------------------------------------------------------------------------------|
| `gramps.gen.types`    | `PersonHandle`, `FamilyHandle`, …, `PersonGrampsID`, `FamilyGrampsID`, …                    |

Prefer these over bare `str` in addon code that handles either kind of identifier. It documents intent for the next reader and makes mistakes (handle vs ID) catchable with `mypy`. See [16-guidelines → Coding style](16-guidelines.md#coding-style).

### Errors

| Module                              | Use                                                                  |
|-------------------------------------|----------------------------------------------------------------------|
| `gramps.gen.errors`                 | Raise existing exceptions here before inventing new classes          |
| `gramps.gen.errors.HandleError`     | Invalid or missing handles                                           |
| `gramps.gen.db.exceptions`          | DB-layer-specific exceptions                                         |

### Plugin base classes

| Class / module                                          | Used by                            |
|---------------------------------------------------------|------------------------------------|
| `gramps.gen.plug.Gramplet`                              | `GRAMPLET` addons                  |
| `gramps.gen.plug.report.Report`                         | `REPORT` addons                    |
| `gramps.gen.plug.report.MenuReportOptions`              | Options form for report addons     |
| `gramps.gen.plug.report.stdoptions`                     | Pre-built options like locale chooser |
| `gramps.gen.plug.docgen.BaseDoc`                        | `DOCGEN` addons (base)             |
| `gramps.gen.plug.docgen.TextDoc`                        | Text reports                       |
| `gramps.gen.plug.docgen.DrawDoc`                        | Graphical (drawing) reports        |
| `gramps.gen.plug.docgen.GVDoc`                          | Graphviz-based reports             |
| `gramps.gen.plug.docgen.FontStyle`, `ParagraphStyle`    | Style definitions for text reports |
| `gramps.gen.plug.docgen.PaperStyle`, `PaperSize`        | Page geometry for graphical reports |
| `gramps.gen.plug.menu`                                  | Options-form widgets               |
| `gramps.gen.filters.rules.Rule` (and namespace bases)   | `RULE` addons                      |
| `gramps.gen.simple.SimpleAccess`, `SimpleDoc`           | Quick Views                        |

Most `gramps.gui.*` classes are *internal*; addons that import from there will break across Gramps versions. The exceptions used in this manual's tutorials — `gramps.gui.plug.tool.Tool`, `gramps.gui.plug.quick.QuickTable`, `gramps.gui.dialog.OkDialog` — are documented because every existing Tool / Quick View in core uses them, but they are nevertheless GUI-coupled. Pure logic factored out into modules that import only from `gen` stays unit-testable without a display.

### Report categories

For `REPORT` addons, register with one of these category constants (see [`_pluginreg.py:141-149`](https://github.com/gramps-project/gramps/blob/maintenance/gramps60/gramps/gen/plug/_pluginreg.py)):

| Category               | Docgen interface       | Notes                                                  |
|------------------------|------------------------|--------------------------------------------------------|
| `CATEGORY_TEXT`        | `TextDoc`              | Text reports — PDF, HTML, ODF, plain text              |
| `CATEGORY_DRAW`        | `DrawDoc`              | Graphical reports drawn at exact coordinates           |
| `CATEGORY_GRAPHVIZ`    | `GVDoc`                | Graphviz / DOT input — laid out by graphviz            |
| `CATEGORY_WEB`         | (direct file I/O)      | Narrative website — writes HTML/CSS directly to files  |
| `CATEGORY_BOOK`        | `TextDoc` + `DrawDoc`  | A composition of Text and Draw reports                 |
| `CATEGORY_TREE`        | `DrawDoc`              | Genealogical tree-chart layouts                        |
| `CATEGORY_CODE`        | (none)                 | Catch-all for reports that don't fit elsewhere         |

Only `CATEGORY_TEXT` and `CATEGORY_DRAW` participate in `CATEGORY_BOOK`.

### Document API: structure at a glance

The three docgen interfaces have distinct hierarchies. Knowing which container nests what saves a long trip through the source.

**`TextDoc` — sequential text layout, paginated by the backend.**

```
Document
├── Paragraph
├── Pagebreak
├── Table
│   └── Row
│       └── Cell
│           ├── Paragraph
│           └── Image
└── Image
```

Paragraph styles drive titles, body text, list entries. The backend or external viewer handles pagination, except where a manual `Pagebreak` is inserted. Index marks attach to text within a paragraph (`gramps.gen.plug.docgen.IndexMark`), feeding the table of contents in Book reports.

**`DrawDoc` — exact-coordinate graphics on a frame.**

```
Document
└── Frame
    ├── Line
    ├── Polygon
    ├── Box
    └── Text
```

The frame is the drawing surface; elements get placed by coordinates supplied by the report. The origin is the top-left of the usable area (page minus margins). Graphical reports need to honour `PaperStyle.get_usable_width()` / `…_height()` — drawing into the margins is a contract violation.

**`GVDoc` — graphviz model.**

```
Document
└── Subgraph
    ├── Node
    ├── Link
    └── Comment
```

The report defines nodes, links, and comments; layout is the external graphviz binary's job. This is why `requires_exe=["dot"]` appears on Graphviz-based addons.

### Paper geometry (Draw / Tree only)

`gramps.gen.plug.docgen.PaperStyle` holds:

- the paper size (a `PaperSize` instance),
- margins,
- orientation (portrait / landscape).

Convenience accessors `get_usable_width()` and `get_usable_height()` return the drawing-area dimensions (paper size minus margins, in orientation order — width is always horizontal). Text reports don't need to read these; the backend paginates around them.

### Locale and translation

| Module / class                                              | Use                                                        |
|-------------------------------------------------------------|------------------------------------------------------------|
| `gramps.gen.const.GRAMPS_LOCALE` (alias `glocale`)          | The live locale; entry point for `_()` injection           |
| `glocale.get_addon_translator(__file__).gettext`            | Bind `_` to the addon's own `po/` catalog                  |
| `gramps.gen.utils.grampslocale.GrampsLocale`                | Instantiate directly to pin a locale in repro scripts      |
| `glocale.translation.ngettext`                              | Plural-aware translation                                   |
| `glocale.translation.sgettext`                              | Strip translator-hint prefix; used with `"hint | msg"` form|

See [04-fundamentals → Translation](04-fundamentals.md#translation) for the addon-side opt-in, and [08-debug → Reproduction scripts that bypass the GUI](08-debug.md#reproduction-scripts-that-bypass-the-gui) for the `GrampsLocale(localedir, languages)` pattern in repros.

### Filters and selection

| Module / class                                          | Use                                            |
|---------------------------------------------------------|------------------------------------------------|
| `gramps.gen.filters.GenericFilterFactory`               | Construct a filter for a namespace             |
| `gramps.gen.filters.rules`                              | The rule catalogue (one subpackage per namespace) |
| `gramps.gen.filters.rules.<namespace>.Rule`             | Base class to subclass when writing a custom rule (see [02-tutorials](02-tutorials.md#a-custom-filter-rule)) |

The modern rule entry point is `apply_to_one(db, obj)` (see [`_rule.py:162`](https://github.com/gramps-project/gramps/blob/maintenance/gramps60/gramps/gen/filters/rules/_rule.py#L162)). Older code used `apply()`.

### Logging

| Module / class            | Use                                                |
|---------------------------|----------------------------------------------------|
| `logging.getLogger(__name__)` | Module-level logger; see [04-fundamentals → Logging](04-fundamentals.md#logging) |

There's nothing addon-specific to import here; addons use stdlib `logging` exactly like Gramps' own modules do.

### Simple Access (Quick Views)

| Class                                       | Use                                                            |
|---------------------------------------------|----------------------------------------------------------------|
| `gramps.gen.simple.SimpleAccess`            | High-level DB read interface — hides handles and refs          |
| `gramps.gen.simple.SimpleDoc`               | Matching write interface — `title`, `paragraph`, `header1`, …  |
| `gramps.gui.plug.quick.QuickTable`          | Clickable result table (GUI-coupled; QuickView-only)           |

See [02-tutorials → A Quick View](02-tutorials.md#a-quick-view) for the standard pattern.

## What's NOT API

Anything under `gramps.gui.*` or `gramps.plugins.*` is internal to the shipped distribution; addons that import from there break across Gramps versions. The exceptions (Tool / Quick View / Dialog) are documented above and unavoidable for those addon kinds, but pure logic should be factored out behind a `gen.*`-only boundary so it stays unit-testable without a display.

If you find yourself reaching into `gramps.gui.*` or `gramps.plugins.*` for something that *isn't* tied to GUI display, the right move is usually to ask upstream to promote what you need into `gen`. The [committing policies wiki page](https://www.gramps-project.org/wiki/index.php/Committing_policies) and the gramps-devel mailing list are the channels.

## See also

- [03-addon-kinds](03-addon-kinds.md) — which kinds use which base classes.
- [04-fundamentals](04-fundamentals.md) — the cross-cutting concepts (logging, translation, signals) backed by this surface.
- [05-data-access](05-data-access.md) — patterns over the DB API.
- [14-compatibility](14-compatibility.md) — what changes across Gramps versions in this surface.
- [Report API](https://gramps-project.org/wiki/index.php/Report_API), [Report Generation](https://gramps-project.org/wiki/index.php/Report_Generation) — standalone wiki references for the docgen subsystem.
- [Simple Access API](https://gramps-project.org/wiki/index.php/Simple_Access_API) — the standalone wiki page for `SimpleAccess` / `SimpleDoc`.
- [Gramps Developer Reference](https://gramps-project.org/docs/) — upstream Sphinx-generated API docs.
