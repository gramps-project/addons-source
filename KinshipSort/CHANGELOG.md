# Changes

## 0.2.8 — publication preparation

- Skip kinship calculations when the column is hidden; calculate fresh values
  when it is shown again. Rank surname groups only when sorting by kinship.

- Add English interface text and a Polish translation catalog.
- Add GPL-2.0-or-later headers, license text and attribution of adapted Gramps
  grouped-view behavior.
- Extract biological graph calculations into a module that can be tested
  without Gramps or GTK.
- Count Birth siblings in a shared family even when one or both parents have
  no person records: degree 2 for siblings, 3 for their children and 4 for
  first cousins. Include further descendants without creating database records.
- Keep each missing parent local to its family and check Birth per parent,
  avoiding false connections through adoption, spouses or sibling chains.
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
