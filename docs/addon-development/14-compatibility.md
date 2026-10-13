# Compatibility

[← Previous](13-community.md) · [Index](01-overview.md) · [Next →](15-whats-new.md)

<!--
  Cross-version porting for addon authors. Concrete deltas cited here
  are verified against gramps-project/gramps and gramps-project/addons-source.
  Cite path:lines or commit/PR# explicitly so this chapter can be audited.
-->

## Summary

How an addon survives — or fails — across Gramps versions. Two things to understand: the `gramps_target_version` contract (Gramps' minor matters; majors aren't even discussed), and the concrete deltas between adjacent maintenance branches that bite ports in practice.

A working addon for Gramps 6.0 is usually a working addon for 6.1 with **zero** code changes. The exceptions are documented here; when in doubt, the safest move is to maintain one addon folder per Gramps minor in parallel `maintenance/gramps*` branches of `addons-source`.

The page starts with the contract itself — what **`gramps_target_version`** actually promises, and how to support several minors at once without forking your own code. **Branch targeting for fixes** answers the question that follows immediately: given a bug that affects two releases, which branch does the fix go to, and how does it reach the other. Then the section that earns the page its keep — **"applies cleanly" is not "remains correct"**: a patch that merges without conflict onto another branch can still be wrong there, because the surrounding code has moved. Cherry-picking is not verification.

**Notable 6.0 → 6.1 deltas** is the concrete inventory for the port most authors face now: plugin discovery following symlinks (which changes the development loop on Linux and macOS), the Windows toolchain move to UCRT64, the GExiv2 version-handling rewrite, and the BSDDB-on-Windows skip. **Reading the deprecation signal** covers how upstream telegraphs that something is going away, so you can act on a warning rather than on a breakage. The page closes with **sanity checks before a port** — the short list to run before claiming an addon supports a new minor.

This page is the *procedure*; the per-release inventory of what changed is [What's New](15-whats-new.md).

## `gramps_target_version` semantics

The `.gpr.py` registration declares which Gramps minor the addon targets:

```python
register(
    GRAMPLET,
    id="MyAddon",
    gramps_target_version="6.0",   # major.minor
    ...
)
```

Gramps matches this **on the major.minor pair** at plugin discovery. A `6.0` addon will not load in 6.1, and a `6.1` addon will not load in 6.0 — the plugin manager silently skips the registration entry.

### Supporting multiple minors

The one-addon-per-minor convention is enforced by the branch directory split in the [`addons/`](https://github.com/gramps-project/addons) repo and the matching `maintenance/gramps*` branches in [`addons-source/`](https://github.com/gramps-project/addons-source). For an addon that supports 6.0 and 6.1:

```
addons-source @ maintenance/gramps60: MyAddon/MyAddon.gpr.py declares "6.0"
addons-source @ maintenance/gramps61: MyAddon/MyAddon.gpr.py declares "6.1"
```

A single `make.py gramps60 build MyAddon` on `maintenance/gramps60` produces the 6.0-targeted `.addon.tgz`; the same command with `gramps61` on `maintenance/gramps61` produces the 6.1-targeted one. See [12-packaging](12-packaging.md) for the workflow.

When the **code is identical** between minors, the maintainer forward-merges the `maintenance/gramps60` branch into `maintenance/gramps61` and rebuilds — no per-minor source maintenance needed.

When the code **isn't identical** (e.g. the GExiv2 version handling delta below), the two branches diverge intentionally, and you commit the minor-specific fix to each.

## Branch targeting for fixes

The rule that determines which branch a fix lands on differs between the two repos:

- **`addons-source/`** → `maintenance/gramps60`. Gary cherry-picks forward to `gramps61`. (Gary Griffin, addons-source PR 915, 2026-05-24.)
- **`gramps/`** (core) → `maintenance/gramps61`. Fixes and cleanups go on the current production branch and forward-merge to `master`. Only genuinely new-feature work targets `master`. (jralls, gramps#2298.)

A reviewer's instruction on a specific PR overrides the default (e.g. Nick-Hall asking for `master` on gramps#2299). See [16-guidelines → Contributor workflow](16-guidelines.md#contributor-workflow) for the normative form.

## "Applies cleanly" is not "remains correct"

A cherry-pick that `git` accepts without conflict can still be wrong on the target branch — the branches' *related* code may have changed even though the patch's hunks didn't.

**Concrete example.** addons-source PR 829 rewrote GExiv2 version handling on `maintenance/gramps61` only. An addon that pins `requires_gi=[("GExiv2", "0.10")]` is fine on 6.0; the same pin on 6.1 may need adjustment because the code that reads the pin has changed shape. A cherry-pick of the addon would land cleanly and still be wrong.

**The check.** Before treating a cross-branch port as done, diff the related code on the target branch — not just the file the patch touched. Read the surrounding functions; read the modules the declaration interacts with.

## Notable 6.0 → 6.1 deltas

The complete delta lives in the Gramps changelog; the entries below are the ones that have repeatedly affected addon authors.

### Plugin discovery follows symlinks

Gramps 6.0 plugin discovery **does not** follow symlinks; the addon folder must be physically present under the plugin path. Gramps 6.1 follows symlinks with realpath-based dedup against symlink loops (commit [`9443dcbb30`](https://github.com/gramps-project/gramps/commit/9443dcbb30) on `maintenance/gramps61`, with `_manager_symlinks_test.py` covering both the scan-via-symlink and loop-terminates cases).

**Impact on dev loop.** On 6.0, copy or `rsync` the working tree into the user plugin directory on every save. On 6.1+ Linux/macOS, symlink once and edit in place. On Windows, the symlink test is skipped because the platform's symlink behaviour is inconsistent without elevated privileges; physical copy remains the safe approach on 6.1+ too.

### Windows toolchain migrated to UCRT64

Gramps' Windows build migrated from MINGW64 to MSYS2 **UCRT64** in gramps PR [#2198](https://github.com/gramps-project/gramps/pull/2198) on `maintenance/gramps61` (merged 2026-04-19). MINGW64's Python target triple is rejected by orjson's `maturin` backend, so the change was forced.

**Impact on addon Windows testing.** Addon tests run on UCRT64 on 6.1 and master only. Windows testing on 6.0 is unsupported by upstream's addons-source CI. See [07-testing](07-testing.md) for the filename-prefix convention that selects per-OS tests.

### GExiv2 version handling rewritten

addons-source PR [829](https://github.com/gramps-project/addons-source/pull/829) rewrote the GExiv2 version handling on `maintenance/gramps61`, in the EditExifMetadata addon. An addon that interacts with GExiv2 via `requires_gi` may need branch-specific declarations.

**The check.** When the addon imports `GExiv2` or declares it in `requires_gi`, read the EditExifMetadata addon on the *target* branch before assuming a pin is correct.

### BSDDB-on-Windows skip

A test-skip rule for BSDDB on Windows landed on `maintenance/gramps61` only. Addons that exercise the BSDDB backend in tests need to account for the absence of BSDDB on Windows 6.1, not assume the 6.0 behaviour transfers.

## Reading the deprecation signal

When core deprecates an API, addon authors see two things in order:

- A `DeprecationWarning` raised the first time the deprecated symbol is touched. Visible when Gramps runs with `python -W default`, or in the Gramps log window at `WARNING` level.
- A scheduled removal in the next major release.

**Practical step.** Once a release, launch with `python -W default` against `example.gramps` and skim the log window. Every `DeprecationWarning` is a maintenance task for the next minor; deferring them until removal turns "the addon shows up but does nothing" bugs into the dominant porting failure mode.

For the actual deprecated surface in the running Gramps, the authoritative reference is the source — search `gramps/gen/**/*.py` for `DeprecationWarning` on the target branch.

## Sanity checks before a port

1. **Read the new branch's relevant code.** Not the patch — the surrounding code. The patch lands; the assumption around it may have shifted.
2. **Run the addon's tests on the new branch.** The whole point of the per-OS prefix convention in [07-testing](07-testing.md) is to catch this exact case.
3. **Reproduce against `example.gramps` on both branches.** The canonical fixture is identical across minors, so an output difference is an actionable signal.
4. **Check the open PRs against `gramps` and `addons-source` for anything affecting your addon.** A fix may be in flight upstream; verifying that PR is usually better than writing your own.

## See also

- [01-overview → Where addons live](01-overview.md#where-addons-live) — the 6.0 vs 6.1 symlink discovery rule, with the dev-loop consequence.
- [04-fundamentals → The `.gpr.py` registration file](04-fundamentals.md#the-gprpy-registration-file) — `gramps_target_version` declaration in context.
- [12-packaging](12-packaging.md) — how the per-minor build flow uses `gramps_target_version`.
- [15-whats-new](15-whats-new.md) — scheduled per-release changes affecting addon authors.
- [16-guidelines → Contributor workflow](16-guidelines.md#contributor-workflow) — normative branch-targeting rules.
