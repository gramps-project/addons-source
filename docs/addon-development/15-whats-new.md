# What's New

[← Previous](14-compatibility.md) · [Index](01-overview.md) · [Next →](16-guidelines.md)

## Summary

API and convention changes that affect addon authors, per Gramps minor release. The audience is someone with a working addon on the previous version asking *"what do I need to know before I bump `gramps_target_version`?"*

This page is the **addon-author slice** of the change log. It's not the full release notes — those live on the wiki proper. Entries here are filtered for things that affect:

- the `gramps.gen.*` import surface,
- the plugin-registration surface (`_pluginreg.py`),
- the docgen and report APIs,
- per-addon translation / locale plumbing,
- the addon discovery and loading mechanism.

Each release gets its own section, and within it the same four headings: **Added**, **Changed**, **Deprecated**, **Removed**. That shape is deliberate — it maps to the four things a port has to react to. *Added* is opportunity you can ignore safely. *Changed* is where an addon that still runs may now behave differently. *Deprecated* is a deadline you have until the next major release to meet. *Removed* is the one that breaks on load. Reading a release section top to bottom therefore goes from optional to urgent.

Currently covered: **Gramps 6.1** and **Gramps 6.0** in full, with **earlier releases** summarised rather than enumerated, since an addon that far behind needs a port rather than a change list. **How to read this page** sets out the two conventions worth knowing before you rely on an entry: sections are *incremental*, describing the delta from the previous minor rather than the cumulative surface, and entries carry an inline citation to the upstream commit or PR where one exists, so any claim here can be checked against the source. Entries without a citation record conventions that emerged rather than discrete changes.

For the current surface — what exists right now, rather than what changed — use [06-api-reference](06-api-reference.md). For the practical *how to port* guidance — what to check on a cross-version port, when to maintain parallel branches — see [14-compatibility](14-compatibility.md). This page is the inventory; 14-compatibility is the procedure.

## Gramps 6.1

Targeted from `maintenance/gramps61`; `master` until the 6.1.0 release.

### Added

- **Plugin discovery follows symlinks.** Symlinking a working-tree addon folder into the user plugin directory now works, with realpath-based dedup so cycles terminate. Commit [`9443dcbb30`](https://github.com/gramps-project/gramps/commit/9443dcbb30), with `_manager_symlinks_test.py` covering both the scan-via-symlink case and loop termination. The dev loop on Linux/macOS becomes *symlink once, edit in place*. (See [01-overview → Where addons live](01-overview.md#where-addons-live).)

### Changed

- **Windows toolchain migrated from MINGW64 to MSYS2 UCRT64.** Gramps' Windows build moved in PR [#2198](https://github.com/gramps-project/gramps/pull/2198) (merged 2026-04-19). MINGW64's Python target triple is rejected by orjson's `maturin` backend; the migration was forced.
  - **Impact on addon authors:** Windows addon testing targets `maintenance/gramps61` and `master` only — Windows on 6.0 is not upstream-tested. See [14-compatibility → Windows toolchain migrated to UCRT64](14-compatibility.md#windows-toolchain-migrated-to-ucrt64).
- **GExiv2 version handling rewritten.** addons-source PR [829](https://github.com/gramps-project/addons-source/pull/829) rewrote how GExiv2's version is read and pinned. An addon's `requires_gi=[("GExiv2", "0.10")]` declaration may need adjustment; read the EditExifMetadata addon's GExiv2 code on the target branch before assuming a 6.0 pin transfers. See [14-compatibility → GExiv2 version handling rewritten](14-compatibility.md#gexiv2-version-handling-rewritten).
- **BSDDB-on-Windows test skip.** A skip rule for BSDDB on Windows landed on `maintenance/gramps61`. Addons exercising the BSDDB backend in tests need to account for its absence on Windows 6.1 (use `@unittest.skipUnless(...)`; see [07-testing → Skip cleanly](07-testing.md#skip-cleanly)).

### Deprecated

*None tracked here yet.* The authoritative reference for runtime deprecations is the source — search `gramps/gen/**/*.py` on the target branch for `DeprecationWarning`. See [14-compatibility → Reading the deprecation signal](14-compatibility.md#reading-the-deprecation-signal) for the recipe.

### Removed

*None tracked here yet.*

## Gramps 6.0

The manual's baseline target. Addons declaring `gramps_target_version="6.0"` run on 6.0.x and are not loaded by 6.1 or later (and vice versa); see [14-compatibility → `gramps_target_version` semantics](14-compatibility.md#gramps_target_version-semantics).

### Added

- **SQLite became the default database backend.** New trees are SQLite-backed unless the user explicitly chooses BSDDB. Addons that do straight `gramps.gen.db.*` reads keep working unchanged — the abstraction holds — but addons that bypassed the abstraction (e.g. reaching into BSDDB-specific cursor APIs) need to migrate to the portable interface.

### Changed

- **Python 3.10+ minimum.** Older Pythons no longer run Gramps 6.0, which means addons can use modern type-hint syntax — `X | None` instead of `Optional[X]`, `list[X]` instead of `typing.List[X]` — without a compatibility shim. See [16-guidelines → Coding style](16-guidelines.md#coding-style).

### Deprecated

*Verify against the source.* `DeprecationWarning`s on `maintenance/gramps60` are the authoritative list.

### Removed

*None tracked here yet.*

## Earlier releases

The 5.x → 6.0 transition was a major release; many APIs changed and the maintenance window for addons targeting earlier minors is closing. The authoritative reference for cross-major changes is the [Gramps wiki's release-notes pages](https://www.gramps-project.org/wiki/index.php/Portal:Using_Gramps#Release_notes).

Practical guidance: addons still targeting 5.x should pin `gramps_target_version="5.2"` (the last 5.x minor) and live on the matching `addons-source` branch; the cross-major port is a separate exercise from the per-minor deltas this page tracks.

## How to read this page

- Each release section is **incremental** — entries describe what changed *from the previous minor*, not the cumulative API surface.
- Where an entry has an upstream commit, PR, or addon-side fix, it's cited inline so the change is auditable. Entries without a citation reflect conventions that emerged rather than discrete commits.
- The *current* surface (what's available right now) lives in [06-api-reference](06-api-reference.md), not here.

## See also

- [14-compatibility](14-compatibility.md) — porting an addon across these releases; the practical companion to this inventory.
- [06-api-reference](06-api-reference.md) — the current `gramps.gen.*` surface.
- [Portal:Using Gramps → Release notes](https://www.gramps-project.org/wiki/index.php/Portal:Using_Gramps#Release_notes) — upstream release notes (full, not addon-filtered).
- [`gramps/NEWS`](https://github.com/gramps-project/gramps/blob/maintenance/gramps61/NEWS) — the in-tree change log on the target branch.
