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
Combined View - Base page
"""

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
from html import escape
import pickle

#-------------------------------------------------------------------------
#
# GTK/Gnome modules
#
#-------------------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import Gdk

#-------------------------------------------------------------------------
#
# Gramps Modules
#
#-------------------------------------------------------------------------
from gramps.gen.utils.callback import Callback
from gramps.gen.config import config
from gramps.gen.lib import (ChildRef, EventType, Family,
                            Name, Person, Surname)
from gramps.gen.db import DbTxn
from gramps.gui import widgets
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.display.place import displayer as place_displayer
from gramps.gui.editors import EditPerson, EditFamily, EditEvent
from gramps.gui.widgets.reorderfam import Reorder
from gramps.gui.selectors import SelectorFactory
from gramps.gen.errors import WindowActiveError
from gramps.gui.widgets import ShadeBox
from gramps.gui.ddtargets import DdTargets
from gramps.gen.utils.db import (get_birth_or_fallback, get_death_or_fallback,
                                 preset_name)
from gramps.gen.utils.thumbnails import get_thumbnail_image
from gramps.gen.utils.file import media_path_full
from gramps.gui.utils import open_file_with_default_application
from gramps.gen.datehandler import displayer
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.sgettext


_GenderCode = {
    Person.MALE    : '\u2642',
    Person.FEMALE  : '\u2640',
    Person.UNKNOWN : '\u2650',
    }

_RETURN = Gdk.keyval_from_name("Return")
_KP_ENTER = Gdk.keyval_from_name("KP_Enter")
_SPACE = Gdk.keyval_from_name("space")
_LEFT_BUTTON = 1
_RIGHT_BUTTON = 3

def button_activated(event, mouse_button):
    if (event.type == Gdk.EventType.BUTTON_PRESS and
        event.button == mouse_button) or \
       (event.type == Gdk.EventType.KEY_PRESS and
        event.keyval in (_RETURN, _KP_ENTER, _SPACE)):
        return True
    else:
        return False


class BasePage(Callback):

    __signals__ = {
        'object-changed' : (str, str),
        }

    def __init__(self, dbstate, uistate, addon_config):
        Callback.__init__(self)

        self.dbstate = dbstate
        self.uistate = uistate
        self._config = addon_config
        self.handle = None

        self.config_update()

    def config_update(self):
        self.use_shade = self._config.get('preferences.relation-shade')
        self.show_tags = self._config.get('preferences.show-tags')
        self.theme = self._config.get('preferences.relation-display-theme')
        self.toolbar_visible = config.get('interface.toolbar-on')

        self.show_details = self._config.get('preferences.family-details')
        self.vertical = self._config.get('preferences.vertical-details')
        self.show_siblings = self._config.get('preferences.family-siblings')

    def get_handle(self):
        return self.handle

    def edit_person_button(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            self.edit_person(handle)

    def edit_family_button(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            self.edit_family(handle)

    def edit_event_button(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            self.edit_event(handle)

    def edit_person(self, handle):
        person = self.dbstate.db.get_person_from_handle(handle)
        try:
            EditPerson(self.dbstate, self.uistate, [], person)
        except WindowActiveError:
            pass

    def edit_family(self, handle):
        family = self.dbstate.db.get_family_from_handle(handle)
        try:
            EditFamily(self.dbstate, self.uistate, [], family)
        except WindowActiveError:
            pass

    def edit_event(self, handle):
        event = self.dbstate.db.get_event_from_handle(handle)
        try:
            EditEvent(self.dbstate, self.uistate, [], event)
        except WindowActiveError:
            pass

    def make_dragbox(self, box, dragtype, handle):
        eventbox = ShadeBox(self.use_shade)
        eventbox.add(box)

        if handle is not None:
            if dragtype == 'Person':
                self._set_draggable(eventbox, handle, DdTargets.PERSON_LINK, 'gramps-person')
            elif dragtype == 'Family':
                self._set_draggable(eventbox, handle, DdTargets.FAMILY_LINK, 'gramps-family')
            elif dragtype == 'Event':
                self._set_draggable(eventbox, handle, DdTargets.EVENT, 'gramps-event')
            elif dragtype == 'Citation':
                self._set_draggable(eventbox, handle, DdTargets.CITATION_LINK, 'gramps-citation')

        return eventbox

    def _set_draggable(self, eventbox, object_h, dnd_type, stock_icon):
        """
        Register the given eventbox as a drag_source with given object_h
        """
        eventbox.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                                 [], Gdk.DragAction.COPY)
        tglist = Gtk.TargetList.new([])
        tglist.add(dnd_type.atom_drag_type,
                   dnd_type.target_flags,
                   dnd_type.app_id)
        eventbox.drag_source_set_target_list(tglist)
        eventbox.drag_source_set_icon_name(stock_icon)
        eventbox.connect('drag_data_get',
                         self._make_drag_data_get_func(object_h, dnd_type))

    def _make_drag_data_get_func(self, object_h, dnd_type):
        """
        Generate at runtime a drag_data_get function returning the given dnd_type and object_h
        """
        def drag_data_get(widget, context, sel_data, info, time):
            if info == dnd_type.app_id:
                data = (dnd_type.drag_type, id(self), object_h, 0)
                sel_data.set(dnd_type.atom_drag_type, 8, pickle.dumps(data))
        return drag_data_get

    def format_event(self, event):
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
                }
        else:
            pname = None
            dobj = None

        if dobj:
            if pname:
                return _('%(date)s in %(place)s') % value
            else:
                return '%(date)s' % value
        elif pname:
            return pname
        else:
            return ''

    def get_name(self, handle, use_gender=False):
        if handle:
            person = self.dbstate.db.get_person_from_handle(handle)
            name = name_displayer.display(person)
            if use_gender:
                gender = _GenderCode[person.gender]
            else:
                gender = ""
            return (name, gender)
        else:
            return (_("Unknown"), "")

    def get_thumbnail(self, media_ref, size):
        mobj = self.dbstate.db.get_media_from_handle(media_ref.ref)
        if mobj and mobj.get_mime_type()[0:5] == "image":
            pixbuf = get_thumbnail_image(
                            media_path_full(self.dbstate.db,
                                            mobj.get_path()),
                            rectangle=media_ref.get_rectangle(),
                            size=size)
            image = Gtk.Image()
            image.set_from_pixbuf(pixbuf)
            button = Gtk.Button()
            button.add(image)
            button.connect("clicked", lambda obj: self.view_photo(mobj))
            button.show_all()
            return button
        return None

    def view_photo(self, photo):
        """
        Open this picture in the default picture viewer.
        """
        photo_path = media_path_full(self.dbstate.db, photo.get_path())
        open_file_with_default_application(photo_path, self.uistate)

    def load_images(self, citation):
        """
        Load the primary image into the main form if it exists.
        """
        images = Gtk.Box(False, 3)

        media_list = citation.get_media_list()
        for media_ref in media_list:
            media_handle = media_ref.get_reference_handle()
            media = self.dbstate.db.get_media_from_handle(media_handle)
            full_path = media_path_full(self.dbstate.db, media.get_path())
            mime_type = media.get_mime_type()
            if mime_type and mime_type.startswith("image"):
                photo = widgets.Photo(self.uistate.screen_height() < 1000)
                photo.set_image(full_path, mime_type, media_ref.get_rectangle())
                photo.set_uistate(self.uistate, media_handle)
                images.pack_start(photo, False, False, 0)

        return images

    def get_tag_list(self, obj):
        tags_list = []
        for handle in obj.get_tag_list():
            tag = self.dbstate.db.get_tag_from_handle(handle)
            tags_list.append((tag.priority, tag.name, tag.color))
        tags_list.sort()
        return [(item[1], item[2]) for item in tags_list]

    def add_family(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            family = Family()
            person = self.dbstate.db.get_person_from_handle(self.get_handle())
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

    def add_parent_family(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            family = Family()
            person = self.dbstate.db.get_person_from_handle(self.get_handle())

            ref = ChildRef()
            ref.ref = person.handle
            family.add_child_ref(ref)

            try:
                EditFamily(self.dbstate, self.uistate, [], family)
            except WindowActiveError:
                pass

    def select_family(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            SelectFamily = SelectorFactory('Family')

            phandle = self.get_handle()
            person = self.dbstate.db.get_person_from_handle(phandle)
            skip = set(person.get_family_handle_list())

            dialog = SelectFamily(self.dbstate, self.uistate, skip=skip)
            family = dialog.run()

            if family:
                child = self.dbstate.db.get_person_from_handle(self.get_handle())

                self.dbstate.db.add_child_to_family(family, child)

    def delete_family(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            self.dbstate.db.remove_parent_from_family(self.get_handle(), handle)

    def delete_parent_family(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            self.dbstate.db.remove_child_from_family(self.get_handle(), handle)

    def add_child_to_fam(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            callback = lambda x: self.callback_add_child(x, handle)
            person = Person()
            name = Name()
            #the editor requires a surname
            name.add_surname(Surname())
            name.set_primary_surname(0)
            family = self.dbstate.db.get_family_from_handle(handle)
            father_h = family.get_father_handle()
            if father_h:
                father = self.dbstate.db.get_person_from_handle(father_h)
                if father:
                    preset_name(father, name)
            person.set_primary_name(name)
            try:
                EditPerson(self.dbstate, self.uistate, [], person,
                           callback=callback)
            except WindowActiveError:
                pass

    def callback_add_child(self, person, family_handle):
        ref = ChildRef()
        ref.ref = person.get_handle()
        family = self.dbstate.db.get_family_from_handle(family_handle)
        family.add_child_ref(ref)

        with DbTxn(_("Add Child to Family"), self.dbstate.db) as trans:
            #add parentref to child
            person.add_parent_family_handle(family_handle)
            #default relationship is used
            self.dbstate.db.commit_person(person, trans)
            #add child to family
            self.dbstate.db.commit_family(family, trans)

    def sel_child_to_fam(self, obj, event, handle, surname=None):
        if button_activated(event, _LEFT_BUTTON):
            SelectPerson = SelectorFactory('Person')
            family = self.dbstate.db.get_family_from_handle(handle)
            # it only makes sense to skip those who are already in the family
            skip_list = [family.get_father_handle(),
                         family.get_mother_handle()]
            skip_list.extend(x.ref for x in family.get_child_ref_list())

            sel = SelectPerson(self.dbstate, self.uistate, [],
                               _("Select Child"), skip=skip_list)
            person = sel.run()

            if person:
                self.callback_add_child(person, handle)

    def reorder_button_press(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            self.reorder(obj)

    def reorder(self, *obj):
        if self.handle:
            try:
                Reorder(self.dbstate, self.uistate, [], self.handle)
            except WindowActiveError:
                pass

    def _person_link(self, obj, event, handle):
        self._link(event, 'Person', handle)

    def _event_link(self, obj, event, handle):
        self._link(event, 'Event', handle)

    def _link(self, event, obj_type, handle):
        if button_activated(event, _LEFT_BUTTON):
            self.emit('object-changed', (obj_type, handle))
        elif button_activated(event, _RIGHT_BUTTON):
            self.my_menu = Gtk.Menu()
            self.my_menu.append(self.build_menu_item(obj_type, handle))
            if Gtk.get_minor_version() >= 22:
                self.my_menu.popup_at_pointer(event)
            else:
                self.my_menu.popup(None, None, None, None,
                                   event.button, event.time)

    def build_menu_item(self, obj_type, handle):

        if obj_type == 'Person':
            person = self.dbstate.db.get_person_from_handle(handle)
            name = name_displayer.display(person)
        elif obj_type == 'Event':
            event = self.dbstate.db.get_event_from_handle(handle)
            name = str(event.get_type())

        item = Gtk.ImageMenuItem(None)
        image = Gtk.Image.new_from_icon_name('gtk-edit', Gtk.IconSize.MENU)
        image.show()
        label = Gtk.Label(label=_("Edit %s") % name)
        label.show()
        label.set_halign(Gtk.Align.START)

        item.set_image(image)
        item.add(label)

        item.connect('activate', self.edit_menu, handle, obj_type)
        item.show()
        return item

    def edit_menu(self, obj, handle, obj_type):
        if obj_type == 'Person':
            person = self.dbstate.db.get_person_from_handle(handle)
            try:
                EditPerson(self.dbstate, self.uistate, [], person)
            except WindowActiveError:
                pass
        elif obj_type == 'Event':
            event = self.dbstate.db.get_event_from_handle(handle)
            try:
                EditEvent(self.dbstate, self.uistate, [], event)
            except WindowActiveError:
                pass

    def info_box(self, handle):
        if self.vertical:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        else:
            box = Gtk.Box()
            box.set_spacing(6)

        person = self.dbstate.db.get_person_from_handle(handle)
        if not person:
            return box

        birth = get_birth_or_fallback(self.dbstate.db, person)
        label1 = widgets.MarkupLabel(self.format_box(birth, EventType.BIRTH))
        box.pack_start(label1, False, False, 0)

        death = get_death_or_fallback(self.dbstate.db, person)
        label2 = widgets.MarkupLabel(self.format_box(death, EventType.DEATH))
        box.pack_start(label2, False, False, 0)

        return box

    def format_box(self, event, main_type):
        if event:
            dobj = event.get_date_object()
            pname = place_displayer.display_event(self.dbstate.db, event)
            value = {
                'abbrev': event.type.get_abbreviation(),
                'date' : displayer.display(dobj),
                'place' : pname
                }
        else:
            return ''

        if pname and not dobj.is_empty():
            info = _('%(abbrev)s %(date)s in %(place)s') % value
        else:
            info = _('%(abbrev)s %(date)s%(place)s') % value

        if event.type != main_type:
            return '<i>%s</i>' % escape(info)
        else:
            return escape(info)

    def has_children(self, p):
        """
        Return if a person has children.
        """
        for family_handle in p.get_family_handle_list():
            family = self.dbstate.db.get_family_from_handle(family_handle)
            childlist = family.get_child_ref_list()
            if childlist and len(childlist) > 0:
                return True
        return False
