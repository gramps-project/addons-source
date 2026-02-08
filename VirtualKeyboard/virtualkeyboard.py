# virtualkeyboard.py
# Virtual Keyboard Gramplet generated for Gramps 5.2
# Touch-friendly on-screen keyboard for clipboarded data entry
# Default: Special (accented) layout
#
# Copyright (C) 2026 Brian McCullough, wish-coder
#    (ChatGPT, Perplexity and Codex development)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
import os
import csv
import logging

from pathlib import Path
from gi.repository import Gdk, Gtk, GObject
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.plug import Gramplet
from gramps.gen.config import config


LOG = logging.getLogger(__name__)
_ = glocale.get_addon_translator(__file__).gettext

# Virtual Keyboard mappings

# Oops keyboard layout failure
OOPS_ROWS = [
    " 😭 @#$%&! 💣 💣 💣 ",
    " See  💡warning   in  statusbar. ",
    " 😠 Fix  or  remove  the ",
    " broken layout! ",
]

# QWERTY (US English)
QWERTY_ROWS = [
    "`1234567890-=  ⌫",
    "⇥ qwertyuiop[]\\",
    "⇪  asdfghjkl;'  ↩",
    "⇧   zxcvbnm,./    ⇧",
]
QWERTY_SHIFT_ROWS = [
    "~!@#$%^&*()_+  ⌦",
    "⇤ QWERTYUIOP{}|",
    '⇫  ASDFGHJKL:"  ⏎',
    "⇧   ZXCVBNM<>?    ⇧",
]

SPECIAL_ROWS = [
    "áàâäéèêëíìîïóòôöúùûü",
    "ÁÀÂÄÉÈÊËÍÌÎÏÓÒÔÖÚÙÛÜ",
    "ñÑçÇßΒðÐþÞæÆœŒøåÿğış",
    "ÑÇŞĞİığş.,!?;:⁂§¶†‡№●°",
    "$¢€c£p¥₹₽кR₱₩元角圓₪₴",
    "©® ⌘⊞⌥⎇≣ ×±÷—–… ⅛¼⅓⅜½⅝⅔¾⅞",
]

MATH_ROWS = [ #https://math.typeit.org/
    "⟨⟩⟦⟧⌊⌈⌋⌉ ↑⇐←↦ ℰℓℒℳ ’“”–—",
    "½¼∕∤⊥∥‰ø≪≫~⊢⊨□◇ ℂℕℙℚℝℤ",
    "ΓΔΛΞΠΣΦΨΩ Åℏ ∞∘∂∫∮∯∇ ′″‴",
    "αβγδεζηθκλμνξπρστυφχψω",
    "ΑΒΓΔΕΖΗΘΚΛΜΝΞΠΡΣΤΥΦΧΨΩ",
    "⇒→⇔↔ ∈∉⊂⊆⊄⊈⊃∪∩∖∅ ∏∑ ̅̂⃗̇̈\u201c\u201d",
    "¬∨∧∀∃ −±⊕·×⊗÷²³√∛ ≠≈≡≝≤≥ °∠",
]

COMPOSED_ROWS = [
    "áÁéÉíÍóÓúÚàÀèÈìÌòÒùÙ",
    "äÄëËïÏöÖüÜÿŸżŻċĊġĠıİ",
    "åÅãÃñÑõÕçÇşŞąĄęĘįĮųŲ",
    "âÂêÊîÎôÔûÛ –—…≤≥≠",
    "øØðÐþÞłŁŋŊßẞæÆœŒ",
]

# QWERTZ (Gerrman-style variant)
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
QWERTZ_ALTGR_ROWS = [
    "¦@#{|}\\}",
    "¤¬¦¨´¸ˆ˜",
    "ÆŒœªº¿¡",
    "µ§£¢∞€",
]
QWERTZ_ALTGR_SHIFT_ROWS = [
    "¶©ªº¯\\€",
    "¢¬¶¨¸ˆ˜",
    "æœŒºª¿¡",
    "¶§¥¹∞¥",
]

# AZERTY (French-style variant) — matches layouts/fr.csv
AZERTY_ROWS = [
    "&é\"'(-è_çà)",
    "azertyuiop^$",
    "qsdfghjklmù*",
    "wxcvbn,;:!",
]
AZERTY_SHIFT_ROWS = [
    "1234567890°+",
    "AZERTYUIOP¨£",
    "QSDFGHJKLM%µ",
    "WXCVBN?./§",
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

# Layout tuple order:
# (rows, layout_id, button_label, button_tooltip)
LayoutSets = {

    "oops": {  # Error reporting
        "layouts": [
            ("OOPS_ROWS", "oops",
                _("⚠  Layout Set Invalid"),
                _("The selected keyboard layout set could not be loaded")),
        ],
        "default_layout": "oops",
    },

    "gb": {  # English (GB and US) keyboard layout button menu
        "id": "GB_QWERTY",
        "language": "en",
        "button": "🇬🇧",
        "labels": {
            "native": "English",
            "en": "English",
        },
        "tooltips": {
            "tooltip_native": "Standard QWERTY keyboard",
            "tooltip_en": "Standard QWERTY keyboard",
        },
        "layouts": [
            ("QWERTY_ROWS", "qwerty",
                _("QWERTY"), _("Most common English-language keyboard layout")),
            ("QWERTY_SHIFT_ROWS", "qwerty_shift",
                _("Shift QWERTY"), _("Uppercase letters and shifted symbols")),
            ("COMPOSED_ROWS", "composed",
                _("Composed / Dead Keys"),
                _("Mashup of diacritics, extended, and composed characters")),
            ("SPECIAL_ROWS", "special",
                _("Special"), _("Mashup of special characters")),
            ("MATH_ROWS", "math",
                _("Math"), _("Mashup of mathematical operators")),
        ],
        "default_layout": "special",
    },

    "fr": {  # French keyboard layout button menu — matches layouts/fr.csv
        "id": "FR_AZERTY",
        "language": "fr",
        "button": "🇫🇷",
        "labels": {
            "native": "Français",
            "en": "French",
        },
        "tooltips": {
            "tooltip_native": "Clavier français AZERTY",
            "tooltip_en": "AZERTY keyboard",
        },
        "layouts": [
            ("AZERTY_ROWS", "azerty",
                _("azerty"), _("Disposition française standard")),
            ("AZERTY_SHIFT_ROWS", "azerty_shift",
                _("AZERTY1"), _("Majuscules et chiffres")),
            ("SPECIAL_ROWS", "special",
                _("Special"), _("Caractères spéciaux")),
            ("COMPOSED_ROWS", "composed",
                _("Compose"), _("Caractères composés et diacritiques")),
        ],
        "default_layout": "azerty",
    },

    "de": {  # German keyboard layout button menu
        "id": "DE_QWERTZ",
        "language": "de",
        "button": "🇩🇪",
        "labels": {
            "native": "Deutsch",
            "en": "German",
        },
        "tooltips": {
            "tooltip_native": "Deutsche QWERTZ-Tastatur",
            "tooltip_en": "German QWERTZ keyboard",
        },
        "layouts": [
            ("QWERTZ_ROWS", "qwertz",
                _("QWERTZ"),
                _("Standard German keyboard layout")),
            ("QWERTZ_SHIFT_ROWS", "qwertz_shift",
                _("Shift QWERTZ"),
                _("German uppercase letters and shifted symbols")),
            ("QWERTZ_ALTGR_ROWS", "qwertz_altgr",
                _("AltGr"),
                _("Alternate characters, symbols, and currency")),
            ("QWERTZ_ALTGR_SHIFT_ROWS", "qwertz_altgr_shift",
                _("Shift AltGr"),
                _("Shifted alternate characters, symbols, and currency")),
            ("SPECIAL_ROWS", "special",
                _("Special"), _("Mashup of special characters")),
            ("COMPOSED_ROWS", "composed",
                _("Composed / Dead Keys"),
                _("Mashup of diacritics, extended, and composed characters")),
        ],
        "default_layout": "qwertz_altgr",
    },
}

LAYOUT_SETS = LayoutSets

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------

# TODO:
# CONFIG_ID is currently used both for config identity and diagnostics.
# This is intentional for now. A later refactor may separate persistent
# identity from schema/version labeling.
CONFIG_ID = "LocalTerm"
CONFIG_SCHEMA_VERSION = "0.0.1.5"

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
LAYOUTS_DIR = Path(PLUGIN_DIR) / "layouts"

# IMPORTANT: no ".ini" — Gramps adds it
_config_file = os.path.join(PLUGIN_DIR, CONFIG_ID)

config = config.register_manager(_config_file)

# schema metadata
config.register("VirtualKeyboard.config_id", CONFIG_ID)
# IMPORTANT:
# config_schema MUST NOT default to the current version,
# otherwise Gramps will comment it out and schema mismatch
# detection will never trigger.
# config.register("VirtualKeyboard.config_schema", CONFIG_SCHEMA_VERSION)
config.register("VirtualKeyboard.config_schema", "")
config.register("VirtualKeyboard.layout_id", "fr")
# options
config.register("VirtualKeyboard.show_anchor", False)

def layout_id_from_path(path: Path) -> str:
    return path.stem  # e.g. "fr", "fr-azerty", "en_us"

def iter_layout_csvs():
    if not LAYOUTS_DIR.is_dir():
        return []
    return sorted(LAYOUTS_DIR.glob("*.csv"))

def get_available_layouts():
    return {
        layout_id_from_path(p): p
        for p in iter_layout_csvs()
    }

# Map layout @id (no rows in CSV) -> built-in rows ref name
BUILTIN_LAYOUT_ROWS = {
    "SPECIAL": "SPECIAL_ROWS",
    "COMPOSED": "COMPOSED_ROWS",
    "QWERTY": "QWERTY_ROWS",
    "QWERTY_SHIFT": "QWERTY_SHIFT_ROWS",
    "QWERTZ": "QWERTZ_ROWS",
    "QWERTZ_SHIFT": "QWERTZ_SHIFT_ROWS",
    "QWERTZ_ALTGR": "QWERTZ_ALTGR_ROWS",
    "QWERTZ_ALTGR_SHIFT": "QWERTZ_ALTGR_SHIFT_ROWS",
    "AZERTY": "AZERTY_ROWS",
    "AZERTY_SHIFT": "AZERTY_SHIFT_ROWS",
    "AZERTY_ALTGR": "AZERTY_ALTGR_ROWS",
    "AZERTY_ALTGR_SHIFT": "AZERTY_ALTGR_SHIFT_ROWS",
}

def _parse_csv_directive(line: str):
    """Parse '@key,value' into (key, value). Returns None for non-directives."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if not line.startswith("@"):
        return None
    idx = line.find(",")
    if idx < 0:
        return (line[1:].lower(), "")
    return (line[1:idx].lower(), line[idx + 1 :].strip())

def load_layout_csv(path: Path):
    """
    Parse a layout CSV per spec 1.2.0. Returns set_def dict or None on error.
    Layouts without @row use built-in row mappings from BUILTIN_LAYOUT_ROWS.
    """
    try:
        with open(path, encoding="utf-8", newline="") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError) as e:
        LOG.warning("VirtualKeyboard: cannot load %s: %s", path, e)
        return None

    set_data = {}
    layouts = []
    current_layout = None
    current_rows = []
    ui_lang = (glocale.language or ["en"])[0][:2] if glocale.language else "en"

    for line in lines:
        parsed = _parse_csv_directive(line)
        if not parsed:
            continue
        key, val = parsed

        if key == "set":
            continue
        if key in ("id", "language", "button", "default_layout", "label_native",
                   "label_en", "label", "tooltip_native", "tooltip_en",
                   "language_iso3", "region"):
            if current_layout is None:
                if key == "default_layout":
                    set_data["default_layout"] = val.lower()
                elif key == "id":
                    set_data["id"] = val
                elif key == "language":
                    set_data["language"] = val[:2]
                elif key == "button":
                    set_data["button"] = val
                elif key == "label_native":
                    set_data["_label_native"] = val
                elif key == "label_en":
                    set_data["_label_en"] = val
                elif key == "label":
                    set_data["_label_en"] = set_data.get("_label_en") or val
                elif key == "tooltip_native":
                    set_data["_tooltip_native"] = val
                elif key == "tooltip_en":
                    set_data["_tooltip_en"] = val
            else:
                if key == "id":
                    current_layout["id"] = val
                elif key == "label_native":
                    current_layout["_label_native"] = val
                elif key == "label_en":
                    current_layout["_label_en"] = val
                elif key == "label":
                    current_layout["_label_en"] = current_layout.get("_label_en") or val
                elif key == "tooltip_native":
                    current_layout["_tooltip_native"] = val
                elif key == "tooltip_en":
                    current_layout["_tooltip_en"] = val
            continue
        if key == "layout":
            if current_layout is not None and current_layout.get("id"):
                _flush_layout(current_layout, current_rows, layouts, ui_lang)
            current_layout = {"id": None, "_label_native": "", "_label_en": "",
                             "_tooltip_native": "", "_tooltip_en": ""}
            current_rows = []
            continue
        if key == "row":
            if current_layout is not None:
                try:
                    row_val = next(csv.reader([val]), [val])[0]
                except Exception:
                    row_val = val
                current_rows.append(row_val)
            continue

    if current_layout is not None and current_layout.get("id"):
        _flush_layout(current_layout, current_rows, layouts, ui_lang)

    if not layouts:
        LOG.warning("VirtualKeyboard: no layouts in %s", path)
        return None

    set_data["layouts"] = layouts
    set_data["labels"] = {
        "native": set_data.pop("_label_native", ""),
        "en": set_data.pop("_label_en", ""),
    }
    set_data["tooltips"] = {
        "tooltip_native": set_data.pop("_tooltip_native", ""),
        "tooltip_en": set_data.pop("_tooltip_en", ""),
    }
    return set_data

def _flush_layout(layout_data, rows, layouts, ui_lang):
    lid = layout_data.get("id")
    if not lid:
        return
    lid_lower = lid.lower().replace(" ", "_")
    label_nat = layout_data.get("_label_native", "")
    label_en = layout_data.get("_label_en", label_nat)
    tooltip_nat = layout_data.get("_tooltip_native", "")
    tooltip_en = layout_data.get("_tooltip_en", tooltip_nat)
    label = label_nat if ui_lang != "en" and label_nat else (label_en or lid_lower)
    tooltip = tooltip_nat if ui_lang != "en" and tooltip_nat else (tooltip_en or "")
    if rows:
        rows_ref = rows
    else:
        rows_ref = BUILTIN_LAYOUT_ROWS.get(lid.upper().replace(" ", "_"), "")
    layouts.append((rows_ref, lid_lower, label, tooltip))

def get_effective_layout_sets():
    """
    Merge built-in layout sets with CSV overrides.
    CSV definitions supersede built-in for the same set id (path stem).
    """
    effective = dict(LAYOUT_SETS)
    for set_id, csv_path in get_available_layouts().items():
        loaded = load_layout_csv(csv_path)
        if loaded:
            effective[set_id] = loaded
    return effective

def get_layout_set_id_for_language(lang_code: str) -> str:
    """Map Gramps GUI language to layout set id. Fallback to gb (English)."""
    if not lang_code:
        return "gb"
    lang = (lang_code.split("_")[0] if "_" in lang_code else lang_code)[:2].lower()
    sets = get_effective_layout_sets()
    if lang in sets:
        return lang
    return "gb"

class VirtualKeyboard(Gramplet):
    def init(self):
        self.config = config
        # only set if not already configured
        if not self.config.get("VirtualKeyboard.layout_id"):
            self.config.set("VirtualKeyboard.layout_id", "fr")

        self.buffer = ""
        lang = (glocale.language or ["en"])[0] if glocale.language else "en"
        self.current_layout_set = get_layout_set_id_for_language(lang)

        self.current_layout = None
        self.layout_defs = {}
        self.gui.uistate.connect("filter-changed", self.update)
        self.dbstate.connect("database-changed", self.update)
        self.build_interface()


    def build_interface(self):
        top = self.gui.get_container_widget()

        # Suppress Gramps-injected gramplet tooltip
        def _suppress_tooltip(widget, *args):
            GObject.signal_stop_emission_by_name(widget, "query-tooltip")
            return False

        top.set_has_tooltip(True)
        top.connect("query-tooltip", _suppress_tooltip)

        for child in top.get_children():
            top.remove(child)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox.set_border_width(4)

        # ---- Display ----
        self.display = Gtk.Entry()
        self.display.set_editable(False)
        vbox.pack_start(self.display, False, False, 0)

        # ---- Layout buttons ----
        self.layout_hbox = Gtk.Box(spacing=4)
        vbox.pack_start(self.layout_hbox, False, False, 0)

        # ---- Keyboard body (always exists) ----
        self.keyboard_vbox = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=2
        )
        vbox.pack_start(self.keyboard_vbox, True, True, 0)

        # ---- Bottom control bar ----
        control_hbox = Gtk.Box(spacing=4)
        btns = [
            ("🇬🇧", self.on_flag_clicked, "gb"),
            ("🇫🇷", self.on_flag_clicked, "fr"),
            ("🇩🇪", self.on_flag_clicked, "de"),
            ("⌫", self.on_backspace),
            (_("⌧ Clear"), self.on_clear),
            (_("␣ Space"), self.on_space),
            (_("⇥ Tab"), self.on_tab),
            ("↵", self.on_newline),
            (_("📋 Copy"), self.on_copy_clipboard),
            # (_("⎋ Esc"), self.on_copy_clipboard),
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

        # ---- Initial layout build ----
        self.build_layout_buttons()
        self.select_default_layout()
        if self.current_layout:
            self.set_active_layout(self.current_layout)

        vbox.show_all()
        self.update_flag_buttons()

    def select_default_layout(self):
        sets = get_effective_layout_sets()
        set_def = sets.get(self.current_layout_set, {})
        default_id = set_def.get("default_layout")

        if default_id and default_id in self.layout_defs:
            self.current_layout = default_id
        elif self.layout_defs:
            self.current_layout = next(iter(self.layout_defs))
        else:
            self.current_layout = None

    def build_layout_buttons(self):
        # Clear existing buttons
        for child in self.layout_hbox.get_children():
            self.layout_hbox.remove(child)

        self.layout_buttons = []
        self.layout_defs = {}

        sets = get_effective_layout_sets()
        set_def = sets.get(self.current_layout_set, {})
        layouts = set_def.get("layouts", [])

        set_invalid = False
        resolved_layouts = []

        # ---- Pass 1: validate and resolve ----
        for rows_ref, layout_id, label, tooltip in layouts:
            # structural sanity
            assert isinstance(layout_id, str), "layout_id must be a string"
            assert isinstance(label, str), f"{layout_id}: label must be a string"
            assert tooltip is None or isinstance(
                tooltip, str
            ), f"{layout_id}: tooltip must be a string or None"

            # resolve rows
            if isinstance(rows_ref, str):
                rows = globals().get(rows_ref)
                if rows is None:
                    LOG.warning(
                        "VirtualKeyboard: layout set '%s' invalid: "
                        "layout '%s' references undefined rows '%s'",
                        self.current_layout_set,
                        layout_id,
                        rows_ref,
                    )
                    set_invalid = True
                    continue
            else:
                rows = rows_ref

            if not isinstance(rows, list):
                LOG.warning(
                    "VirtualKeyboard: layout set '%s' invalid: "
                    "layout '%s' rows must be a list",
                    self.current_layout_set,
                    layout_id,
                )
                set_invalid = True
                continue

            resolved_layouts.append((rows, layout_id, label, tooltip))

        # ---- Abort entire set if anything was wrong ----
        if set_invalid:
            LOG.warning(
                "VirtualKeyboard: layout set '%s' is invalid; falling back to 'error keyboard layout'",
                self.current_layout_set,
            )
            self.current_layout_set = "oops"
            return self.build_layout_buttons()

        # ---- Pass 2: build buttons ----
        for rows, layout_id, label, tooltip in resolved_layouts:
            btn = Gtk.ToggleButton(label=label)
            btn.set_tooltip_text(tooltip)
            btn.connect("toggled", self.on_layout_toggled, layout_id)

            self.layout_hbox.pack_start(btn, True, True, 0)
            self.layout_buttons.append((layout_id, btn))
            self.layout_defs[layout_id] = rows

        self.layout_hbox.set_visible(True)
        self.layout_hbox.show_all()
        return True

    def set_active_layout(self, layout_id):
        """Activate a layout button and build its keyboard."""
        if layout_id not in self.layout_defs:
            return

        self.current_layout = layout_id

        for other_id, btn in self.layout_buttons:
            btn.set_active(other_id == layout_id)

        self.build_keyboard(layout_id)


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
                if ch == " ":
                    spacer = Gtk.Box()
                    spacer.set_size_request(10, -1)  # half-key or fixed width
                    spacer.set_has_tooltip(False)
                    hbox.pack_start(spacer, False, False, 0)
                    continue
                btn = Gtk.Button(label=ch)
                btn.set_has_tooltip(False)
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
