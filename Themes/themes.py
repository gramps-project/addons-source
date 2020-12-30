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
This module implements the Preferences Themes load patches.
"""
import os
import subprocess
import types
import glob
from gi.repository import Gtk, Gio, GLib, Pango
from gi.repository.Gdk import Screen
from gi.repository.GObject import BindingFlags
#-------------------------------------------------------------------------
#
# gramps modules
#
#-------------------------------------------------------------------------
from gramps.gen.config import config
from gramps.gui.configure import (GrampsPreferences, ConfigureDialog,
                                  WIKI_HELP_PAGE, WIKI_HELP_SEC)
from gramps.gui.display import display_help
from gramps.gen.utils.alive import update_constants
from gramps.gen.constfunc import win
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext


#-------------------------------------------------------------------------
#
# GrampsPreferences
#
#-------------------------------------------------------------------------
class MyPrefs(GrampsPreferences):
    ''' Adds a new line of controls to the 'Colors' preferences panel.
    Theme, dark-theme and Font choices are added. '''

    def __init__(self, uistate, dbstate):
        ''' this replaces the GrampsPreferences __init__
        It includes the patching fixes and calls my version of the Theme panel
        '''
        # Patching in the methods
        self.add_themes_panel = types.MethodType(
            MyPrefs.add_themes_panel, self)
        self.gtk_css = types.MethodType(
            MyPrefs.gtk_css, self)
        self.theme_changed = types.MethodType(
            MyPrefs.theme_changed, self)
        self.dark_variant_changed = types.MethodType(
            MyPrefs.dark_variant_changed, self)
        self.t_text_changed = types.MethodType(
            MyPrefs.t_text_changed, self)
        self.font_changed = types.MethodType(
            MyPrefs.font_changed, self)
        self.font_filter = types.MethodType(
            MyPrefs.font_filter, self)
        self.default_clicked = types.MethodType(
            MyPrefs.default_clicked, self)
        self.scroll_changed = types.MethodType(
            MyPrefs.scroll_changed, self)
        # Copy of original __init__
        if hasattr(self, 'add_ptypes_panel'):
            page_funcs = (
                self.add_data_panel,
                self.add_general_panel,
                self.add_addons_panel,
                self.add_famtree_panel,
                self.add_import_panel,
                self.add_limits_panel,
                self.add_idformats_panel,
                self.add_symbols_panel,
                self.add_color_panel,
                self.add_text_panel,
                self.add_warnings_panel,
                self.add_researcher_panel,
                self.add_themes_panel)
            ConfigureDialog.__init__(self, uistate, dbstate, page_funcs,
                                     GrampsPreferences, config,
                                     on_close=self._close)
        else:
            page_funcs = (
                self.add_data_panel,
                self.add_general_panel,
                self.add_addons_panel,
                self.add_famtree_panel,
                self.add_import_panel,
                self.add_limits_panel,
                self.add_idformats_panel,
                self.add_symbols_panel,
                self.add_color_panel,
                self.add_text_panel,
                self.add_warnings_panel,
                self.add_researcher_panel,
                self.add_themes_panel)
            ConfigureDialog.__init__(self, uistate, dbstate, page_funcs,
                                     GrampsPreferences, config,
                                     on_close=update_constants)

        help_btn = self.window.add_button(_('_Help'), Gtk.ResponseType.HELP)
        help_btn.connect(
            'clicked', lambda x: display_help(WIKI_HELP_PAGE, WIKI_HELP_SEC))
        self.setup_configs('interface.grampspreferences', 700, 450)

    def add_themes_panel(self, configdialog):
        ''' This adds a Theme panel '''
        grid = Gtk.Grid()
        grid.set_border_width(12)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)

        # Theme combo
        self.theme = Gtk.ComboBoxText()
        self.t_names = set()
        # scan for standard Gtk themes
        themes = Gio.resources_enumerate_children("/org/gtk/libgtk/theme", 0)
        for theme in themes:
            if theme.endswith('/'):  # the modern way of finding
                self.t_names.add(theme[:-1])
            elif (theme.startswith('HighContrast') or
                  theme.startswith('Raleigh') or
                  theme.startswith('gtk-win32')):  # older method of hard coded
                self.t_names.add(theme.replace('.css', ''))
        # scan for user themes
        self.gtk_css(os.path.join(GLib.get_home_dir(), '.themes'))
        self.gtk_css(os.path.join(GLib.get_user_data_dir(), 'themes'))
        # scan for system themes
        dirs = GLib.get_system_data_dirs()
        for directory in dirs:
            self.gtk_css(os.path.join(directory, 'themes'))

        self.gtksettings = Gtk.Settings.get_default()
        # get current theme
        c_theme = self.gtksettings.get_property('gtk-theme-name')
        # fill combo with names and select active if current matches
        for indx, theme in enumerate(self.t_names):
            self.theme.append_text(theme)
            if theme == c_theme:
                self.theme.set_active(indx)

        if os.environ.get("GTK_THEME"):
            # theme is hardcoded, nothing we can do
            self.theme.set_sensitive(False)
            self.theme.set_tooltip_text(_("Theme is hardcoded by GTK_THEME"))
        else:
            self.theme.connect('changed', self.theme_changed)
        lwidget = Gtk.Label(label=(_("%s: ") % _('Theme')))
        grid.attach(lwidget, 0, 0, 1, 1)
        grid.attach(self.theme, 1, 0, 1, 1)

        # Dark theme
        self.dark = Gtk.CheckButton(label=_("Dark Variant"))
        value = self.gtksettings.get_property(
            'gtk-application-prefer-dark-theme')
        self.dark.set_active(value)
        self.dark.connect('toggled', self.dark_variant_changed)
        grid.attach(self.dark, 2, 0, 1, 1)
        self.dark_variant_changed(self.dark)
        if os.environ.get("GTK_THEME"):
            # theme is hardcoded, nothing we can do
            self.dark.set_sensitive(False)
            self.dark.set_tooltip_text(_("Theme is hardcoded by GTK_THEME"))

        # Font
        font_button = Gtk.FontButton(show_style=False)
        font_button.set_filter_func(self.font_filter, None)
        self.gtksettings.bind_property(
            'gtk-font-name', font_button, "font-name",
            BindingFlags.BIDIRECTIONAL | BindingFlags.SYNC_CREATE)
        lwidget = Gtk.Label(label=_("%s: ") % _('Font'))
        grid.attach(lwidget, 0, 1, 1, 1)
        grid.attach(font_button, 1, 1, 1, 1)
        font_button.connect('font-set', self.font_changed)

        # Toolbar Text
        t_text = Gtk.CheckButton.new_with_mnemonic(
            _("_Toolbar") + ' ' + _('Text'))
        value = config.get('interface.toolbar-text')
        t_text.set_active(value)
        t_text.connect('toggled', self.t_text_changed)
        grid.attach(t_text, 0, 2, 2, 1)

        # Scrollbar Windows style
        if win():
            self.sc_text = Gtk.CheckButton.new_with_mnemonic(
                _("Fixed Scrollbar (requires restart)"))
            value = config.get('interface.fixed-scrollbar')
            self.sc_text.set_active(value)
            self.sc_text.connect('toggled', self.scroll_changed)
            grid.attach(self.sc_text, 0, 3, 2, 1)

        # Default
        button = Gtk.Button(label=_('Restore to defaults'), expand=False)
        button.connect('clicked', self.default_clicked)
        grid.attach(button, 0, 4, 2, 1)

        return _('Theme'), grid

    def theme_changed(self, obj):
        ''' deal with combo changed '''
        value = obj.get_active_text()
        if value:
            config.set('preferences.theme', value)
            self.gtksettings.set_property('gtk-theme-name', value)

    def dark_variant_changed(self, obj):
        """
        Update dark_variant widget.
        """
        value = obj.get_active()
        config.set('preferences.theme-dark-variant', str(value))
        self.gtksettings.set_property('gtk-application-prefer-dark-theme',
                                      value)

    def scroll_changed(self, obj):
        ''' Scrollbar changed '''
        value = obj.get_active()
        config.set('interface.fixed-scrollbar', str(value))
        self.gtksettings.set_property('gtk-primary-button-warps-slider',
                                      not value)
        if hasattr(MyPrefs, 'provider'):
            Gtk.StyleContext.remove_provider_for_screen(
                Screen.get_default(), MyPrefs.provider)
        if value:
            MyPrefs.provider = Gtk.CssProvider()
            css = ('* { -GtkScrollbar-has-backward-stepper: 1; '
                   '-GtkScrollbar-has-forward-stepper: 1; }')
            MyPrefs.provider.load_from_data(css.encode('utf8'))
            Gtk.StyleContext.add_provider_for_screen(
                Screen.get_default(), MyPrefs.provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        try:
            if value:
                txt = subprocess.check_output('setx GTK_OVERLAY_SCROLLING 0',
                                              shell=True)
            else:
                txt = subprocess.check_output(
                    'reg delete HKCU\Environment /v GTK_OVERLAY_SCROLLING /f',
                    shell=True)
        except subprocess.CalledProcessError:
            print("Cannot set environment variable GTK_OVERLAY_SCROLLING")

    def t_text_changed(self, obj):
        ''' Toolbar text changed '''
        value = obj.get_active()
        config.set('interface.toolbar-text', value)
        toolbar = self.uistate.uimanager.get_widget('ToolBar')
        toolbar.set_style(
            Gtk.ToolbarStyle.BOTH if value else Gtk.ToolbarStyle.ICONS)

    def font_changed(self, obj):
        ''' deal with font changed '''
        font = obj.get_font()
        config.set('preferences.font', font)

    def font_filter(self, family, face, *obj):
        desc = face.describe()
        if (desc.get_style() == Pango.Style.NORMAL and
            desc.get_weight() == Pango.Weight.NORMAL):
            return True
        return False

    def default_clicked(self, obj):
        self.gtksettings.set_property('gtk-font-name', self.def_font)
        self.gtksettings.set_property('gtk-theme-name', self.def_theme)
        self.gtksettings.set_property('gtk-application-prefer-dark-theme',
                                      self.def_dark)
        config.set('preferences.font', '')
        config.set('preferences.theme', '')
        config.set('preferences.theme-dark-variant', '')
        # fill combo with names and select active if current matches
        self.theme.remove_all()
        for indx, theme in enumerate(self.t_names):
            self.theme.append_text(theme)
            if theme == self.def_theme:
                self.theme.set_active(indx)
        self.dark.set_active(self.def_dark)
        # Clear out scrollbar stuff
        if not win():  # don't mess with this on Linux etc.
            return
        self.sc_text.set_active(False)
        config.set('interface.fixed-scrollbar', '')
        self.gtksettings.set_property('gtk-primary-button-warps-slider', 1)
        if hasattr(MyPrefs, 'provider'):
            Gtk.StyleContext.remove_provider_for_screen(
                Screen.get_default(), MyPrefs.provider)
        try:
            txt = subprocess.check_output(
                'reg delete HKCU\Environment /v GTK_OVERLAY_SCROLLING /f',
                 shell=True)
        except subprocess.CalledProcessError:
            pass

    def gtk_css(self, directory):
        if not os.path.isdir(directory):
            return
        for dir_entry in glob.glob(
            os.path.join(directory, '*', 'gtk-3.*', 'gtk.css')):
            self.t_names.add(dir_entry.replace('\\', '/').split('/')[-3])
