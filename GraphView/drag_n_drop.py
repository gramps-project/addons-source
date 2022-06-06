#!/usr/bin/env python3

import pickle
from gi.repository import Gtk, Gdk

from gramps.gen.db import DbTxn
from gramps.gen.display.name import displayer
from gramps.gen.utils.libformatting import FormattingHelper
from gramps.gen.lib import ChildRef
from gramps.gui.ddtargets import DdTargets
from gramps.gui.dialog import QuestionDialog2

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
ngettext = glocale.translation.ngettext


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
        if state:
            self.canvas.drag_source_set(
                Gdk.ModifierType.BUTTON1_MASK,
                [],
                Gdk.DragAction.COPY)
        else:
            self.canvas.drag_source_unset()

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

        # if person is dropped to family node then add them to this family
        if receiver[0] == 'familynode' and out_data:
            title = ngettext("Add child to family?",
                             "Add children to family?",
                             len(out_data))
            quest = ngettext("Do you want to add child to the family?",
                             "Do you want to add children to the family?",
                             len(out_data))
            dialog = QuestionDialog2(title, quest, _("Yes"), _("No"),
                                     self.uistate.window)
            if dialog.run():
                for person_handle in out_data:
                    self.__add_child_to_family(person_handle, receiver[1])

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

    def __add_child_to_family(self, person_handle, family):
        """
        Write data to db.
        """
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
