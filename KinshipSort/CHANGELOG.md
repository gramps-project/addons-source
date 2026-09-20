# Changes

## 0.2.8 — publication preparation

- Add English interface text and a Polish translation catalog.
- Add GPL-2.0-or-later headers, license text and attribution of adapted Gramps
  grouped-view behavior.
- Extract biological graph calculations into a module that can be tested
  without Gramps or GTK, retaining the 0.2.7 calculation algorithm.
- Return empty results when no database is open or the saved Home Person
  handle no longer exists, avoiding a Gramps `HandleError`.
- Document descending sort behavior, the meaning of blank degrees, filtering
  of surname groups and the availability of standard editing actions.
- Correct the Windows installation path for current Gramps 6.0 installations.
- Add calculation regression tests and Gramps integration tests.
- Keep both existing plugin IDs and configuration names; retain experimental
  status while interactive and cross-platform checks remain outstanding.

## 0.2.7

Replace repeated searches from individual ancestors with one shared downward
priority-queue search seeded by all biological ancestors of the Home Person.

## Earlier prototype versions

- 0.2.6: clickable column headers and standard sorting of other columns.
- 0.2.5: require a common biological ancestor; exclude paths through a shared
  child to an unrelated spouse.
- 0.2.4: generation-level tie-breaker in the flat view.
- 0.2.3: fix class-body scope during configuration initialization.
- 0.2.2: configurable kinship column and migration of column settings.
- 0.2.1: grouped-view startup and group sort-key fixes.
