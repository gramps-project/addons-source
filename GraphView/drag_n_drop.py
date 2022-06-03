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

    def __init__(self, canvas, dbstate):
        self.drag_person = None
        self.drag_family = None

        self.dbstate = dbstate
        self.canvas = canvas
        self.canvas.connect("drag_data_get", self.drag_data_get)
        self.canvas.connect("drag_begin", self.begin)
        self.canvas.connect("drag_end", self.stop)

        self.enable_dnd(True)

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
