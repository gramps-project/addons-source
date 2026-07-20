# Debug

[← Previous](07-testing.md) · [Index](01-overview.md) · [Next →](09-troubleshoot.md)

<!--
  Authoritative scraped source:
  ../04 - Technical Documentation/debugging-gramps.md (182L).
  That page is core-developer-oriented; this chapter cherry-picks the
  parts addon authors actually use (logger flag, profile hook, pdb)
  and adds addon-specific patterns (repro scripts via GrampsLocale,
  PrerequisitesCheckerGramplet, the Mac no-debug-mode caveat).
-->

## Overview

How to see what an addon is actually doing — where it logs, how to enable verbose output, and the patterns for reproducing a problem without sitting through a full Gramps launch cycle each time.

Most addon bugs are reachable through three escalating tools, in order: read the log window, enable per-logger debug output, or write a tight repro script that bypasses the GUI entirely. The heavier tools (pdb, gdb) are documented at the bottom for the cases where the lighter ones don't suffice.

## Where addon output goes

Two surfaces, both populated by the same logging calls:

| Surface                | When you see it                                                                                |
|------------------------|------------------------------------------------------------------------------------------------|
| **Gramps log window**  | Help → Log. Always populated. Visible to the user.                                              |
| **stderr / terminal**  | Whatever shell launched Gramps. Populated only when Gramps is run from a terminal.              |

The logging module that backs both is the stdlib `logging`; an addon's module-level logger feeds in like any other:

```python
import logging
LOG = logging.getLogger(__name__)

LOG.debug("Computed candidate set: %s", candidates)
LOG.info("Processed %d people", n)
LOG.warning("Skipping malformed event %s", event.gramps_id)
LOG.error("Could not parse %s", filename)
```

`__name__` for an addon resolves to the addon's `id` (e.g. `"MyAddon.myaddon"`), so the logger inherits the addon's name naturally — useful for per-logger filtering below.

**Don't use `print()`.** It bypasses both surfaces and breaks under windowed launches that have no terminal attached. The [16-guidelines](16-guidelines.md#runtime) page makes this a hard rule.

## Default log levels

Gramps configures the root logger at `WARNING` by default; `DEBUG` and `INFO` are filtered. Two ways to lower the bar:

### `--debug=<logger_name>`

Launch Gramps with the `--debug` flag to enable `DEBUG` for one named logger:

```bash
gramps --debug=MyAddon
gramps --debug=MyAddon.myaddon       # narrower
gramps --debug=gramps.gen.db          # for DB internals
```

Pass it more than once to enable several loggers. The flag is strictly opt-in per logger — that's why you set it on the launch command, not in code. Other loggers stay quiet, so you're not swimming in noise.

### Module-level override (development only)

When iterating tightly, drop a one-line override at the top of the implementation module:

```python
import logging
logging.getLogger(__name__).setLevel(logging.DEBUG)
```

Remove before committing — published addons should rely on `--debug=…` so users aren't forced into verbose output.

## Reproduction scripts that bypass the GUI

Restarting Gramps to test a one-line change burns minutes. For anything that *can* be tested without the GUI, write a tight repro script that instantiates the addon's testable pieces directly.

The pattern looks like this:

```python
# repro_<bug>.py — run with `python3 repro_<bug>.py`.
import os, sys
sys.path.insert(0, os.path.expanduser("~/path/to/gramps"))

from gramps.gen.const import GRAMPS_LOCALE
from gramps.gen.utils.grampslocale import GrampsLocale
from gramps.gen.db.utils import open_database

# Pin the locale without touching system locale config.
glocale = GrampsLocale(
    localedir=os.path.expanduser("~/path/to/gramps/po"),
    languages=["fi"],         # the language under test
)

db = open_database("example.gramps")
# … exercise the buggy code path …
```

`GrampsLocale(localedir, languages)` is the key escape hatch — it bypasses both `LANGUAGE` env-var setup and `locale-gen`-style OS config, neither of which is needed for an in-process test. The pattern came out of triaging [Mantis 14100](https://gramps-project.org/bugs/view.php?id=14100) (Finnish month-inflection crash).

For DB-traversal code, the canonical fixture is `example.gramps` shipped with Gramps source. Real-data tests against `example.gramps` catch bugs mocked DBs miss — see [05-data-access → Testing data access](05-data-access.md#testing-data-access).

The same pattern, formalised as a `unittest.TestCase`, becomes a regression test. See [07-testing](07-testing.md).

## In-app diagnostics: `PrerequisitesCheckerGramplet`

When a user reports an addon misbehaving, the first triage step is *"what's the running environment?"* The PrerequisitesCheckerGramplet (an addon itself) lists every optional dependency Gramps detects and the version it found. Asking a reporter to install it, run it, and paste the output is the fastest baseline.

It also surfaces missing GI bindings, which addons typically declare via `requires_gi` — a `requires_gi=[("GExiv2", "0.10")]` that fails silently is almost always something the PrerequisitesCheckerGramplet output would have surfaced.

[Mantis 13966](https://gramps-project.org/bugs/view.php?id=13966) (active_page None on tree close) was a teardown-order bug *in* this gramplet; the fix lives in addons-source PR 913.

## Platform notes

**Linux** — the standard environment. `gramps --debug=…` works as documented; logging surfaces in the terminal that launched Gramps, plus the in-app log window.

**Windows** — debug flags work the same way, but the launcher is typically a `.bat` or `.exe` shortcut rather than a terminal command. Launch from MSYS2 UCRT64 (`/ucrt64/bin/gramps`) to get a terminal attached for stderr. Some bugs reproduce only on Windows; when reporting one, include the Gramps version, the MSYS2 UCRT64 toolchain version, and the exact reproduction steps in the Mantis ticket so a Windows-equipped maintainer can confirm.

**macOS** — there is **no Gramps debug mode equivalent on Mac**, and contributors typically can't install addon dependencies into the Gramps Python (Gary Griffin, 2026-05-16). This shapes two testing-side decisions: tests must run cleanly without `requires_mod` deps installed (see [07-testing](07-testing.md)), and a Mac repro that needs GUI inspection usually requires triaging via screenshots the reporter pastes into the Mantis ticket.

## Heavier tools

When the lighter approaches aren't enough.

### `pdb` (Python debugger)

Drop a breakpoint at the line of interest:

```python
breakpoint()           # Python 3.7+; same as `import pdb; pdb.set_trace()`
```

Launch Gramps from a terminal; when execution reaches the breakpoint, Gramps freezes and you get an interactive `(Pdb)` prompt. Commands: `n` (next line), `s` (step into), `c` (continue), `l` (list source), `p expr` (print). Full reference: [Python pdb docs](https://docs.python.org/3/library/pdb.html).

### `python -m trace`

For "where on earth does the crash come from?":

```bash
python3 -m trace -t /path/to/Gramps.py >/tmp/trace.out
```

Produces every executed line of Python in the file. Huge, but `grep` of the last hundred lines often pins the crash site.

### `gdb` (C debugger)

For segfaults coming from C libraries (GTK, GObject Introspection):

```bash
gdb python3
(gdb) run /path/to/Gramps.py
# … reproduce the crash …
(gdb) bt              # Python+C backtrace; the C frames pin the C-side cause
```

To trap GTK warnings as hard errors:

```bash
G_DEBUG=fatal-warnings gdb python3
```

Then `r /path/to/Gramps.py`; any GTK warning aborts with a backtrace showing the originating call.

Addons rarely need `gdb` — segfaults that bubble up from C are usually GI binding issues (wrong typelib version, missing `gir1.2-*` package). When you do hit one, the C backtrace plus the user's `PrerequisitesCheckerGramplet` output typically point at the missing package.

### Profiling

`gramps.gen.utils.debug.profile` is a convenience wrapper around `cProfile`. Replace the call you want to profile:

```python
from gramps.gen.utils.debug import profile

def cb_save(self, *obj):
    profile(self.save, *obj)
```

On the next save, a profile report goes to stdout: per-function call counts and cumulative time. Useful when a gramplet's `main()` is unexpectedly slow.

## See also

- [04-fundamentals → Logging](04-fundamentals.md#logging) — the conventions for setting up the logger in the first place.
- [07-testing](07-testing.md) — formalising a repro script into a regression test.
- [09-troubleshoot](09-troubleshoot.md) — symptom-first guide to the failure modes these tools surface.
- [16-guidelines](16-guidelines.md) — the rules around logging and diagnostics (logger over `print`, etc.).
- [Debugging Gramps](https://gramps-project.org/wiki/index.php/Debugging_Gramps) — the standalone wiki page; primary scraped source.
- [Logging system](https://gramps-project.org/wiki/index.php/Logging_system) — the deeper reference for Gramps' logging configuration.
