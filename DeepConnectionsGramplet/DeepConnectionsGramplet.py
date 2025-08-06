# encoding: utf-8
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009 Doug Blank <doug.blank@gmail.com>
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
# along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

# $Id$

# ------------------------------------------------------------------------
#
# Python modules
#
# ------------------------------------------------------------------------
from gi.repository import Gtk, GLib

# ------------------------------------------------------------------------
#
# GRAMPS modules
#
# ------------------------------------------------------------------------
from gramps.gen.relationship import get_relationship_calculator
from gramps.gen.lib import EventType, FamilyRelType
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.plug import Gramplet
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# ------------------------------------------------------------------------
#
# The Gramplet
#
# ------------------------------------------------------------------------
class DeepConnectionsGramplet(Gramplet):
    """
    Finds deep connections people the home person and the active person.
    """

    def init(self):
        self.selected_handles = set()
        self.relationship_calc = get_relationship_calculator()
        self.set_tooltip(_("Double-click name for details"))
        self.set_text(_("No Family Tree loaded."))
        self.set_use_markup(True)

        # Remove default textview and create custom UI
        self.gui.get_container_widget().remove(self.gui.textview)

        # Create main container
        vbox = Gtk.VBox(spacing=6)

        # Create status bar
        self.status_label = Gtk.Label()
        self.status_label.set_line_wrap(True)
        self.status_label.set_selectable(True)
        status_frame = Gtk.Frame()
        status_frame.set_shadow_type(Gtk.ShadowType.IN)
        status_frame.add(self.status_label)
        vbox.pack_start(status_frame, False, False, 0)

        # Create progress bar
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_visible(False)
        vbox.pack_start(self.progress_bar, False, False, 0)

        # Create search info label
        self.search_info = Gtk.Label()
        self.search_info.set_line_wrap(True)
        self.search_info.set_selectable(True)
        vbox.pack_start(self.search_info, False, False, 0)

        # Create textview with scrollbar
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(self.gui.textview)
        vbox.pack_start(scrolled_window, True, True, 0)

        # Create button container
        button_box = Gtk.HBox(spacing=6)
        button_box.set_margin_start(6)
        button_box.set_margin_end(6)
        button_box.set_margin_top(6)
        button_box.set_margin_bottom(6)

        # Create buttons with icons
        self.pause_button = Gtk.Button.new_with_label(_("⏸ Pause"))
        self.pause_button.set_sensitive(False)
        self.pause_button.set_tooltip_text(_("Pause the current search"))
        self.pause_button.connect("clicked", self.interrupt_search)

        self.continue_button = Gtk.Button.new_with_label(_("▶ Continue"))
        self.continue_button.set_sensitive(False)
        self.continue_button.set_tooltip_text(
            _("Continue searching for more relations")
        )
        self.continue_button.connect("clicked", self.resume_search)

        self.copy_button = Gtk.Button.new_with_label(_("📋 Copy"))
        self.copy_button.set_sensitive(False)
        self.copy_button.set_tooltip_text(_("Copy selected people to clipboard"))
        self.copy_button.connect(
            "clicked",
            lambda widget: self.gui.pane.pageview.copy_to_clipboard(
                "Person", self.selected_handles
            ),
        )

        self.clear_button = Gtk.Button.new_with_label(_("🗑 Clear"))
        self.clear_button.set_tooltip_text(_("Clear all results and reset"))
        self.clear_button.connect("clicked", self.clear_results)

        # Pack buttons
        button_box.pack_start(self.pause_button, False, False, 0)
        button_box.pack_start(self.continue_button, False, False, 0)
        button_box.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0
        )
        button_box.pack_start(self.copy_button, False, False, 0)
        button_box.pack_start(self.clear_button, False, False, 0)
        button_box.pack_end(Gtk.Label(), True, True, 0)  # Spacer

        vbox.pack_start(button_box, False, False, 0)

        # Add to container
        self.gui.get_container_widget().add_with_viewport(vbox)
        vbox.show_all()

        # Initialize search state
        self.search_active = False
        self.search_depth = 0
        self.people_processed = 0
        self.queue_size = 0

    def clear_results(self, widget=None):
        """Clear the current results and reset the display."""
        self.set_text("")
        self.selected_handles.clear()
        self.status_label.set_text(_("Ready to search"))
        self.search_info.set_text("")
        self.progress_bar.set_visible(False)
        self.copy_button.set_sensitive(False)
        self.pause_button.set_sensitive(False)
        self.continue_button.set_sensitive(False)

    def update_status(self, message):
        """Update the status label with a message."""
        self.status_label.set_text(message)
        # Force UI update
        while Gtk.events_pending():
            Gtk.main_iteration()

    def update_progress(self, current, total):
        """Update the progress bar."""
        if total > 0:
            fraction = min(current / total, 1.0)
            self.progress_bar.set_fraction(fraction)
            self.progress_bar.set_text(f"{current}/{total}")
        else:
            self.progress_bar.set_fraction(0.0)
            self.progress_bar.set_text("")

    def update_search_info(self, depth, processed, queue_size):
        """Update the search information display."""
        info_text = _(
            "Search Depth: {depth} | People Processed: {processed} | Queue Size: {queue_size}"
        ).format(depth=depth, processed=processed, queue_size=queue_size)
        self.search_info.set_text(info_text)

    def db_changed(self):
        """
        If person or family changes, the relatives of active person might have
        changed
        """
        self.selected_handles = set()
        self.connect(self.dbstate.db, "home-person-changed", self.update)
        self.connect(self.dbstate.db, "person-add", self.update)
        self.connect(self.dbstate.db, "person-delete", self.update)
        self.connect(self.dbstate.db, "person-update", self.update)
        self.connect(self.dbstate.db, "family-add", self.update)
        self.connect(self.dbstate.db, "family-delete", self.update)
        self.connect(self.dbstate.db, "person-rebuild", self.update)
        self.connect(self.dbstate.db, "family-rebuild", self.update)

    def get_links_from_notes(self, obj, path, relation, person_handle):
        """
        Get anyone mentioned in any note attached to this object.
        """
        retval = []
        note_list = obj.get_note_list()
        for note_handle in note_list:
            note = self.dbstate.db.get_note_from_handle(note_handle)
            if note:
                links = note.get_links()
                for link in links:
                    if link[0] == "gramps" and link[1] == "Person":
                        relation = _("mentioned in note")
                        if link[2] == "handle":
                            retval += [(link[3], (path, (relation, person_handle)))]
        return retval

    def get_relatives(self, person_handle, path):
        """
        Gets all of the relations of person_handle.
        """
        retval = []
        person = self.dbstate.db.get_person_from_handle(person_handle)
        if person is None:
            return []
        family_list = person.get_family_handle_list()
        for family_handle in family_list:
            family = self.dbstate.db.get_family_from_handle(family_handle)
            if family:
                children = family.get_child_ref_list()
                husband = family.get_father_handle()
                wife = family.get_mother_handle()
                retval.extend(
                    (child_ref.ref, (path, (_("child"), person_handle, husband, wife)))
                    for child_ref in children
                )
                if husband and husband != person_handle:
                    retval += [(husband, (path, (_("husband"), person_handle)))]
                if wife and wife != person_handle:
                    retval += [(wife, (path, (_("wife"), person_handle)))]
                retval += self.get_links_from_notes(
                    family, path, _("Note on Family"), person_handle
                )

        parent_family_list = person.get_parent_family_handle_list()
        for family_handle in parent_family_list:
            family = self.dbstate.db.get_family_from_handle(family_handle)
            if family:
                children = family.get_child_ref_list()
                husband = family.get_father_handle()
                wife = family.get_mother_handle()
                retval.extend(
                    (
                        child_ref.ref,
                        (path, (_("sibling"), person_handle, husband, wife)),
                    )
                    for child_ref in children
                    if child_ref.ref != person_handle
                )
                if husband and husband != person_handle:
                    retval += [(husband, (path, (_("father"), person_handle, wife)))]
                if wife and wife != person_handle:
                    retval += [(wife, (path, (_("mother"), person_handle, husband)))]
                retval += self.get_links_from_notes(
                    family, path, _("Note on Parent Family"), person_handle
                )
        assoc_list = person.get_person_ref_list()
        for assoc in assoc_list:
            relation = _("%s (association)") % assoc.get_relation()
            assoc_handle = assoc.get_reference_handle()
            retval += [(assoc_handle, (path, (relation, person_handle)))]

        retval += self.get_links_from_notes(
            person, path, _("Note on Person"), person_handle
        )
        return retval

    def active_changed(self, handle):
        """
        Update the gramplet on active person change.
        """
        self.update()

    def pretty_print(self, path):
        """
        Print a path to a person, with links.
        """
        # (path, (relation_text, handle, [p1, [p2]]))
        more_path = path[0]
        text = path[1][0]
        handle = path[1][1]
        parents = path[1][2:]
        person = self.dbstate.db.get_person_from_handle(handle)
        if person is None:
            return
        name = person.get_primary_name()
        self.selected_handles.add(person.handle)
        for parent in parents:
            if parent:
                p = self.dbstate.db.get_person_from_handle(parent)
                if p:
                    self.selected_handles.add(p.handle)

        if text != "self":
            self.append_text(_("\n   %s of ") % text)
            self.link(name_displayer.display_name(name), "Person", handle)
            relationship = self.relationship_calc.get_one_relationship(
                self.dbstate.db, self.default_person, person
            )
            if relationship:
                self.append_text(" [%s]" % relationship)
            if more_path is not None:
                self.pretty_print(more_path)

    def main(self):
        """
        Main method.
        """
        self.total_relations_found = 0
        self.search_active = True
        self.search_depth = 0
        self.people_processed = 0
        self.queue_size = 0

        yield True

        try:
            self.default_person = self.dbstate.db.get_default_person()
            active_person = self.get_active_object("Person")

            if self.default_person == None:
                self.set_text(_("No Home Person set."))
                self.update_status(_("Error: No Home Person set"))
                self.search_active = False
                return

            if active_person == None:
                self.set_text(_("No Active Person set."))
                self.update_status(_("Error: No Active Person set"))
                self.search_active = False
                return

            # Update UI for search start
            self.update_status(_("Initializing search..."))
            self.progress_bar.set_visible(True)
            self.pause_button.set_sensitive(True)
            self.copy_button.set_sensitive(False)

            self.cache = set()
            self.queue = [
                (
                    self.default_person.handle,
                    (None, (_("self"), self.default_person.handle, [])),
                )
            ]

            default_name = self.default_person.get_primary_name()
            active_name = active_person.get_primary_name()

            self.set_text("")
            self.render_text(
                (
                    _("Looking for relationship between\n")
                    + _("  <b>%s</b> (Home Person) and\n")
                    + _("  <b>%s</b> (Active Person)...\n")
                )
                % (
                    name_displayer.display_name(default_name),
                    name_displayer.display_name(active_name),
                )
            )

            yield True

            relationship = self.relationship_calc.get_one_relationship(
                self.dbstate.db, self.default_person, active_person
            )

            self.update_status(_("Searching for connections..."))

            while self.queue:
                current_handle, current_path = self.queue.pop(0)
                self.queue_size = len(self.queue)
                self.people_processed += 1

                # Update progress every 10 people processed
                if self.people_processed % 10 == 0:
                    self.update_progress(
                        self.people_processed, self.people_processed + self.queue_size
                    )
                    self.update_search_info(
                        self.search_depth, self.people_processed, self.queue_size
                    )
                    yield True

                if current_handle == active_person.handle:
                    self.total_relations_found += 1
                    self.append_text(
                        _("Found relation #%d: \n   ") % self.total_relations_found
                    )

                    self.link(
                        name_displayer.display_name(active_name),
                        "Person",
                        active_person.handle,
                    )
                    if relationship:
                        self.append_text(" [%s]" % relationship)
                    self.selected_handles.clear()
                    self.selected_handles.add(active_person.handle)
                    self.pretty_print(current_path)
                    self.append_text("\n")

                    # Enable copy button when we have results
                    self.copy_button.set_sensitive(True)

                    if self.default_person.handle != active_person.handle:
                        self.append_text(
                            _(
                                "Paused.\nPress Continue to search for additional relations.\n"
                            )
                        )
                        self.update_status(
                            _("Paused - Press Continue to search for more relations")
                        )
                        self.continue_button.set_sensitive(True)
                        self.pause_button.set_sensitive(False)
                        self.pause()
                        yield False
                    else:
                        break
                elif current_handle in self.cache:
                    continue

                self.cache.add(current_handle)
                relatives = self.get_relatives(current_handle, current_path)

                # Track search depth
                if current_path[0] is not None:
                    self.search_depth = max(
                        self.search_depth, self._calculate_path_depth(current_path)
                    )

                for items in relatives:
                    person_handle = items[0]
                    path = items[1]
                    if person_handle is not None:
                        self.queue.append((person_handle, path))

                yield True

            self.append_text(
                _("\nSearch completed. %d relation paths found.")
                % self.total_relations_found
            )
            self.update_status(
                _("Search completed - {} relation paths found").format(
                    self.total_relations_found
                )
            )
            self.progress_bar.set_visible(False)
            self.pause_button.set_sensitive(False)
            self.continue_button.set_sensitive(False)
            self.search_active = False
            yield False

        except Exception as e:
            self.update_status(_("Error during search: {}").format(str(e)))
            self.progress_bar.set_visible(False)
            self.pause_button.set_sensitive(False)
            self.continue_button.set_sensitive(False)
            self.search_active = False
            yield False

    def resume_search(self, widget):
        """Resume the search after being paused."""
        if self.search_active:
            self.update_status(_("Resuming search..."))
            self.continue_button.set_sensitive(False)
            self.pause_button.set_sensitive(True)
            self.resume()

    def interrupt_search(self, widget):
        """Interrupt the current search."""
        if self.search_active:
            self.update_status(_("Search interrupted by user"))
            self.pause_button.set_sensitive(False)
            self.continue_button.set_sensitive(True)
            self.interrupt()

    def _calculate_path_depth(self, path):
        """Calculate the depth of a relationship path."""
        depth = 0
        current_path = path
        while current_path[0] is not None:
            depth += 1
            current_path = current_path[0]
        return depth
