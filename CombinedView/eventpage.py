# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020       Nick Hall
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
Combined View - Event page
"""

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
from html import escape

#-------------------------------------------------------------------------
#
# GTK/Gnome modules
#
#-------------------------------------------------------------------------
from gi.repository import Gtk

#-------------------------------------------------------------------------
#
# Gramps Modules
#
#-------------------------------------------------------------------------
from gramps.gui import widgets
from gramps.gen.lib import Person, EventRef
from gramps.gui.editors import EditPerson
from gramps.gui.selectors import SelectorFactory
from gramps.gen.errors import WindowActiveError
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.datehandler import get_date
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gui.uimanager import ActionGroup

from basepage import BasePage
from taglist import TagList

_ = glocale.translation.sgettext


class EventPage(BasePage):

    def __init__(self, dbstate, uistate, config):
        BasePage.__init__(self, dbstate, uistate, config)

    def obj_type(self):
        return 'Event'

    def define_actions(self, view):
        self.event_action = ActionGroup(name='Event')
        self.event_action.add_actions([
            ('AddParticipant', self.add_participant),
            ('ShareParticipant', self.select_participant)])

        view._add_action_group(self.event_action)

    def enable_actions(self, uimanager, event):
        uimanager.set_actions_visible(self.event_action, True)

    def disable_actions(self, uimanager):
        uimanager.set_actions_visible(self.event_action, False)

    def write_title(self, event):

        self.handle = event.handle

        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(0)

        # event title and edit button
        etype = str(event.get_type())
        desc = event.get_description()
        if desc:
            title = '%s (%s)' % (etype, desc)
        else:
            title = etype
        fmt = '<span size="larger" weight="bold">%s</span>'
        text = fmt % escape(title)
        label = widgets.MarkupLabel(text, halign=Gtk.Align.END)
        if self._config.get('preferences.releditbtn'):
            button = widgets.IconButton(self.edit_event_button, event.handle)
            button.set_tooltip_text(_('Edit %s') % title)
        else:
            button = None

        hbox = widgets.LinkBox(label, button)
        if self.show_tags:
            tag_list = TagList(self.get_tag_list(event))
            hbox.pack_start(tag_list, False, False, 0)
        eventbox = self.make_dragbox(hbox, 'Event', event.get_handle())
        grid.attach(eventbox, 0, 0, 2, 1)

        subgrid = Gtk.Grid()
        subgrid.set_column_spacing(12)
        subgrid.set_row_spacing(0)
        eventbox = self.make_dragbox(subgrid, 'Event', event.get_handle())
        grid.attach(eventbox, 1, 1, 1, 1)

        # Gramps ID
        subgrid.attach(widgets.BasicLabel("%s:" % _('ID')), 1, 0, 1, 1)
        label = widgets.BasicLabel(event.gramps_id)
        label.set_hexpand(True)
        subgrid.attach(label, 2, 0, 1, 1)

        # Date
        subgrid.attach(widgets.BasicLabel("%s:" % 'Date'), 1, 1, 1, 1)
        subgrid.attach(widgets.BasicLabel(get_date(event)), 2, 1, 1, 1)

        # Place
        place = place_displayer.display_event(self.dbstate.db, event)
        subgrid.attach(widgets.BasicLabel("%s:" % 'Place'), 1, 2, 1, 1)
        subgrid.attach(widgets.BasicLabel(place), 2, 2, 1, 1)

        grid.show_all()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.pack_start(grid, False, True, 0)

        # Attributes
        attrs = event.get_attribute_list()
        if len(attrs):
            ex = Gtk.Expander(label='%s:' % _('Attributes'))
            attr_grid = self.get_attribute_grid(attrs)
            ex.set_margin_start(24)
            ex.add(attr_grid)
            ex.show()
            vbox.pack_start(ex, False, True, 0)

        vbox.show_all()
        return vbox

    def write_stack(self, event, stack):
        self.write_participants(event, stack)
        self.write_citations(event, stack)

##############################################################################
#
# Participants list
#
##############################################################################

    def write_participants(self, event, stack):

        self.vbox2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        scroll = Gtk.ScrolledWindow()
        scroll.add(self.vbox2)
        scroll.show_all()
        stack.add_titled(scroll, 'participant', _('Participants'))

        roles = {}
        for item in self.dbstate.db.find_backlink_handles(event.handle,
                include_classes=['Person', 'Family']):

            handle = item[1]
            if item[0] == 'Person':
                obj = self.dbstate.db.get_person_from_handle(handle)
            elif item[0] == 'Family':
                obj = self.dbstate.db.get_family_from_handle(handle)

            for eventref in obj.get_event_ref_list():
                if eventref.ref == event.handle:
                    participant = (item[0], obj, eventref)
                    if str(eventref.role) not in roles:
                        roles[str(eventref.role)] = [participant]
                    else:
                        roles[str(eventref.role)].append(participant)

        for role in roles.keys():
            self.write_role(role, roles[role])

    def write_role(self, role, participant_list):

        title = '<span weight="bold">%s: </span>' % role
        label = widgets.MarkupLabel(title)
        self.vbox2.pack_start(label, False, False, 2)

        participants = []
        for participant in participant_list:
            obj_type, obj, eventref = participant
            order = 0
            attrs = eventref.get_attribute_list()
            for attr in attrs:
                if str(attr.get_type()) == _('Order'):
                    order = int(attr.get_value())
            if obj_type == 'Person':
                participants.append((order, obj, attrs))
            elif obj_type == 'Family':
                father_handle = obj.get_father_handle()
                if father_handle:
                    father = self.dbstate.db.get_person_from_handle(father_handle)
                    participants.append((order, father, []))
                mother_handle = obj.get_mother_handle()
                if mother_handle:
                    mother = self.dbstate.db.get_person_from_handle(mother_handle)
                    participants.append((order, mother, []))

        for person in sorted(participants, key=lambda x: x[0]):
            self.write_participant(person[1], person[2])

    def write_participant(self, person, attrs):

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        handle = person.handle
        name = self.get_name(handle, True)
        if self.has_children(person):
            emph = True
        else:
            emph = False
        link_func = self._person_link
        link_label = widgets.LinkLabel(name, link_func, handle, emph,
                                       theme=self.theme)
        link_label.set_padding(3, 0)
        if self._config.get('preferences.releditbtn'):
            button = widgets.IconButton(self.edit_person_button, handle)
            button.set_tooltip_text(_('Edit %s') % name[0])
        else:
            button = None

        hbox = Gtk.Box()
        hbox.set_spacing(6)
        hbox.pack_start(link_label, False, False, 0)
        if self.show_details:
            box = self.info_box(handle)
            if box:
                hbox.pack_start(box, False, False, 0)
        if button is not None:
            hbox.pack_start(button, False, False, 0)
        if self.show_tags:
            tag_list = TagList(self.get_tag_list(person))
            hbox.pack_start(tag_list, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        # Write attributes
        attr_grid = self.get_attribute_grid(attrs)
        attr_grid.set_margin_start(24)
        vbox.pack_start(attr_grid, False, False, 0)

        eventbox = self.make_dragbox(vbox, 'Person', handle)
        eventbox.show_all()

        self.vbox2.pack_start(eventbox, False, False, 1)

    def get_attribute_grid(self, attrs):
        grid = Gtk.Grid()
        row = 0
        for attr in attrs:
            if str(attr.get_type()) != _('Order'):
                label = widgets.BasicLabel('%s: ' % str(attr.get_type()))
                grid.attach(label, 0, row, 1, 1)
                label = widgets.BasicLabel(attr.get_value())
                grid.attach(label, 1, row, 1, 1)
                row += 1
        grid.show_all()
        return grid

##############################################################################
#
# Citations list
#
##############################################################################

    def write_citations(self, event, stack):

        self.vbox2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        scroll = Gtk.ScrolledWindow()
        scroll.add(self.vbox2)
        scroll.show_all()
        stack.add_titled(scroll, 'citation', _('Citations'))

        for handle in event.get_citation_list():
            self.write_full_citation(handle)

    def write_full_citation(self, chandle):

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        citation = self.dbstate.db.get_citation_from_handle(chandle)
        shandle = citation.get_reference_handle()
        source = self.dbstate.db.get_source_from_handle(shandle)
        heading = source.get_title() + ' ' + citation.get_page()

        vbox.pack_start(widgets.BasicLabel(heading), False, False, 0)

        hbox = self.load_images(citation)
        vbox.pack_start(hbox, False, False, 0)

        eventbox = self.make_dragbox(vbox, 'Citation', chandle)
        eventbox.show_all()

        self.vbox2.pack_start(eventbox, False, False, 1)

##############################################################################
#
# Toolbar actions
#
##############################################################################

    def edit_active(self, *obj):
        self.edit_event(self.handle)

    def select_participant(self, *obj):
        SelectPerson = SelectorFactory('Person')
        dialog = SelectPerson(self.dbstate, self.uistate)
        person = dialog.run()
        if person is None:
            return

        ref = EventRef()
        ref.ref = self.handle
        person.add_event_ref(ref)

        try:
            EditPerson(self.dbstate, self.uistate, [], person)
        except WindowActiveError:
            pass

    def add_participant(self, *obj):
        person = Person()
        ref = EventRef()
        ref.ref = self.handle
        person.add_event_ref(ref)

        try:
            EditPerson(self.dbstate, self.uistate, [], person)
        except WindowActiveError:
            pass

    def add_tag(self, trans, object_handle, tag_handle):
        """
        Add the given tag to the active object.
        """
        event = self.dbstate.db.get_event_from_handle(object_handle)
        event.add_tag(tag_handle)
        self.dbstate.db.commit_event(event, trans)

