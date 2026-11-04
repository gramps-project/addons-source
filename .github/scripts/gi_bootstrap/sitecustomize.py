"""Pin the GObject-introspection versions, like the Gramps GUI launcher.

Put this directory on ``PYTHONPATH`` for a test step and the interpreter imports
this ``sitecustomize`` at startup — before any test (or subprocess it spawns)
imports a ``gramps.gui`` module.

Why: gramps pins its GI versions in the GUI launcher (``gramps/gui/grampsgui.py``
calls ``gi.require_version`` for Pango/PangoCairo/Gtk at import). A test that
imports a ``gramps.gui.*`` module directly never runs that launcher, so Gtk/Pango
get imported with no version pinned first — emitting a ``PyGIWarning`` and, on a
host where GTK 4 is the default, risking the wrong stack. This shim performs the
same bootstrap, so tests run under the supported GTK 3 stack.

Used for the discover-based / subprocess-loading steps (e.g. plugin
registration), where the bootstrap must be inherited via ``PYTHONPATH`` by every
spawned interpreter. The in-process unit/integration runner
(``run_addon_tests.py``) does the same ``require_version`` itself.
"""

try:
    import gi

    for _ns, _ver in (("Pango", "1.0"), ("PangoCairo", "1.0"), ("Gtk", "3.0")):
        try:
            gi.require_version(_ns, _ver)
        except (ValueError, AttributeError):
            pass
except ImportError:
    pass
