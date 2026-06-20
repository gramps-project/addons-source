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
Audit Tab UI component for the Names Tool.
Contains all GTK widgets, layout structures, and column definitions for the audit tab.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gi.repository import Gtk

from gramps.gen.const import GRAMPS_LOCALE as glocale

from name_processor.models.audit import AuditIssue, AuditScope
from name_processor.presentation.markup import format_confidence, generate_pango_diff
from name_processor.presentation.row_schemas import AuditRowData
from name_processor.views.base_tab import BaseTab

if TYPE_CHECKING:
    from gi.repository.Gtk import Window
    from name_processor.controllers.tool import ToolController


_ = glocale.translation.gettext


class AuditTab(BaseTab):
    """
    GTK Audit Tab component. Manages the audit patronymics tab UI.
    All business logic is delegated to the controller.
    """

    def __init__(self, parent_window: Window, controller: ToolController) -> None:
        """
        Initialize the AuditTab.

        Args:
            parent_window: The parent GTK window for dialog references
            controller: The tool controller for business logic calls
        """
        super().__init__(parent_window, controller)

        # Local view state (UI specific)
        self.enabled_rules: dict[str, bool] = {}
        self.audit_issues: list[AuditIssue] = []

        # Widget properties (initialized in build())
        self.scope_combo: Gtk.ComboBoxText
        self.rules_btn: Gtk.Button
        self.pre_reform_check: Gtk.CheckButton
        self.run_btn: Gtk.Button
        self.progress: Gtk.ProgressBar

    def build(self) -> Gtk.Widget:
        """
        Build and return the audit tab UI widget.

        Returns:
            Gtk.Box: The audit tab container widget
        """
        audit_tab_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        audit_tab_box.set_border_width(8)

        audit_header_frame = Gtk.Frame(label=_("Auditing Settings"))
        audit_tab_box.pack_start(audit_header_frame, False, False, 0)

        audit_header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        audit_header_box.set_border_width(8)
        audit_header_frame.add(audit_header_box)

        self.scope_combo = Gtk.ComboBoxText()
        self.scope_combo.append_text(_("All Records"))
        self.scope_combo.append_text(_("Males Only"))
        self.scope_combo.append_text(_("Females Only"))
        self.scope_combo.set_active(0)
        audit_header_box.pack_start(self.scope_combo, False, False, 0)

        self.rules_btn = Gtk.Button(label=_("Configure Rules..."))
        self.rules_btn.connect("clicked", self.on_configure_rules_clicked)
        audit_header_box.pack_start(self.rules_btn, False, False, 0)

        self.pre_reform_check = Gtk.CheckButton(
            label=_("Match Pre-Revolutionary Orthography")
        )
        self.pre_reform_check.set_active(False)
        audit_header_box.pack_start(self.pre_reform_check, False, False, 0)

        audit_action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        audit_tab_box.pack_start(audit_action_box, False, False, 0)

        self.run_btn = Gtk.Button(label=_("Audit Database"))
        self.run_btn.connect("clicked", self.on_run_clicked)
        audit_action_box.pack_start(self.run_btn, False, False, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        audit_action_box.pack_start(self.progress, True, True, 0)

        audit_scroll = Gtk.ScrolledWindow()
        audit_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        audit_tab_box.pack_start(audit_scroll, True, True, 0)

        self.store = Gtk.ListStore(
            bool, str, str, str, str, str, str, str, str, str, str, str
        )
        self.tree = Gtk.TreeView(model=self.store)
        audit_scroll.add(self.tree)
        self.setup_columns()

        audit_footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        audit_tab_box.pack_start(audit_footer_box, False, False, 0)

        self.select_all = Gtk.CheckButton(label=_("Select All Safe Corrections"))
        self.select_all.set_active(True)
        self.select_all.connect("toggled", self.on_select_all_toggled)
        audit_footer_box.pack_start(self.select_all, False, False, 0)

        self.apply_btn = Gtk.Button(label=_("Apply Selected Corrections"))
        self.apply_btn.set_sensitive(False)
        self.apply_btn.connect("clicked", self.on_apply_clicked)
        audit_footer_box.pack_end(self.apply_btn, False, False, 0)
        self.tree.connect("row-activated", self.on_row_activated)
        return audit_tab_box

    # --- Event Handlers ---
    def on_run_clicked(self, widget: Any) -> None:
        self.run_btn.set_sensitive(False)
        scope_idx = self.scope_combo.get_active()
        audit_scope = {
            0: AuditScope.ALL,
            1: AuditScope.MALES_ONLY,
            2: AuditScope.FEMALES_ONLY,
        }.get(scope_idx, AuditScope.ALL)
        use_pre_reform = self.pre_reform_check.get_active()
        enabled_rules_set = {
            r_id for r_id, enabled in self.enabled_rules.items() if enabled
        }
        self.controller.run_audit_scan(audit_scope, enabled_rules_set, use_pre_reform)

    def on_apply_clicked(self, widget: Any) -> None:
        use_pre_reform = self.pre_reform_check.get_active()
        if self.controller.apply_checked_audit_fixes(use_pre_reform):
            self.clear_results()
            self.update_apply_button()

    def on_row_toggled(self, widget: Any, path: str) -> None:
        """Override to add select_all checkbox sync logic."""
        chk_idx = AuditRowData._fields.index("checkbox")
        self.store[path][chk_idx] = not self.store[path][chk_idx]
        self.update_apply_button()
        all_selected = all(row[chk_idx] for row in self.store)
        self.select_all.handler_block_by_func(self.on_select_all_toggled)
        self.select_all.set_active(all_selected)
        self.select_all.handler_unblock_by_func(self.on_select_all_toggled)

    def on_configure_rules_clicked(self, widget: Any) -> None:
        dialog = Gtk.Dialog(
            title=_("Configure Rules"),
            parent=self.parent_window,
            flags=Gtk.DialogFlags.MODAL,
        )
        dialog.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        dialog.get_content_area().add(vbox)
        checks = {}
        for rule_id in self.controller.get_available_audit_rules():
            chk = Gtk.CheckButton(label=rule_id)
            chk.set_active(self.enabled_rules[rule_id])
            vbox.pack_start(chk, False, False, 0)
            checks[rule_id] = chk
        dialog.show_all()
        if dialog.run() == Gtk.ResponseType.OK:
            for r_id, chk in checks.items():
                self.enabled_rules[r_id] = chk.get_active()
        dialog.destroy()

    # --- Column Setup ---
    def setup_columns(self) -> None:
        self._add_checkbox_column(AuditRowData, self.on_row_toggled)
        self._add_text_column(_("ID"), "gramps_id", AuditRowData)
        self._add_text_column(
            _("Individual"), "display_name", AuditRowData, expand=True
        )
        self._add_text_column(_("Father"), "father_name", AuditRowData, expand=True)
        self._add_text_column(
            _("Current"), "current_patronymic", AuditRowData, expand=True
        )
        self._add_text_column(
            _("Correction"),
            "diff_markup",
            AuditRowData,
            expand=True,
            use_markup=True,
            sort_field="suggested_string",
        )
        self._add_text_column(_("Conf"), "confidence", AuditRowData)
        self._add_text_column(_("Ref Year"), "ref_year", AuditRowData)
        self._add_text_column(_("Rule"), "rule_id", AuditRowData)
        self._add_text_column(
            _("Explanation"), "explanation", AuditRowData, expand=True
        )

    # --- Port Methods (Controller → View) ---
    def clear_results(self) -> None:
        self.store.clear()
        self.audit_issues = []

    def get_result_count(self) -> int:
        return len(self.audit_issues)

    def append_issue(self, issue: AuditIssue) -> None:
        diff_markup = generate_pango_diff(issue.current_value, issue.suggested_fix)
        confidence_str = format_confidence(getattr(issue, "confidence", 0))
        row = AuditRowData(
            checkbox=True,
            display_name=issue.display_name,
            gramps_id=issue.gramps_id,
            father_name=issue.father_name or "",
            current_patronymic=issue.current_value,
            diff_markup=diff_markup,
            confidence=confidence_str,
            ref_year=issue.reference_year,
            rule_id=issue.rule_id,
            handle=issue.person_handle,
            suggested_string=issue.suggested_fix,
            explanation=issue.explanation,
        )
        self.store.append(list(row))
        self.audit_issues.append(issue)

    def update_progress(self, fraction: float, text: str) -> None:
        self.progress.set_fraction(fraction)
        self.progress.set_text(text)

    def on_complete(self, total_found: int) -> None:
        from gramps.gui.dialog import OkDialog

        self.progress.set_fraction(1.0)
        self.progress.set_text(_("Audit Complete!"))
        self.run_btn.set_sensitive(True)
        self.select_all.set_active(True)
        self.update_apply_button()
        if total_found == 0:
            OkDialog(_("No Results"), _("No issues found."), self.parent_window)

    def get_row_data_type(self) -> type[AuditRowData]:
        """Return the RowData type for this tab."""
        return AuditRowData

    def get_checked_keys(self) -> set[tuple[str, str]]:
        chk_idx = AuditRowData._fields.index("checkbox")
        h_idx = AuditRowData._fields.index("handle")
        r_idx = AuditRowData._fields.index("rule_id")
        return {(row[h_idx], row[r_idx]) for row in self.store if row[chk_idx]}

    def get_enabled_rules(self) -> set[str]:
        return {r_id for r_id, enabled in self.enabled_rules.items() if enabled}
