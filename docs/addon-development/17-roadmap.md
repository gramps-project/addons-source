# Roadmap

[← Previous](16-guidelines.md) · [Index](01-overview.md)

## Summary

Forward-looking view of the addon-development surface — what's planned, what's in flight, what's slated for deprecation, and what open questions will eventually become rules. The audience is an addon author asking "what do I need to plan around?"

This page is the **prospective** counterpart to [What's new](15-whats-new.md), which is retrospective. An item moves from this page to *What's new* once it ships in a release.

**How to read this page** comes first because entries here carry less certainty than elsewhere in the section, and the four fields on each — **Status**, **Target**, **Impact**, **Tracking** — are what let you judge how much weight to put on one. The rule the page holds itself to is worth knowing as a reader: an entry without a tracking link is a wish rather than a plan, and belongs somewhere other than a roadmap.

Entries are then grouped by how settled they are. **In flight** is work already underway upstream. **Accepted but not yet implemented** is agreed in principle with nobody currently on it — the section where volunteering is most useful. **Deprecations and removals** is the one to check against your own addon, since it is where your future breakage is announced. **Open questions** are the genuinely undecided ones, which is also the invitation to weigh in before they harden into rules. **Deferred / rejected** exists so that a proposal that keeps resurfacing has a recorded answer and the reasoning behind it.

A final section tracks the **documentation roadmap** — the state of this manual itself, page by page, and the publishing-pipeline conventions behind it. That is meta rather than API, but it is where to look before proposing a documentation change.

## How to read this page

Each entry should answer four things:

| Field | Meaning |
|-------|---------|
| **Status** | proposed / accepted / in-flight / shipped / deferred / rejected |
| **Target** | Gramps version (`6.1`, `6.2`, ...) or "unscheduled" |
| **Impact** | what addon authors need to do (rewrite / opt-in / nothing) |
| **Tracking** | PR / Mantis bug / wiki RFC / mailing-list thread |

A roadmap entry without a tracking link is a wish, not a plan; either add the link or move the entry to a separate "ideas" section. *Open questions* are the one exception: a question that has not been raised upstream yet has nothing to link, and says so in its **Tracking** field rather than borrowing a citation that doesn't cover it.

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

- **Should CI flag an addon-root `__init__.py`?** Follows from the rule being a SHOULD NOT rather than a MUST NOT ([16-guidelines → Structure](16-guidelines.md#structure)).
  - **Status** open · **Target** unscheduled · **Impact** none for authors unless it becomes gating · **Tracking** none yet — raise on `addons-source` before acting
  - The case for a check: the seven current instances are mostly accidental — six of the seven files are empty, so nothing depends on them, and an advisory flag would stop the pattern spreading by imitation.
  - The case against gating on it: `maintenance/gramps60` has seven violations today, so a blocking check starts red and pressures a change to working addons for no functional gain. A lint also cannot tell the deliberate case (`PostgreSQLEnhanced`, which exposes a package API and needs its `__init__.py`) from a cargo-culted empty file.
  - If it lands, the shape that fits the rule's actual strength is **advisory** — report the file list, don't fail the build — or a gate with the existing seven grandfathered by allowlist. Gating a SHOULD is a contradiction; either the rule rises back to MUST on new evidence, or the check stays a warning.

## Deferred / rejected

<!-- TODO: things that came up, got considered, and were declined.
     Recording them here is the antidote to re-proposing the same
     shape and re-running the same debate. Cite the closing PR /
     thread so a future reader can see WHY. -->

- _none recorded yet_

## Documentation roadmap

The state of this manual itself. All seventeen pages are `managed: true` and publish; the only `managed: false` file in the section is the vault-internal sidebar. A page added later starts `managed: false` and is promoted once its content lands.

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

### Second publish target: `addons-source`

Since 2026-07-24 this manual has two homes. Alongside the wiki, it is exported to GitHub-native Markdown and lives in the repository it documents, as `docs/addon-development/` on both `maintenance/gramps60` and `maintenance/gramps61` (addons-source PR [994](https://github.com/gramps-project/addons-source/pull/994); `README.md` and `CONTRIBUTING.md` point at it per PR [995](https://github.com/gramps-project/addons-source/pull/995)). The repository's `AGENTS.md` cites `docs/addon-development/16-guidelines.md` as the normative rule set (PR [991](https://github.com/gramps-project/addons-source/pull/991)).

Consequences for anyone editing these pages:

- The **vault stays the source of truth**; the in-repo copy is generated, never hand-edited. Drift is detected by re-running the exporter and diffing in the target checkout before committing.
- A rules change here now lands in a repository whose agent guidelines *cite* it, so an error propagates further than the wiki. Verify a rule against the repository's actual implementation before stating it — the pins-location correction (per-addon versus repo-root `tests/__init__.py`) came from exactly this failure.
- Where `AGENTS.md` and [Rules](16-guidelines.md) disagree, upstream's own documentation is inconsistent; the fix is a report upstream, not a silent divergence here.

### Page-by-page state

The section is substantive across all seventeen pages. Open deepening work:

- [Tutorials](02-tutorials.md) — the screenshots for each tutorial's "Try it" closer are pending capture.
- [Data access](05-data-access.md) — worked examples for some API touch-points are still thin.
- [API Reference](06-api-reference.md) — needs periodic re-synchronisation against `gramps/gen/__init__.py` on the maintenance branch this manual targets.

## See also

- [What's new](15-whats-new.md) — retrospective counterpart.
- [Compatibility](14-compatibility.md) — porting guidance once an item ships.
- [Mantis bug tracker](https://gramps-project.org/bugs) — feature requests and design discussions originate here.
- [Gramps mailing lists](https://gramps-project.org/contact/) — where larger design questions get hashed out.
