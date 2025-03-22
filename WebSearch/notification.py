#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Yurii Liubymyi <jurchello@gmail.com>
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

# ----------------------------------------------------------------------------

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GObject, Pango

class Notification(Gtk.Window):
    """
    Notification class for displaying temporary pop-up messages.

    This class creates a small floating window that displays a message and
    automatically disappears after a few seconds. It is designed to be used
    for brief notifications in the Gramps WebSearch Gramplet.

    Key Features:
    - Transparent background with rounded corners.
    - Auto-closes after 2 seconds.
    - Appears at the top-right corner of the screen.
    - Uses GTK and Pango for text formatting.

    Methods:
    - __init__(message): Initializes the notification window with the given message.
    - close_window(): Closes the notification window after a timeout.
    - apply_css(): Applies custom CSS for transparency and styling.
    """
    def __init__(self, message):
        super().__init__()

        screen = Gdk.Screen.get_default()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_name("TransparentWindow")
        self.apply_css()

        self.set_decorated(False)
        self.set_accept_focus(False)
        self.set_size_request(200, -1)
        self.set_keep_above(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(10)
        box.set_margin_end(10)

        label = Gtk.Label(label=message)
        label.set_line_wrap(True)
        label.set_max_width_chars(10)
        label.set_ellipsize(Pango.EllipsizeMode.NONE)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        box.pack_start(label, True, True, 0)
        self.add(box)

        self.show_all()

        width, height = self.get_size()
        self.set_size_request(100, height)
        monitor = screen.get_monitor_geometry(0)
        screen_width = monitor.width
        width, height = self.get_size()
        x = screen_width - width - 10
        y = 10
        self.move(x, y)

        GObject.timeout_add(2000, self.close_window)

    def close_window(self):
        self.destroy()
        return False

    def apply_css(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            #TransparentWindow {
                background-color: rgba(0, 0, 0, 0.7);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        context = Gtk.StyleContext()
        screen = Gdk.Screen.get_default()
        context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
