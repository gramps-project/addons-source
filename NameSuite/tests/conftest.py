#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Dmitry Bryndin
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

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
