"""Pin the GTK / GDK introspection versions for the repo-root test suite.

``python3 -m unittest discover -s tests`` imports this package before any test
module under ``tests/``, so requiring the versions here pins the whole suite to
the GTK 3 / GDK 3 stack a real Gramps GUI session uses. A test that imports a
``gramps.gui.*`` module directly never runs the launcher's own
``require_version``; without this the GI stack can resolve to GTK 4 on a host
where that is the default — emitting ``PyGIWarning`` and risking the wrong stack.

This module also runs before Gramps is imported, so it is where we silence
log/warning spam that is expected when testing *uncompiled, source-tree* addons
(no ``locale/*.mo``) and would otherwise bury the test results.
"""

import logging
import warnings

try:
    import gi

    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
except Exception:
    # No PyGObject, or the 3.0 typelibs are unavailable — leave the environment
    # untouched; this only fixes the version when it can.
    pass

# Gramps warns once per addon that lacks a compiled locale dir (source-tree
# addons ship ``po/*.po`` only), plus a startup warning about the main locale
# dir — expected here, not a failure. Raising the logger to ERROR is robust:
# logging levels are not reset by the test runners, so this holds on every
# entrypoint.
logging.getLogger(".gramps.gen.utils.grampslocale").setLevel(logging.ERROR)
# PyGObject deprecation shout from gramps.gui.glade on import — not our concern.
# NOTE: this warning *filter* is honoured by ``make.py test`` (TextTestRunner),
# but a bare ``python -m unittest`` resets warning filters mid-run and may still
# print it once. The documented entrypoint (make.py) stays clean; suppressing it
# everywhere would mean importing gramps.gui.glade eagerly here (pulls in Gtk on
# every run), which isn't worth it for one cosmetic line.
warnings.filterwarnings("ignore", message=r".*shouldn't use __slots__.*")
