# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026       David Straub
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

"""Test package for the Gramps Web Sync addon.

Importing this package pins GTK to 3.0, adds :data:`ADDON_DIR` and
:data:`ADDONS_ROOT` to ``sys.path`` and sets ``GRAMPS_RESOURCES`` if unset, so
test modules can import ``gramps`` and the addon's flat modules directly.
"""

from __future__ import annotations

import os
import sys

import gi

# Must precede any gramps import, or PyGObject may load GTK 4 and the
# gramps.gui chain dies on the GTK 3-only Gtk.IconSize.MENU.
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

#: The ``GrampsWebSync`` addon directory, i.e. the parent of this package.
ADDON_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

#: The ``addons-source`` checkout root.
ADDONS_ROOT: str = os.path.dirname(ADDON_DIR)
if ADDONS_ROOT not in sys.path:
    sys.path.insert(0, ADDONS_ROOT)

if "GRAMPS_RESOURCES" not in os.environ:
    import gramps

    os.environ["GRAMPS_RESOURCES"] = os.path.dirname(os.path.dirname(gramps.__file__))
