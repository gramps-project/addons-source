#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Douglas S. Blank
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

"""Tool window for generating blank fillable PDF forms."""

import os

from gi.repository import Gio, Gtk

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gui.dialog import ErrorDialog, OkDialog
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.plug import tool as Tool

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

from generate_pdf import generate_form_pdf, list_forms, load_form
from generate_pedigree_pdf import generate_pedigree_pdf


# ── Tool ─────────────────────────────────────────────────────────────────────

class GeneratePDFForm(Tool.Tool, ManagedWindow):

    def __init__(self, dbstate, user, options_class, name, callback=None):
        Tool.Tool.__init__(self, dbstate, options_class, name)
        ManagedWindow.__init__(self, user.uistate, [], self.__class__)

        self._opts = self.options.handler.options_dict
        self._build_ui(user.uistate.window)

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self, parent):
        window = Gtk.Dialog(
            title=_("Generate PDF Forms"),
            transient_for=parent,
            destroy_with_parent=True,
        )
        window.set_default_size(480, -1)
        window.set_resizable(False)
        self.set_window(window, None, _("Generate PDF Forms"))

        box = window.get_content_area()
        box.set_spacing(0)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        outer.set_margin_start(12)
        outer.set_margin_end(12)
        box.pack_start(outer, True, True, 0)

        # ── PDF type radio buttons ────────────────────────────────────────
        type_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        self._radio_census = Gtk.RadioButton.new_with_label(None, _("Census / Event Form"))
        self._radio_pedigree = Gtk.RadioButton.new_with_label_from_widget(
            self._radio_census, _("Ahnentafel Pedigree Chart")
        )
        type_box.pack_start(self._radio_census, False, False, 0)
        type_box.pack_start(self._radio_pedigree, False, False, 0)
        outer.pack_start(type_box, False, False, 0)

        outer.pack_start(Gtk.Separator(), False, False, 0)

        # ── Stack: census panel / pedigree panel ──────────────────────────
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.NONE)
        outer.pack_start(self._stack, False, False, 0)

        self._stack.add_named(self._build_census_panel(), "census")
        self._stack.add_named(self._build_pedigree_panel(), "pedigree")

        outer.pack_start(Gtk.Separator(), False, False, 0)

        # ── Output path row ───────────────────────────────────────────────
        path_grid = Gtk.Grid(column_spacing=6, row_spacing=4)
        lbl = Gtk.Label(label=_("Output file:"), xalign=1.0)
        path_grid.attach(lbl, 0, 0, 1, 1)

        self._path_entry = Gtk.Entry()
        self._path_entry.set_hexpand(True)
        self._path_entry.set_text(self._opts.get("last_output", os.path.expanduser("~")))
        path_grid.attach(self._path_entry, 1, 0, 1, 1)

        browse_btn = Gtk.Button(label=_("Browse…"))
        browse_btn.connect("clicked", self._on_browse)
        path_grid.attach(browse_btn, 2, 0, 1, 1)

        outer.pack_start(path_grid, False, False, 0)

        outer.pack_start(Gtk.Separator(), False, False, 0)

        # ── Open after generate checkbox ──────────────────────────────────
        self._open_check = Gtk.CheckButton(label=_("Open PDF after generating"))
        self._open_check.set_active(self._opts.get("open_after", True))
        outer.pack_start(self._open_check, False, False, 0)

        # ── Action buttons ────────────────────────────────────────────────
        btn_box = Gtk.ButtonBox(orientation=Gtk.Orientation.HORIZONTAL)
        btn_box.set_layout(Gtk.ButtonBoxStyle.END)
        btn_box.set_spacing(6)

        close_btn = Gtk.Button(label=_("Close"))
        close_btn.connect("clicked", lambda *_: self.close())
        btn_box.pack_start(close_btn, False, False, 0)

        gen_btn = Gtk.Button(label=_("Generate"))
        gen_btn.get_style_context().add_class("suggested-action")
        gen_btn.connect("clicked", self._on_generate)
        btn_box.pack_start(gen_btn, False, False, 0)

        outer.pack_start(btn_box, False, False, 0)

        # ── Wire up radio toggles ─────────────────────────────────────────
        self._radio_census.connect("toggled", self._on_type_toggled)
        self._radio_pedigree.connect("toggled", self._on_type_toggled)

        # Restore last-used type
        if self._opts.get("last_type", "census") == "pedigree":
            self._radio_pedigree.set_active(True)
        else:
            self._radio_census.set_active(True)

        window.show_all()
        # Must come after show_all() — show_all() recursively shows all stack
        # children, overriding the stack's hidden-child state.
        self._sync_stack()
        self._update_default_path()

    def _build_census_panel(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6)
        grid.set_margin_top(6)
        grid.set_margin_bottom(6)

        lbl = Gtk.Label(label=_("Form:"), xalign=1.0)
        grid.attach(lbl, 0, 0, 1, 1)

        self._form_combo = Gtk.ComboBoxText()
        self._form_ids = []
        saved_id = self._opts.get("last_form_id", "")
        active_idx = 0
        for i, (fid, title) in enumerate(list_forms()):
            self._form_combo.append_text(f"{fid} — {title}")
            self._form_ids.append(fid)
            if fid == saved_id:
                active_idx = i
        self._form_combo.set_active(active_idx)
        self._form_combo.set_hexpand(True)
        self._form_combo.connect("changed", lambda *_: self._update_default_path())
        grid.attach(self._form_combo, 1, 0, 1, 1)

        lbl2 = Gtk.Label(label=_("Rows:"), xalign=1.0)
        grid.attach(lbl2, 0, 1, 1, 1)

        adj = Gtk.Adjustment(
            value=self._opts.get("last_rows", 30),
            lower=1, upper=200, step_increment=1, page_increment=10,
        )
        self._rows_spin = Gtk.SpinButton(adjustment=adj, climb_rate=1, digits=0)
        self._rows_spin.set_halign(Gtk.Align.START)
        grid.attach(self._rows_spin, 1, 1, 1, 1)

        note = Gtk.Label(
            label=_("(Rows only affect multi-row sections such as census household lists.)"),
            xalign=0.0,
        )
        note.get_style_context().add_class("dim-label")
        note.set_line_wrap(True)
        grid.attach(note, 1, 2, 1, 1)

        return grid

    def _build_pedigree_panel(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6)
        grid.set_margin_top(6)
        grid.set_margin_bottom(6)

        lbl = Gtk.Label(label=_("Generations:"), xalign=1.0)
        grid.attach(lbl, 0, 0, 1, 1)

        adj = Gtk.Adjustment(
            value=self._opts.get("last_generations", 4),
            lower=1, upper=5, step_increment=1, page_increment=1,
        )
        self._gen_spin = Gtk.SpinButton(adjustment=adj, climb_rate=1, digits=0)
        self._gen_spin.set_halign(Gtk.Align.START)
        self._gen_spin.connect("value-changed", lambda *_: self._update_default_path())
        grid.attach(self._gen_spin, 1, 0, 1, 1)

        note = Gtk.Label(
            label=_("Includes subject plus up to 5 ancestor generations (2–32 people)."),
            xalign=0.0,
        )
        note.get_style_context().add_class("dim-label")
        note.set_line_wrap(True)
        grid.attach(note, 1, 1, 1, 1)

        return grid

    # ── Signal handlers ───────────────────────────────────────────────────

    def _on_type_toggled(self, btn):
        if btn.get_active():
            self._sync_stack()
            self._update_default_path()

    def _sync_stack(self):
        self._stack.set_visible_child_name(
            "census" if self._radio_census.get_active() else "pedigree"
        )

    def _update_default_path(self):
        """Suggest a sensible output filename based on current selections."""
        current = self._path_entry.get_text()
        # Only auto-update if the current value looks like a previous suggestion
        # (i.e. it's a directory or ends with a .pdf we put there).
        if os.path.isdir(current) or current.endswith(".pdf"):
            directory = current if os.path.isdir(current) else os.path.dirname(current)
            if self._radio_census.get_active():
                idx = self._form_combo.get_active()
                name = (self._form_ids[idx] if idx >= 0 and idx < len(self._form_ids)
                        else "form") + ".pdf"
            else:
                gens = int(self._gen_spin.get_value())
                name = f"Pedigree{gens}.pdf"
            self._path_entry.set_text(os.path.join(directory, name))

    def _on_browse(self, _btn):
        dialog = Gtk.FileChooserDialog(
            title=_("Save PDF as…"),
            transient_for=self.window,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons(
            _("Cancel"), Gtk.ResponseType.CANCEL,
            _("Save"), Gtk.ResponseType.OK,
        )
        dialog.set_do_overwrite_confirmation(True)

        pdf_filter = Gtk.FileFilter()
        pdf_filter.set_name(_("PDF files"))
        pdf_filter.add_pattern("*.pdf")
        dialog.add_filter(pdf_filter)

        current = self._path_entry.get_text()
        if os.path.isdir(current):
            dialog.set_current_folder(current)
        elif current:
            dialog.set_filename(current)

        if dialog.run() == Gtk.ResponseType.OK:
            path = dialog.get_filename()
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            self._path_entry.set_text(path)
        dialog.destroy()

    def _on_generate(self, _btn):
        output = self._path_entry.get_text().strip()
        if not output:
            ErrorDialog(_("No output file"), _("Please specify an output file path."))
            return

        if not output.lower().endswith(".pdf"):
            output += ".pdf"

        try:
            if self._radio_census.get_active():
                idx = self._form_combo.get_active()
                if idx < 0 or idx >= len(self._form_ids):
                    ErrorDialog(_("No form selected"), _("Please select a census form."))
                    return
                form_id = self._form_ids[idx]
                rows = int(self._rows_spin.get_value())
                form = load_form(form_id)
                if form is None:
                    ErrorDialog(_("Form not found"), _(f"Could not load form '{form_id}'."))
                    return
                generate_form_pdf(form, rows, output)
            else:
                gens = int(self._gen_spin.get_value())
                generate_pedigree_pdf(gens, output)
        except Exception as err:
            ErrorDialog(_("Generation failed"), str(err))
            return

        self._save_options(output)

        if self._open_check.get_active():
            try:
                Gio.AppInfo.launch_default_for_uri(f"file://{os.path.abspath(output)}", None)
            except Exception:
                pass

        OkDialog(_("PDF generated"), _(f"Saved to:\n{output}"))

    # ── Persistence ───────────────────────────────────────────────────────

    def _save_options(self, output):
        opts = self._opts
        opts["last_output"] = output
        opts["last_type"] = "census" if self._radio_census.get_active() else "pedigree"
        opts["open_after"] = self._open_check.get_active()
        if self._radio_census.get_active():
            idx = self._form_combo.get_active()
            if 0 <= idx < len(self._form_ids):
                opts["last_form_id"] = self._form_ids[idx]
            opts["last_rows"] = int(self._rows_spin.get_value())
        else:
            opts["last_generations"] = int(self._gen_spin.get_value())
        self.options.handler.save_options()


# ── Options ───────────────────────────────────────────────────────────────────

class GeneratePDFFormOptions(Tool.ToolOptions):

    def __init__(self, name, person_id=None):
        Tool.ToolOptions.__init__(self, name, person_id)
        self.set_new_options()

    def set_new_options(self):
        self.options_dict = {
            "last_type":        "census",
            "last_form_id":     "",
            "last_rows":        30,
            "last_generations": 4,
            "last_output":      os.path.expanduser("~"),
            "open_after":       True,
        }
        self.options_help = {
            "last_type":        ("=str", "Last PDF type selected (census/pedigree)", "string"),
            "last_form_id":     ("=str", "Last census form ID used", "string"),
            "last_rows":        ("=int", "Last row count for multi sections", "integer"),
            "last_generations": ("=int", "Last generation count for pedigree", "integer"),
            "last_output":      ("=str", "Last output file path", "string"),
            "open_after":       ("=bool", "Open PDF after generating", "boolean"),
        }
