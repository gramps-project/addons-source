#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Dmitry Bryndin
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

"""
Rename Tab UI component for the Names Tool.
Contains all GTK widgets, layout structures, and column definitions for the rename tab.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gi.repository import Gtk

from gramps.gen.const import GRAMPS_LOCALE as glocale

from name_processor.models.renamer import AltAction, MatchMode
from name_processor.presentation.row_schemas import GivenRowData
from name_processor.views.base_tab import BaseTab

if TYPE_CHECKING:
    from gi.repository.Gtk import Window
    from name_processor.controllers.tool import ToolController


try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


class RenameTab(BaseTab):
    """
    GTK Rename Tab component. Manages the rename given names tab UI.
    All business logic is delegated to the controller.
    """

    def __init__(self, parent_window: Window, controller: ToolController) -> None:
        """
        Initialize the RenameTab.

        Args:
            parent_window: The parent GTK window for dialog references
            controller: The tool controller for business logic calls
        """
        super().__init__(parent_window, controller)

        # Widget properties (initialized in build())
        self.source_entry: Gtk.Entry
        self.target_entry: Gtk.Entry
        self.match_combo: Gtk.ComboBoxText
        self.scan_btn: Gtk.Button
        self.preserve_check: Gtk.CheckButton

    def build(self) -> Gtk.Widget:
        """
        Build and return the rename tab UI widget.

        Returns:
            Gtk.Box: The rename tab container widget
        """
        given_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        given_box.set_border_width(8)

        given_config_frame = Gtk.Frame(label=_("Search and Replace Options"))
        given_box.pack_start(given_config_frame, False, False, 0)

        given_config_grid = Gtk.Grid(column_spacing=10, row_spacing=10)
        given_config_grid.set_border_width(8)
        given_config_frame.add(given_config_grid)

        given_config_grid.attach(Gtk.Label(label=_("Source Name:")), 0, 0, 1, 1)
        self.source_entry = Gtk.Entry()
        self.source_entry.set_placeholder_text(_("e.g. Иоанн"))
        given_config_grid.attach(self.source_entry, 1, 0, 1, 1)

        given_config_grid.attach(Gtk.Label(label=_("Target Name:")), 0, 1, 1, 1)
        self.target_entry = Gtk.Entry()
        self.target_entry.set_placeholder_text(_("e.g. Иван"))
        given_config_grid.attach(self.target_entry, 1, 1, 1, 1)

        given_config_grid.attach(Gtk.Label(label=_("Match Mode:")), 2, 0, 1, 1)
        self.match_combo = Gtk.ComboBoxText()
        self.match_combo.append_text(_("Exact Match"))
        self.match_combo.append_text(_("Substring"))
        self.match_combo.append_text(_("Regular Expression"))
        self.match_combo.set_active(0)
        given_config_grid.attach(self.match_combo, 3, 0, 1, 1)

        self.scan_btn = Gtk.Button(label=_("Scan for Names"))
        self.scan_btn.connect("clicked", self.on_scan_clicked)
        given_config_grid.attach(self.scan_btn, 3, 1, 1, 1)

        self.preserve_check = Gtk.CheckButton(
            label=_("Preserve original name as alternative")
        )
        self.preserve_check.set_active(True)
        self.preserve_check.connect("toggled", self.on_preserve_toggled)
        given_box.pack_start(self.preserve_check, False, False, 0)

        given_scroll_win = Gtk.ScrolledWindow()
        given_scroll_win.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        given_box.pack_start(given_scroll_win, True, True, 0)

        self.store = Gtk.ListStore(bool, str, str, str, str, str, str)
        self.tree = Gtk.TreeView(model=self.store)
        given_scroll_win.add(self.tree)
        self.setup_columns()

        given_footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        given_box.pack_start(given_footer_box, False, False, 0)

        self.select_all = Gtk.CheckButton(label=_("Select All"))
        self.select_all.set_active(True)
        self.select_all.connect("toggled", self.on_select_all_toggled)
        given_footer_box.pack_start(self.select_all, False, False, 0)

        self.apply_btn = Gtk.Button(label=_("Apply Selected Corrections"))
        self.apply_btn.set_sensitive(False)
        self.apply_btn.connect("clicked", self.on_apply_clicked)
        given_footer_box.pack_end(self.apply_btn, False, False, 0)

        self.tree.connect("row-activated", self.on_row_activated)
        return given_box

    # --- Event Handlers ---

    def on_scan_clicked(self, widget: Any) -> None:
        if not self.controller:
            return
        source = self.source_entry.get_text().strip()
        target = self.target_entry.get_text().strip()
        match_mode = {
            0: MatchMode.EXACT,
            1: MatchMode.SUBSTRING,
            2: MatchMode.REGEX,
        }.get(self.match_combo.get_active(), MatchMode.EXACT)
        self.controller.on_rename_scan_requested(source, target, match_mode)
        self.update_apply_button()

    def on_apply_clicked(self, widget: Any) -> None:
        if self.controller.apply_checked_renamings():
            self.store.clear()
            self.update_apply_button()

    def on_preserve_toggled(self, widget: Gtk.CheckButton) -> None:
        if self.controller:
            self.controller.update_preserve_alt(
                AltAction.PRESERVE if widget.get_active() else AltAction.OVERWRITE
            )

    # --- Column Setup ---
    def setup_columns(self) -> None:
        """Setup treeview columns for the rename tab."""
        self._add_checkbox_column(GivenRowData, self.on_row_toggled)
        self._add_text_column(_("ID"), "gramps_id", GivenRowData)
        self._add_text_column(
            _("Individual"), "display_name", GivenRowData, expand=True
        )
        self._add_text_column(_("Current"), "current", GivenRowData, expand=True)
        self._add_text_column(
            _("Proposed"), "proposed", GivenRowData, expand=True, use_markup=True
        )
        self._add_text_column(_("Action"), "alt_action", GivenRowData)

    # --- Port Methods (Controller → View) ---

    def setup_autocompletion(self) -> None:
        given_names_set = self.controller.get_given_names()
        if not given_names_set:
            return
        completion_store = Gtk.ListStore(str)
        for name in sorted(given_names_set):
            completion_store.append([name])
        completion = Gtk.EntryCompletion()
        completion.set_model(completion_store)
        completion.set_text_column(0)
        completion.set_minimum_key_length(1)
        completion.set_inline_completion(True)
        completion.set_inline_selection(True)
        self.source_entry.set_completion(completion)

    def clear_proposals(self) -> None:
        self.store.clear()

    def append_proposal(self, row_data: GivenRowData) -> None:
        row_list = list(row_data)
        act_idx = GivenRowData._fields.index("alt_action")
        row_list[act_idx] = _(row_data.alt_action.value)
        self.store.append(row_list)

    def update_actions(self, new_action: AltAction) -> None:
        act_idx = GivenRowData._fields.index("alt_action")
        translated = _(new_action.value)
        for row in self.store:
            row[act_idx] = translated

    def get_row_data_type(self) -> type[GivenRowData]:
        """Return the RowData type for this tab."""
        return GivenRowData

    def get_checked_handles(self) -> set[str]:
        chk_idx = GivenRowData._fields.index("checkbox")
        h_idx = GivenRowData._fields.index("handle")
        return {row[h_idx] for row in self.store if row[chk_idx]}

    def is_preserve_enabled(self) -> bool:
        return self.preserve_check.get_active()
