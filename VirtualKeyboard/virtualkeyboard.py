# virtualkeyboard.py
# Virtual Keyboard Gramplet generated for Gramps 5.2
# Touch-friendly on-screen keyboard for clipboarded data entry
# Default: Special (accented) layout
#
# Copyright (C) 2026 Brian McCullough (prompting Perplexity AI Assistant)
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
# Generated: 17 Jan 2026 - Perplexity AI Assistant v1.0
#

from gi.repository import Gtk, Gdk
from gramps.gen.plug import Gramplet

# Complete keyboard layouts
QWERTY_ROWS = ["`1234567890-=", "qwertyuiop[]\\", "asdfghjkl;'", "zxcvbnm,./ "]

QWERTY_UPPER_ROWS = ["~!@#$%^&*()_+", "QWERTYUIOP{}|", 'ASDFGHJKL:"', "ZXCVBNM<>?   "]

SPECIAL_ROWS = [
    "áàâäéèêëíìîïóòôöúùûü",
    "ÁÀÂÄÉÈÊËÍÌÎÏÓÒÔÖÚÙÛÜ",
    "ñÑçÇßðÐþÞæøåÿğış",
    "ÑÇŞĞİığş.,!?;:",
]


class VirtualKeyboard(Gramplet):
    def init(self):
        self.buffer = ""
        self.current_layout = "accent"  # Default layout
        self.gui.uistate.connect("filter-changed", self.update)
        self.dbstate.connect("database-changed", self.update)
        self.build_interface()

    def build_interface(self):
        # CLEAR EXISTING CONTENT
        top = self.gui.get_container_widget()
        for child in top.get_children():
            top.remove(child)

        # CREATE MAIN VERTICAL BOX
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox.set_border_width(4)

        # DISPLAY BUFFER
        self.display = Gtk.Entry()
        self.display.set_editable(False)
        vbox.pack_start(self.display, False, False, 0)

        # LAYOUT BUTTONS (touch-friendly) - NO set_active()
        layout_hbox = Gtk.Box(spacing=4)
        self.layout_buttons = []
        layouts = [("qwerty", "qwerty"), ("upper", "QWERTY"), ("accent", "Special")]
        for layout_id, label in layouts:
            btn = Gtk.Button(label=label)
            btn.connect("clicked", self.on_layout_button, layout_id)
            layout_hbox.pack_start(btn, True, True, 0)
            self.layout_buttons.append((layout_id, btn))
        vbox.pack_start(layout_hbox, False, False, 0)

        # KEYBOARD AREA
        self.keyboard_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        vbox.pack_start(self.keyboard_vbox, True, True, 0)

        # CONTROL BUTTONS
        control_hbox = Gtk.Box(spacing=4)
        btns = [
            ("←", self.on_backspace),
            ("Clear", self.on_clear),
            ("Space", self.on_space),
            ("↵", self.on_newline),
            ("Insert", self.on_insert_into_field),
            ("Copy", self.on_copy_clipboard),
        ]
        for label, callback in btns:
            btn = Gtk.Button(label=label)
            btn.connect("clicked", callback)
            control_hbox.pack_start(btn, False, False, 0)
        vbox.pack_start(control_hbox, False, False, 0)

        # ADD TO GRAMPS CONTAINER
        top.add(vbox)
        vbox.show_all()

        # BUILD DEFAULT KEYBOARD (Special/accented)
        self.build_keyboard("accent")

    def on_layout_button(self, button, layout_id):
        self.current_layout = layout_id
        self.build_keyboard(layout_id)

    def build_keyboard(self, layout):
        # Clear existing keyboard
        for child in self.keyboard_vbox.get_children():
            self.keyboard_vbox.remove(child)

        # Select layout rows
        ROWS = {
            "qwerty": QWERTY_ROWS,
            "upper": QWERTY_UPPER_ROWS,
            "accent": SPECIAL_ROWS,
        }
        rows = ROWS.get(layout, SPECIAL_ROWS)

        # Build keyboard rows
        for row_chars in rows:
            hbox = Gtk.Box(spacing=1)
            for ch in row_chars:
                if ch in [
                    "Caps",
                    "Shift",
                    "Tab",
                    "caps",
                    "shift",
                    "tab",
                    "←",
                    "Clear",
                    "Space",
                    "↵",
                    "Copy",
                    "Insert",
                ]:
                    continue  # Skip function keys (handled by control row)
                btn = Gtk.Button(label=ch)
                btn.connect("clicked", self.on_char_clicked, ch)
                hbox.pack_start(btn, True, True, 0)
            self.keyboard_vbox.pack_start(hbox, False, False, 0)
        self.keyboard_vbox.show_all()

    def on_char_clicked(self, btn, ch):
        self.buffer += ch
        self.display.set_text(self.buffer)

    def on_backspace(self, btn):
        self.buffer = self.buffer[:-1]
        self.display.set_text(self.buffer)

    def on_clear(self, btn):
        self.buffer = ""
        self.display.set_text(self.buffer)

    def on_space(self, btn):
        self.buffer += " "
        self.display.set_text(self.buffer)

    def on_newline(self, btn):
        self.buffer += "\n"
        self.display.set_text(self.buffer)

    def on_copy_clipboard(self, btn):
        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clip.set_text(self.buffer, -1)

    def on_insert_into_field(self, btn):
        self.on_copy_clipboard(btn)
