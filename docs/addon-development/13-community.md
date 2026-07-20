# Community

[← Previous](12-packaging.md) · [Index](01-overview.md) · [Next →](14-compatibility.md)

<!--
  The post-merge community steps — upstream Addons_development steps 5-8
  (list on the wiki, document on the wiki, announce, support), adapted.
  Everything here happens on the wiki / forum / Mantis, not in a repo.
-->

## Overview

When the PR is merged and the package published ([Packaging](12-packaging.md)), the addon *exists* — but nobody can find it, read about it, or reach you about it. This page covers the four steps that make a merged addon part of the ecosystem: the addon-list entry, the addon's own wiki page, the announcement, and the ongoing support duty. None of them touch code; all of them decide whether the addon gets used.

## List your addon

Add a row for your addon to the release's addon list — [6.0 Addons](https://gramps-project.org/wiki/index.php/6.0_Addons) for the current release, or the next release's list (e.g. [6.1 Addons](https://gramps-project.org/wiki/index.php/6.1_Addons)) if the addon targets an unreleased minor. Copy an existing row and fill in the columns; the [Addon list legend](https://gramps-project.org/wiki/index.php/Addon_list_legend) explains what each column means (type, audience, rating, contact, download).

The row skeleton, as it appears in the list page's wiki source:

```
|- <!-- Copy this section and list your Addon -->
|<!-- Plugin / Documentation -->
|<!-- Type -->
|<!-- Image -->
|<!-- Description -->
|<!-- Use -->
|<!-- Rating (out of 4) -->
|<!-- Contact -->
|<!-- Download -->
|-
```

This listing is what users browse; the Plugin Manager's download listing ([Packaging](12-packaging.md) → the `make.py listing` step) is what Gramps itself reads. An addon needs both.

## Document your addon

Give the addon its own wiki support page — the page the addon list's first column links to. Examine other addons' pages for the format; the conventional skeleton:

```
{{Third-party plugin}}   <!-- standard banner shown on every addon page -->

== Usage ==

=== Configure Options ===

== Features ==

== Prerequisites ==

== Issues ==

[[Category:Addons]]
[[Category:Plugins]]
[[Category:Developers/General]]
```

Only add the sections the addon needs — a Gramplet with no options doesn't need *Configure Options*. The `{{Third-party plugin}}` template expands to the standard notice that the addon is third-party and where to report problems; every addon page carries it.

## Announce the addon

Join the [Gramps forum](https://gramps.discourse.group/) and announce the addon to users: what it does, why you built it, and how to use it. This is the step authors skip most — and an unannounced addon is invisible to the users who would have wanted it.

## Support it through the issue tracker

Register on the [Gramps MantisBT tracker](https://gramps-project.org/bugs/) and check it regularly. **There is no automated notification** that routes issues against your addon to you — reports sit unseen unless you look. (For fix workflow, the tracker conventions, and the commit-message trailers that close Mantis issues, see [Rules](16-guidelines.md) → Commit messages.)

Users don't read code and they make assumptions; reports will be ambiguous or wrong about the cause. Be kind and guiding — a curt reply from an addon's own author is the fastest way to lose the users the announcement won.

## Why addons exist

Worth keeping in mind across the maintenance years that follow ([Compatibility](14-compatibility.md), [What's New](15-whats-new.md)): the addon channel is deliberately low-barrier. It provides:

- a quick way for anyone to share their work — the project has never refused an addon;
- a place for a component to evolve continuously, often before core acceptance;
- a home for plugins that will never be accepted into core but are loved by many users;
- a place for experimental components to live.

## See also

- [Packaging](12-packaging.md) — the build/listing mechanics that precede these steps.
- [Compatibility](14-compatibility.md) — keeping the published addon working across Gramps versions.
- [Addons development](https://gramps-project.org/wiki/index.php/Addons_development) — the upstream page these steps derive from.
- [6.0 Addons](https://gramps-project.org/wiki/index.php/6.0_Addons) — the addon list itself.
