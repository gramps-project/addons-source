import sys
from unittest.mock import MagicMock

# 1. Mock 'gi' (GObject Introspection)
gi_mock = MagicMock()
sys.modules["gi"] = gi_mock
sys.modules["gi.repository"] = gi_mock.repository
sys.modules["gi.repository.Gtk"] = gi_mock.repository.Gtk
sys.modules["gi.repository.GLib"] = gi_mock.repository.GLib


# 2. Mock 'gramps' namespace recursively
def mock_gramps_namespace():
    # Define the deep path we need to support
    modules = [
        "gramps",
        "gramps.gen",
        "gramps.gen.db",
        "gramps.gen.lib",
        "gramps.gen.lib.nameorigintype",
        "gramps.gen.display",
        "gramps.gen.display.name",
        "gramps.gui",
        "gramps.gui.plug",
        "gramps.gui.dialog",
        "gramps.gui.editors",
        "gramps.gen.errors",
        "gramps.gen.const",
    ]

    for mod in modules:
        sys.modules[mod] = MagicMock()


mock_gramps_namespace()
