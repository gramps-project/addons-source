"""Prepare the optional selector icon during Gramps user-plugin registration."""
from pathlib import Path

ICON_NAME = "gramps-descendants-timeline-view"


def load_on_reg(dbstate, uistate, initializer):
    if uistate is None:
        return
    from gramps.gen.plug import BasePluginManager
    from gramps.gen.plug._pluginreg import VIEW

    plugin = BasePluginManager.get_instance().get_plugin("descendants_timeline")
    if (plugin is None or plugin.ptype != VIEW or
            plugin.fname != "descendants_timeline_plugin.py" or
            Path(plugin.directory) != Path(initializer.directory)):
        return
    plugin.stock_icon = None
    directory = Path(plugin.directory) / "icons"

    from gi.repository import GdkPixbuf, GLib, Gtk

    theme = Gtk.IconTheme.get_default()
    if theme is None:
        return
    icon_name = _startup_icon_name(Gtk)
    expected = directory / (icon_name + ".svg")
    if not expected.is_file():
        return
    flags = Gtk.IconLookupFlags.FORCE_SIZE
    try:
        existing = theme.lookup_icon(icon_name, 16, flags)
        if existing and not _matches_file(existing, expected):
            return
        # Reject invalid artwork before changing the process's icon search path.
        GdkPixbuf.Pixbuf.new_from_file_at_scale(str(expected), 32, 32, True)
        if directory not in map(Path, theme.get_search_path()):
            theme.append_search_path(str(directory))
        for size in (16, 32):
            info = theme.lookup_icon(icon_name, size, flags)
            if not info or not _matches_file(info, expected) or info.load_icon() is None:
                return
    except (GLib.Error, OSError):
        return
    plugin.stock_icon = icon_name


def _matches_file(info, expected):
    filename = info.get_filename()
    return bool(filename) and Path(filename).samefile(expected)


def _startup_icon_name(gtk):
    """Use the resolved GTK button background once, before the selector exists."""
    button = gtk.ToggleButton()
    try:
        found, color = button.get_style_context().lookup_color("theme_bg_color")
    finally:
        button.destroy()
    if not found:
        return ICON_NAME
    channels = (color.red, color.green, color.blue)
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
              for v in channels]
    luminance = sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    return ICON_NAME + "-dark" if luminance < 0.18 else ICON_NAME
