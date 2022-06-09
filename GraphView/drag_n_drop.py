#!/usr/bin/env python3

import pickle
from gi.repository import Gtk, Gdk

from gramps.gen.db import DbTxn
from gramps.gen.display.name import displayer
from gramps.gen.utils.libformatting import FormattingHelper
from gramps.gen.lib import ChildRef, PersonRef, Person, Family
from gramps.gui.ddtargets import DdTargets

from gramps.gui.editors import EditPersonRef, EditFamily
from gramps.gen.errors import WindowActiveError

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
ngettext = glocale.translation.ngettext

gtk_version = float("%s.%s" % (Gtk.MAJOR_VERSION, Gtk.MINOR_VERSION))


class DragAndDrop():
    """
    Add Drag-n-Drop feature to GraphView addon.
    """
    def __init__(self, canvas, dbstate, uistate, h_adj, v_adj):
        self.drag_person = None
        self.drag_family = None

        self.h_adj = h_adj
        self.v_adj = v_adj
        self.dbstate = dbstate
        self.uistate = uistate
        self.canvas = canvas
        self.canvas.connect("drag_data_get", self.drag_data_get)
        self.canvas.connect("drag_begin", self.begin)
        self.canvas.connect("drag_end", self.stop)

        self.drag_enabled = False
        self.enable_dnd(True)

        # add drop support
        self.canvas.drag_dest_set(
            Gtk.DestDefaults.ALL,
            [],
            Gdk.DragAction.COPY
        )
        tglist = Gtk.TargetList.new([])
        tglist.add(DdTargets.PERSON_LINK.atom_drag_type,
                   DdTargets.PERSON_LINK.target_flags,
                   DdTargets.PERSON_LINK.app_id,
                   )
        # TODO: add other targets. For now only person drop supported.
        self.canvas.drag_dest_set_target_list(tglist)
        self.canvas.connect("drag-motion", self.drag_motion)
        self.canvas.connect("drag-data-received", self.drag_data_receive)

        self.item_cache = {}

    def enable_dnd(self, state):
        """
        Enable or disable drag-n-drop for canvas widget.
        """
        if self.drag_enabled == state:
            return
        if state:
            self.canvas.drag_source_set(
                Gdk.ModifierType.BUTTON1_MASK,
                [],
                Gdk.DragAction.COPY)
        else:
            self.canvas.drag_source_unset()
        self.drag_enabled = state

    def begin(self, widget, context):
        """
        Called when drag is start.
        """
        tgs = [x.name() for x in context.list_targets()]
        # set icon depending on person or family drag
        if DdTargets.PERSON_LINK.drag_type in tgs:
            Gtk.drag_set_icon_name(context, 'gramps-person', 0, 0)
        if DdTargets.FAMILY_LINK.drag_type in tgs:
            Gtk.drag_set_icon_name(context, 'gramps-family', 0, 0)

        self.item_cache.clear()

    def stop(self, *args):
        """
        Called when drag is end.
        """
        self.drag_person = None
        self.drag_family = None

    def set_target(self, node_class, handle):
        """
        Set targets for drag-n-drop.
        """
        self.stop()
        tglist = Gtk.TargetList.new([])
        if node_class == 'node':
            self.drag_person = self.dbstate.db.get_person_from_handle(handle)
            tglist.add(DdTargets.PERSON_LINK.atom_drag_type,
                       DdTargets.PERSON_LINK.target_flags,
                       DdTargets.PERSON_LINK.app_id,
                       )
            # allow drag to a text document, info on drag_get will be 0
            tglist.add_text_targets(0)
        elif node_class == 'familynode':
            self.drag_family = self.dbstate.db.get_family_from_handle(handle)
            tglist.add(DdTargets.FAMILY_LINK.atom_drag_type,
                       DdTargets.FAMILY_LINK.target_flags,
                       DdTargets.FAMILY_LINK.app_id,
                       )
            # allow drag to a text document, info on drag_get will be 1
            tglist.add_text_targets(1)

        if tglist:
            self.canvas.drag_source_set_target_list(tglist)
        else:
            self.enable_dnd(False)

    def drag_data_get(self, widget, context, sel_data, info, time):
        """
        Returned parameters after drag.
        Specified for 'person-link' and 'family-link',
        also to return text info about person or family.
        """
        tgs = [x.name() for x in context.list_targets()]

        if info == DdTargets.PERSON_LINK.app_id:
            data = (DdTargets.PERSON_LINK.drag_type,
                    id(widget), self.drag_person.handle, 0)
            sel_data.set(sel_data.get_target(), 8, pickle.dumps(data))
        elif info == DdTargets.FAMILY_LINK.app_id:
            data = (DdTargets.FAMILY_LINK.drag_type,
                    id(widget), self.drag_family.handle, 0)
            sel_data.set(sel_data.get_target(), 8, pickle.dumps(data))
        elif ('TEXT' in tgs or 'text/plain' in tgs):
            if info == 0:
                format_helper = FormattingHelper(self.dbstate)
                sel_data.set_text(
                    format_helper.format_person(self.drag_person, 11), -1)
            if info == 1:
                f_handle = self.drag_family.get_father_handle()
                m_handle = self.drag_family.get_mother_handle()
                if f_handle:
                    father = self.dbstate.db.get_person_from_handle(f_handle)
                    father = displayer.display(father)
                else:
                    father = '...'
                if m_handle:
                    mother = self.dbstate.db.get_person_from_handle(m_handle)
                    mother = displayer.display(mother)
                else:
                    mother = '...'
                sel_data.set_text(
                    _('Family of %s and %s') % (father, mother), -1)

    def drag_motion(self, widget, context, x, y, time):
        """
        Monitor drag motion. And check if we can receive the data.
        Disable drop if we are not at person or family node.
        """
        if self.get_item_at_pos(x, y) is None:
            # disable drop
            Gdk.drag_status(context, 0, time)

    def drag_data_receive(self, widget, context, x, y, data, info, time):
        """
        Handle drop event.
        """
        receiver = self.get_item_at_pos(x, y)

        # unpickle data and get dropped person's handles
        out_data = []
        p_data = pickle.loads(data.get_data())
        if isinstance(p_data[0], bytes):
            for d in p_data:
                tmp = pickle.loads(d)
                if tmp[0] == 'person-link':
                    out_data.append(tmp[2])
        elif p_data[0] == 'person-link':
            out_data.append(p_data[2])

        action_menu = Popover(self.canvas)
        rect = Gdk.Rectangle()
        rect.x = x
        rect.y = y
        rect.height = rect.width = 1
        action_menu.set_pointing_to(rect)

        # ===========================
        # Generate actions popup menu
        # ===========================

        # if person is dropped to family node then add them to this family
        if receiver[0] == 'familynode' and out_data:
            title = ngettext("Add as child to family",
                             "Add as children to family",
                             len(out_data))
            action_menu.add_action(title, self.add_children_to_family,
                                   receiver[1], out_data)
            # add spouse to family
            if len(out_data) == 1:
                person = self.dbstate.db.get_person_from_handle(out_data[0])
                gender = person.get_gender()
                f_handle = receiver[1].get_father_handle()
                m_handle = receiver[1].get_mother_handle()

                if not f_handle and gender in (Person.MALE, Person.UNKNOWN):
                    action_menu.add_action(_('Add spouse as father'),
                                           self.add_spouse,
                                           out_data[0], None, receiver[1])
                if not m_handle and gender in (Person.FEMALE, Person.UNKNOWN):
                    action_menu.add_action(_('Add spouse as mother'),
                                           self.add_spouse,
                                           None, out_data[0], receiver[1])

        # if drop to person node
        if receiver[0] == 'node' and out_data:
            # add relation (reference)
            if len(out_data) == 1:
                action_menu.add_action(_('Add relation'), self.add_personref,
                                       receiver[1], out_data[0])
            # add as parent
            if len(out_data) in (1, 2):
                parent_family_list = receiver[1].get_parent_family_handle_list()
                # dropped 1 person and 1 family exists
                if len(parent_family_list) == 1 and len(out_data) == 1:
                    person = self.dbstate.db.get_person_from_handle(out_data[0])
                    gender = person.get_gender()
                    family = self.dbstate.db.get_family_from_handle(
                        parent_family_list[0])
                    f_handle = family.get_father_handle()
                    m_handle = family.get_mother_handle()

                    if not f_handle and gender in (Person.MALE, Person.UNKNOWN):
                        action_menu.add_action(_('Add as father'),
                                               self.add_spouse,
                                               out_data[0], None, family)
                    elif not m_handle and gender in (Person.FEMALE,
                                                     Person.UNKNOWN):
                        action_menu.add_action(_('Add as mother'),
                                               self.add_spouse,
                                               None, out_data[0], family)
                # create family for person
                elif not parent_family_list:
                    father = None
                    mother = None
                    for p in out_data:
                        person = self.dbstate.db.get_person_from_handle(p)
                        gender = person.get_gender()
                        if gender == Person.MALE:
                            father = p if father is None else None
                        if gender == Person.FEMALE:
                            mother = p if mother is None else None
                    if father or mother:
                        child = receiver[1].get_handle()
                        action_menu.add_action(_('Add parents'),
                                               self.add_spouse,
                                               father, mother, None, child)
        action_menu.popup()

    def get_item_at_pos(self, x, y):
        """
        Get GooCanvas item at cursor position.
        Return: (node_class, person/family object) or None.
        """
        scale_coef = self.canvas.get_scale()
        x_pos = (x + self.h_adj.get_value()) / scale_coef
        y_pos = (y + self.v_adj.get_value()) / scale_coef

        item = self.canvas.get_item_at(x_pos, y_pos, True)
        obj = self.item_cache.get(item)
        if obj is not None:
            return obj
        try:
            # data stored in GooCanvasGroup which is parent of the item
            parent = item.get_parent()
            handle = parent.title
            node_class = parent.description

            if node_class == 'node' and handle:
                obj = (node_class,
                       self.dbstate.db.get_person_from_handle(handle))
            elif node_class == 'familynode' and handle:
                obj = (node_class,
                       self.dbstate.db.get_family_from_handle(handle))
            else:
                return None
            self.item_cache[item] = obj
            return obj
        except:
            pass
        return None

    def add_spouse(self, widget, father_handle, mother_handle,
                   family=None, child=None):
        """
        Add spouse to family.
        If family is not provided it will be created for specified child.
        """
        if family is None:
            if child is None:
                # we need child to refer to new family
                return
            family = Family()
            childref = ChildRef()
            childref.set_reference_handle(child)
            family.add_child_ref(childref)

        if father_handle:
            family.set_father_handle(father_handle)
        if mother_handle:
            family.set_mother_handle(mother_handle)

        try:
            EditFamily(self.dbstate, self.uistate, [], family)
        except WindowActiveError:
            pass

    def add_children_to_family(self, widget, family, data):
        """
        Add persons to family.
        data: list of person handles
        """
        for person_handle in data:
            person = self.dbstate.db.get_person_from_handle(person_handle)
            ref = ChildRef()
            ref.ref = person_handle
            family.add_child_ref(ref)
            person.add_parent_family_handle(family.get_handle())

            with DbTxn(_("Add Child to Family"), self.dbstate.db) as trans:
                # default relationship is used
                self.dbstate.db.commit_person(person, trans)
                # add child to family
                self.dbstate.db.commit_family(family, trans)

    def add_personref(self, widget, source, person_handle):
        """
        Open dialog to add reference to person.
        """
        ref = PersonRef()
        ref.rel = _('Godfather')    # default role
        ref.source = source
        try:
            dialog = EditPersonRef(self.dbstate, self.uistate, [],
                                   ref, self.__cb_add_ref)
            dialog.update_person(
                self.dbstate.db.get_person_from_handle(person_handle))
        except WindowActiveError:
            pass

    def __cb_add_ref(self, obj):
        """
        Save person reference.
        """
        person = obj.source
        person.add_person_ref(obj)
        with DbTxn(_("Add Reference to Person"), self.dbstate.db) as trans:
            self.dbstate.db.commit_person(person, trans)


class Popover(Gtk.Popover):
    """
    Display available actions on drop event.
    """
    def __init__(self, widget):
        Gtk.Popover.__init__(self, relative_to=widget)
        self.set_modal(True)

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.cancel_btn = Gtk.Button(label=_('Cancel'), margin_top=5)
        self.box.pack_end(self.cancel_btn, True, True, 1)
        self.cancel_btn.connect('clicked', self.popdown)

        # set all widgets visible
        self.box.show_all()
        self.add(self.box)

    def add_action(self, label, callback, *args):
        """
        Add button to popover with action.
        """
        action = Gtk.Button(label=label)
        self.box.pack_start(action, True, True, 1)
        if callback:
            action.connect('clicked', callback, *args)
        action.connect('clicked', self.popdown)
        action.show()

    def popup(self):
        """
        Different popup depending on gtk version.
        """
        if gtk_version >= 3.22:
            super(self.__class__, self).popup()
        else:
            self.show()

    def popdown(self, *args):
        """
        Different popdown depending on gtk version.
        """
        if gtk_version >= 3.22:
            super(self.__class__, self).popdown()
        else:
            self.hide()
