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
GTK Window layout for the Names Tool batch processing interface.
Acts as a shell window that delegates to tab-specific components.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TYPE_CHECKING

from gi.repository import Gtk

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gui.dialog import OkDialog

from name_processor.models.audit import AuditIssue
from name_processor.models.renamer import AltAction
from name_processor.presentation.row_schemas import GivenRowData

from name_processor.views.tool_audit_tab import AuditTab
from name_processor.views.tool_rename_tab import RenameTab

if TYPE_CHECKING:
    from name_processor.controllers.tool import ToolController


logger = logging.getLogger(__name__)

_ = glocale.translation.gettext


class ToolWindow:
    """
    GTK Batch Processing Window. Acts as a Passive View in the MVP/MVCS pattern.
    All business logic and long-running tasks are delegated to the controller.
    """

    def __init__(self, callback: Callable[[], None] | None = None) -> None:
        """Initializes the GTK Window."""
        self.callback = callback
        self.controller: ToolController | None = None

        # Tab instances (will be created in build_window)
        self.rename_tab: RenameTab | None = None
        self.audit_tab: AuditTab | None = None

        # Window will be built when controller is set
        self.window: Gtk.Window | None = None

    def set_controller(self, controller: ToolController) -> None:
        """Sets the controller instance and runs initial loads."""
        self.controller = controller

        # Build window if not already built
        if self.window is None:
            self.build_window()

        # Update controller reference in tabs
        if self.rename_tab:
            self.rename_tab.controller = controller
        if self.audit_tab:
            self.audit_tab.controller = controller

        # Initialize enabled rules in audit tab
        if self.audit_tab:
            self.audit_tab.enabled_rules = {
                rule_id: True for rule_id in self.controller.get_available_audit_rules()
            }

        # Set up autocompletion for given name entry (delegated to rename tab)
        if self.rename_tab:
            self.rename_tab.setup_autocompletion()

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

    def build_window(self) -> None:
        """Build the main window structure with tab components."""
        self.window = Gtk.Window(title=_("Infer East Slavic Patronymics"))
        self.window.set_default_size(900, 600)
        self.window.set_position(Gtk.WindowPosition.CENTER)
        self.window.set_border_width(12)

        self.window.connect("destroy", self.on_destroy)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.window.add(main_box)

        notebook = Gtk.Notebook()
        main_box.pack_start(notebook, True, True, 0)

        # Instantiate tabs (controller must be set first)
        assert self.controller is not None
        self.rename_tab = RenameTab(self.window, self.controller)
        self.audit_tab = AuditTab(self.window, self.controller)

        # Add tabs to notebook
        rename_widget = self.rename_tab.build()
        notebook.append_page(rename_widget, Gtk.Label(label=_("Rename Given Names")))

        audit_widget = self.audit_tab.build()
        notebook.append_page(audit_widget, Gtk.Label(label=_("Audit Patronymics")))

        self.window.show_all()

    def on_destroy(self, widget: Any) -> None:
        if self.controller:
            self.controller.cleanup()
        if self.callback:
            self.callback()

    # --- Delegation Methods (Rename Tab) ---

    def clear_rename_proposals(self) -> None:
        """Delegate to rename_tab.clear_proposals()"""
        if self.rename_tab:
            self.rename_tab.clear_proposals()

    def append_rename_proposal(self, row: GivenRowData) -> None:
        """Delegate to rename_tab.append_proposal(row)"""
        if self.rename_tab:
            self.rename_tab.append_proposal(row)

    def update_given_store_actions(self, action: AltAction) -> None:
        """Delegate to rename_tab.update_actions(action)"""
        if self.rename_tab:
            self.rename_tab.update_actions(action)

    def update_given_apply_button(self) -> None:
        """Delegate to rename_tab.update_apply_button()"""
        if self.rename_tab:
            self.rename_tab.update_apply_button()

    def get_checked_renaming_handles(self) -> set[str]:
        """Delegate to rename_tab.get_checked_handles()"""
        if self.rename_tab:
            return self.rename_tab.get_checked_handles()
        return set()

    def is_preserve_alt_enabled(self) -> bool:
        """Delegate to rename_tab.is_preserve_enabled()"""
        if self.rename_tab:
            return self.rename_tab.is_preserve_enabled()
        return False

    # --- Delegation Methods (Audit Tab) ---

    def clear_audit_results(self) -> None:
        """Delegate to audit_tab.clear_results()"""
        if self.audit_tab:
            self.audit_tab.clear_results()

    def append_issue(self, issue: AuditIssue) -> None:
        """Delegate to audit_tab.append_issue(issue)"""
        if self.audit_tab:
            self.audit_tab.append_issue(issue)

    def update_audit_progress(self, fraction: float, text: str) -> None:
        """Delegate to audit_tab.update_progress(fraction, text)"""
        if self.audit_tab:
            self.audit_tab.update_progress(fraction, text)

    def on_audit_complete(self, total_found: int) -> None:
        """Delegate to audit_tab.on_complete(total_found)"""
        if self.audit_tab:
            self.audit_tab.on_complete(total_found)

    def update_audit_apply_button(self) -> None:
        """Delegate to audit_tab.update_apply_button()"""
        if self.audit_tab:
            self.audit_tab.update_apply_button()

    def get_checked_audit_keys(self) -> set[tuple[str, str]]:
        """Delegate to audit_tab.get_checked_keys()"""
        if self.audit_tab:
            return self.audit_tab.get_checked_keys()
        return set()

    def get_audit_result_count(self) -> int:
        """Delegate to audit_tab.get_result_count()"""
        if self.audit_tab:
            return self.audit_tab.get_result_count()
        return 0

    def get_enabled_audit_rules(self) -> set[str]:
        """Delegate to audit_tab.get_enabled_rules()"""
        if self.audit_tab:
            return self.audit_tab.get_enabled_rules()
        return set()

    # --- Shared Dialog Methods ---

    def show_ok_dialog(self, title: str, message: str) -> None:
        OkDialog(title, message, self.window)

    def setup_given_name_autocompletion(self) -> None:
        """Set up autocompletion for given name entry (delegated to rename tab)."""
        if self.rename_tab:
            self.rename_tab.setup_autocompletion()
