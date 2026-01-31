# virtualkeyboard.py
# Virtual Keyboard Gramplet generated for Gramps 5.2
# Touch-friendly on-screen keyboard for clipboarded data entry
# Default: Special (accented) layout
#
# Copyright (C) 2026 Brian McCullough
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#

from gi.repository import Gdk, Gtk
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.plug import Gramplet

_ = glocale.translation.gettext


# QWERTY (US English)
QWERTY_ROWS = [
    "`1234567890-=",
    "qwertyuiop[]\\",
    "asdfghjkl;'",
    "zxcvbnm,./ ",
]
QWERTY_SHIFT_ROWS = [
    "~!@#$%^&*()_+",
    "QWERTYUIOP{}|",
    'ASDFGHJKL:"',
    "ZXCVBNM<>?   ",
]

SPECIAL_ROWS = [
    "áàâäéèêëíìîïóòôöúùûü",
    "ÁÀÂÄÉÈÊËÍÌÎÏÓÒÔÖÚÙÛÜ",
    "ñÑçÇßΒðÐþÞæÆœŒøåÿğış",
    "ÑÇŞĞİığş.,!?;:⁂§¶†‡№●°",
    "$€£¥₹₽R₱₩元圓₪₴",
    "©®×±÷—–…⅛¼⅓⅜½⅝⅔¾⅞",
]

# QWERTZ (French-style variant)
QWERTZ_ROWS = [
    "^1234567890ß´",
    "qwertzuiopü+",
    "asdfghjklöä#",
    "<yxcvbnm,.- ",
]
QWERTZ_SHIFT_ROWS = [
    "°!\"§$%&/()=?`",
    "QWERTZUIOPÜ*",
    "ASDFGHJKLÖÄ'",
    ">YXCVBNM;:_ ",
]

# AZERTY (German-style variant)
AZERTY_ROWS = [
    "²&é\"'(-è_çà)= ",
    "azertyuiop^$",
    "qsdfghjklmù*",
    "<wxcvbn,?:.!",
]
AZERTY_SHIFT_ROWS = [
    "³1234567890+ ",
    "AZERTYUIOP¨£",
    "QSDFGHJKLM%µ",
    ">WXCVBN/?.:§",
]

AZERTY_ALTGR_ROWS = [
    "¦@#{|}\\}",
    "¤¬¦¨´¸ˆ˜",
    "ÆŒœªº¿¡",
    "µ§£¢∞€",
]
AZERTY_ALTGR_SHIFT_ROWS = [
    "¶©ªº¯\\€",
    "¢¬¶¨¸ˆ˜",
    "æœŒºª¿¡",
    "¶§¥¹∞¥",
]


LAYOUT_SETS = {
    "gb": {
        "default": "special",
        "layouts": [
            ("qwerty", "qwerty", QWERTY_ROWS),
            ("QWERTY", "Shift QWERTY", QWERTY_SHIFT_ROWS),
            ("special", _("Special"), SPECIAL_ROWS),
        ],
    },
    "fr": {
        "default": "special",
        "layouts": [
            ("qwertz", "qwertz", QWERTZ_ROWS),
            ("QWERTZ", "Shift QWERTZ", QWERTZ_SHIFT_ROWS),
            ("special", _("Special"), SPECIAL_ROWS),
        ],
    },
    "de": {
        "default": "azertyaltgr",
        "layouts": [
            ("azerty", "azerty", AZERTY_ROWS),
            ("AZERTY", "Shift AZERTY", AZERTY_SHIFT_ROWS),
            ("azertyaltgr", "AltGr", AZERTY_ALTGR_ROWS),
            ("AZERTYALTGR", "Shift AltGr", AZERTY_ALTGR_SHIFT_ROWS),
            ("special", _("Special"), SPECIAL_ROWS),
        ],
    },
}


class VirtualKeyboard(Gramplet):
    def init(self):
        self.buffer = ""
        self.current_layout_set = "gb"
        self.current_layout = None
        self.layout_defs = {}

        self.gui.uistate.connect("filter-changed", self.update)
        self.dbstate.connect("database-changed", self.update)

        self.build_interface()

    def build_interface(self):
        top = self.gui.get_container_widget()
        for child in top.get_children():
            top.remove(child)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox.set_border_width(4)

        self.display = Gtk.Entry()
        self.display.set_editable(False)
        vbox.pack_start(self.display, False, False, 0)

        self.layout_hbox = Gtk.Box(spacing=4)
        vbox.pack_start(self.layout_hbox, False, False, 0)

        self.keyboard_vbox = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=2
        )
        vbox.pack_start(self.keyboard_vbox, True, True, 0)

        self.build_layout_buttons()
        self.select_default_layout()

        if self.current_layout:
            for layout_id, btn in self.layout_buttons:
                btn.set_active(layout_id == self.current_layout)
            self.build_keyboard(self.current_layout)

        control_hbox = Gtk.Box(spacing=4)
        btns = [
            ("🇬🇧", self.on_flag_clicked, "gb"),
            ("🇫🇷", self.on_flag_clicked, "fr"),
            ("🇩🇪", self.on_flag_clicked, "de"),
            ("←", self.on_backspace),
            (_("Clear"), self.on_clear),
            (_("Space"), self.on_space),
            (_("Tab"), self.on_tab),
            ("↵", self.on_newline),
            (_("Copy"), self.on_copy_clipboard),
        ]

        self.flag_buttons = []

        for item in btns:
            if len(item) == 2:
                label, callback = item
                btn = Gtk.Button(label=label)
                btn.connect("clicked", callback)
            else:
                label, callback, set_id = item
                btn = Gtk.Button(label=label)
                btn.connect("clicked", callback, set_id)
                self.flag_buttons.append((set_id, btn))

            control_hbox.pack_start(btn, False, False, 0)

        vbox.pack_start(control_hbox, False, False, 0)

        top.add(vbox)
        vbox.show_all()
        self.update_flag_buttons()

    def select_default_layout(self):
        set_def = LAYOUT_SETS.get(self.current_layout_set, {})
        default_id = set_def.get("default")

        if default_id and default_id in self.layout_defs:
            self.current_layout = default_id
        elif self.layout_defs:
            self.current_layout = next(iter(self.layout_defs))
        else:
            self.current_layout = None

    def build_layout_buttons(self):
        for child in self.layout_hbox.get_children():
            self.layout_hbox.remove(child)

        self.layout_buttons = []
        self.layout_defs = {}

        set_def = LAYOUT_SETS.get(self.current_layout_set, {})
        layouts = set_def.get("layouts", [])

        for layout_id, label, rows in layouts:
            btn = Gtk.ToggleButton(label=label)
            btn.connect("toggled", self.on_layout_toggled, layout_id)
            self.layout_hbox.pack_start(btn, True, True, 0)

            self.layout_buttons.append((layout_id, btn))
            self.layout_defs[layout_id] = rows

        self.layout_hbox.set_visible(bool(layouts))
        self.layout_hbox.show_all()

    def on_layout_toggled(self, btn, layout_id):
        if not btn.get_active():
            return
        self.current_layout = layout_id
        self.build_keyboard(layout_id)

        for other_id, other_btn in self.layout_buttons:
            if other_btn is not btn:
                other_btn.set_active(False)

    def build_keyboard(self, layout_id):
        if not hasattr(self, "keyboard_vbox"):
            return

        for child in self.keyboard_vbox.get_children():
            self.keyboard_vbox.remove(child)

        rows = self.layout_defs.get(layout_id)
        if not rows:
            return

        for row_chars in rows:
            hbox = Gtk.Box(spacing=1)
            for ch in row_chars:
                btn = Gtk.Button(label=ch)
                btn.connect("clicked", self.on_char_clicked, ch)
                hbox.pack_start(btn, True, True, 0)
            self.keyboard_vbox.pack_start(hbox, False, False, 0)

        self.keyboard_vbox.show_all()

    def update_flag_buttons(self):
        for set_id, btn in self.flag_buttons:
            btn.set_sensitive(set_id != self.current_layout_set)

    def on_flag_clicked(self, btn, set_id):
        if set_id == self.current_layout_set:
            return

        self.current_layout_set = set_id
        self.update_flag_buttons()
        self.build_layout_buttons()
        self.select_default_layout()

        if self.current_layout:
            for layout_id, btn in self.layout_buttons:
                btn.set_active(layout_id == self.current_layout)
            self.build_keyboard(self.current_layout)
        else:
            for child in self.keyboard_vbox.get_children():
                self.keyboard_vbox.remove(child)

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

    def on_tab(self, btn):
        self.buffer += "\t"
        self.display.set_text(self.buffer)

    def on_newline(self, btn):
        self.buffer += "\n"
        self.display.set_text(self.buffer)

    def on_copy_clipboard(self, btn):
        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clip.set_text(self.buffer, -1)
