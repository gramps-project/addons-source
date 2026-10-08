# FastRelationshipGraph

Fast relationship search for Gramps, as a standalone addon — no SQL, no
changes to Gramps core.

`gramps.gen.relationship.RelationshipCalculator` re-derives an ancestor's
entire closure every time it's reached a second time via a different
branch, which makes relationship lookups exponential under pedigree
collapse. Measured on a real 100,000-person tree: 40% of random
person-pair lookups didn't finish within 20 seconds. The fix for this is
submitted upstream as
[gramps-project/gramps#2526](https://github.com/gramps-project/gramps/pull/2526),
but a core PR can take a long time to land. This addon carries the exact
same fix (a verbatim copy of that PR's method bodies), delivered as a new
class rather than a patch to core, so it's usable immediately and doesn't
depend on that PR merging.

## How it works, and why there's no monkeypatching

`fast_relationship_engine.py` defines `FastRelationshipMixin`, which
overrides only the handful of methods the fix touches
(`__apply_filter`, `get_relationship_distance_new`, and two small
helpers). `fast_calculator_class()` combines this mixin with whichever
locale-specific calculator class `gramps.gen.relationship.
get_relationship_calculator()` would itself have returned, via ordinary
Python multiple inheritance:

```python
type("Fast" + base_class.__name__, (FastRelationshipMixin, base_class), {})
```

No existing class or instance is ever mutated. Every other method —
including all locale-specific wording, across every language Gramps
ships translations for — falls through untouched to the real calculator
class being mixed in.

## The API

`fast_relationship_graph.py` defines `FastRelationshipGraph`, matching
[gramps-sql-extensions](https://github.com/dsblank/gramps-sql-extensions)'
five-function shape, but working entirely through the object API (no SQL,
no dependency on that project):

```python
from fast_relationship_graph import FastRelationshipGraph

graph = FastRelationshipGraph(db)  # db: any DbReadBase

graph.relationship(h1, h2, depth=None)
graph.all_relationships(h1, h2, depth=None)
graph.relationship_path(h1, h2, depth=None)
graph.all_relationship_paths(h1, h2, depth=None, max_paths=None)
graph.relationships_to(h1, handles=None, depth=None, page=0, pagesize=20, bulk_threshold=700)
```

- **`relationship()` / `all_relationships()`** — thin wrappers around
  the now-fast `get_one_relationship()`/`get_all_relationships()`, using
  core's own `collapse_relations()` unchanged. Results match core's
  literal behavior exactly.
- **`relationship_path()` / `all_relationship_paths()`** — core has no
  equivalent (it only ever returns wording, never the chain of people).
  New code: a bounded, visited-once ancestor-map BFS with the same
  ancestor-couple collapse logic gramps-sql-extensions uses, ported here
  rather than imported.
- **`relationships_to()`** — core has no bulk API at all. Two
  strategies chosen by target count: a per-target bounded BFS below
  `bulk_threshold` (default 700), and a one-time full-tree edge index at
  or above it. See the method's own docstring for the measured
  crossover on a 100,000-person tree.

Pass a `PrivateProxyDb`-wrapped `db` for restricted queries — every
lookup goes through `db.get_person_from_handle()`/`get_family_from_handle()`
exactly as core does, so privacy filtering is correct automatically,
with no privacy logic of this addon's own to drift from core's rules.

## Installing

Drop this directory into your Gramps addons path (or install via the
Plugin Manager once packaged). It registers as a `GENERAL` plugin for
discoverability only — `load_on_reg=False`, since nothing here runs
automatically at Gramps startup. Import
`fast_relationship_graph.FastRelationshipGraph` directly wherever you
need it (e.g. from `gramps-web-api`).

## Testing

```bash
export GRAMPS_RESOURCES=/path/to/gramps/build/share
python3 -m unittest FastRelationshipGraph.tests.test_relationship -v
python3 -m unittest FastRelationshipGraph.tests.test_paths -v
python3 -m unittest FastRelationshipGraph.tests.test_relationships_to -v
python3 -m unittest FastRelationshipGraph.tests.test_privacy -v
```

Run from the `addons-source` repo root so the addon's namespace package
resolves. See `addons-source/AGENTS.md` for the repo-wide testing
conventions these follow.
