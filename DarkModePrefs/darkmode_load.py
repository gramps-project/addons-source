#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026       stolpee
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
"""Dark mode addon loader and startup hook."""

from gi.repository import GLib

from gramps.gui.configure import GrampsPreferences

from darkmode import (
    DarkModePrefs,
    apply_darkmode_settings,
    register_config_defaults,
    setup_system_darkmode_listener,
)


def _apply_patch():
    GrampsPreferences.__init__ = DarkModePrefs.__init__
    apply_darkmode_settings()
    return False


def load_on_reg(dbstate, uistate, plugin):
    """
    Runs when plugin is registered.
    """
    if not uistate:
        # Avoid GUI patches in CLI mode.
        return

    register_config_defaults()
    _apply_patch()
    # Re-apply after startup in case another addon monkey-patches
    # GrampsPreferences later during load_on_reg processing.
    GLib.idle_add(_apply_patch)
    GLib.timeout_add(1000, _apply_patch)
    setup_system_darkmode_listener()
