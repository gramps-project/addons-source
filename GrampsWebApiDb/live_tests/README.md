# Live tests (not part of the normal test suite)

Everything in this directory runs against the real, live demo server
(`https://gramps-connect.duckdns.org/`) over real HTTP, using the real
`GrampsWebApiDb`/`WebApiHandler` code -- no mocked `web_client`, no fake
transport. They exist to verify specific behaviors (and specific bug
reports) against the actual server this addon talks to in production,
which `tests/` (mocked `web_client`, `InlineTaskRunner`, synthetic local
DBs) structurally cannot do.

**Deliberately not named `test_*.py` and not under `tests/`** so
`python3 -m unittest discover` (the addon's normal suite, see the repo's
`CLAUDE.md`) never picks these up. They need network access and real
`editor-1` credentials, they take real wall-clock time (real HTTP round
trips, real background export tasks), and most importantly they write to
the shared "Example" tree other demo visitors see.

## Isolation

Every object these scripts create on the server is tagged
`addon-live-test` (`live_harness.TEST_TAG`). Every test cleans up what it
created in a `finally` block. `python3 sweep.py` finds and deletes
anything still tagged `addon-live-test` regardless of which test left it
behind (a crashed run, a Ctrl-C, ...) -- run it before and after a test
session.

## Running

```bash
export GRAMPS_RESOURCES=/path/to/gramps/build/share
export GDK_BACKEND=-
cd GrampsWebApiDb/live_tests
python3 sweep.py                        # clean slate
python3 test_live_birth_death_index_bootstrap.py
python3 sweep.py                        # clean up after
```

Each script is a standalone `unittest`-based module runnable directly
(`python3 test_live_....py`), not via discovery, so a stray
`test_*.py`-shaped file never gets swept into a `python3 -m unittest
discover` run by mistake even if this directory is later renamed.
