# -*- coding: utf-8 -*-
"""
GTK Window layout for the Names Tool batch processing interface.
Contains all GTK widgets, layout structures, and column definitions.
"""

import logging
import re
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from gi.repository import Gtk
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gui.dialog import OkDialog
from gramps.gui.editors import EditPerson
from gramps.gen.errors import WindowActiveError

from name_processor.models.audit import AuditScope
from name_processor.models.renamer import MatchMode

if TYPE_CHECKING:
    from name_processor.controllers.tool import ToolController
    from name_processor.models.audit import AuditIssue
    from name_processor.models.renamer import ProposedRename

logger = logging.getLogger(__name__)

_ = glocale.translation.gettext


class MatchModeIndex(Enum):
    """Combo box index positions for match mode options."""

    EXACT = 0
    SUBSTRING = 1
    REGEX = 2


class MatchModeLabel(Enum):
    """UI labels for match mode combo box."""

    EXACT = "Exact Match"
    SUBSTRING = "Substring"
    REGEX = "Regular Expression"


def pango_escape(text: str) -> str:
    """Escapes XML special characters to prevent GTK Pango parsing crashes."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generate_pango_diff(old_str: str, new_str: str) -> str:
    """
    Generates a simple before/after diff in Pango markup.
    Format: <current> -> <suggested>
    Example: Иванович -> Ивановна
    """
    old_esc = pango_escape(old_str)
    new_esc = pango_escape(new_str)

    if not old_esc and not new_esc:
        return ""
    if not old_esc:
        return f"<span weight='bold'>{new_esc}</span>"
    if not new_esc:
        return f"{old_esc}"

    return f"{old_esc} → <span weight='bold'>{new_esc}</span>"


class ToolWindow:
    """
    GTK Batch Processing Window. Acts as a Passive View in the MVP/MVCS pattern.
    All business logic and long-running tasks are delegated to the controller.
    """

    # Given Names store column indices (Tab 1 - Rename Given Names)
    GIVEN_COL_CHECKBOX = 0
    GIVEN_COL_GRAMPS_ID = 1
    GIVEN_COL_DISPLAY_NAME = 2
    GIVEN_COL_CURRENT = 3
    GIVEN_COL_PROPOSED = 4
    GIVEN_COL_ALT_ACTION = 5
    GIVEN_COL_HANDLE = 6
    GIVEN_COL_PROPOSED_RAW = 7

    # Audit store column indices (Tab 2 - Audit Patronymics)
    AUDIT_COL_CHECKBOX = 0
    AUDIT_COL_DISPLAY_NAME = 1
    AUDIT_COL_GRAMPS_ID = 2
    AUDIT_COL_FATHER_NAME = 3
    AUDIT_COL_CURRENT_PAT = 4
    AUDIT_COL_DIFF_MARKUP = 5
    AUDIT_COL_CONFIDENCE = 6
    AUDIT_COL_REF_YEAR = 7
    AUDIT_COL_RULE_ID = 8
    AUDIT_COL_HANDLE = 9
    AUDIT_COL_RULE_ID_DUP = 10
    AUDIT_COL_SUGGESTED_STRING = 11
    AUDIT_COL_EXPLANATION = 12

    def __init__(self, callback: Callable[[], None] | None = None) -> None:
        """Initializes the GTK Window."""
        self.callback = callback
        self.controller: "ToolController" | None = None

        # Local view state (UI specific)
        self.enabled_rules: dict[str, bool] = {}
        self.audit_issues: list["AuditIssue"] = []

        # Build GTK Window UI
        self.build_window()

    def set_controller(self, controller: "ToolController") -> None:
        """Sets the controller instance and runs initial loads."""
        self.controller = controller
        self.enabled_rules = {
            rule_id: True for rule_id in self.controller.get_available_audit_rules()
        }
        # Set up autocompletion for given name entry
        self.setup_given_name_autocompletion()
        # Run background calculations and fetch historical logs on display
        try:
            self.controller.initialize_median_year_async()
        except Exception as e:
            logger.error(f"Error initializing median year: {e}")
            raise
        try:
            self.controller.initialize_given_names_async()
        except Exception as e:
            logger.error(f"Error initializing given names: {e}")
            raise

    def setup_given_name_autocompletion(self) -> None:
        """Sets up autocompletion for the given source name entry using DB names."""
        given_names_set = self.controller.get_given_names()
        if not given_names_set:
            return

        # Create a list store with a single string column
        completion_store = Gtk.ListStore(str)
        for name in sorted(given_names_set):
            completion_store.append([name])

        # Create entry completion
        completion = Gtk.EntryCompletion()
        completion.set_model(completion_store)
        completion.set_text_column(0)
        completion.set_minimum_key_length(1)
        completion.set_inline_completion(True)
        completion.set_inline_selection(True)

        # Attach completion to the entry
        self.given_source_entry.set_completion(completion)

    def build_window(self) -> None:
        self.window = Gtk.Window(title=_("Infer East Slavic Patronymics"))
        self.window.set_default_size(900, 600)
        self.window.set_position(Gtk.WindowPosition.CENTER)
        self.window.set_border_width(12)

        self.window.connect("destroy", self.on_destroy)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.window.add(main_box)

        notebook = Gtk.Notebook()
        main_box.pack_start(notebook, True, True, 0)

        # --- TAB 0: Given Names (Rename Given Names) ---
        given_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        given_box.set_border_width(8)
        notebook.append_page(given_box, Gtk.Label(label=_("Rename Given Names")))

        given_config_frame = Gtk.Frame(label=_("Search and Replace Options"))
        given_box.pack_start(given_config_frame, False, False, 0)

        given_config_grid = Gtk.Grid(column_spacing=10, row_spacing=10)
        given_config_grid.set_border_width(8)
        given_config_frame.add(given_config_grid)

        given_config_grid.attach(Gtk.Label(label=_("Source Name:")), 0, 0, 1, 1)
        self.given_source_entry = Gtk.Entry()
        self.given_source_entry.set_placeholder_text(_("e.g. Иоанн"))
        given_config_grid.attach(self.given_source_entry, 1, 0, 1, 1)

        given_config_grid.attach(Gtk.Label(label=_("Target Name:")), 0, 1, 1, 1)
        self.given_target_entry = Gtk.Entry()
        self.given_target_entry.set_placeholder_text(_("e.g. Иван"))
        given_config_grid.attach(self.given_target_entry, 1, 1, 1, 1)

        given_config_grid.attach(Gtk.Label(label=_("Match Mode:")), 2, 0, 1, 1)
        self.given_match_type_combo = Gtk.ComboBoxText()
        self.given_match_type_combo.append_text(_(MatchModeLabel.EXACT.value))
        self.given_match_type_combo.append_text(_(MatchModeLabel.SUBSTRING.value))
        self.given_match_type_combo.append_text(_(MatchModeLabel.REGEX.value))
        self.given_match_type_combo.set_active(MatchModeIndex.EXACT.value)
        given_config_grid.attach(self.given_match_type_combo, 3, 0, 1, 1)

        self.given_scan_btn = Gtk.Button(label=_("Scan for Names"))
        self.given_scan_btn.connect("clicked", self.on_given_scan_clicked)
        given_config_grid.attach(self.given_scan_btn, 3, 1, 1, 1)

        self.preserve_alt_check = Gtk.CheckButton(
            label=_("Preserve original name as alternative")
        )
        self.preserve_alt_check.set_active(True)
        self.preserve_alt_check.connect("toggled", self.on_preserve_alt_toggled)
        given_box.pack_start(self.preserve_alt_check, False, False, 0)

        given_scroll_win = Gtk.ScrolledWindow()
        given_scroll_win.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        given_box.pack_start(given_scroll_win, True, True, 0)

        self.given_store = Gtk.ListStore(bool, str, str, str, str, str, str, str)
        self.given_tree = Gtk.TreeView(model=self.given_store)
        given_scroll_win.add(self.given_tree)
        self.setup_given_names_rename_columns()

        given_footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        given_box.pack_start(given_footer_box, False, False, 0)

        self.given_select_all = Gtk.CheckButton(label=_("Select All"))
        self.given_select_all.set_active(True)
        self.given_select_all.connect("toggled", self.on_given_select_all_toggled)
        given_footer_box.pack_start(self.given_select_all, False, False, 0)

        self.given_apply_btn = Gtk.Button(label=_("Apply Selected Corrections"))
        self.given_apply_btn.set_sensitive(False)
        self.given_apply_btn.connect("clicked", self.on_given_apply_clicked)
        given_footer_box.pack_end(self.given_apply_btn, False, False, 0)

        # --- TAB 1: Database Auditor (The Linter) ---
        audit_tab_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        audit_tab_box.set_border_width(8)
        notebook.append_page(audit_tab_box, Gtk.Label(label=_("Audit Patronymics")))

        audit_header_frame = Gtk.Frame(label=_("Auditing Settings"))
        audit_tab_box.pack_start(audit_header_frame, False, False, 0)

        audit_header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        audit_header_box.set_border_width(8)
        audit_header_frame.add(audit_header_box)

        self.audit_scope_combo = Gtk.ComboBoxText()
        self.audit_scope_combo.append_text(_("All Records"))
        self.audit_scope_combo.append_text(_("Males Only"))
        self.audit_scope_combo.append_text(_("Females Only"))
        self.audit_scope_combo.set_active(0)
        audit_header_box.pack_start(self.audit_scope_combo, False, False, 0)

        self.rules_config_btn = Gtk.Button(label=_("Configure Rules..."))
        self.rules_config_btn.connect("clicked", self.on_configure_rules_clicked)
        audit_header_box.pack_start(self.rules_config_btn, False, False, 0)

        self.audit_pre_reform_check = Gtk.CheckButton(
            label=_("Match Pre-Revolutionary Orthography")
        )
        self.audit_pre_reform_check.set_active(False)
        audit_header_box.pack_start(self.audit_pre_reform_check, False, False, 0)

        audit_action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        audit_tab_box.pack_start(audit_action_box, False, False, 0)

        self.audit_run_btn = Gtk.Button(label=_("Audit Database"))
        self.audit_run_btn.connect("clicked", self.on_audit_run_clicked)
        audit_action_box.pack_start(self.audit_run_btn, False, False, 0)

        self.audit_progress = Gtk.ProgressBar()
        self.audit_progress.set_show_text(True)
        audit_action_box.pack_start(self.audit_progress, True, True, 0)

        audit_scroll = Gtk.ScrolledWindow()
        audit_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        audit_tab_box.pack_start(audit_scroll, True, True, 0)

        self.audit_store = Gtk.ListStore(
            bool, str, str, str, str, str, str, str, str, str, str, str, str
        )
        self.audit_tree = Gtk.TreeView(model=self.audit_store)
        audit_scroll.add(self.audit_tree)
        self.setup_audit_columns()

        audit_footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        audit_tab_box.pack_start(audit_footer_box, False, False, 0)

        self.audit_select_all = Gtk.CheckButton(label=_("Select All Safe Corrections"))
        self.audit_select_all.set_active(True)
        self.audit_select_all.connect("toggled", self.on_audit_select_all_toggled)
        audit_footer_box.pack_start(self.audit_select_all, False, False, 0)

        self.audit_apply_btn = Gtk.Button(label=_("Apply Selected Corrections"))
        self.audit_apply_btn.set_sensitive(False)
        self.audit_apply_btn.connect("clicked", self.on_audit_apply_clicked)
        audit_footer_box.pack_end(self.audit_apply_btn, False, False, 0)

        # --- Double-Click Row Activation Connections ---
        self.audit_tree.connect("row-activated", self.on_audit_row_activated)
        self.given_tree.connect("row-activated", self.on_given_row_activated)

        self.window.show_all()

    def on_destroy(self, widget: Any) -> None:
        if self.controller:
            self.controller.cleanup()
        if self.callback:
            self.callback()

    # --- Scanning & Processing Callbacks ---

    def on_given_scan_clicked(self, widget: Any) -> None:
        source = self.given_source_entry.get_text().strip()
        target = self.given_target_entry.get_text().strip()
        match_type = self.given_match_type_combo.get_active()

        mode_map = {
            MatchModeIndex.EXACT.value: MatchMode.EXACT,
            MatchModeIndex.SUBSTRING.value: MatchMode.SUBSTRING,
            MatchModeIndex.REGEX.value: MatchMode.REGEX,
        }
        match_mode = mode_map.get(match_type, None)

        # Validate source input
        if not source:
            self.show_ok_dialog(_("Invalid Input"), _("Source name cannot be empty."))
            return

        # Validate regex pattern when Regular Expression match mode is selected
        if match_mode == MatchMode.REGEX:
            try:
                re.compile(source)
            except re.error:
                self.show_ok_dialog(
                    _("Invalid Input"),
                    _("Invalid regular expression pattern in source name."),
                )
                return

        # Validate target input for non-empty when provided
        if target and not target.strip():
            self.show_ok_dialog(
                _("Invalid Input"), _("Target name cannot contain only whitespace.")
            )
            return

        has_results = self.controller.run_rename_scan(source, target, match_mode)
        self.update_given_apply_button()
        if not has_results:
            self.show_ok_dialog(_("No Results"), _("No matching given names found."))

    def on_given_apply_clicked(self, widget: Any) -> None:
        if self.controller.apply_checked_renamings():
            self.given_store.clear()
            self.update_given_apply_button()

    def on_audit_run_clicked(self, widget: Any) -> None:
        self.audit_run_btn.set_sensitive(False)
        scope_idx = self.audit_scope_combo.get_active()

        # Explicit mapping from UI index to Enum
        scope_map = {
            0: AuditScope.ALL,
            1: AuditScope.MALES_ONLY,
            2: AuditScope.FEMALES_ONLY,
        }
        audit_scope = scope_map.get(scope_idx, AuditScope.ALL)

        use_pre_reform = self.audit_pre_reform_check.get_active()
        enabled_rules_set = {
            r_id for r_id, enabled in self.enabled_rules.items() if enabled
        }
        self.controller.run_audit_scan(audit_scope, enabled_rules_set, use_pre_reform)

    def on_audit_apply_clicked(self, widget: Any) -> None:
        use_pre_reform = self.audit_pre_reform_check.get_active()
        if self.controller.apply_checked_audit_fixes(use_pre_reform):
            self.clear_audit_results()
            self.update_audit_apply_button()

    # --- Auditor Utilities ---

    def clear_audit_results(self) -> None:
        self.audit_store.clear()
        self.audit_issues = []

    def _append_issue_to_store(self, issue: Any) -> None:
        """Append an audit issue to the treeview store with Pango markup formatting."""
        diff_markup = generate_pango_diff(issue.current_value, issue.suggested_fix)

        confidence_str = f"{int(getattr(issue, 'confidence', 0) * 100)}%"  # Placeholder

        # TODO: create a mapping from AuditIssue to treeview columns
        self.audit_store.append(
            [
                True,  # AUDIT_COL_CHECKBOX
                issue.display_name,  # AUDIT_COL_DISPLAY_NAME
                issue.gramps_id,  # AUDIT_COL_GRAMPS_ID
                issue.father_name,  # AUDIT_COL_FATHER_NAME
                issue.current_value,  # AUDIT_COL_CURRENT_PAT
                diff_markup,  # AUDIT_COL_DIFF_MARKUP
                confidence_str,  # AUDIT_COL_CONFIDENCE
                issue.reference_year,  # AUDIT_COL_REF_YEAR
                issue.rule_id,  # AUDIT_COL_RULE_ID
                issue.person_handle,  # AUDIT_COL_HANDLE
                issue.rule_id,  # AUDIT_COL_RULE_ID_DUP
                issue.suggested_fix,  # AUDIT_COL_SUGGESTED_STRING
                issue.explanation,  # AUDIT_COL_EXPLANATION
            ]
        )

    def _append_rename_proposal_to_store(
        self, prop: "ProposedRename", match_mode: MatchMode
    ) -> None:
        """Append a given name rename proposal to the given store."""
        # For substring and regex modes, highlight only the matched portion
        if match_mode in (MatchMode.SUBSTRING, MatchMode.REGEX) and prop.matched_text:
            proposed_esc = pango_escape(prop.proposed_given_name)
            matched_esc = pango_escape(prop.matched_text)
            # Replace the matched portion with highlighted version
            markup = proposed_esc.replace(
                matched_esc,
                f'<span weight="bold">{matched_esc}</span>',
            )
        else:
            # For exact match, highlight the entire proposed name
            markup = (
                f'<span weight="bold">{pango_escape(prop.proposed_given_name)}</span>'
            )

        self.given_store.append(
            [
                True,  # GIVEN_COL_CHECKBOX
                prop.gramps_id,  # GIVEN_COL_GRAMPS_ID
                prop.display_name,  # GIVEN_COL_DISPLAY_NAME
                prop.original_given_name,  # GIVEN_COL_CURRENT
                markup,  # GIVEN_COL_PROPOSED
                _(prop.alt_action),  # GIVEN_COL_ALT_ACTION
                prop.handle,  # GIVEN_COL_HANDLE
                prop.proposed_given_name,  # GIVEN_COL_PROPOSED_RAW
            ]
        )

    def update_audit_progress(self, fraction: float, text: str) -> None:
        self.audit_progress.set_fraction(fraction)
        self.audit_progress.set_text(text)

    def on_audit_complete(self, total_found: int) -> None:
        self.audit_progress.set_fraction(1.0)
        self.audit_progress.set_text(_("Audit Complete!"))
        self.audit_run_btn.set_sensitive(True)
        self.audit_select_all.set_active(True)
        self.update_audit_apply_button()
        if total_found == 0:
            self.show_ok_dialog(_("No Results"), _("No issues found."))

    def update_given_apply_button(self) -> None:
        has_checked = any(row[self.GIVEN_COL_CHECKBOX] for row in self.given_store)
        self.given_apply_btn.set_sensitive(has_checked)

    def update_audit_apply_button(self) -> None:
        has_checked = any(row[self.AUDIT_COL_CHECKBOX] for row in self.audit_store)
        self.audit_apply_btn.set_sensitive(has_checked)

    # --- Column Setup Methods ---

    def setup_given_names_rename_columns(self) -> None:
        renderer_toggle = Gtk.CellRendererToggle()
        renderer_toggle.connect("toggled", self.on_given_row_toggled)
        self.given_tree.append_column(
            Gtk.TreeViewColumn(
                _("Use"), renderer_toggle, active=self.GIVEN_COL_CHECKBOX
            )
        )
        col = Gtk.TreeViewColumn(
            _("ID"), Gtk.CellRendererText(), text=self.GIVEN_COL_GRAMPS_ID
        )
        col.set_sort_column_id(self.GIVEN_COL_GRAMPS_ID)
        self.given_tree.append_column(col)

        individual_col = Gtk.TreeViewColumn(
            _("Individual"), Gtk.CellRendererText(), text=self.GIVEN_COL_DISPLAY_NAME
        )
        individual_col.set_expand(True)
        individual_col.set_sort_column_id(self.GIVEN_COL_DISPLAY_NAME)
        self.given_tree.append_column(individual_col)

        current_col = Gtk.TreeViewColumn(
            _("Current"), Gtk.CellRendererText(), text=self.GIVEN_COL_CURRENT
        )
        current_col.set_expand(True)
        current_col.set_sort_column_id(self.GIVEN_COL_CURRENT)
        self.given_tree.append_column(current_col)

        proposed_col = Gtk.TreeViewColumn(
            _("Proposed"), Gtk.CellRendererText(), markup=self.GIVEN_COL_PROPOSED
        )
        proposed_col.set_expand(True)
        proposed_col.set_sort_column_id(self.GIVEN_COL_PROPOSED_RAW)
        self.given_tree.append_column(proposed_col)

        action_col = Gtk.TreeViewColumn(
            _("Action"), Gtk.CellRendererText(), text=self.GIVEN_COL_ALT_ACTION
        )
        action_col.set_sort_column_id(self.GIVEN_COL_ALT_ACTION)
        self.given_tree.append_column(action_col)

    def setup_audit_columns(self) -> None:
        renderer_toggle = Gtk.CellRendererToggle()
        renderer_toggle.connect("toggled", self.on_audit_row_toggled)
        self.audit_tree.append_column(
            Gtk.TreeViewColumn(
                _("Use"), renderer_toggle, active=self.AUDIT_COL_CHECKBOX
            )
        )
        col = Gtk.TreeViewColumn(
            _("ID"), Gtk.CellRendererText(), text=self.AUDIT_COL_GRAMPS_ID
        )
        col.set_sort_column_id(self.AUDIT_COL_GRAMPS_ID)
        self.audit_tree.append_column(col)

        individual_col = Gtk.TreeViewColumn(
            _("Individual"), Gtk.CellRendererText(), text=self.AUDIT_COL_DISPLAY_NAME
        )
        individual_col.set_expand(True)
        individual_col.set_sort_column_id(self.AUDIT_COL_DISPLAY_NAME)
        self.audit_tree.append_column(individual_col)

        # ADDED FATHER COLUMN
        father_col = Gtk.TreeViewColumn(
            _("Father"), Gtk.CellRendererText(), text=self.AUDIT_COL_FATHER_NAME
        )
        father_col.set_expand(True)
        father_col.set_sort_column_id(self.AUDIT_COL_FATHER_NAME)
        self.audit_tree.append_column(father_col)

        current_col = Gtk.TreeViewColumn(
            _("Current"), Gtk.CellRendererText(), text=self.AUDIT_COL_CURRENT_PAT
        )
        current_col.set_expand(True)
        current_col.set_sort_column_id(self.AUDIT_COL_CURRENT_PAT)
        self.audit_tree.append_column(current_col)

        correction_col = Gtk.TreeViewColumn(
            _("Correction"), Gtk.CellRendererText(), markup=self.AUDIT_COL_DIFF_MARKUP
        )
        correction_col.set_expand(True)
        correction_col.set_sort_column_id(self.AUDIT_COL_SUGGESTED_STRING)
        self.audit_tree.append_column(correction_col)

        # ADDED CONFIDENCE COLUMN
        conf_col = Gtk.TreeViewColumn(
            _("Conf"), Gtk.CellRendererText(), text=self.AUDIT_COL_CONFIDENCE
        )
        conf_col.set_sort_column_id(self.AUDIT_COL_CONFIDENCE)
        self.audit_tree.append_column(conf_col)

        # RENAMED YEAR TO REF YEAR
        year_col = Gtk.TreeViewColumn(
            _("Ref Year"), Gtk.CellRendererText(), text=self.AUDIT_COL_REF_YEAR
        )
        year_col.set_sort_column_id(self.AUDIT_COL_REF_YEAR)
        self.audit_tree.append_column(year_col)

        rule_col = Gtk.TreeViewColumn(
            _("Rule"), Gtk.CellRendererText(), text=self.AUDIT_COL_RULE_ID
        )
        rule_col.set_sort_column_id(self.AUDIT_COL_RULE_ID)
        self.audit_tree.append_column(rule_col)

        explanation_col = Gtk.TreeViewColumn(
            _("Explanation"), Gtk.CellRendererText(), text=self.AUDIT_COL_EXPLANATION
        )
        explanation_col.set_expand(True)
        explanation_col.set_sort_column_id(self.AUDIT_COL_EXPLANATION)
        self.audit_tree.append_column(explanation_col)

    def on_preserve_alt_toggled(self, widget: Gtk.CheckButton) -> None:
        """Handler for toggling the preserve alternative names option."""
        if self.controller:
            self.controller.update_preserve_alt(widget.get_active())

    def update_given_store_actions(self, new_action: str) -> None:
        """Update the Action column in given_store to match the new action."""
        translated_action = _(new_action)
        for row in self.given_store:
            row[self.GIVEN_COL_ALT_ACTION] = translated_action

    # --- Row Toggle Handlers ---

    def on_given_row_toggled(self, widget: Any, path: str) -> None:
        self.given_store[path][self.GIVEN_COL_CHECKBOX] = not self.given_store[path][
            self.GIVEN_COL_CHECKBOX
        ]
        self.update_given_apply_button()

    def on_audit_row_toggled(self, widget: Any, path: str) -> None:
        self.audit_store[path][self.AUDIT_COL_CHECKBOX] = not self.audit_store[path][
            self.AUDIT_COL_CHECKBOX
        ]
        self.update_audit_apply_button()

        all_selected = all(row[self.AUDIT_COL_CHECKBOX] for row in self.audit_store)
        self.audit_select_all.handler_block_by_func(self.on_audit_select_all_toggled)
        self.audit_select_all.set_active(all_selected)
        self.audit_select_all.handler_unblock_by_func(self.on_audit_select_all_toggled)

    # --- Select All Handlers ---

    def on_given_select_all_toggled(self, widget: Any) -> None:
        for row in self.given_store:
            row[self.GIVEN_COL_CHECKBOX] = widget.get_active()
        self.update_given_apply_button()

    def on_audit_select_all_toggled(self, widget: Any) -> None:
        for row in self.audit_store:
            row[self.AUDIT_COL_CHECKBOX] = widget.get_active()
        self.update_audit_apply_button()

    # --- Configure Rules Dialog ---

    def on_configure_rules_clicked(self, widget: Any) -> None:
        dialog = Gtk.Dialog(
            title=_("Configure Rules"), parent=self.window, flags=Gtk.DialogFlags.MODAL
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

    # --- Person Edit Dialog ---

    def _open_person_edit_dialog(
        self, treeview: Gtk.TreeView, path: str, handle_column: int
    ) -> None:
        handle = treeview.get_model()[path][handle_column]
        gramps_person = self.controller.get_gramps_person(handle)
        dbstate = self.controller.dbstate
        uistate = getattr(self.controller.user, "uistate", None)
        if gramps_person is None or dbstate is None or uistate is None:
            return

        try:
            EditPerson(dbstate, uistate, [], gramps_person)
        except WindowActiveError:
            pass

    def on_audit_row_activated(
        self, tv: Gtk.TreeView, path: str, col: Gtk.TreeViewColumn
    ) -> None:
        self._open_person_edit_dialog(tv, path, self.AUDIT_COL_HANDLE)

    def on_given_row_activated(
        self, tv: Gtk.TreeView, path: str, col: Gtk.TreeViewColumn
    ) -> None:
        self._open_person_edit_dialog(tv, path, self.GIVEN_COL_HANDLE)

    def get_checked_renaming_handles(self) -> set[str]:
        """Returns the set of person handles for checked renaming rows."""
        return {
            row[self.GIVEN_COL_HANDLE]
            for row in self.given_store
            if row[self.GIVEN_COL_CHECKBOX]
        }

    def get_checked_audit_keys(self) -> set[tuple[str, str]]:
        """Returns the set of (person_handle, rule_id) for checked audit rows."""
        return {
            (row[self.AUDIT_COL_HANDLE], row[self.AUDIT_COL_RULE_ID])
            for row in self.audit_store
            if row[self.AUDIT_COL_CHECKBOX]
        }

    def show_ok_dialog(self, title: str, message: str) -> None:
        OkDialog(title, message, self.window)
