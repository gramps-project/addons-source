# Validation

Run from the `addons-source` root in a POSIX shell (MSYS2 on Windows).
The calculation suite needs only Python's standard library:

```sh
python3 -m unittest KinshipSort.tests.test_kinship_calculation -v
```

It includes explicit family scenarios and 1,050 comparisons against a slower,
independent common-ancestor reference, including malformed cyclic data.

The integration suite needs Gramps 6.0, its SQLite backend and GTK 3.
Use an isolated `GRAMPSHOME`; importing the repo-root `tests` package applies
the repository's central GTK/GDK pins before loading GUI model modules:

```sh
python3 -m unittest tests.__init__ KinshipSort.tests.test_gramps_integration -v
```

All database fixtures are synthetic and temporary. Missing Gramps/PyGObject
produces a skip, not a successful integration check. The registration check
runs without generated files. The Polish translation check skips unless the
catalog has been compiled to `locale/pl/LC_MESSAGES/addon.mo`.

These tests exercise real Gramps models, without opening application windows.
They also compare degree and generation values with Gramps'
`RelationshipCalculator` on a fixture with recorded common ancestors,
including a related spouse, multiple parent families and non-birth exclusions.
Regression fixtures also cover siblings without parent records, their
descendants and cousins, each missing-parent slot, later parent entry,
unchanged genealogical records and separation of unrelated families.
The `test_gramps_integration.py` name intentionally uses the all-platform
`test_` prefix: it can run wherever Gramps 6.0/GTK 3 are available.

## Interactive checks before marking stable

These are not covered by the headless model tests:

- Start Gramps without an open tree, then open and close a synthetic tree in
  both addon views; check that no error dialog appears.
- Change the Home Person while each view is active, and while another view is
  active. Confirm that switching back recalculates degrees.
- Edit a birth/adoption relation and delete a family. Check immediate refresh,
  then Undo and Redo, without reopening the view.
- Move, resize and hide the kinship column. Restart Gramps and check that
  settings are retained. Check migration from version 0.2.7 settings.
- Click every visible heading in both directions. Confirm name sorting,
  generation ties, blank degrees and surname groups match the README.
- Use the sidebar filter and text search. Confirm results and document any
  confusing effect of hidden people on surname-group ranking.
- Add a person from a selected surname group; check the inherited surname.
- Check English and Polish interfaces, including popup labels.
- Try a large synthetic tree and repeated edits; measure full rebuild time
  and responsiveness, separately from graph-only timings.
- Repeat smoke checks on Linux and macOS before claiming those platforms
  have been tested.

No real family tree or identifying user data is needed for these checks.
