# Fundamentals

[← Previous](03-addon-kinds.md) · [Index](01-overview.md) · [Next →](05-data-access.md)

<!--
  Cross-cutting concerns every addon author hits regardless of kind.
  Ordered by the sequence an author actually meets them, not
  alphabetically. Authoritative cross-references inside the manual:
    - per-kind specifics  -> 03-addon-kinds
    - DB API surface      -> 05-data-access
    - testing             -> 07-testing
    - failure modes       -> 09-troubleshoot
-->

## Overview

The cross-cutting concerns every addon author hits regardless of which kind they're building. If something in a kind-specific page assumes a piece of background, it's described here.

![Fig. 1 — Plugin discovery and load sequence. Gramps scans the plugin directory at startup, executes each `register()` call into a metadata-only catalog, and loads the implementation module lazily when the user first invokes the addon.](_media/plugin-discovery.svg)

Note that the catalog → invoke arrow is dashed: addon implementation modules are *not* loaded at startup. The `.gpr.py` is what runs during discovery; the `fname` module only loads on first use. This is why a registration-time error blocks the whole addon from appearing, but a runtime error in the implementation only surfaces when the user triggers it.

## The `.gpr.py` registration file

Every addon ships exactly one `.gpr.py` per folder, executed at startup by Gramps' plugin scanner. Its single job is to call `register(...)` one or more times, declaring the addon's *metadata* — what kind it is, what version of Gramps it targets, which implementation module to load on demand.

The general shape:

```python
register(
    GRAMPLET,                          # kind (see 03-addon-kinds)
    id="HelloGramplet",                # stable identifier — folder name
    name=_("Hello Gramplet"),          # user-visible label
    description=_("A minimal example"),
    version="1.0.0",                   # addon version, X.Y.Z
    gramps_target_version="6.0",       # which Gramps minor this targets
    status=STABLE,                     # STABLE / BETA / EXPERIMENTAL / UNSTABLE
    fname="hellogramplet.py",          # implementation module
    # kind-specific fields go here
    gramplet="HelloGramplet",
    gramplet_title=_("Hello"),
)
```

### Fields every kind needs

| Field                   | Meaning                                                                          |
|-------------------------|----------------------------------------------------------------------------------|
| `id`                    | Stable plugin key, unique across addons; need **not** match the folder name      |
| `name`                  | User-visible label, translatable                                                 |
| `version`               | Addon version, dotted `X.Y.Z`                                                    |
| `gramps_target_version` | The Gramps minor this targets, e.g. `"6.0"`                                      |
| `status`                | `STABLE`, `BETA`, `EXPERIMENTAL`, or `UNSTABLE`                                  |
| `fname`                 | The implementation module Gramps loads on first use                              |

### Fields most kinds want

- `description` — shown in the Plugin Manager tooltip.
- `authors`, `authors_email` — credit and contact, both lists.
- `maintainers`, `maintainers_email` — only set if different from authors.
- `help_url` — wiki page name; Gramps prepends the base URL and may add a language extension. Don't wrap in `_()` unless you actually want per-language wiki pages.
- `audience` — `EVERYONE` (default), `EXPERT`, or `DEVELOPER`; filters visibility in the Plugin Manager. The constants live at `_pluginreg.py:75-77` — note `EVERYONE`, not `ALL` (an outdated wiki page documents `ALL`; the code has only ever used `EVERYONE`).

### Kind-specific fields

Every kind adds its own. A few examples:

- `GRAMPLET` adds `gramplet` (class or function name), `gramplet_title`, `height`, `expand`, `navtypes`, `force_update`.
- `REPORT` adds `reportclass`, `optionclass`, `category`, `report_modes`, `require_active`.
- `TOOL` adds `toolclass`, `optionclass`, `category`, `tool_modes`.
- `QUICKVIEW` adds `runfunc`, `category`.

[03-addon-kinds](03-addon-kinds.md) lists the kind-specific fields per kind. The authoritative reference is the `expand_*` helpers in [`_pluginreg.py`](https://github.com/gramps-project/gramps/blob/maintenance/gramps60/gramps/gen/plug/_pluginreg.py).

### Multiple registrations per file

A single `.gpr.py` may call `register(...)` more than once — for example a report that also exposes a quick view, or two related gramplets sharing one implementation module. Each call is independent metadata.

## Plugin discovery

Gramps walks the plugin path at startup, executes every `.gpr.py` it finds, and builds an in-memory catalog from each `register()` call. The implementation modules pointed to by `fname` are **not** loaded at this point — they're imported lazily on first invocation. This split matters for diagnostics:

- A `SyntaxError` or import failure in `.gpr.py` makes the addon disappear entirely from menus — the catalog never got an entry for it.
- A failure inside the implementation module surfaces only when the user triggers the addon, with a traceback in the Plugin Manager and the log window.

### The plugin path

Plugin folders are searched under each path Gramps was configured to scan — typically the system-wide plugin dir plus the per-user plugin dir. The per-user dir is the safe one to develop in; system locations generally need elevated permissions and shouldn't be edited directly. The exact paths are platform-specific; [the Addons page](https://gramps-project.org/wiki/index.php/6.0_Addons) lists them.

### Symlinks

Plugin discovery's symlink handling changed between 6.0 and 6.1:

- **Gramps 6.0** — symlinks are **not** followed. An addon symlinked in is invisible. Development loop: copy/`rsync` from working tree on save.
- **Gramps 6.1+** — symlinks **are** followed, with realpath-based dedup so cycles terminate. Symlinking the working tree into the user plugin dir works in place. (Gramps commit [`9443dcbb30`](https://github.com/gramps-project/gramps/commit/9443dcbb30) on `maintenance/gramps61`.) The symlink test is skipped on Windows because the platform's symlink behaviour is inconsistent without elevated privileges; on Windows, a physical copy remains the safe approach even on 6.1+.

Concrete sync recipes live in [01-overview → Where addons live](01-overview.md#where-addons-live).

## Names Gramps injects into `.gpr.py`

The `.gpr.py` runs in a scope where several names are *pre-populated* by the plugin loader. You **must not import** them; Gramps puts them there and an `import` masks them with stale bindings.

| Injected name                                                    | Source                              |
|------------------------------------------------------------------|-------------------------------------|
| `register`                                                       | the loader itself                   |
| `_` (and `ngettext`)                                              | the addon's local translation       |
| Kind constants — `GRAMPLET`, `REPORT`, `TOOL`, …                  | `gramps.gen.plug._pluginreg`        |
| Status constants — `STABLE`, `BETA`, `EXPERIMENTAL`, `UNSTABLE`   | `_pluginreg.py:62-65`               |
| Audience constants — `EVERYONE`, `EXPERT`, `DEVELOPER`            | `_pluginreg.py:75-77`               |
| Report category constants — `CATEGORY_TEXT`, `CATEGORY_DRAW`, …   | `_pluginreg.py:141-149`             |
| Tool category constants — `TOOL_DBPROC`, `TOOL_DBFIX`, …          | `_pluginreg.py:154-159`             |
| Quick View category constants — `CATEGORY_QR_PERSON`, …           | `_pluginreg.py:163-174`             |
| Report mode constants — `REPORT_MODE_GUI`, `REPORT_MODE_BKI`, …   | `_pluginreg.py`                     |

In the implementation module, none of these are injected — the rules are normal Python. Import what you need from `gramps.gen.*` there.

## The provided environment

The injected names are one half of what Gramps hands an addon; the other half is process-global. An addon — whatever its kind — is a **guest in Gramps' process**: before the first plugin loads, Gramps' startup (`gramps/grampsapp.py`, with `gramps/gen/utils/grampslocale.py` and `gramps/gen/plug/_manager.py`) has already configured the state the addon runs inside. Each item below is a real temptation, because setting it up yourself is exactly what makes a module work *standalone* — and each one either collides with, or silently hijacks, the running application. The rule is uniform: **the app provides this state at runtime; the test root provides it under test; addon modules touch none of it.**

| Gramps sets up at startup | The tempting mistake | An addon instead | Documented in |
|---------------------------|----------------------|------------------|---------------|
| **GI version pins** — `gi.require_version("Gtk", "3.0")` / `("Gdk", "3.0")` before any plugin loads | Pinning in the addon module or a test file so bare `unittest` imports work | Never pin; addons-source's repo-root `tests/__init__.py` carries the pins (PR 950) | [07-testing → The GTK-pin contract](07-testing.md#the-gtk-pin-contract) |
| **Locale & translation** — `locale.setlocale(LC_ALL, "")`, gettext domain binding, ICU collators | `gettext.install()` (overwrites the builtin `_` app-wide), `locale.setlocale` for date/number formatting, `locale.strcoll` for sorting | Use the injected `_` in `.gpr.py`; `glocale.get_addon_translator(__file__)` in modules; `glocale.sort_key` for collation | [Translation](#translation) below, [11-internationalization](11-internationalization.md) |
| **Root logger & error reporting** — WARNING-level root logger with stderr/file handlers; in the GUI, `GtkHandler` turns ERROR into the error-report dialog | `logging.basicConfig(...)` or `getLogger().setLevel(...)` in a module or test to "see output" — duplicates handlers and reroutes the error dialog for the whole app | A named module-level logger only: `LOG = logging.getLogger(".MyAddon")` | [Logging](#logging) below, [08-debug → Default log levels](08-debug.md#default-log-levels) |
| **`sys.path`** — the plugin manager adds your addon dir *transiently* at import and pops it after | `sys.path.insert(0, os.path.dirname(__file__))` at module level so sibling/vendored imports resolve standalone — inside Gramps the entry is permanent and global, and a generic `utils.py` shadows every other addon's | Rely on the loader's import semantics; under test, the invocation through the package root provides the path | [09-troubleshoot → Imports and namespace traps](09-troubleshoot.md#imports-and-python-namespace-traps) |
| **The GTK main loop & global GTK state** — one `Gtk.main()` loop, the icon theme, screen-wide CSS, `Gtk.Settings` | `Gtk.main()` / `Gtk.main_quit()` around your own dialog (the standalone-script habit); installing app-wide CSS providers or retheming globally | Use Gramps' dialog and windowing machinery; style your own widgets, never the screen | [16-guidelines → Runtime](16-guidelines.md#runtime) |
| **`sys.excepthook`** — logs unhandled exceptions and, on a `HandleError`, flags the DB for check-and-repair at next start | Installing your own hook for "nicer" error handling — disables crash reporting *and* the DB-repair flag app-wide | Let exceptions propagate; log expected failures through your module logger | [08-debug](08-debug.md) |
| **Environment & user paths** — `GRAMPS_RESOURCES`, `PANGOCAIRO_BACKEND` (Windows), the user config/plugin directories | `os.environ[...] = ...` in module or test-module code; computing Gramps paths from `__file__` | Paths come from `gramps.gen.const`; environment setup belongs to the harness (test root, CI) | [07-testing → Running tests locally](07-testing.md#running-tests-locally) |

The test-side mirror of this table — the repository-root `tests/__init__.py` reproducing the slice of this environment modules under test need, with test runs going through the repo root so it loads — is the contract in [07-testing → The GTK-pin contract](07-testing.md#the-gtk-pin-contract).

## Translation

Every user-visible string in the `.gpr.py` and in the implementation goes through `_()`. The function is set up differently in the two files because the `.gpr.py` runs in the injected-name scope.

**In `.gpr.py`**: just use `_()`. The loader has already wired it.

```python
register(
    GRAMPLET,
    id="HelloGramplet",
    name=_("Hello"),
    description=_("A minimal example"),
    ...
)
```

**In the implementation module**: opt into the addon's own translation catalog at the top of the file, then use `_()` normally.

```python
from gramps.gen.const import GRAMPS_LOCALE as glocale

_ = glocale.get_addon_translator(__file__).gettext
```

This binds `_` to translations stored in the addon's own `po/` folder rather than Gramps' core catalog. Without this line, `_()` falls back to the core catalog and your addon-specific strings stay in English regardless of UI language.

### Plurals

Use `ngettext(singular, plural, n)` whenever a number is being formatted into a string. Languages with non-trivial plural rules (Russian, Polish, …) need both forms to render correctly.

```python
msg = ngettext("{n} match", "{n} matches", n).format(n=n)
```

### Disambiguating contexts

When the same English word translates differently in different contexts, add a context hint. Gramps' `_()` accepts `_(msg, context)`; the older `pgettext(context, msg)` form also works but the comma form is preferred because the source remains readable as plain English.

```python
_("Source", "citation")   # vs. _("Source", "person attribute")
```

## Logging

Use a module-level logger; never use `print()` for diagnostics.

```python
import logging

LOG = logging.getLogger(".".join(__name__.split(".")[-2:]))
# or simply:
LOG = logging.getLogger(__name__)

LOG.debug("Reached the interesting branch with n=%d", n)
LOG.warning("Skipping malformed event %s", event.gramps_id)
```

Log output flows into:

- **The Gramps log window** (Help → Log) — visible to the user.
- **stderr** when Gramps is launched with `--debug` or with `GRAMPS_DEBUG=1` set.

See [08-debug](08-debug.md) for how to enable debug levels per logger.

## Lifecycle hooks

Every kind has its own entry points; the shape varies, but the pattern is consistent: a small number of named methods that Gramps calls at specific moments, and you override the ones you need.

### Gramplets

Subclass `gramps.gen.plug.Gramplet`. The hooks Gramps calls:

| Method               | When                                                                              |
|----------------------|-----------------------------------------------------------------------------------|
| `init(self)`         | Once, on first show. Build the UI here. Don't read the DB yet — it may not be open.  |
| `db_changed(self)`   | When the active database changes. Reconnect any signals you wired on the old DB.      |
| `active_changed(self, handle)` | When the active person / family / etc. changes. Default is to call `update()`. |
| `main(self)`         | The work itself. May be a generator — `yield True` to keep going, `yield False` to stop.  |
| `update(self)`       | Don't override. Calls `main()` for you; you call `update()` to schedule a redraw.     |
| `on_load(self)` / `on_save(self)` | When the gramplet's persistent data is loaded / saved.                  |

Inside the class, `self.dbstate.db` is your live database, `self.uistate` is the GUI state. See [05-data-access](05-data-access.md) for what you can do with `self.dbstate.db`.

### Reports

Subclass `gramps.gen.plug.report.Report`. The constructor receives `(database, options_class, user)`. Override `write_report()` — that's the single hook Gramps calls. Everything else is plumbing you initialise in `__init__`.

### Tools

Subclass from `gramps.gui.plug.tool`. The constructor receives `(dbstate, user, options_class, name, callback=None)` and does the work inline (there's no separate `run()` for non-CLI tools). For CLI mode, `tool_modes=[TOOL_MODE_CLI]` triggers a different entry path.

### Quick Views

Plain function: `run(database, document, person_or_family_or_…)`. No class to subclass. Point `runfunc` at it in the registration.

### Importers / Exporters

Plain function pointed to by `fname` + the kind's entry-point field. Signature varies by kind and minor; reading a live importer/exporter is the most reliable way to lock down the exact shape on your target branch.

## Signals: addons reacting to changes

Gramps' database and UI emit *signals* when state changes. Addons that need to stay in sync — gramplets that refresh on data changes, views that follow the selection — `connect()` to those signals.

### The minimal pattern

```python
key = self.dbstate.db.connect("person-update", self.cb_person_changed)
# … later, in teardown …
self.dbstate.db.disconnect(key)
```

`connect()` returns an opaque key; pass it to `disconnect()` when the addon shuts down or the database changes. Forgetting to disconnect leaves stale callbacks pointing into freed objects and crashes Gramps sooner or later.

### The signals that matter most

| Source                 | Signal                                           | When                                                               |
|------------------------|--------------------------------------------------|--------------------------------------------------------------------|
| `dbstate.db`           | `person-add`, `family-add`, `event-add`, …       | One object added. Arg: list of handles.                            |
| `dbstate.db`           | `person-update`, `family-update`, …              | One object updated. Arg: list of handles.                          |
| `dbstate.db`           | `person-delete`, `family-delete`, …              | One object deleted. Arg: list of handles.                          |
| `dbstate.db`           | `person-rebuild`, `family-rebuild`, …            | Mass change (import, db repair). No args.                          |
| `dbstate.db`           | `home-person-changed`                            | Home person changed. No args.                                      |
| `dbstate`              | `database-changed`                               | Active database swapped. Arg: the new db.                          |
| `dbstate`              | `no-database`                                    | No db is open.                                                     |
| `uistate`              | `nameformat-changed`, `filter-name-changed`, …   | Various UI preferences.                                            |
| view's history         | `active-changed`                                 | Selected object changed. Arg: the new handle.                      |

Pattern: `person-update` / `family-update` / etc. fire one *after* a transaction commits, with a *list* of affected handles. They never fire mid-transaction, so callbacks can safely re-read the DB.

### Subscribing to "anything changed"

A common gramplet pattern is "redraw on any structural change to the tree", typically done by wiring `db_changed`:

```python
def db_changed(self):
    self.dbstate.db.connect("person-add",    self.update)
    self.dbstate.db.connect("person-delete", self.update)
    self.dbstate.db.connect("person-update", self.update)
    self.dbstate.db.connect("family-add",    self.update)
    self.dbstate.db.connect("family-delete", self.update)
    self.dbstate.db.connect("family-update", self.update)
```

For complex subscriptions across many object types, the `CallbackManager` in `gramps.gen.utils.callman` is a higher-level filter that lets you register dictionaries of `{signal: handler}` and tracks keys for `disconnect_all()` on teardown. See [Signals and callbacks](https://gramps-project.org/wiki/index.php/Signals_and_Callbacks) for the full inventory.

### Signal ordering

Signals are deferred until a transaction commits and are emitted in a specific order: deletes first, then adds, then updates; within each phase, by object type in the order persons → families → sources → events → media → places → repositories → notes → tags → citations. This deterministic order matters when a single transaction touches related objects (a family merge deletes one family and updates another plus its members); a handler that re-reads the DB on `person-delete` will see a consistent state.

## Reading and writing the database

The DB API is covered in depth in [05-data-access](05-data-access.md). The rule worth stating here, where every addon meets it:

- **Reading** is unrestricted. Any addon may read freely from `self.dbstate.db`.
- **Writing** goes through a transaction. Always:

  ```python
  with DbTxn(_("Description for Undo history"), db) as trans:
      person = db.get_person_from_handle(handle)
      person.set_privacy(True)
      db.commit_person(person, trans)
  ```

The transaction message is user-visible in the Undo history; translate it.

## Declaring dependencies

Addons may need Python packages or system tools that aren't part of Gramps' core dependencies. Declare these in the registration so the plugin manager can surface a clear "missing X" message instead of a generic import failure.

### `requires_mod` — Python modules

```python
requires_mod = ["PIL", "lxml"]
```

Uses the **importable** module name (what you `import`), **not** the PyPI distribution name. PIL not Pillow, lxml fine either way (matches), yaml not PyYAML. Verify before you push:

```python
from importlib.util import find_spec
assert find_spec("PIL") is not None
```

A mismatch shows up the first time the addon's tests run against a clean install — the import fails. Always verify the name with `find_spec` before publishing.

### `requires_gi` — GObject Introspection bindings

```python
requires_gi = [("GExiv2", "0.10")]
```

A list of `(namespace, version)` tuples. The user has to install these through their OS package manager; Gramps cannot install GI bindings. The version pin must match what your code actually imports — and on gramps61 the version handling for GExiv2 was rewritten (addons-source PR 829), so a `requires_gi` pinned for one branch isn't guaranteed correct on the other. Verify against the target branch's related code before assuming a cherry-pick is correct.

### `requires_exe` — Executables on PATH

```python
requires_exe = ["graphviz", "dot"]
```

External binaries the user must have installed. Gramps checks PATH for them and surfaces a missing-dependency message.

### `depends_on` — Other addons

```python
depends_on = ["libwebconnect"]
```

Other addons that must load first. The plugin manager resolves these automatically when the user installs your addon. Circular dependencies break the load and disable the addon — the loader chooses safety over guessing.

## Configuration and persistent settings

For settings that should survive between sessions, Gramps' configuration manager handles the file I/O and migration; you only declare the keys.

```python
from gramps.gen.config import config as configman

config = configman.register_manager("my_addon")
config.register("section.key1", default_value)
config.register("section.key2", another_default)
config.load()       # read existing settings file, if any
config.save()       # write defaults out if the file didn't exist
```

`config.get("section.key1")` and `config.set("section.key1", value)` read and write at runtime. Gramplets persist via the lifecycle hook:

```python
def on_save(self):
    config.save()
```

The settings file lives in the addon's plugin folder by default. For a system-wide config (rare):

```python
config = configman.register_manager("my_addon", use_config_path=True)
```

Other code — another addon, a repro script — can read an addon's settings without re-registering the keys, via `get_manager`:

```python
from gramps.gen.config import config as configman

config = configman.get_manager("my_addon")
value = config.get("section.key1")
```

## See also

- [01-overview → Your first addon](01-overview.md#your-first-addon-a-minimal-gramplet) — the first end-to-end Gramplet putting these concepts together.
- [03-addon-kinds](03-addon-kinds.md) — what each kind adds to the registration shape described here.
- [05-data-access](05-data-access.md) — the DB API surface.
- [06-api-reference](06-api-reference.md) — the curated `gramps.gen.*` surface that addons may import.
- [09-troubleshoot](09-troubleshoot.md) — what failure modes look like when one of these conventions is off.
- [Signals and Callbacks](https://gramps-project.org/wiki/index.php/Signals_and_Callbacks) — the standalone wiki page covering signals and the `CallbackManager` in more depth.
