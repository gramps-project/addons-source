# CLAUDE.md — Gramps Addons Source

## Project Overview

This is the **gramps-project/addons-source** repository — third-party addons
for [Gramps](https://gramps-project.org/), a GTK+/GNOME based genealogy
program. The current branch (`maintenance/gramps60`) targets **Gramps 6.0**.

There are ~149 addons, each in its own top-level directory. Addon types
include: Importer, Exporter, Gramplet, View, Report, Tool, QuickReport,
Rule, MapService, Database backend, and more.

## Repository Layout

```
AddonName/
├── *.gpr.py          # Gramps plugin registration (declares type, version, etc.)
├── *.py              # Addon source code
├── *.glade           # Optional GTK UI definitions
├── po/               # Translation files (.pot, *-local.po)
├── locale/           # Compiled translations (.mo)
├── tests/            # Tests (if present)
└── README.md         # Optional addon documentation
make.py               # Build tool (init, build, compile, listing, clean)
setup.py              # Legacy setup script
CONTRIBUTING.md       # Comprehensive addon development guide
.travis.yml           # STALE — do not use (targets Gramps 5.1 / Python 3.3)
```

## Build System

The build tool is `make.py`. Common commands:

```bash
# Build a single addon tarball
python3 make.py gramps60 build AddonName

# Build all addons
python3 make.py gramps60 build all

# Compile translations
python3 make.py gramps60 compile AddonName

# Generate listing
python3 make.py gramps60 listing all

# Build only changed addons + listings + cleanup
python3 make.py gramps60 as-needed

# Clean
python3 make.py gramps60 clean
```

The `GRAMPSPATH` environment variable should point to a Gramps source checkout
if not at the default `../../..` relative path.

## Code Style (from Gramps AGENTS.md)

Addons should follow the main Gramps coding conventions where practical:

### Formatting
- **Black** for Python formatting
- **4-space indentation**, never tabs
- PEP 8 compliant (Black takes precedence in conflicts)

### Type Hints
- Use Python 3.10+ syntax: `X | None` not `Optional[X]`
- Use `list[X]`, `dict[K, V]`, `tuple[X, ...]` not `typing` equivalents

### Docstrings
- Sphinx format for all functions and methods

### Imports
Organize into three groups separated by blank lines:
```python
# ------------------------
# Python modules
# ------------------------
import os
import logging

# ------------------------
# Gramps modules
# ------------------------
from gramps.gen.db.base import DbReadBase

# ------------------------
# Gramps specific
# ------------------------
from .mymodule import MyClass
```

### Logging
- Use `LOG = logging.getLogger(__name__)` — no `print()` for diagnostics

### Internationalization
- Wrap user-visible strings with `_()` for translation
- Use `ngettext(singular, plural, n)` for plural forms

### File Headers
Every new `.py` file must include the GPL-2.0-or-later license header:
```python
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) <YEAR>  <Author Name>
#
# This program is free software; you can redistribute it and/or modify
# ...
```

### Callbacks
Prefix callback function names with `cb_`.

### Class Headers
```python
#------------------------------------------------------------
#
# MyClass
#
#------------------------------------------------------------
class MyClass:
    ...
```

## Addon Structure Requirements

Every addon directory **must** contain:
- `*.gpr.py` — Gramps plugin registration file
- `po/template.pot` — translation template with all translatable strings

CI enforces this. To generate `template.pot` for an addon:
```bash
python3 make.py gramps60 init AddonName
```

## Plugin Registration

Each addon has a `*.gpr.py` file that calls `register()` with:
- Plugin type (IMPORT, EXPORT, GRAMPLET, VIEW, REPORT, TOOL, etc.)
- `gramps_target_version="6.0"` for this branch
- `version`, `status` (STABLE/UNSTABLE), `fname`, `authors`, etc.

See [CONTRIBUTING.md](CONTRIBUTING.md) for full registration API.

## Testing

### Current State
Only ~5 addons have per-addon tests. The repo-wide integration test suite
(`tests/`) validates all addons through the Gramps plugin system. Expanding
per-addon test coverage is an active goal.

### Test Infrastructure

The repo has a shared test harness at `tests/conftest.py` that provides
pytest fixtures for Gramps-backed testing:

| Fixture | Scope | Description |
|---------|-------|-------------|
| `gramps_user` | session | Headless `gramps.cli.user.User(auto_accept=True, quiet=True)` |
| `gramps_plugin_manager` | session | `BasePluginManager` with built-in + all addon plugins registered |
| `gramps_plugin_registry` | session | `PluginRegister` for querying registered plugin data |
| `gramps_db` | function | Fresh in-memory SQLite Gramps database (created/torn down per test) |
| `gramps_db_session` | session | Shared in-memory database for expensive setup-once tests |

### Conventions
- Test files in a `tests/` subdirectory within each addon
- **Unit tests**: `test_*.py` (exclude `test_integration`) — fast, no external
  data or services required
- **Integration tests**: `test_integration*.py` — use real Gramps DB, plugin
  system, and sample data; run separately in CI after unit tests pass
- Run individual addon tests:
  ```bash
  python3 -m pytest AddonName/tests/ -v
  ```
- Run repo-wide integration tests:
  ```bash
  python3 -m pytest tests/ -v
  ```

### Unit Tests
- Test pure logic, parsing, data transformations
- Mock Gramps DB when needed (`unittest.mock`)
- Should run fast with no external dependencies beyond pip packages

### Integration Tests (Gramps-backed)
Integration tests use Gramps as the runtime infrastructure. Two levels:

**Repo-wide** (`tests/test_plugin_registration.py`):
- Verifies every addon registers through the Gramps plugin system
- Attempts to load every addon module (reports missing deps as warnings)
- Checks plugin metadata (target version = 6.0, valid id/name/version)
- Smoke-tests import/export plugins have callable entry functions

**Per-addon** (`AddonName/tests/test_integration*.py`):
- Use real Gramps database via `gramps_db` fixture or `make_database("sqlite")`
- Include sample data files (e.g., `.sqz`, `.ged`) in `tests/`
- Skip gracefully when fixtures are missing:
  ```python
  @unittest.skipUnless(os.path.exists(DATA_PATH), f'Test data not found: {DATA_PATH}')
  class TestFullPipeline(unittest.TestCase):
      ...
  ```
- For large test fixtures, use Git LFS or an environment variable

### Writing a New Integration Test

Example for an importer addon:
```python
def test_import_runs(gramps_db, gramps_user):
    """Import sample data and verify record counts."""
    from MyImporter.myimporter import importData
    importData(gramps_db, "MyImporter/tests/sample.ged", gramps_user)
    assert gramps_db.get_number_of_people() > 0

def test_plugin_loads(gramps_plugin_registry):
    """Verify the plugin is registered with correct metadata."""
    pdata = gramps_plugin_registry.get_plugin("im_myformat")
    assert pdata is not None
    assert pdata.gramps_target_version.startswith("6.0")
```

### Key Gramps APIs for Testing

```python
from gramps.gen.db.utils import make_database       # Create database
from gramps.cli.user import User                     # Headless user
from gramps.gen.plug import BasePluginManager        # Plugin manager
from gramps.gen.plug._pluginreg import (             # Plugin types
    PluginRegister, IMPORT, EXPORT, REPORT, TOOL, GRAMPLET,
)

# Database operations
db = make_database("sqlite")
db.load("/path/to/db", None)
db.get_number_of_people()
db.get_person_from_handle(handle)

# Plugin operations
pmgr = BasePluginManager.get_instance()
pmgr.reg_plugins(directory, None, None)     # Scan dir for .gpr.py files
mod = pmgr.load_plugin(pdata)               # Load plugin module
preg = PluginRegister.get_instance()
pdata = preg.get_plugin("plugin_id")        # Get plugin by ID
preg.import_plugins()                       # All IMPORT plugins
preg.type_plugins(REPORT)                   # All plugins of a type
```

### GUI vs Headless Test Marker

Tests that require GTK must be marked with `@pytest.mark.gui`:
```python
import pytest

@pytest.mark.gui
def test_dialog_opens(gramps_db):
    """Requires GTK — auto-skipped on headless/Windows."""
    from gi.repository import Gtk
    # ...

def test_data_parsing():
    """Pure logic — runs everywhere."""
    assert parse_date("2024-01-01") is not None
```

The root `conftest.py` auto-skips `@pytest.mark.gui` tests when GTK is not
importable. CI also passes `-m 'not gui'` in headless/Windows jobs.

For test files that import GTK-dependent addon modules at the top level:
```python
pytest.importorskip("gi")  # skips entire module if gi unavailable
```

## CI/CD

### Container Images

CI jobs run inside pre-built Docker images hosted on GitHub Container Registry:

| Image | Contents | Used by |
|-------|----------|---------|
| `ghcr.io/<repo>/gramps-headless:gramps60` | Python 3.12 + Gramps 6.0 + ruff, pytest, dbf, intltool, gettext | lint, compile-check, unit-test-linux, build |
| `ghcr.io/<repo>/gramps-gtk:gramps60` | headless + GTK/GI system packages | integration-test |

Images are rebuilt by `.github/workflows/docker-build.yml` when
`.github/docker/**` files change, or via manual `workflow_dispatch`.

Dockerfiles live in `.github/docker/gramps-headless/` and `.github/docker/gramps-gtk/`.

### CI Pipeline (`.github/workflows/ci.yml`)

```
lint (headless) ────────────┐
addon-structure (bare) ─────┤
compile-check (headless) ───┤── all parallel
build (headless) ───────────┤
unit-test-windows (bare) ───┘
unit-test-linux (headless) ──── integration-test (gtk)
```

Jobs:
- **Lint**: ruff syntax/import checks (`.gpr.py` excluded) + trailing whitespace
- **Addon structure**: verifies every addon has `po/template.pot`
- **Compile check**: `python3 -m py_compile` on every `.py` file
- **Unit tests (Linux)**: per-addon `test_*.py`, `-m 'not gui'`, excludes `test_integration*.py`
- **Unit tests (Windows)**: same tests on `windows-latest` via `pip install gramps` (no GTK)
- **Integration tests** (Gramps GTK, runs after Linux unit tests):
  - `tests/` — repo-wide plugin registration, loading, and smoke tests
  - `*/tests/test_integration*.py` — per-addon integration tests
- **Build**: `make.py gramps60 build all`

### Running CI Locally

```bash
# Build the headless image
docker build -t gramps-headless .github/docker/gramps-headless/

# Run unit tests in the container
docker run --rm -v "$(pwd)":/workspace gramps-headless \
    python3 -m pytest TMGimporter/tests/ -v -m 'not gui'

# Build the GTK image (after headless is built)
docker build -t gramps-gtk \
    --build-arg REGISTRY='' --build-arg REPO='' --build-arg TAG=gramps-headless \
    .github/docker/gramps-gtk/

# Run integration tests
docker run --rm -v "$(pwd)":/workspace gramps-gtk \
    python3 -m pytest tests/ -v
```

## Commit Messages

- First line: short summary, max 70 characters
- Body lines wrapped at 80 characters
- Describe changes from user's perspective
- Reference issues: `Fixes #12345`

## Key References

- [CONTRIBUTING.md](CONTRIBUTING.md) — full addon development guide
- [Gramps AGENTS.md](https://github.com/eduralph/gramps/blob/master/AGENTS.md) — core Gramps coding standards
- [Gramps Wiki — Third-Party Addons](https://gramps-project.org/wiki/index.php/Third-party_Addons)
- [Gramps Plugin Registry API](https://github.com/gramps-project/gramps/blob/master/gramps/gen/plug/_pluginreg.py)
