"""Pin the GTK / GDK introspection versions for the repo-root test suite.

``python3 -m unittest discover -s tests`` imports this package before any test
module under ``tests/``, so requiring the versions here pins the whole suite to
the GTK 3 / GDK 3 stack a real Gramps GUI session uses. A test that imports a
``gramps.gui.*`` module directly never runs the launcher's own
``require_version``; without this the GI stack can resolve to GTK 4 on a host
where that is the default — emitting ``PyGIWarning`` and risking the wrong stack.
"""

try:
    import gi

    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
except Exception:
    # No PyGObject, or the 3.0 typelibs are unavailable — leave the environment
    # untouched; this only fixes the version when it can.
    pass
