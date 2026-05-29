#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Eduard Ralph
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

"""Test package for the RepositoriesReport addon.

Pins the GTK 3 stack (Gtk + Gdk) before any test module imports a
``gramps`` GUI/plugin module. The addon's import chain pulls
``gramps.gen.plug.docgen``, which loads Gtk; on a host where GTK 4 is the
default GI resolution a bare import would bind the wrong version (or warn
and skip). Pinning here — mirroring ``gramps/gen/constfunc.py`` — applies on
every launch path, including a direct ``python3 -m unittest`` run with no
test runner.
"""

try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
except (ImportError, ValueError):
    # No PyGObject / GTK 3 here; the test modules guard their imports and
    # skip cleanly.
    pass
