#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2006  Donald N. Allingham
# Copyright (C) 2009  Jerome Rapinat
# Copyright (C) 2026  Brian McCullough, with assistance from Anthropic Claude and GitHub Copilot
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
Associations Statistics Tool.

Display and edit all person associations in a sortable table with
context menu support and ability to create linked notes.

Refactored v1.2.1:
- Retained context menu for copy/edit operations
- Retained styled note creation with person hyperlinks
- Simplified GTK widget hierarchy while preserving sorting capability
- Added progress dialog for large database operations
- Lazy-loaded editor imports for performance
- Added proper type hints and docstrings per Gramps AGENTS.md
- Improved import organization and code structure
- Retained help button with dynamic help_url support
- Added status bar with association count
"""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
import logging

# -------------------------------------------------------------------------
#
# GTK/Gnome modules
#
# -------------------------------------------------------------------------
from gi.repository import Gdk, Gtk, GLib

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.lib import Note, NoteType, StyledText, StyledTextTag, StyledTextTagType
from gramps.gen.relationship import get_relationship_calculator
from gramps.gui.display import display_url
from gramps.gui.listmodel import ListModel, NOSORT
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.plug import tool
from typing import Optional, Tuple
from gramps.version import VERSION_TUPLE

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

# Helper function for Gramps 5.2/6.x compatibility
def get_ref_relation(ref):
    """Get the relation string from a PersonRef object (Gramps 5.2/6.x compatible)."""
    if VERSION_TUPLE < (6, 0, 99):
        # Gramps 5.2 and 6.0: use get_relation() method
        return str(ref.get_relation()) if hasattr(ref, 'get_relation') else ""
    else:
        # Gramps 6.1 and +: use .relation attribute
        return str(ref.relation) if hasattr(ref, 'relation') else ""

LOG = logging.getLogger(__name__)

# Column indices
COL_NAME1 = 0      # Starting person name
COL_CALC = 1       # Calculated relationship
COL_BULLET = 2     # Visual separator
COL_NAME2 = 3      # Associated person name
COL_LINK = 4       # Association type
COL_TOOLTIP = 5    # Tooltip text (hidden)
COL_HANDLE1 = 6    # Starting person handle (hidden)
COL_HANDLE2 = 7    # Associated person handle (hidden)

# Progress dialog threshold (milliseconds)
PROGRESS_THRESHOLD_MS = 1000


# -------------------------------------------------------------------------
#
# AssociationsTool
#
# -------------------------------------------------------------------------
class AssociationsTool(tool.Tool, ManagedWindow):
    """
    Tool to display and edit all person associations.

    Displays associations in a sortable table with double-click editing,
    context menu support, and ability to create linked notes with
    person hyperlinks. Includes progress indication for large databases.
    """

    def __init__(
        self,
        dbstate,
        user,
        options_class,
        name,
        callback=None,
    ):
        """
        Initialize the Associations tool.

        :param dbstate: Database state object
        :param user: User object (carries uistate)
        :param options_class: Tool options class
        :param name: Tool name
        :param callback: Unused callback parameter
        """
        uistate = user.uistate
        self.label = _("Associations state tool")
        self.dbstate = dbstate
        self.uistate = uistate
        self.help_url = "Addon:Check_Associations"
        self.stats_list = []
        self.progress_dialog = None
        self.current_progress = 0
        self.total_progress = 0

        tool.Tool.__init__(self, dbstate, options_class, name)

        if uistate:
            ManagedWindow.__init__(self, uistate, [], self.__class__)
            # Schedule data building AFTER ManagedWindow is fully initialized.
            # Use a higher priority idle callback to ensure window setup completes first.
            GLib.idle_add(self._build_with_progress, priority=GLib.PRIORITY_LOW)
        else:
            # CLI mode: build synchronously
            self._build_stats_list()
            self._print_cli(self.stats_list)

    # ---------------------------------------------------------------------
    #
    # Data Building (Main thread with progress)
    #
    # ---------------------------------------------------------------------

    def _build_with_progress(self) -> bool:
        """
        Build associations with periodic progress updates.

        Uses GLib.idle_add to yield control and prevent blocking.
        Only shows progress dialog if operation takes > 1 second.

        All database access uses Gramps API (backend-agnostic).

        :returns: False to prevent repeated calls
        """
        # First call: initialize
        if not hasattr(self, '_build_started'):
            self._build_started = True
            self._build_index = 0
            self._build_data = []
            self._start_time = GLib.get_real_time() / 1000.0  # Convert to ms

            # Get initial data via Gramps API
            try:
                self._plist = self.dbstate.db.get_person_handles(sort_handles=True)
                self.total_progress = len(self._plist)
                self._relationship = get_relationship_calculator()
            except Exception as e:
                LOG.error(_("Error initializing data: %s") % str(e))
                self._finalize_display()
                return False

        # Process next batch
        batch_size = 50
        for _ in range(batch_size):
            if self._build_index >= len(self._plist):
                # Done processing
                self.stats_list = self._build_data
                self._finalize_display()
                return False

            handle = self._plist[self._build_index]
            self._build_index += 1

            try:
                # Gramps API: backend-agnostic database access
                person = self.dbstate.db.get_person_from_handle(handle)
                name1 = name_displayer.display(person)
                refs = person.get_person_ref_list()

                if refs:
                    for ref in refs:
                        two = ref.ref # Handle of the associated person
                        value = get_ref_relation(ref) # Relationship type (e.g., "Godparent")
                        try:
                            person2 = self.dbstate.db.get_person_from_handle(two)
                        except Exception:
                            continue

                        name2 = name_displayer.display(person2)
                        rel = self._relationship.get_one_relationship(
                            self.dbstate.db, person2, person
                        )
                        tooltip = f"{name1} → {name2} [{value}]"

                        self._build_data.append(
                            (name1, rel, "•", name2, value, tooltip, handle, two)
                        )
            except Exception as e:
                LOG.warning(_("Error processing person %s: %s" % (handle, str(e))))
                continue

            # Check if we should show progress dialog
            elapsed_ms = (GLib.get_real_time() / 1000.0) - self._start_time
            if elapsed_ms > PROGRESS_THRESHOLD_MS and not self.progress_dialog:
                self._show_progress_dialog()

            # Update progress if dialog exists
            if self.progress_dialog:
                self.current_progress = self._build_index
                self._update_progress_display()

        # Schedule next batch
        GLib.idle_add(self._build_with_progress, priority=GLib.PRIORITY_LOW)
        return False

    def _show_progress_dialog(self) -> None:
        """
        Create and show the progress dialog.

        Only called if processing takes > 1 second.
        """
        try:
            parent = self.uistate.window if self.uistate else None
            self.progress_dialog = Gtk.MessageDialog(
                parent=parent,
                flags=Gtk.DialogFlags.MODAL,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.CANCEL,
                message_format=_("Processing associations..."),
            )
            self.progress_dialog.connect("response", self._on_progress_response)
            self.progress_dialog.show()
        except Exception as e:
            LOG.warning(_("Could not create progress dialog: %s") % str(e))

    def _on_progress_response(self, dialog, response_id) -> None:
        """
        Handle progress dialog response (e.g., Cancel button).

        :param dialog: Dialog widget
        :param response_id: Response ID from button
        """
        if response_id == Gtk.ResponseType.CANCEL:
            try:
                dialog.destroy()
            except Exception:
                pass
            self.progress_dialog = None
            self._finalize_display()

    def _update_progress_display(self) -> None:
        """
        Update the progress dialog with current count.
        """
        if self.progress_dialog:
            try:
                self.progress_dialog.format_secondary_text(
                    _("Processing %d of %d persons") % (
                        self.current_progress,
                        self.total_progress,
                    )
                )
            except Exception:
                pass

    def _build_stats_list(self) -> None:
        """
        Build list of associations (synchronous, for CLI mode).

        Uses only Gramps API for database access.
        """
        self.stats_list = []
        relationship = get_relationship_calculator()

        plist = self.dbstate.db.get_person_handles(sort_handles=True)

        for handle in plist:
            try:
                person = self.dbstate.db.get_person_from_handle(handle)
            except Exception:
                continue

            name1 = name_displayer.display(person)
            refs = person.get_person_ref_list()

            if refs:
                for ref in refs:
                    two = ref.ref # Handle of the associated person
                    value = get_ref_relation(ref)
                    try:
                        person2 = self.dbstate.db.get_person_from_handle(two)
                    except Exception:
                        continue

                    name2 = name_displayer.display(person2)
                    rel = relationship.get_one_relationship(
                        self.dbstate.db, person2, person
                    )
                    tooltip = f"{name1} → {name2} [{value}]"

                    self.stats_list.append(
                        (name1, rel, "•", name2, value, tooltip, handle, two)
                    )

    def _finalize_display(self) -> bool:
        """
        Close progress dialog and build the GUI with collected data.

        Safely checks for window existence before attempting to use it.

        :returns: False to prevent repeated calls
        """
        if self.progress_dialog:
            try:
                self.progress_dialog.destroy()
            except Exception:
                pass
            self.progress_dialog = None

        try:
            # Build the GUI window and populate with data
            self._build_gui(self.stats_list)
        except Exception as e:
            LOG.error(_("Error displaying associations: %s") % str(e))

        return False

    # ---------------------------------------------------------------------
    #
    # GUI Building
    #
    # ---------------------------------------------------------------------

    def _build_gui(self, stats_list: list) -> None:
        """
        Build and display the GTK window.

        :param stats_list: List of association row tuples
        :type stats_list: list
        """
        titles = [
            (_("Starting Name"), COL_NAME1, 200),
            (_("Calculated"), COL_CALC, 200),
            ("•", NOSORT, 35),
            (_("Associate"), COL_NAME2, 200),
            (_("Link Type"), COL_LINK, 200),
            ("", NOSORT, 1),    # Hidden: tooltip
            ("", NOSORT, 1),    # Hidden: handle1
            ("", NOSORT, 1),    # Hidden: handle2
        ]

        self.treeview = Gtk.TreeView()
        self.treeview.set_tooltip_column(COL_TOOLTIP)
        self.treeview.connect("row-activated", self.cb_row_activated)

        self.model = ListModel(
            self.treeview,
            titles,
            right_click=self.cb_right_click,
        )
        for entry in stats_list:
            self.model.add(list(entry), entry[COL_NAME1])

        # Hide internal columns
        columns = self.treeview.get_columns()
        for col_idx in (COL_TOOLTIP, COL_HANDLE1, COL_HANDLE2):
            if col_idx < len(columns):
                columns[col_idx].set_visible(False)

        # Build window
        window = Gtk.Window()
        window.set_default_size(1000, 600)

        if self.uistate and self.uistate.window:
            window.set_transient_for(self.uistate.window)

        # Main vertical box
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Scroller with treeview
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.add(self.treeview)
        vbox.pack_start(scroller, True, True, 0)

        # Bottom button and status bar
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        hbox.set_margin_start(4)
        hbox.set_margin_end(4)
        hbox.set_margin_top(4)
        hbox.set_margin_bottom(4)

        btn_help = Gtk.Button.new_with_mnemonic(_("_Help"))
        btn_help.connect("clicked", self.cb_help)
        hbox.pack_start(btn_help, False, False, 0)

        # Status label (stretches to fill space)
        status_label = Gtk.Label()
        status_label.set_text(
            _("Total associations found: %d") % len(stats_list)
        )
        status_label.set_xalign(1.0)  # Right-align
        hbox.pack_end(status_label, True, True, 0)

        vbox.pack_start(hbox, False, False, 0)

        window.add(vbox)
        window.show_all()

        self.set_window(window, None, self.label)
        self.show()

    def _print_cli(self, stats_list: list) -> None:
        """
        Print associations to stdout (CLI mode).

        :param stats_list: List of association row tuples
        :type stats_list: list
        """
        header = (
            _("Starting Name"),
            _("Calculated"),
            "•",
            _("Associate"),
            _("Link Type"),
        )
        print("\t%s" * 5 % header)
        print()
        for entry in stats_list:
            print("\t%s" * 5 % entry[:5])
        print()
        print(_("Total associations found: %d") % len(stats_list))

    # ---------------------------------------------------------------------
    #
    # Selection Helper
    #
    # ---------------------------------------------------------------------

    def _get_selected_row(self) -> Optional[Tuple]:
        """
        Return the full model row values for the selected row, or None.

        :returns: Tuple of 8 model values, or None
        :rtype: tuple | None
        """
        model, tree_iter = self.treeview.get_selection().get_selected()
        if not tree_iter:
            return None
        return tuple(model.get_value(tree_iter, col) for col in range(8))

    # ---------------------------------------------------------------------
    #
    # Event Handlers - Double-click
    #
    # ---------------------------------------------------------------------

    def cb_row_activated(self, treeview, path, column) -> None:
        """
        Handle double-click on row to open appropriate editor.

        Routes to the correct editor based on which column was activated:
        - COL_NAME2: Edit the associated person
        - COL_LINK: Edit the association relationship
        - Other columns: Edit the starting person

        :param treeview: TreeView widget
        :param path: TreePath of activated row
        :param column: TreeViewColumn that was double-clicked
        """
        # Lazy import to avoid loading editors unless needed
        from gramps.gui.editors import (  # noqa: PLC0415
            EditPerson,
            EditPersonRef,
        )

        try:
            model = treeview.get_model()
            tree_iter = model.get_iter(path)
            col_idx = treeview.get_columns().index(column)

            handle1 = model.get_value(tree_iter, COL_HANDLE1)
            handle2 = model.get_value(tree_iter, COL_HANDLE2)

            if col_idx == COL_NAME2:
                person = self.dbstate.db.get_person_from_handle(handle2)
                EditPerson(self.dbstate, self.uistate, [], person)
            elif col_idx == COL_LINK:
                person = self.dbstate.db.get_person_from_handle(handle1)
                for ref in person.get_person_ref_list():
                    if ref.ref == handle2:
                        EditPersonRef(
                            self.dbstate,
                            self.uistate,
                            [],
                            ref,
                            lambda *args: None,
                        )
                        return
            else:
                person = self.dbstate.db.get_person_from_handle(handle1)
                EditPerson(self.dbstate, self.uistate, [], person)
        except Exception:
            pass

    # ---------------------------------------------------------------------
    #
    # Event Handlers - Context Menu
    #
    # ---------------------------------------------------------------------

    def cb_right_click(self, treeview, event) -> None:
        """
        Show a context menu on right-click.

        :param treeview: The TreeView widget
        :param event: The button event
        """
        row = self._get_selected_row()
        has_row = row is not None

        menu = Gtk.Menu()
        menu.set_reserve_toggle_size(False)

        entries = [
            (_("Edit Starting Person"), self.cb_edit_person1, has_row),
            (_("Edit Associate Person"), self.cb_edit_person2, has_row),
            (_("Edit Association"), self.cb_edit_association, has_row),
            (None, None, 0),
            (_("Copy row to clipboard"), self.cb_copy_row, has_row),
            (_("Create Note from row"), self.cb_create_note, has_row),
        ]

        for title, callback, sensitive in entries:
            if title is None:
                item = Gtk.SeparatorMenuItem()
            else:
                item = Gtk.MenuItem(label=title)
                if callback:
                    item.connect("activate", callback)
                item.set_sensitive(sensitive)
            item.show()
            menu.append(item)

        menu.popup_at_pointer(event)

    def cb_edit_person1(self, obj) -> None:
        """
        Open Person Editor for the Starting Name of the selected row.

        :param obj: Menu item (unused)
        """
        from gramps.gui.editors import EditPerson  # noqa: PLC0415

        row = self._get_selected_row()
        if row:
            try:
                person = self.dbstate.db.get_person_from_handle(row[COL_HANDLE1])
                EditPerson(self.dbstate, self.uistate, [], person)
            except Exception:
                pass

    def cb_edit_person2(self, obj) -> None:
        """
        Open Person Editor for the Associate of the selected row.

        :param obj: Menu item (unused)
        """
        from gramps.gui.editors import EditPerson  # noqa: PLC0415

        row = self._get_selected_row()
        if row:
            try:
                person = self.dbstate.db.get_person_from_handle(row[COL_HANDLE2])
                EditPerson(self.dbstate, self.uistate, [], person)
            except Exception:
                pass

    def cb_edit_association(self, obj) -> None:
        """
        Open the Association Editor for the selected row.

        :param obj: Menu item (unused)
        """
        from gramps.gui.editors import EditPersonRef  # noqa: PLC0415

        row = self._get_selected_row()
        if not row:
            return
        try:
            person = self.dbstate.db.get_person_from_handle(row[COL_HANDLE1])
            for ref in person.get_person_ref_list():
                if ref.ref == row[COL_HANDLE2]:
                    EditPersonRef(
                        self.dbstate,
                        self.uistate,
                        [],
                        ref,
                        lambda *args: None,
                    )
                    return
        except Exception:
            pass

    def cb_copy_row(self, obj) -> None:
        """
        Copy the selected row display text to the system clipboard.

        :param obj: Menu item (unused)
        """
        row = self._get_selected_row()
        if not row:
            return
        text = "\t".join(str(row[col]) for col in range(5))
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)

    def cb_create_note(self, obj) -> None:
        """
        Create a Note pre-populated with row data and open the Note Editor.

        The note body lists each field on its own line with person names
        rendered as gramps:// deep-link URLs; the Note editor renders
        these as clickable hyperlinks.

        :param obj: Menu item (unused)
        """
        from gramps.gui.editors import EditNote  # noqa: PLC0415

        row = self._get_selected_row()
        if not row:
            return

        name1 = row[COL_NAME1]
        rel = row[COL_CALC]
        name2 = row[COL_NAME2]
        value = row[COL_LINK]
        handle1 = row[COL_HANDLE1]
        handle2 = row[COL_HANDLE2]

        url1 = f"gramps://Person/handle/{handle1}"
        url2 = f"gramps://Person/handle/{handle2}"

        # Build note text with styled hyperlinks on person names
        seg_header = _("Association:") + "\n"
        seg_p1_pre = _("Starting Person") + ": "
        seg_mid = "\n" + _("Relationship") + ": "
        seg_suffix = f" ({rel})\n" + _("Link type") + ": " + value

        raw_text = seg_header + seg_p1_pre + name1 + seg_mid + name2 + seg_suffix

        off1_start = len(seg_header) + len(seg_p1_pre)
        off1_end = off1_start + len(name1)
        off2_start = off1_end + len(seg_mid)
        off2_end = off2_start + len(name2)

        tag1 = StyledTextTag(
            StyledTextTagType.LINK,
            url1,
            [(off1_start, off1_end)],
        )
        tag2 = StyledTextTag(
            StyledTextTagType.LINK,
            url2,
            [(off2_start, off2_end)],
        )
        styled = StyledText(raw_text, [tag1, tag2])

        note = Note()
        note.set_styledtext(styled)
        note.set_type(NoteType.GENERAL)

        EditNote(self.dbstate, self.uistate, [], note)

    def cb_help(self, obj) -> None:
        """
        Open the addon wiki page in the default web browser.

        Uses the registered help_url from the plugin metadata.

        :param obj: Button widget (unused)
        """
        display_url(f"https://www.gramps-project.org/wiki/index.php/{self.help_url}")

    # ---------------------------------------------------------------------
    #
    # Menu
    #
    # ---------------------------------------------------------------------

    def build_menu_names(self, obj) -> tuple:
        """
        Return menu names for managed window.

        :param obj: Unused
        :returns: Tuple of (label, None)
        :rtype: tuple
        """
        return (self.label, None)


# -------------------------------------------------------------------------
#
# AssociationsToolOptions
#
# -------------------------------------------------------------------------
class AssociationsToolOptions(tool.ToolOptions):
    """Defines options and provides handling interface."""

    def __init__(self, name, person_id: Optional[str] = None) -> None:
        """
        Initialize tool options.

        :param name: Tool name
        :param person_id: Optional active person Gramps ID
        :type person_id: str | None
        """
        tool.ToolOptions.__init__(self, name, person_id)
