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
Base class for tab UI components with common treeview functionality.
Provides reusable GTK treeview patterns and event handlers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple

from gi.repository import Gtk

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.errors import WindowActiveError
from gramps.gui.editors import EditPerson

if TYPE_CHECKING:
    from gi.repository.Gtk import Window
    from name_processor.controllers.tool import ToolController


_ = glocale.translation.gettext


class BaseTab:
    """
    Base class for tab UI components with common treeview functionality.
    Subclasses must provide their specific RowData type and implement abstract methods.
    """

    def __init__(self, parent_window: Window, controller: ToolController) -> None:
        """
        Initialize the BaseTab.

        Args:
            parent_window: The parent GTK window for dialog references
            controller: The tool controller for business logic calls
        """
        self.parent_window = parent_window
        self.controller = controller

        # Widget properties (initialized in subclass build())
        self.store: Gtk.ListStore
        self.tree: Gtk.TreeView
        self.select_all: Gtk.CheckButton
        self.apply_btn: Gtk.Button

    # --- Common Event Handlers ---

    def on_row_activated(
        self, tv: Gtk.TreeView, path: str, col: Gtk.TreeViewColumn
    ) -> None:
        """
        Handle row double-click to open person editor.
        Subclasses must override get_row_data_type() to provide their RowData namedtuple.
        """
        row_data_type = self.get_row_data_type()
        handle = tv.get_model()[path][row_data_type._fields.index("handle")]
        gramps_person = self.controller.get_gramps_person(handle)
        dbstate = self.controller.dbstate
        uistate = getattr(self.controller.user, "uistate", None)
        if gramps_person is None or dbstate is None or uistate is None:
            return
        try:
            EditPerson(dbstate, uistate, [], gramps_person)
        except WindowActiveError:
            pass

    def on_select_all_toggled(self, widget: Any) -> None:
        """
        Handle select all checkbox toggle.
        Subclasses must override get_row_data_type() to provide their RowData namedtuple.
        """
        row_data_type = self.get_row_data_type()
        chk_idx = row_data_type._fields.index("checkbox")
        for row in self.store:
            row[chk_idx] = widget.get_active()
        self.update_apply_button()

    def on_row_toggled(self, widget: Any, path: str) -> None:
        """
        Handle individual row checkbox toggle.
        Subclasses must override get_row_data_type() to provide their RowData namedtuple.
        Override this if additional sync logic is needed (e.g., select_all checkbox).
        """
        row_data_type = self.get_row_data_type()
        chk_idx = row_data_type._fields.index("checkbox")
        self.store[path][chk_idx] = not self.store[path][chk_idx]
        self.update_apply_button()

    def update_apply_button(self) -> None:
        """
        Enable/disable apply button based on checked rows.
        Subclasses must override get_row_data_type() to provide their RowData namedtuple.
        """
        row_data_type = self.get_row_data_type()
        chk_idx = row_data_type._fields.index("checkbox")
        self.apply_btn.set_sensitive(any(row[chk_idx] for row in self.store))

    # --- Common Column Setup Helpers ---

    def _add_text_column(
        self,
        title: str,
        field_name: str,
        row_data_type: type[NamedTuple],
        expand: bool = False,
        use_markup: bool = False,
        sort_field: str | None = None,
    ) -> None:
        """
        Helper to add a text column to the treeview.

        Args:
            title: Column header text
            field_name: Field name in RowData namedtuple
            row_data_type: The RowData namedtuple type
            expand: Whether column should expand
            use_markup: Whether to use Pango markup
            sort_field: Optional field to use for sorting (defaults to field_name)
        """
        attr = "markup" if use_markup else "text"
        sort_id = row_data_type._fields.index(sort_field if sort_field else field_name)
        col = Gtk.TreeViewColumn(
            title,
            Gtk.CellRendererText(),
            **{attr: row_data_type._fields.index(field_name)},
        )
        col.set_expand(expand)
        col.set_sort_column_id(sort_id)
        self.tree.append_column(col)

    def _add_checkbox_column(
        self, row_data_type: type[NamedTuple], toggle_handler: Any
    ) -> None:
        """
        Helper to add a checkbox column to the treeview.

        Args:
            row_data_type: The RowData namedtuple type
            toggle_handler: The callback function for toggle events
        """
        renderer_toggle = Gtk.CellRendererToggle()
        renderer_toggle.connect("toggled", toggle_handler)
        self.tree.append_column(
            Gtk.TreeViewColumn(
                _("Use"),
                renderer_toggle,
                active=row_data_type._fields.index("checkbox"),
            )
        )

    # --- Abstract Methods ---

    def get_row_data_type(self) -> type[NamedTuple]:
        """
        Return the RowData namedtuple type for this tab.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement get_row_data_type()")
