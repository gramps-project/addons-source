#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2017       Paul Culley <paulr2787_at_gmail.com>
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
""" Help/Plugin Manager
This module implements the enhanced Plugin manager load patches.
"""
import sys
import os


def load_on_reg(dbstate, uistate, plugin):
    """
    Runs when plugin is registered.
    """
    if uistate:
        # It is necessary to avoid load GUI elements when run under CLI mode.
        # So we just don't load it at all.
        sys.path.append(os.path.abspath(os.path.dirname(__file__)))
        from PluginManager import available_updates, PluginStatus
        # Monkey patch my version of available_updates into the system
        import gramps.gen.plug.utils
        gramps.gen.plug.utils.__dict__['available_updates'] = available_updates
        import gramps.gui.configure
        gramps.gui.configure.__dict__['available_updates'] = available_updates
        import gramps.gui.utils
        gramps.gui.utils.__dict__['available_updates'] = available_updates
        import gramps.gui.viewmanager
        gramps.gui.viewmanager.__dict__[
            'PluginWindows'].PluginStatus = PluginStatus
