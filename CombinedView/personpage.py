# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2001-2007  Donald N. Allingham
# Copyright (C) 2009-2010  Gary Burton
# Copyright (C) 2015-2016  Nick Hall
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
Combined View - Person page
"""

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
from html import escape
from operator import itemgetter
import re

#-------------------------------------------------------------------------
#
# GTK/Gnome modules
#
#-------------------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import Pango

#-------------------------------------------------------------------------
#
# Gramps Modules
#
#-------------------------------------------------------------------------
from taglist import TagList
from combined_timeline import Timeline
from basepage import BasePage

from gramps.gen.lib.date import Today
from gramps.gui.display import display_url
from gramps.gui.uimanager import ActionGroup

from gramps.gen.config import config
from gramps.gen.lib import (EventRoleType, EventType, FamilyRelType, Person, Family, ChildRef)
from gramps.gui.editors import EditFamily
from gramps.gen.errors import WindowActiveError
from gramps.gui.selectors import SelectorFactory
from gramps.gui import widgets
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.utils.db import (get_birth_or_fallback, get_death_or_fallback)
from gramps.gen.utils.db import get_participant_from_event
from gramps.gen.relationship import get_relationship_calculator
from gramps.gen.utils.alive import probably_alive
from gramps.gen.utils.thumbnails import (SIZE_NORMAL, SIZE_LARGE)
from gramps.gui.widgets.styledtexteditor import StyledTextEditor
from gramps.gen.datehandler import displayer
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.sgettext


_GenderCode = {
    Person.MALE    : '\u2642',
    Person.FEMALE  : '\u2640',
    Person.UNKNOWN : '\u2650',
    }

URL_MATCH = re.compile(r'https?://[^\s]+')

class PersonPage(BasePage):

    def __init__(self, dbstate, uistate, config):
        BasePage.__init__(self, dbstate, uistate, config)
        self.reorder_sensitive = True
        self.expanders = {}

    def obj_type(self):
        return 'Person'

    def define_actions(self, view):
        self.order_action = ActionGroup(name='ChangeOrder')
        self.order_action.add_actions([
            ('ChangeOrder', self.reorder)])

        self.family_action = ActionGroup(name='Family')
        self.family_action.add_actions([
            ('AddSpouse', self.add_spouse),
            ('AddParents', self.add_parents),
            ('ShareFamily', self.select_parents)])

        view._add_action_group(self.order_action)
        view._add_action_group(self.family_action)

    def enable_actions(self, uimanager, person):
        uimanager.set_actions_visible(self.family_action, True)
        uimanager.set_actions_visible(self.order_action, True)

    def disable_actions(self, uimanager):
        uimanager.set_actions_visible(self.family_action, False)
        uimanager.set_actions_visible(self.order_action, False)

    def write_title(self, person):

        self.handle = person.handle

        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(0)

        # name and edit button
        name = name_displayer.display(person)
        fmt = '<span size="larger" weight="bold">%s</span>'
        text = fmt % escape(name)
        label = widgets.DualMarkupLabel(text, _GenderCode[person.gender],
                                        halign=Gtk.Align.END)
        if self._config.get('preferences.releditbtn'):
            button = widgets.IconButton(self.edit_person_button,
                                        person.handle)
            button.set_tooltip_text(_('Edit %s') % name)
        else:
            button = None


        hbox = widgets.LinkBox(label, button)
        if self.show_tags:
            tag_list = TagList(self.get_tag_list(person))
            hbox.pack_start(tag_list, False, False, 0)
        eventbox = self.make_dragbox(hbox, 'Person', person.get_handle())
        grid.attach(eventbox, 0, 0, 2, 1)

        subgrid = Gtk.Grid()
        subgrid.set_column_spacing(12)
        subgrid.set_row_spacing(0)
        eventbox = self.make_dragbox(subgrid, 'Person', person.get_handle())
        grid.attach(eventbox, 1, 1, 1, 1)

        # GRAMPS ID
        subgrid.attach(widgets.BasicLabel("%s:" % _('ID')), 1, 0, 1, 1)
        label = widgets.BasicLabel(person.gramps_id)
        label.set_hexpand(True)
        subgrid.attach(label, 2, 0, 1, 1)

        # Birth event.
        birth = get_birth_or_fallback(self.dbstate.db, person)
        if birth:
            birth_title = birth.get_type()
        else:
            birth_title = _("Birth")

        subgrid.attach(widgets.BasicLabel("%s:" % birth_title), 1, 1, 1, 1)
        subgrid.attach(widgets.BasicLabel(self.format_event(birth)), 2, 1, 1, 1)

        death = get_death_or_fallback(self.dbstate.db, person)
        if death:
            death_title = death.get_type()
        else:
            death_title = _("Death")

        showed_death = False
        if birth:
            birth_date = birth.get_date_object()
            if (birth_date and birth_date.get_valid()):
                if death:
                    death_date = death.get_date_object()
                    if (death_date and death_date.get_valid()):
                        age = death_date - birth_date
                        subgrid.attach(widgets.BasicLabel("%s:" % death_title),
                                      1, 2, 1, 1)
                        subgrid.attach(widgets.BasicLabel("%s (%s)" %
                                                         (self.format_event(death), age),
                                                         Pango.EllipsizeMode.END),
                                      2, 2, 1, 1)
                        showed_death = True
                if not showed_death:
                    age = Today() - birth_date
                    if probably_alive(person, self.dbstate.db):
                        subgrid.attach(widgets.BasicLabel("%s:" % _("Alive")),
                                      1, 2, 1, 1)
                        subgrid.attach(widgets.BasicLabel("(%s)" % age, Pango.EllipsizeMode.END),
                                      2, 2, 1, 1)
                    else:
                        subgrid.attach(widgets.BasicLabel("%s:" % _("Death")),
                                      1, 2, 1, 1)
                        subgrid.attach(widgets.BasicLabel("%s (%s)" % (_("unknown"), age),
                                                         Pango.EllipsizeMode.END),
                                      2, 2, 1, 1)
                    showed_death = True

        if not showed_death:
            subgrid.attach(widgets.BasicLabel("%s:" % death_title),
                          1, 2, 1, 1)
            subgrid.attach(widgets.BasicLabel(self.format_event(death)),
                          2, 2, 1, 1)

        mbox = Gtk.Box()
        mbox.add(grid)

        # image
        image_list = person.get_media_list()
        if image_list:
            button = self.get_thumbnail(image_list[0], size=SIZE_NORMAL)
            if button:
                mbox.pack_end(button, False, True, 0)
        mbox.show_all()
        return mbox

    def write_stack(self, person, stack):
        self.write_families(person, stack)
        self.write_events(person, stack)
        self.write_album(person, stack)
        self.write_timeline(person, stack)
        self.write_associations(person, stack)


##############################################################################
#
# Families list
#
##############################################################################

    def expander_toggled(self, expander, handle):
        self.expanders[handle] = not expander.get_expanded()

    def write_families(self, person, stack):

        self.vbox2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        scroll = Gtk.ScrolledWindow()
        scroll.add(self.vbox2)
        scroll.show_all()
        stack.add_titled(scroll, 'relationship', _('Relationships'))

        family_handle_list = person.get_parent_family_handle_list()

        self.reorder_sensitive = len(family_handle_list)> 1

        if family_handle_list:
            for family_handle in family_handle_list:
                if family_handle:
                    self.write_parents(family_handle, person)
        else:
            heading = self.write_label(_('Parents'), None, True)
            self.vbox2.pack_start(heading, False, True, 0)

        family_handle_list = person.get_family_handle_list()

        if not self.reorder_sensitive:
            self.reorder_sensitive = len(family_handle_list)> 1

        if family_handle_list:
            for family_handle in family_handle_list:
                if family_handle:
                    self.write_family(family_handle, person)

        self.vbox2.show_all()

    def write_parents(self, family_handle, person = None):
        family = self.dbstate.db.get_family_from_handle(family_handle)
        if not family:
            return

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        heading = self.write_label(_('Parents'), family, True)
        vbox.pack_start(heading, False, False, 1)
        f_handle = family.get_father_handle()
        box = self.write_person(_('Father'), f_handle)
        ebox = self.make_dragbox(box, 'Person', f_handle)
        vbox.pack_start(ebox, False, False, 1)
        m_handle = family.get_mother_handle()
        box = self.write_person(_('Mother'), m_handle)
        ebox = self.make_dragbox(box, 'Person', m_handle)
        vbox.pack_start(ebox, False, False, 1)

        if self.show_siblings:
            active = self.get_handle()

            count = len(family.get_child_ref_list())
            ex2 = Gtk.Expander(label='%s (%s):' % (_('Siblings'), count))
            ex2.connect("activate", self.expander_toggled, family_handle)
            ex2.set_expanded(self.expanders.get(family_handle, True))
            ex2.set_margin_start(24)
            vbox.pack_start(ex2, False, False, 6)

            vbox2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            hbox = Gtk.Box()
            addchild = widgets.IconButton(self.add_child_to_fam,
                                          family.handle,
                                          'list-add')
            addchild.set_tooltip_text(_('Add new child to family'))
            selchild = widgets.IconButton(self.sel_child_to_fam,
                                          family.handle,
                                          'gtk-index')
            selchild.set_tooltip_text(_('Add existing child to family'))
            hbox.pack_start(addchild, False, True, 0)
            hbox.pack_start(selchild, False, True, 0)

            vbox2.pack_start(hbox, False, False, 0)
            i = 1
            child_list = [ref.ref for ref in family.get_child_ref_list()]
            for child_handle in child_list:
                child_should_be_linked = (child_handle != active)
                widget = self.write_child(child_handle, i, child_should_be_linked)
                vbox2.pack_start(widget, True, True, 1)
                i += 1

            ex2.add(vbox2)

        self.vbox2.pack_start(vbox, False, True, 0)

    def write_family(self, family_handle, person = None):
        family = self.dbstate.db.get_family_from_handle(family_handle)
        if family is None:
            from gramps.gui.dialog import WarningDialog
            WarningDialog(
                _('Broken family detected'),
                _('Please run the Check and Repair Database tool'),
                parent=self.uistate.window)
            return

        father_handle = family.get_father_handle()
        mother_handle = family.get_mother_handle()
        if self.get_handle() == father_handle:
            handle = mother_handle
        else:
            handle = father_handle

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        heading = self.write_label(_('Family'), family, False)
        vbox.pack_start(heading, False, False, 1)

        if handle or family.get_relationship() != FamilyRelType.UNKNOWN:
            box = self.write_person(_('Spouse'), handle)
            if not self.write_relationship_events(box, family):
                self.write_relationship(box, family)
            ebox = self.make_dragbox(box, 'Person', handle)
            vbox.pack_start(ebox, False, False, 1)

        count = len(family.get_child_ref_list())
        ex2 = Gtk.Expander(label='%s (%s):' % (_('Children'), count))
        ex2.connect("activate", self.expander_toggled, family_handle)
        ex2.set_expanded(self.expanders.get(family_handle, True))
        ex2.set_margin_start(24)
        vbox.pack_start(ex2, False, False, 6)

        vbox2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        hbox = Gtk.Box()
        addchild = widgets.IconButton(self.add_child_to_fam,
                                      family.handle,
                                      'list-add')
        addchild.set_tooltip_text(_('Add new child to family'))
        selchild = widgets.IconButton(self.sel_child_to_fam,
                                      family.handle,
                                      'gtk-index')
        selchild.set_tooltip_text(_('Add existing child to family'))
        hbox.pack_start(addchild, False, True, 0)
        hbox.pack_start(selchild, False, True, 0)

        vbox2.pack_start(hbox, False, False, 0)

        i = 1
        child_list = family.get_child_ref_list()
        for child_ref in child_list:
            widget = self.write_child(child_ref.ref, i, True)
            vbox2.pack_start(widget, True, True, 1)
            i += 1

        ex2.add(vbox2)

        self.vbox2.pack_start(vbox, False, True, 0)

    def write_label(self, title, family, is_parent):
        """
        Write a Family header row
        Shows following elements:
        (Parents/Family title label, Family gramps_id, and add-choose-edit-delete buttons)
        """
        hbox = Gtk.Box()
        if family:
            msg = '<b>%s (%s):</b>' % (escape(title), escape(family.gramps_id))
        else:
            msg = '<b>%s:</b>' % escape(title)
        label = widgets.MarkupLabel(msg, halign=Gtk.Align.START)
        hbox.pack_start(label, False, True, 0)

        bbox = Gtk.Box()
        if is_parent:
            call_fcn = self.add_parent_family
            del_fcn = self.delete_parent_family
            add_msg = _('Add a new set of parents')
            sel_msg = _('Add person as child to an existing family')
            edit_msg = _('Edit parents')
            ord_msg = _('Reorder parents')
            del_msg = _('Remove person as child of these parents')
        else:
            add_msg = _('Add a new family with person as parent')
            sel_msg = None
            edit_msg = _('Edit family')
            ord_msg = _('Reorder families')
            del_msg = _('Remove person as parent in this family')
            call_fcn = self.add_family
            del_fcn = self.delete_family

        if not self.toolbar_visible and not self.dbstate.db.readonly:
            # Show edit-Buttons if toolbar is not visible
            if self.reorder_sensitive:
                add = widgets.IconButton(self.reorder_button_press, None,
                                         'view-sort-ascending')
                add.set_tooltip_text(ord_msg)
                bbox.pack_start(add, False, True, 0)

            add = widgets.IconButton(call_fcn, None, 'list-add')
            add.set_tooltip_text(add_msg)
            bbox.pack_start(add, False, True, 0)

            if is_parent:
                add = widgets.IconButton(self.select_family, None,
                                         'gtk-index')
                add.set_tooltip_text(sel_msg)
                bbox.pack_start(add, False, True, 0)

        if family:
            edit = widgets.IconButton(self.edit_family_button,
                                      family.handle, 'gtk-edit')
            edit.set_tooltip_text(edit_msg)
            bbox.pack_start(edit, False, True, 0)
            if not self.dbstate.db.readonly:
                delete = widgets.IconButton(del_fcn, family.handle,
                                            'list-remove')
                delete.set_tooltip_text(del_msg)
                bbox.pack_start(delete, False, True, 0)

        hbox.pack_start(bbox, False, True, 6)

        if family:
            if self.show_tags:
                tag_list = TagList(self.get_tag_list(family))
                hbox.pack_start(tag_list, False, False, 3)
            eventbox = self.make_dragbox(hbox, 'Family', family.handle)
            return eventbox
        else:
            return hbox

    def write_person(self, title, handle):
        """
        Create and show a person cell.
        """
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        if handle:
            name = self.get_name(handle, True)
            person = self.dbstate.db.get_person_from_handle(handle)
            parent = len(person.get_parent_family_handle_list()) > 0
            if parent:
                emph = True
            else:
                emph = False
            link_label = widgets.LinkLabel(name, self._person_link,
                                           handle, emph, theme=self.theme)
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
            vbox.pack_start(hbox, True, True, 0)
        else:
            link_label = Gtk.Label(label=_('Unknown'))
            link_label.set_halign(Gtk.Align.START)
            link_label.show()
            vbox.pack_start(link_label, True, True, 0)

        return vbox

    def write_child(self, handle, index, child_should_be_linked):
        """
        Write a child cell (used for children and siblings of active person)
        """
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        parent = self.has_children(
                    self.dbstate.db.get_person_from_handle(handle))
        emph = False
        if child_should_be_linked and parent:
            emph = True
        elif child_should_be_linked and not parent:
            emph = False
        elif parent and not child_should_be_linked:
            emph = None

        if child_should_be_linked:
            link_func = self._person_link
        else:
            link_func = None

        name = self.get_name(handle, True)
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
        l = widgets.BasicLabel("%d." % index)
        l.set_width_chars(3)
        l.set_halign(Gtk.Align.END)
        hbox.pack_start(l, False, False, 0)
        person = self.dbstate.db.get_person_from_handle(handle)
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
        hbox.show()
        vbox.pack_start(hbox, True, True, 0)

        ev = self.make_dragbox(vbox, 'Person', handle)

        if not child_should_be_linked:
            frame = Gtk.Frame()
            frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
            frame.add(ev)
            return frame
        else:
            return ev

    def write_relationship(self, box, family):
        msg = _('Relationship type: %s') % escape(str(family.get_relationship()))
        box.add(widgets.MarkupLabel(msg))

    def write_relationship_events(self, vbox, family):
        value = False
        for event_ref in family.get_event_ref_list():
            handle = event_ref.ref
            event = self.dbstate.db.get_event_from_handle(handle)
            if (event and event.get_type().is_relationship_event() and
                (event_ref.get_role() == EventRoleType.FAMILY or
                 event_ref.get_role() == EventRoleType.PRIMARY)):
                self.write_event_ref(vbox, event.get_type().string, event)
                value = True
        return value

    def write_event_ref(self, vbox, ename, event):
        if event:
            dobj = event.get_date_object()
            phandle = event.get_place_handle()
            if phandle:
                pname = place_displayer.display_event(self.dbstate.db, event)
            else:
                pname = None

            value = {
                'date' : displayer.display(dobj),
                'place' : pname,
                'event_type' : ename,
                }
        else:
            pname = None
            dobj = None
            value = { 'event_type' : ename, }

        if dobj:
            if pname:
                self.write_data(
                    vbox, _('%(event_type)s: %(date)s in %(place)s') %
                    value)
            else:
                self.write_data(
                    vbox, _('%(event_type)s: %(date)s') % value)
        elif pname:
            self.write_data(
                vbox, _('%(event_type)s: %(place)s') % value)
        else:
            self.write_data(
                vbox, '%(event_type)s:' % value)

    def write_data(self, box, title):
        box.add(widgets.BasicLabel(title))

##############################################################################
#
# Events list
#
##############################################################################

    def write_events(self, person, stack):

        self.vbox2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        scroll = Gtk.ScrolledWindow()
        scroll.add(self.vbox2)
        scroll.show_all()
        stack.add_titled(scroll, 'event', _('Events'))

        events = []
        # Personal events
        for index, event_ref in enumerate(person.get_event_ref_list()):
            event = self.dbstate.db.get_event_from_handle(event_ref.ref)
            sortval = event.get_date_object().get_sort_value()
            events.append(((sortval, index), event_ref, None))

        # Family events
        for family_handle in person.get_family_handle_list():
            family = self.dbstate.db.get_family_from_handle(family_handle)
            father_handle = family.get_father_handle()
            mother_handle = family.get_mother_handle()
            spouse = None
            if father_handle == person.handle:
                if mother_handle:
                    spouse = self.dbstate.db.get_person_from_handle(mother_handle)
            else:
                if father_handle:
                    spouse = self.dbstate.db.get_person_from_handle(father_handle)
            for event_ref in family.get_event_ref_list():
                event = self.dbstate.db.get_event_from_handle(event_ref.ref)
                sortval = event.get_date_object().get_sort_value()
                events.append(((sortval, 0), event_ref, spouse))

        # Write all events sorted by date
        for index, event in enumerate(sorted(events, key=itemgetter(0))):
            self.write_event(event[1], event[2], index+1)

    def write_event(self, event_ref, spouse, index):
        handle = event_ref.ref
        event = self.dbstate.db.get_event_from_handle(handle)
        etype = str(event.get_type())
        desc = event.get_description()
        who = get_participant_from_event(self.dbstate.db, handle)

        title = etype
        if desc:
            title = '%s (%s)' % (title, desc)
        if spouse:
            spouse_name = name_displayer.display(spouse)
            title = '%s - %s' % (title, spouse_name)

        role = event_ref.get_role()
        if role in (EventRoleType.PRIMARY, EventRoleType.FAMILY):
            emph = True
        else:
            emph = False
            title = '%s of %s' % (title, who)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        link_func = self._event_link
        name = (title, None)
        handle = event_ref.ref
        link_label = widgets.LinkLabel(name, link_func, handle, emph,
                                       theme=self.theme)
        link_label.set_padding(3, 0)
        link_label.set_tooltip_text(_('Click to make this event active'))
        if self._config.get('preferences.releditbtn'):
            button = widgets.IconButton(self.edit_event_button, handle)
            button.set_tooltip_text(_('Edit %s') % name[0])
        else:
            button = None

        hbox = widgets.LinkBox(link_label, button)
        if self.show_tags:
            tag_list = TagList(self.get_tag_list(event))
            hbox.pack_start(tag_list, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        line2 = self.format_event(event)
        vbox.pack_start(widgets.BasicLabel(line2), False, False, 0)

        for handle in event.get_citation_list():
            self.write_citation(vbox, handle)

        eventbox = self.make_dragbox(vbox, 'Event', handle)
        eventbox.show_all()
        self.vbox2.pack_start(eventbox, False, False, 1)

    def write_citation(self, vbox, chandle):
        citation = self.dbstate.db.get_citation_from_handle(chandle)
        shandle = citation.get_reference_handle()
        source = self.dbstate.db.get_source_from_handle(shandle)
        heading = source.get_title()
        page = citation.get_page()
        if page:
            heading += ' \u2022 ' + page

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        url_label = self.get_url(citation)
        if url_label:
            box.pack_start(url_label, False, False, 0)
        hbox = self.load_images(citation)
        box.pack_start(hbox, False, False, 0)

        if len(hbox.get_children()) > 0 or url_label:
            exp = Gtk.Expander(label=heading)
            exp.add(box)
            vbox.pack_start(exp, False, False, 0)
        else:
            label = widgets.BasicLabel(heading)
            vbox.pack_start(label, False, False, 0)

    def get_url(self, citation):
        for handle in citation.get_note_list():
            note = self.dbstate.db.get_note_from_handle(handle)
            text = note.get()
            url_match = re.compile(r'https?://[^\s]+')
            result = URL_MATCH.search(text)
            if result:
                url = result.group(0)
                link_func = lambda x,y,z: display_url(url)
                name = (url, None)
                link_label = widgets.LinkLabel(name, link_func, None, False,
                                       theme=self.theme)
                link_label.set_tooltip_text(_('Click to visit this link'))
                return link_label
        return None


##############################################################################
#
# Album
#
##############################################################################

    def write_album(self, person, stack):

        self.vbox2 = Gtk.Grid(orientation=Gtk.Orientation.VERTICAL)

        scroll = Gtk.ScrolledWindow()
        scroll.add(self.vbox2)
        scroll.show_all()
        stack.add_titled(scroll, 'album', _('Album'))

        self.write_media(person.get_media_list(), None)

        for event_ref in person.get_event_ref_list():
            event = self.dbstate.db.get_event_from_handle(event_ref.ref)

            self.write_media(event.get_media_list(), event)

        for family_handle in person.get_family_handle_list():
            family = self.dbstate.db.get_family_from_handle(family_handle)

            self.write_media(family.get_media_list(), None)

            for event_ref in family.get_event_ref_list():
                event = self.dbstate.db.get_event_from_handle(event_ref.ref)

                self.write_media(event.get_media_list(), event)

    def write_media(self, media_list, event):
        for media_ref in media_list:

            mobj = self.dbstate.db.get_media_from_handle(media_ref.ref)
            button = self.get_thumbnail(media_ref, size=SIZE_LARGE)
            if button:

                self.vbox2.add(button)

                vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

                if event:
                    etype = str(event.get_type())
                    label = Gtk.Label(etype)
                    vbox.pack_start(label, False, False, 0)
                    who = get_participant_from_event(self.dbstate.db, event.handle)
                    label = Gtk.Label(who)
                    vbox.pack_start(label, False, False, 0)
                    date_place = self.format_event(event)
                    label = Gtk.Label(date_place)
                    vbox.pack_start(label, False, False, 0)

                notes = mobj.get_note_list()
                if len(notes) > 0:
                    note = self.dbstate.db.get_note_from_handle(notes[0])
                    texteditor = StyledTextEditor()
                    texteditor.set_editable(False)
                    texteditor.set_wrap_mode(Gtk.WrapMode.WORD)
                    texteditor.set_text(note.get_styledtext())
                    texteditor.set_hexpand(True)
                    texteditor.show()
                    vbox.pack_start(texteditor, True, True, 0)
                    vbox.show_all()

                self.vbox2.attach_next_to(vbox, button,
                                          Gtk.PositionType.RIGHT, 1, 1)

##############################################################################
#
# Timeline
#
##############################################################################

    def write_timeline(self, person, stack):

        grid = Gtk.Grid(orientation=Gtk.Orientation.VERTICAL)

        scroll = Gtk.ScrolledWindow()
        scroll.add(grid)
        scroll.show_all()
        stack.add_titled(scroll, 'timeline', _('Timeline'))

        events = []
        start_date = None
        # Personal events
        for index, event_ref in enumerate(person.get_event_ref_list()):
            event = self.dbstate.db.get_event_from_handle(event_ref.ref)
            date = event.get_date_object()
            if (start_date is None and event_ref.role.is_primary() and
                (event.type.is_birth_fallback() or
                 event.type == EventType.BIRTH)):
                start_date = date
            sortval = date.get_sort_value()
            events.append(((sortval, index), event_ref, None))

        # Family events
        for family_handle in person.get_family_handle_list():
            family = self.dbstate.db.get_family_from_handle(family_handle)
            father_handle = family.get_father_handle()
            mother_handle = family.get_mother_handle()
            spouse = None
            if father_handle == person.handle:
                if mother_handle:
                    spouse = self.dbstate.db.get_person_from_handle(mother_handle)
            else:
                if father_handle:
                    spouse = self.dbstate.db.get_person_from_handle(father_handle)
            for event_ref in family.get_event_ref_list():
                event = self.dbstate.db.get_event_from_handle(event_ref.ref)
                sortval = event.get_date_object().get_sort_value()
                events.append(((sortval, 0), event_ref, spouse))

        # Write all events sorted by date
        for index, event in enumerate(sorted(events, key=itemgetter(0))):
            self.write_node(grid, event[1], event[2], index+1, start_date)

        grid.show_all()

    def write_node(self, grid, event_ref, spouse, index, start_date):
        handle = event_ref.ref
        event = self.dbstate.db.get_event_from_handle(handle)
        etype = str(event.get_type())
        desc = event.get_description()
        who = get_participant_from_event(self.dbstate.db, handle)

        title = etype
        if desc:
            title = '%s (%s)' % (title, desc)
        if spouse:
            spouse_name = name_displayer.display(spouse)
            title = '%s - %s' % (title, spouse_name)

        role = event_ref.get_role()
        if role in (EventRoleType.PRIMARY, EventRoleType.FAMILY):
            emph = True
        else:
            emph = False
            title = '%s of %s' % (title, who)

        vbox1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        link_func = self._event_link
        name = (title, None)
        handle = event_ref.ref
        link_label = widgets.LinkLabel(name, link_func, handle, emph,
                                       theme=self.theme)
        link_label.set_padding(3, 0)
        link_label.set_tooltip_text(_('Click to make this event active'))
        if self._config.get('preferences.releditbtn'):
            button = widgets.IconButton(self.edit_event_button, handle)
            button.set_tooltip_text(_('Edit %s') % name[0])
        else:
            button = None

        hbox = widgets.LinkBox(link_label, button)
        if self.show_tags:
            tag_list = TagList(self.get_tag_list(event))
            hbox.pack_start(tag_list, False, False, 0)
        vbox1.pack_start(hbox, False, False, 0)

        pname = place_displayer.display_event(self.dbstate.db, event)
        vbox1.pack_start(widgets.BasicLabel(pname), False, False, 0)
        vbox1.set_vexpand(False)
        vbox1.set_valign(Gtk.Align.CENTER)
        vbox1.show_all()

        eventbox = self.make_dragbox(vbox1, 'Event', handle)
        eventbox.set_hexpand(True)
        eventbox.set_vexpand(False)
        eventbox.set_valign(Gtk.Align.CENTER)
        eventbox.set_margin_top(1)
        eventbox.set_margin_bottom(1)
        eventbox.show_all()

        vbox2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        dobj = event.get_date_object()
        date = widgets.BasicLabel(displayer.display(dobj))
        vbox2.pack_start(date, False, False, 0)
        if start_date is not None:
            age_precision = config.get('preferences.age-display-precision')
            diff = (dobj - start_date).format(precision=age_precision)
            age = widgets.BasicLabel(diff)
            vbox2.pack_start(age, False, False, 0)
        vbox2.set_valign(Gtk.Align.CENTER)
        grid.add(vbox2)

        tl = Timeline()
        grid.attach_next_to(tl, vbox2, Gtk.PositionType.RIGHT, 1, 1)

        grid.attach_next_to(eventbox, tl, Gtk.PositionType.RIGHT, 1, 1)


##############################################################################
#
# Associations
#
##############################################################################

    def write_associations(self, person, stack):

        self.vbox2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        scroll = Gtk.ScrolledWindow()
        scroll.add(self.vbox2)
        scroll.show_all()
        stack.add_titled(scroll, 'associations', _('Associations'))

        for person_ref in person.get_person_ref_list():
            self.write_association(person, person_ref)


    def write_association(self, person1, person_ref):

        vbox = self.write_person('assoc', person_ref.ref)

        assoc = Gtk.Label(_('Association') + _(': ') + person_ref.rel)
        assoc.set_halign(Gtk.Align.START)
        vbox.pack_start(assoc, False, False, 0)

        calc = get_relationship_calculator()
        person2 = self.dbstate.db.get_person_from_handle(person_ref.ref)
        rel_txt = calc.get_one_relationship(self.dbstate.db, person1, person2)
        rel = Gtk.Label(_('Relationship') + _(': ') + rel_txt)
        rel.set_halign(Gtk.Align.START)
        vbox.pack_start(rel, False, False, 0)

        eventbox = self.make_dragbox(vbox, 'Person', person_ref.ref)
        eventbox.show_all()
        self.vbox2.pack_start(eventbox, False, False, 1)

##############################################################################
#
# Toolbar actions
#
##############################################################################

    def edit_active(self, *obj):
        self.edit_person(self.handle)

    def add_spouse(self, *obj):
        family = Family()
        person = self.dbstate.db.get_person_from_handle(self.handle)

        if not person:
            return

        if person.gender == Person.MALE:
            family.set_father_handle(person.handle)
        else:
            family.set_mother_handle(person.handle)

        try:
            EditFamily(self.dbstate, self.uistate, [], family)
        except WindowActiveError:
            pass

    def select_parents(self, *obj):
        SelectFamily = SelectorFactory('Family')

        phandle = self.handle
        person = self.dbstate.db.get_person_from_handle(phandle)
        skip = set(person.get_family_handle_list()+
                   person.get_parent_family_handle_list())

        dialog = SelectFamily(self.dbstate, self.uistate, skip=skip)
        family = dialog.run()

        if family:
            child = self.dbstate.db.get_person_from_handle(self.handle)

            self.dbstate.db.add_child_to_family(family, child)

    def add_parents(self, *obj):
        family = Family()
        person = self.dbstate.db.get_person_from_handle(self.handle)

        if not person:
            return

        ref = ChildRef()
        ref.ref = person.handle
        family.add_child_ref(ref)

        try:
            EditFamily(self.dbstate, self.uistate, [], family)
        except WindowActiveError:
            pass

    def add_tag(self, trans, object_handle, tag_handle):
        """
        Add the given tag to the active object.
        """
        person = self.dbstate.db.get_person_from_handle(object_handle)
        person.add_tag(tag_handle)
        self.dbstate.db.commit_person(person, trans)

