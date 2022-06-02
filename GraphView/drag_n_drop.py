#!/usr/bin/env python3

import pickle
from gi.repository import Gtk, Gdk

from gramps.gen.display.name import displayer
from gramps.gui.ddtargets import DdTargets
from gramps.gen.utils.libformatting import FormattingHelper

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


class DragAndDrop():
    """
    Add Drag-n-Drop feature to GraphView addon.
    """

    def __init__(self, widget, dbstate):
        self.ready = False          # True - when drag can be started
        self.do_drag = False        # True - when drag is started

        self.drag_person = None
        self.drag_family = None

        self.dbstate = dbstate
        self.widget = widget
        self.widget.connect("drag_data_get", self.drag_data_get)
        self.widget.connect("drag_begin", self.begin)
        self.widget.connect("drag_end", self.stop)

    def begin(self, widget, context):
        """
        Called when drag is start.
        """
        self.do_drag = True
        tgs = [x.name() for x in context.list_targets()]
        # set icon depending on person or family drag
        if DdTargets.PERSON_LINK.drag_type in tgs:
            Gtk.drag_set_icon_name(context, 'gramps-person', 0, 0)
        if DdTargets.FAMILY_LINK.drag_type in tgs:
            Gtk.drag_set_icon_name(context, 'gramps-family', 0, 0)

    def stop(self, *args):
        """
        Called when drag is end.
        """
        self.ready = False
        self.do_drag = False
        self.drag_person = None
        self.drag_family = None

    def is_ready(self):
        """
        Check if we ready to drag.
        """
        return self.ready and (not self.do_drag)

    def set_ready(self, node_class, handle):
        """
        Set ready to drag state.
        """
        self.stop()
        if node_class == 'node':
            self.drag_person = self.dbstate.db.get_person_from_handle(handle)
        elif node_class == 'familynode':
            self.drag_family = self.dbstate.db.get_family_from_handle(handle)

        if self.drag_person or self.drag_family:
            self.ready = True

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

    def start_drag(self, pos_x, pos_y, event):
        """
        Activate drag.
        """
        # setup targets
        tglist = Gtk.TargetList.new([])
        if self.drag_person is not None:
            tglist.add(DdTargets.PERSON_LINK.atom_drag_type,
                       DdTargets.PERSON_LINK.target_flags,
                       DdTargets.PERSON_LINK.app_id,
                       )
            # allow drag to a text document, info on drag_get will be 0
            tglist.add_text_targets(0)
        if self.drag_family is not None:
            tglist.add(DdTargets.FAMILY_LINK.atom_drag_type,
                       DdTargets.FAMILY_LINK.target_flags,
                       DdTargets.FAMILY_LINK.app_id,
                       )
            # allow drag to a text document, info on drag_get will be 1
            tglist.add_text_targets(1)

        # start drag
        self.widget.drag_begin_with_coordinates(
            tglist,
            Gdk.DragAction.COPY,
            1,                      # left mouse button = 1
            event,
            pos_x, pos_y)
        return True
