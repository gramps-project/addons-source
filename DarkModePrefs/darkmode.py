#
# Gramps - dark mode preferences panel
#

import glob
import os
import types

from gi.repository import Gio, GLib, Gtk

from gramps.gen.config import config
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.utils.alive import update_constants
from gramps.gui.configure import (
    ConfigureDialog,
    GrampsPreferences,
    WIKI_HELP_PAGE,
    WIKI_HELP_SEC,
)
from gramps.gui.display import display_help


try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


MODE_AUTO = "auto"
MODE_DARK = "dark"
MODE_LIGHT = "light"
VALID_MODES = {MODE_AUTO, MODE_DARK, MODE_LIGHT}

KEY_MODE = "preferences.darkmode.mode"
KEY_THEME_DARK = "preferences.darkmode.theme-dark"
KEY_THEME_LIGHT = "preferences.darkmode.theme-light"
KEY_APPLY_THEME = "preferences.darkmode.apply-theme-name"
KEY_APPLY_CSS_FIXES = "preferences.darkmode.apply-css-fixes"

DEFAULT_THEME_DARK = "Adwaita-dark"
DEFAULT_THEME_LIGHT = "Adwaita"


CSS_FIXES = """
/* Keep text widgets readable if theme CSS is incomplete */
textview text {
  background-color: @theme_base_color;
  color: @theme_text_color;
}

entry, textview {
  caret-color: @theme_text_color;
}
"""


class _State:
    css_provider = None
    gnome_interface_settings = None
    gnome_handler_id = None


def _is_flatpak_runtime():
    return os.path.exists("/.flatpak-info")


def _gtk_theme_override_value():
    value = os.environ.get("GTK_THEME")
    if not value:
        return ""
    return value.strip()


def _gtk_theme_override_active():
    return bool(_gtk_theme_override_value())


def register_config_defaults():
    config.register(KEY_MODE, MODE_AUTO)
    config.register(KEY_THEME_DARK, DEFAULT_THEME_DARK)
    config.register(KEY_THEME_LIGHT, DEFAULT_THEME_LIGHT)
    config.register(KEY_APPLY_THEME, "True")
    config.register(KEY_APPLY_CSS_FIXES, "True")


def _bool_from_config(key, default):
    value = config.get(key)
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _get_mode():
    value = config.get(KEY_MODE)
    if not value:
        return MODE_AUTO
    value = str(value).strip().lower()
    if value in VALID_MODES:
        return value
    return MODE_AUTO


def _gnome_system_prefers_dark():
    schema = Gio.SettingsSchemaSource.get_default()
    if not schema:
        return None

    interface_schema = schema.lookup("org.gnome.desktop.interface", True)
    if not interface_schema:
        return None
    if not interface_schema.has_key("color-scheme"):
        return None

    settings = Gio.Settings.new("org.gnome.desktop.interface")
    value = settings.get_string("color-scheme")
    return value == "prefer-dark"


def _fallback_prefers_dark_from_theme_name():
    settings = Gtk.Settings.get_default()
    if not settings:
        return False
    theme_name = settings.get_property("gtk-theme-name") or ""
    return "dark" in str(theme_name).lower()


def _effective_dark_preference():
    mode = _get_mode()
    if mode == MODE_DARK:
        return True
    if mode == MODE_LIGHT:
        return False

    system_pref = _gnome_system_prefers_dark()
    if system_pref is not None:
        return system_pref
    return _fallback_prefers_dark_from_theme_name()


def _collect_theme_names():
    names = set()

    try:
        for theme in Gio.resources_enumerate_children("/org/gtk/libgtk/theme", 0):
            if theme.endswith("/"):
                names.add(theme[:-1])
            elif theme.startswith(("HighContrast", "Raleigh", "gtk-win32")):
                names.add(theme.replace(".css", ""))
    except Exception:
        pass

    theme_roots = [
        os.path.join(os.path.expanduser("~"), ".themes"),
        os.path.join(os.path.expanduser("~"), ".local", "share", "themes"),
    ]

    for root in theme_roots:
        if not os.path.isdir(root):
            continue
        for css_file in glob.glob(os.path.join(root, "*", "gtk-3.*", "gtk.css")):
            names.add(css_file.replace("\\", "/").split("/")[-3])

    for data_dir in GLib.get_system_data_dirs():
        theme_dir = os.path.join(data_dir, "themes")
        if not os.path.isdir(theme_dir):
            continue
        for css_file in glob.glob(os.path.join(theme_dir, "*", "gtk-3.*", "gtk.css")):
            names.add(css_file.replace("\\", "/").split("/")[-3])

    return names


def _resolve_theme_name(prefer_dark):
    configured = config.get(KEY_THEME_DARK if prefer_dark else KEY_THEME_LIGHT) or ""
    configured = configured.strip()
    available = _collect_theme_names()

    if not available:
        return None

    if configured and configured in available:
        return configured

    if prefer_dark:
        # Prefer any explicitly dark variant that actually exists.
        dark_variants = sorted(
            [name for name in available if "dark" in name.lower()],
            key=str.casefold,
        )
        if dark_variants:
            return dark_variants[0]

        # Flatpak runtimes often expose only Adwaita; combine with
        # gtk-application-prefer-dark-theme instead of forcing invalid names.
        if "Adwaita" in available:
            return "Adwaita"
        return None

    if DEFAULT_THEME_LIGHT in available:
        return DEFAULT_THEME_LIGHT
    return sorted(available, key=str.casefold)[0]


def _apply_css_fixes(enabled):
    screen = None
    try:
        from gi.repository import Gdk

        screen = Gdk.Screen.get_default()
    except Exception:
        screen = None
    if not screen:
        return

    if _State.css_provider is not None:
        Gtk.StyleContext.remove_provider_for_screen(screen, _State.css_provider)
        _State.css_provider = None

    if not enabled:
        return

    provider = Gtk.CssProvider()
    provider.load_from_data(CSS_FIXES.encode("utf8"))
    Gtk.StyleContext.add_provider_for_screen(
        screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    _State.css_provider = provider


def apply_darkmode_settings():
    register_config_defaults()

    gtk_settings = Gtk.Settings.get_default()
    if not gtk_settings:
        return

    prefer_dark = _effective_dark_preference()
    gtk_settings.set_property("gtk-application-prefer-dark-theme", prefer_dark)

    if not _gtk_theme_override_active() and _bool_from_config(KEY_APPLY_THEME, True):
        theme_name = _resolve_theme_name(prefer_dark)
        if theme_name:
            gtk_settings.set_property("gtk-theme-name", theme_name)

    _apply_css_fixes(_bool_from_config(KEY_APPLY_CSS_FIXES, True))


def _on_gnome_color_scheme_changed(*_args):
    if _get_mode() == MODE_AUTO:
        apply_darkmode_settings()


def setup_system_darkmode_listener():
    if _State.gnome_handler_id is not None:
        return

    schema = Gio.SettingsSchemaSource.get_default()
    if not schema:
        return

    interface_schema = schema.lookup("org.gnome.desktop.interface", True)
    if not interface_schema or not interface_schema.has_key("color-scheme"):
        return

    settings = Gio.Settings.new("org.gnome.desktop.interface")
    _State.gnome_handler_id = settings.connect(
        "changed::color-scheme", _on_gnome_color_scheme_changed
    )
    _State.gnome_interface_settings = settings


class DarkModePrefs(GrampsPreferences):
    """
    Extends Preferences with a Dark Mode panel.
    """

    def __init__(self, uistate, dbstate):
        self.add_darkmode_panel = types.MethodType(DarkModePrefs.add_darkmode_panel, self)
        self.mode_changed = types.MethodType(DarkModePrefs.mode_changed, self)
        self.theme_dark_changed = types.MethodType(DarkModePrefs.theme_dark_changed, self)
        self.theme_light_changed = types.MethodType(DarkModePrefs.theme_light_changed, self)
        self.apply_theme_toggled = types.MethodType(DarkModePrefs.apply_theme_toggled, self)
        self.css_fixes_toggled = types.MethodType(DarkModePrefs.css_fixes_toggled, self)
        self.apply_now_clicked = types.MethodType(DarkModePrefs.apply_now_clicked, self)
        self.restore_defaults_clicked = types.MethodType(
            DarkModePrefs.restore_defaults_clicked, self
        )

        if hasattr(self, "add_ptypes_panel"):
            page_funcs = (
                self.add_data_panel,
                self.add_general_panel,
                self.add_famtree_panel,
                self.add_import_panel,
                self.add_limits_panel,
                self.add_color_panel,
                self.add_symbols_panel,
                self.add_idformats_panel,
                self.add_text_panel,
                self.add_warnings_panel,
                self.add_researcher_panel,
                self.add_ptypes_panel,
                self.add_darkmode_panel,
            )
        else:
            page_funcs = (
                self.add_data_panel,
                self.add_general_panel,
                self.add_famtree_panel,
                self.add_import_panel,
                self.add_limits_panel,
                self.add_color_panel,
                self.add_symbols_panel,
                self.add_idformats_panel,
                self.add_text_panel,
                self.add_warnings_panel,
                self.add_researcher_panel,
                self.add_darkmode_panel,
            )

        ConfigureDialog.__init__(
            self,
            uistate,
            dbstate,
            page_funcs,
            GrampsPreferences,
            config,
            on_close=update_constants,
        )
        help_btn = self.window.add_button(_("_Help"), Gtk.ResponseType.HELP)
        help_btn.connect("clicked", lambda x: display_help(WIKI_HELP_PAGE, WIKI_HELP_SEC))
        self.setup_configs("interface.grampspreferences", 760, 480)

    def add_darkmode_panel(self, configdialog):
        register_config_defaults()

        grid = Gtk.Grid()
        grid.set_border_width(12)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)

        info = Gtk.Label(
            label=_(
                "Use Auto to follow GNOME system dark mode. "
                "Use Dark/Light to force a specific mode."
            )
        )
        info.set_halign(Gtk.Align.START)
        info.set_line_wrap(True)
        grid.attach(info, 0, 0, 3, 1)

        mode_label = Gtk.Label(label=_("Mode:"))
        mode_label.set_halign(Gtk.Align.START)
        grid.attach(mode_label, 0, 1, 1, 1)

        self.mode_combo = Gtk.ComboBoxText()
        self.mode_combo.append(MODE_AUTO, _("Auto (follow system)"))
        self.mode_combo.append(MODE_DARK, _("Dark"))
        self.mode_combo.append(MODE_LIGHT, _("Light"))
        self.mode_combo.set_active_id(_get_mode())
        self.mode_combo.connect("changed", self.mode_changed)
        grid.attach(self.mode_combo, 1, 1, 2, 1)

        theme_names = sorted(_collect_theme_names(), key=str.casefold)

        dark_theme_label = Gtk.Label(label=_("Dark theme:"))
        dark_theme_label.set_halign(Gtk.Align.START)
        grid.attach(dark_theme_label, 0, 2, 1, 1)

        self.dark_theme_combo = Gtk.ComboBoxText.new_with_entry()
        for name in theme_names:
            self.dark_theme_combo.append(name, name)
        dark_theme = config.get(KEY_THEME_DARK) or DEFAULT_THEME_DARK
        self.dark_theme_combo.set_active_id(dark_theme)
        if self.dark_theme_combo.get_active_id() is None:
            self.dark_theme_combo.get_child().set_text(dark_theme)
        self.dark_theme_combo.connect("changed", self.theme_dark_changed)
        grid.attach(self.dark_theme_combo, 1, 2, 2, 1)

        light_theme_label = Gtk.Label(label=_("Light theme:"))
        light_theme_label.set_halign(Gtk.Align.START)
        grid.attach(light_theme_label, 0, 3, 1, 1)

        self.light_theme_combo = Gtk.ComboBoxText.new_with_entry()
        for name in theme_names:
            self.light_theme_combo.append(name, name)
        light_theme = config.get(KEY_THEME_LIGHT) or DEFAULT_THEME_LIGHT
        self.light_theme_combo.set_active_id(light_theme)
        if self.light_theme_combo.get_active_id() is None:
            self.light_theme_combo.get_child().set_text(light_theme)
        self.light_theme_combo.connect("changed", self.theme_light_changed)
        grid.attach(self.light_theme_combo, 1, 3, 2, 1)

        self.apply_theme_check = Gtk.CheckButton(label=_("Apply GTK theme name"))
        self.apply_theme_check.set_active(_bool_from_config(KEY_APPLY_THEME, True))
        self.apply_theme_check.connect("toggled", self.apply_theme_toggled)
        grid.attach(self.apply_theme_check, 0, 4, 3, 1)

        self.css_fixes_check = Gtk.CheckButton(
            label=_("Apply compatibility CSS fixes")
        )
        self.css_fixes_check.set_active(_bool_from_config(KEY_APPLY_CSS_FIXES, True))
        self.css_fixes_check.connect("toggled", self.css_fixes_toggled)
        grid.attach(self.css_fixes_check, 0, 5, 3, 1)

        if _gtk_theme_override_active():
            value = _gtk_theme_override_value()
            if _is_flatpak_runtime():
                warning_text = _(
                    "GTK_THEME is set to '%s'. Theme-name changes from addon are disabled. "
                    "If set by Flatpak override, run:\n"
                    "flatpak override --user --unset-env=GTK_THEME org.gramps_project.Gramps"
                ) % value
            else:
                warning_text = _(
                    "GTK_THEME is set to '%s'. Theme-name changes from addon are disabled."
                ) % value
            warning = Gtk.Label(
                label=warning_text
            )
            warning.set_halign(Gtk.Align.START)
            warning.set_line_wrap(True)
            grid.attach(warning, 0, 6, 3, 1)
            self.apply_theme_check.set_sensitive(False)
            self.dark_theme_combo.set_sensitive(False)
            self.light_theme_combo.set_sensitive(False)

        apply_now = Gtk.Button(label=_("Apply now"))
        apply_now.connect("clicked", self.apply_now_clicked)
        grid.attach(apply_now, 0, 7, 1, 1)

        restore = Gtk.Button(label=_("Restore defaults"))
        restore.connect("clicked", self.restore_defaults_clicked)
        grid.attach(restore, 1, 7, 1, 1)

        return _("Dark Mode"), grid

    def _combo_value(self, combo):
        active = combo.get_active_id()
        if active:
            return active
        child = combo.get_child()
        if child:
            return child.get_text().strip()
        return ""

    def mode_changed(self, combo):
        mode = combo.get_active_id() or MODE_AUTO
        if mode not in VALID_MODES:
            mode = MODE_AUTO
        config.set(KEY_MODE, mode)
        apply_darkmode_settings()

    def theme_dark_changed(self, combo):
        value = self._combo_value(combo)
        if value:
            config.set(KEY_THEME_DARK, value)
            apply_darkmode_settings()

    def theme_light_changed(self, combo):
        value = self._combo_value(combo)
        if value:
            config.set(KEY_THEME_LIGHT, value)
            apply_darkmode_settings()

    def apply_theme_toggled(self, obj):
        config.set(KEY_APPLY_THEME, str(obj.get_active()))
        apply_darkmode_settings()

    def css_fixes_toggled(self, obj):
        config.set(KEY_APPLY_CSS_FIXES, str(obj.get_active()))
        apply_darkmode_settings()

    def apply_now_clicked(self, obj):
        apply_darkmode_settings()

    def restore_defaults_clicked(self, obj):
        config.set(KEY_MODE, MODE_AUTO)
        config.set(KEY_THEME_DARK, DEFAULT_THEME_DARK)
        config.set(KEY_THEME_LIGHT, DEFAULT_THEME_LIGHT)
        config.set(KEY_APPLY_THEME, "True")
        config.set(KEY_APPLY_CSS_FIXES, "True")
        apply_darkmode_settings()

        self.mode_combo.set_active_id(MODE_AUTO)
        self.dark_theme_combo.set_active_id(DEFAULT_THEME_DARK)
        if self.dark_theme_combo.get_active_id() is None:
            self.dark_theme_combo.get_child().set_text(DEFAULT_THEME_DARK)
        self.light_theme_combo.set_active_id(DEFAULT_THEME_LIGHT)
        if self.light_theme_combo.get_active_id() is None:
            self.light_theme_combo.get_child().set_text(DEFAULT_THEME_LIGHT)
        self.apply_theme_check.set_active(True)
        self.css_fixes_check.set_active(True)
