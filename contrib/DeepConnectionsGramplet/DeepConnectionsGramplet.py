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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

# $Id$

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.relationship import get_relationship_calculator
from gramps.gen.lib import EventType, FamilyRelType
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.plug import Gramplet
from gramps.gen.utils.trans import get_addon_translator
_ = get_addon_translator().ugettext

#------------------------------------------------------------------------
#
# The Gramplet
#
#------------------------------------------------------------------------
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
        self.gui.get_container_widget().remove(self.gui.textview)
        vbox = Gtk.VBox()
        hbox = Gtk.HBox()
        pause_button = Gtk.Button(_("Pause"))
        pause_button.connect("clicked", self.interrupt)
        continue_button = Gtk.Button(_("Continue"))
        continue_button.connect("clicked", self.resume)
        copy_button = Gtk.Button(_("Copy"))
        copy_button.connect("clicked", lambda widget: \
              self.gui.pane.pageview.copy_to_clipboard('Person', self.selected_handles))
        hbox.pack_start(pause_button, '', '', True)
        hbox.pack_start(copy_button, '', '', True)
        hbox.pack_start(continue_button, '', '', True)
        vbox.pack_start(self.gui.textview, '', '', True)
        vbox.pack_start(hbox, '', '', False)
        self.gui.get_container_widget().add_with_viewport(vbox)
        vbox.show_all()

    def get_relatives(self, person_handle, path):
        """
        Gets all of the relations of person_handle.
        """
        retval = []
        person = self.dbstate.db.get_person_from_handle(person_handle)
        if person is None: return []
        family_list = person.get_family_handle_list()
        for family_handle in family_list:
            family = self.dbstate.db.get_family_from_handle(family_handle)
            if family:
                children = family.get_child_ref_list()
                husband = family.get_father_handle()
                wife = family.get_mother_handle()
                retval.extend((child_ref.ref, (path, (_("child"), person_handle, 
                                                      husband, wife)))
                              for child_ref in children)
                if husband and husband != person_handle:
                    retval += [(husband, (path, (_("husband"), person_handle)))]
                if wife and wife != person_handle:
                    retval += [(wife, (path, (_("wife"), person_handle)))]

        parent_family_list = person.get_parent_family_handle_list()
        for family_handle in parent_family_list:
            family = self.dbstate.db.get_family_from_handle(family_handle)
            if family:
                children = family.get_child_ref_list()
                husband = family.get_father_handle()
                wife = family.get_mother_handle()
                retval.extend((child_ref.ref, (path, 
                                    (_("sibling"), person_handle, husband, wife)))
                              for child_ref in children if child_ref.ref != person_handle)
                if husband and husband != person_handle:
                    retval += [(husband, 
                                (path, (_("father"), person_handle, wife)))]
                if wife and wife != person_handle:
                    retval += [(wife, 
                                (path, (_("mother"), person_handle, husband)))]

        assoc_list = person.get_person_ref_list()
        for assoc in assoc_list:
            relation = _("%s (association)") % assoc.get_relation()
            assoc_handle = assoc.get_reference_handle()
            retval += [(assoc_handle, (path, (relation, person_handle)))]

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
                self.dbstate.db, self.default_person, person)
            if relationship:
                self.append_text(" [%s]" % relationship)
            if more_path is not None:
                self.pretty_print(more_path)

    def main(self):
        """
        Main method.
        """
        self.total_relations_found = 0
        yield True
        self.default_person = self.dbstate.db.get_default_person()
        active_person = self.get_active_object("Person")
        if self.default_person == None:
            self.set_text(_("No Home Person set."))
            return
        if active_person == None:
            self.set_text(_("No Active Person set."))
            return
        self.cache = set() 
        self.queue = [(self.default_person.handle, 
                       (None, (_("self"), self.default_person.handle, [])))]
        default_name = self.default_person.get_primary_name()
        active_name = active_person.get_primary_name()
        self.set_text("")
        self.render_text((_("Looking for relationship between\n") +
                           _("  <b>%s</b> (Home Person) and\n") +
                           _("  <b>%s</b> (Active Person)...\n")) %
                         (name_displayer.display_name(default_name), 
                          name_displayer.display_name(active_name)))
        yield True
        relationship = self.relationship_calc.get_one_relationship(
            self.dbstate.db, self.default_person, active_person)
        while self.queue:
            current_handle, current_path = self.queue.pop(0)
            if current_handle == active_person.handle: 
                self.total_relations_found += 1
                self.append_text(_("Found relation #%d: \n   ") % self.total_relations_found)

                self.link(name_displayer.display_name(active_name), "Person", active_person.handle)
                if relationship:
                    self.append_text(" [%s]" % relationship)
                self.selected_handles.clear()
                self.selected_handles.add(active_person.handle)
                self.pretty_print(current_path)
                self.append_text("\n")
                if self.default_person.handle != active_person.handle:
                    self.append_text(_("Paused.\nPress Continue to search for additional relations.\n"))
                    self.pause()
                    yield False
                else:
                    break
            elif current_handle in self.cache: 
                continue
            self.cache.add(current_handle)
            relatives = self.get_relatives(current_handle, current_path)
            for items in relatives:
                person_handle = items[0]
                path = items[1] 
                if person_handle is not None: # and person_handle not in self.cache: 
                    self.queue.append((person_handle, path))
            yield True
        self.append_text(_("\nSearch completed. %d relations found.") % self.total_relations_found)
        yield False

