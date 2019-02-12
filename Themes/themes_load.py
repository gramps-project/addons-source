#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2019       Paul Culley <paulr2787_at_gmail.com>
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
""" Themes
This module implements the Preferences Colors/Themes load patches.
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
        # Monkey patch my version of Prefs into the system
        from gi.repository.Gtk import Settings
        from gramps.gui.configure import GrampsPreferences
        from gramps.gen.config import config
        sys.path.append(os.path.abspath(os.path.dirname(__file__)))
        from themes import MyPrefs
        GrampsPreferences.__init__ = MyPrefs.__init__
        gtksettings = Settings.get_default()
        # save default (original) settings for later, if not already done
        if not hasattr(GrampsPreferences, 'def_dark'):
            GrampsPreferences.def_dark = gtksettings.get_property(
                'gtk-application-prefer-dark-theme')
            GrampsPreferences.def_theme = gtksettings.get_property(
                'gtk_theme_name')
            GrampsPreferences.def_font = gtksettings.get_property(
                'gtk-font-name')
        # establish config Settings and load current prefs if available
        config.register('preferences.theme-dark-variant', '')
        value = config.get('preferences.theme-dark-variant')
        if value:
            gtksettings.set_property('gtk-application-prefer-dark-theme',
                                     value == 'True')
        config.register('preferences.theme', '')
        value = config.get('preferences.theme')
        if value:
            gtksettings.set_property('gtk_theme_name', value)
        config.register('preferences.font', '')
        value = config.get('preferences.font')
        if value:
            gtksettings.set_property('gtk-font-name', value)
