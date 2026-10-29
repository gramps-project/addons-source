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
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.lib import Person
from gramps.gen.plug import Gramplet
from gramps.gen.const import GRAMPS_LOCALE as glocale

# ------------------------------------------------------------------------
#
# Addon modules
#
# ------------------------------------------------------------------------
from deep_connections import (
    ASSOCIATION,
    CHILD,
    NOTE,
    PARENT,
    SELF,
    SIBLING,
    SPOUSE,
    ConnectionSearch,
    FamilyLinks,
    as_steps,
    connection_label,
    path_people,
    shortest_connection,
)

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

# relation -> {gender: text}; gender None is used for any other gender
RELATION_LABELS = {
    CHILD: {None: _("child")},
    SIBLING: {None: _("sibling")},
    PARENT: {Person.MALE: _("father"), Person.FEMALE: _("mother"), None: _("parent")},
    SPOUSE: {Person.MALE: _("husband"), Person.FEMALE: _("wife"), None: _("spouse")},
    NOTE: {None: _("mentioned in note")},
}


def relation_label(step, gender):
    """
    Return the display text for the relation of a path step, for a person
    of the given gender (the person the relation describes).
    """
    if step.relation == ASSOCIATION:
        return _("%s (association)") % step.detail
    labels = RELATION_LABELS[step.relation]
    return labels.get(gender, labels[None])


class _Genders(dict):
    """Gender of each person, read from the database when first needed."""

    def __init__(self, db):
        super().__init__()
        self.db = db

    def __missing__(self, handle):
        person = self.db.get_person_from_handle(handle)
        gender = person.get_gender() if person else Person.UNKNOWN
        self[handle] = gender
        return gender


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
        # all family links, loaded on the first search and kept until a
        # family changes
        self._family_links = None

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
        self._family_links = None
        self.connect(self.dbstate.db, "home-person-changed", self.update)
        self.connect(self.dbstate.db, "person-add", self.update)
        self.connect(self.dbstate.db, "person-delete", self.update)
        self.connect(self.dbstate.db, "person-update", self.update)
        self.connect(self.dbstate.db, "person-rebuild", self.update)
        for signal in (
            "family-add",
            "family-update",
            "family-delete",
            "family-rebuild",
        ):
            self.connect(self.dbstate.db, signal, self.families_changed)

    def families_changed(self, *args):
        """Reload the family links on the next search."""
        self._family_links = None
        self.update()

    def family_links(self):
        """All family links of the database, loaded once."""
        if self._family_links is None:
            self.update_status(_("Loading family links..."))
            self._family_links = FamilyLinks.load(self.dbstate.db)
        return self._family_links

    def relationship_text(self, handle):
        """
        The relationship of a person to the Home Person in Gramps' wording,
        including in-laws, or "" if there is none.
        """
        if handle not in self._relationships:
            path = shortest_connection(
                self.family_links(), self.default_person.handle, handle
            )
            if path is None:
                text = ""
            elif len(path) == 2 and path[1].relation == SPOUSE:
                # the calculator words spouses and partners
                text = self.relationship_calc.get_one_relationship(
                    self.dbstate.db,
                    self.default_person,
                    self.dbstate.db.get_person_from_handle(handle),
                )
            else:
                text = connection_label(
                    self.family_links(), path, self._genders, self.relationship_calc
                )
            self._relationships[handle] = text
        return self._relationships[handle]

    def active_changed(self, handle):
        """
        Update the gramplet on active person change.
        """
        self.update()

    def pretty_print(self, path, gender):
        """
        Print a path to a person, with links.

        ``gender`` is the gender of the person whose relation the first step
        describes (the person printed just before it).
        """
        # (more_path, Step(relation, handle, parents, detail))
        more_path, step = path
        handle = step.handle
        person = self.dbstate.db.get_person_from_handle(handle)
        if person is None:
            return
        name = person.get_primary_name()
        self.selected_handles.add(person.handle)
        for parent in step.parents:
            if parent:
                p = self.dbstate.db.get_person_from_handle(parent)
                if p:
                    self.selected_handles.add(p.handle)

        if step.relation != SELF:
            self.append_text(_("\n   %s of ") % relation_label(step, gender))
            self.link(name_displayer.display_name(name), "Person", handle)
            relationship = self.relationship_text(handle)
            if relationship:
                self.append_text(" [%s]" % relationship)
            if more_path is not None:
                self.pretty_print(more_path, person.get_gender())

    def show_path(self, path, active_person, relationship):
        """Show a found path from the active person back to the Home Person."""
        self.total_relations_found += 1
        self.append_text(_("Found relation #%d: \n   ") % self.total_relations_found)
        self.link(
            name_displayer.display_name(active_person.get_primary_name()),
            "Person",
            active_person.handle,
        )
        if relationship:
            self.append_text(" [%s]" % relationship)
        self.selected_handles.clear()
        self.selected_handles.add(active_person.handle)
        self.pretty_print(path, active_person.get_gender())
        self.append_text("\n")

        # Enable copy button when we have results
        self.copy_button.set_sensitive(True)

    def wait_for_continue(self):
        """Pause the search until Continue is pressed."""
        self.append_text(
            _("Paused.\nPress Continue to search for additional relations.\n")
        )
        self.update_status(_("Paused - Press Continue to search for more relations"))
        self.continue_button.set_sensitive(True)
        self.pause_button.set_sensitive(False)
        self.pause()

    def main(self):
        """
        Main method.

        The first path comes from the in-memory family links: the closest
        family connection, found quickly even in a large tree.  Continue
        then searches person by person, also following associations and
        people linked in notes, and skips the path already shown.
        """
        self.total_relations_found = 0
        self.search_active = True
        self._relationships = {}
        self._genders = _Genders(self.dbstate.db)

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

            search = ConnectionSearch(
                self.dbstate.db, self.default_person.handle, active_person.handle
            )

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

            relationship = self.relationship_text(active_person.handle)

            self.update_status(_("Searching for connections..."))

            shown = None
            fast = shortest_connection(
                self.family_links(), self.default_person.handle, active_person.handle
            )
            if fast is not None:
                shown = [link.handle for link in reversed(fast)]
                self.show_path(
                    as_steps(self.family_links(), fast), active_person, relationship
                )
                if self.default_person.handle == active_person.handle:
                    search = None
                else:
                    self.wait_for_continue()
                    yield False

            last_update = 0
            for current_path in search.steps() if search else ():
                # Update progress every 10 people processed
                if search.people_processed - last_update >= 10:
                    last_update = search.people_processed
                    self.update_progress(
                        search.people_processed,
                        search.people_processed + search.queue_size,
                    )
                    self.update_search_info(
                        search.depth, search.people_processed, search.queue_size
                    )

                if current_path is not None:
                    if path_people(active_person.handle, current_path) == shown:
                        continue
                    self.show_path(current_path, active_person, relationship)

                    if self.default_person.handle != active_person.handle:
                        self.wait_for_continue()
                        yield False
                    else:
                        break
                else:
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
