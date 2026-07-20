# Roadmap

[← Previous](16-guidelines.md) · [Index](01-overview.md)

## Overview

Forward-looking view of the addon-development surface — what's planned, what's in flight, what's slated for deprecation, and what open questions will eventually become rules. The audience is an addon author asking "what do I need to plan around?"

This page is the **prospective** counterpart to [What's new](https://gramps-project.org/wiki/index.php/Gramps_6.0_Wiki_Manual_-_Addon_Development_-_Whats_New), which is retrospective. An item moves from this page to *What's new* once it ships in a release.

## How to read this page

Each entry should answer four things:

| Field | Meaning |
|-------|---------|
| **Status** | proposed / accepted / in-flight / shipped / deferred / rejected |
| **Target** | Gramps version (`6.1`, `6.2`, ...) or "unscheduled" |
| **Impact** | what addon authors need to do (rewrite / opt-in / nothing) |
| **Tracking** | PR / Mantis bug / wiki RFC / mailing-list thread |

A roadmap entry without a tracking link is a wish, not a plan; either add the link or move the entry to a separate "ideas" section.

## In flight

<!-- TODO: items currently being worked on upstream that will affect
     addon authors. Source these from open gramps / addons-source PRs
     that touch gramps.gen.* or the plugin registration surface. -->

- _none recorded yet_

## Accepted but not yet implemented

<!-- TODO: maintainer-blessed changes with no PR yet. Source from
     accepted Mantis feature requests, wiki RFCs, mailing-list
     decisions. -->

- _none recorded yet_

## Deprecations and removals

<!-- TODO: API surface marked deprecated with a removal target. Pull
     from DeprecationWarning sites in gramps.gen.* and the
     "Removed in N" notes in upstream release notes. -->

- _none recorded yet_

## Open questions

<!-- TODO: design questions affecting addons where the answer isn't
     settled yet. A reader landing here should be able to find the
     thread and contribute. Examples of the shape:
       - "Should Plugin Manager hiding apply to core plugins?"
         (Mantis 10604 — single-flag `core` design emerging.)
       - "Should addon `version` be author-managed or maintainer-managed
         per repo?" -->

- _none recorded yet_

## Deferred / rejected

<!-- TODO: things that came up, got considered, and were declined.
     Recording them here is the antidote to re-proposing the same
     shape and re-running the same debate. Cite the closing PR /
     thread so a future reader can see WHY. -->

- _none recorded yet_

## Documentation roadmap

The doc set itself is in flight. Pages with `managed: false` front-matter are draft stubs and will not appear in published output until promoted. Current draft state — flip to `managed: true` page by page as content lands:

### Publishing-pipeline conventions (now supported)

What `md2wiki.py` and `md2pdf.py` handle as of 2026-05-30 — pages authored with these conventions render correctly in both wikitext and PDF output. Verified by running both pipelines on [Fundamentals](04-fundamentals.md) (which contains an SVG embed + Obsidian-internal links).

| Convention | Where converted | Notes |
|------------|-----------------|-------|
| `![[_media/foo.svg\|cap]]` Obsidian embed | `mdcommon.convert_obsidian_embeds` | Becomes `![cap](_media/foo.svg)` before pandoc |
| `[[Page]]` / `[[Page\|label]]` Obsidian-internal link | `mdcommon.convert_obsidian_internal_links` | Resolved via `mdcommon.build_title_map` (filename-stem → wiki title); unresolved targets error loudly |
| Markdown image with SVG src in PDF | `_preconvert_svgs` (md2pdf) | Pre-converted to PDF via `rsvg-convert` or `inkscape`; embeds natively in xelatex |
| Markdown image with relative path in PDF | `--resource-path` to pandoc | Resolved against the source file's directory |
| `[[File:_media/foo.svg]]` post-pandoc wikitext | `mdcommon.basenameify_file_refs` | Becomes `[[File:foo.svg]]` (MediaWiki's File: namespace is flat) |
| Media files alongside pages | `wikitransport.upload_if_changed` + `publish.upload_media_for` | SHA-1 dedup; uploaded BEFORE the page edit so refs never render red |
| HTML comments | `mdcommon.stash_html_comments` | Stashed around Obsidian preprocessors so syntax inside comments is not rewritten |

What the pipeline already handled before these additions:
- `[label](wiki:Page_Name)` → wikitext `[[Page|label]]` / PDF anchor or external URL.
- `<!--wiki:{{...}}-->` template shims → raw `{{...}}` wikitext / dropped from PDF.
- YAML front-matter → `title`, `categories`, `managed`.
- Fenced code with language tags, tables.

### Page-by-page state

The section is substantive across all seventeen pages. Open deepening work:

- [Tutorials](02-tutorials.md) — the screenshots for each tutorial's "Try it" closer are pending capture.
- [Data access](05-data-access.md) — worked examples for some API touch-points are still thin.
- [API Reference](06-api-reference.md) — needs periodic re-synchronisation against `gramps/gen/__init__.py` on the maintenance branch this manual targets.

## See also

- [What's new](https://gramps-project.org/wiki/index.php/Gramps_6.0_Wiki_Manual_-_Addon_Development_-_Whats_New) — retrospective counterpart.
- [Compatibility](14-compatibility.md) — porting guidance once an item ships.
- [Mantis bug tracker](https://gramps-project.org/bugs) — feature requests and design discussions originate here.
- [Gramps mailing lists](https://gramps-project.org/contact/) — where larger design questions get hashed out.
