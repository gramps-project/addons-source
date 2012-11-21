# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2007-2009  Douglas S. Blank <doug.blank@gmail.com>
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

# $Id$

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk
import pango

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.plug import Gramplet
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.utils.trans import get_addon_translator
_ = get_addon_translator().ugettext
from gramps.gen.const import GLADE_FILE
from gramps.gui.widgets import StyledTextEditor
from gramps.gen.lib import StyledText, Note
from gramps.gen.db import DbTxn
from gramps.gen.errors import WindowActiveError

#------------------------------------------------------------------------
#
# Gramplet class
#
#------------------------------------------------------------------------
class NoteGramplet(Gramplet):
    """
    Gramplet that gives simplified interface to a Person's primary note.
    """
    def init(self):
        rows = Gtk.VBox()
        self._dirty = False
        self._dirty_person = None

        # Active person: Name
        row = Gtk.HBox()
        label = Gtk.Label()
        label.set_text("<b>%s</b>: " % _("Active person"))
        label.set_use_markup(True)
        label.set_alignment(0.0, 0.5)
        row.pack_start(label, False, False, 0)

        apw = Gtk.Label()
        self.active_person_widget = apw
        apw.set_alignment(0.0, 0.5)
        apw.set_use_markup(True)
        row.pack_start(apw, False, False, 0)

        # Add edit for person and family
        icon = Gtk.STOCK_EDIT
        size = Gtk.IconSize.MENU
        button = Gtk.Button()
        image = Gtk.Image()
        image.set_from_stock(icon, size)
        button.add(image)
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.connect("clicked", self.edit_person)
        self.active_person_edit = button
        row.pack_start(button, False, False, 0)

        label = Gtk.Label()
        label.set_text(" %s: " % _("Family"))
        self.active_family_label = label
        row.pack_start(label, False, False, 0)

        button = Gtk.Button()
        image = Gtk.Image()
        image.set_from_stock(icon, size)
        button.add(image)
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.connect("clicked", self.edit_family)
        self.active_family_edit = button
        row.pack_start(button, False, False, 0)

        rows.pack_start(row, False, False, 0)

        row = self.build_interface()
        self.note_buffer = self.texteditor.textbuffer
        self.note_buffer.connect("changed", self.mark_dirty)
        rows.pack_start(row, True, True, 0)

        # Save and Abandon
        row = Gtk.HBox()
        button = Gtk.Button(_("Save"))
        button.connect("clicked", self.save_data_edit)
        row.pack_start(button, True)
        button = Gtk.Button(_("Abandon"))
        button.connect("clicked", self.abandon_data_edit)
        row.pack_start(button, True)
        rows.pack_start(row, False)

        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(rows)
        rows.show_all()
        self.clear_data_entry(None)

    def flow_changed(self, active):
        """
        Changes the wrap/font of text flow.
        """
        if active:
            # Set the text style to monospace
            self.texteditor.set_wrap_mode(Gtk.WrapMode.NONE)
            self.texteditor.modify_font(pango.FontDescription("monospace"))
        else:
            # Set the text style to normal
            self.texteditor.set_wrap_mode(Gtk.WrapMode.WORD)
            self.texteditor.modify_font(pango.FontDescription("normal"))

    def build_interface(self):
        """
        Based on src/Editors/_EditNote.py
        """
        vbox = Gtk.VBox()
        self.texteditor = StyledTextEditor()
        # create a formatting toolbar
        vbox.pack_start(self.texteditor.get_toolbar(),
                        False, False, 0)
        vbox.pack_start(self.texteditor, True, True, 0)
        self.flow_changed(False)
        return vbox

    def main(self): # return false finishes
        if self._dirty:
            return
        self.active_person_edit.hide()
        self.active_family_edit.hide()
        self.active_family_label.hide()
        self.note_buffer.set_text(StyledText())
        active_person = self.get_active_object("Person")
        self._dirty_person = active_person
        self._dirty_family = None
        if active_person:
            self.active_person_edit.show()
            self.active_family_edit.hide()
            self.active_family_label.hide()
            # Fill in current person edits:
            name = name_displayer.display(active_person)
            self.active_person_widget.set_text("<i>%s</i> " % name)
            self.active_person_widget.set_use_markup(True)
            # Note:
            self.note = None
            note_list = active_person.get_referenced_note_handles()
            for (classname, note_handle) in note_list:
                note_obj = self.dbstate.db.get_note_from_handle(note_handle)
                if note_obj.get_type() == _("Person Note"):
                    self.note = note_obj
                    break
            if self.note is None:
                self.note = Note()
            self.texteditor.set_text(self.note.get_styledtext())
            self.flow_changed(self.note.get_format())
            # Family button:
            family_list = active_person.get_family_handle_list()
            if len(family_list) > 0:
                self._dirty_family = self.dbstate.db.get_family_from_handle(family_list[0])
                self.active_family_edit.show()
                self.active_family_label.show()
            else:
                family_list = active_person.get_parent_family_handle_list()
                if len(family_list) > 0:
                    self._dirty_family = self.dbstate.db.get_family_from_handle(family_list[0])
                    self.active_family_edit.show()
                    self.active_family_label.show()
        else:
            self.clear_data_entry(None)
            self.active_person_edit.hide()
            self.active_family_edit.hide()
            self.active_family_label.hide()
        self._dirty = False

    def clear_data_entry(self, obj):
        self.note_buffer.set_text(StyledText())
        self.flow_changed(False)

    def db_changed(self):
        """
        If person or family changes, the relatives of active person might have
        changed
        """
        self._dirty = False
        self._dirty_person = None
        self.clear_data_entry(None)
        self.texteditor.set_editable(not self.dbstate.db.readonly)
        self.update()

    def active_changed(self, handle):
        self.update()

    def mark_dirty(self, obj):
        self._dirty = True

    def abandon_data_edit(self, obj):
        self._dirty = False
        self.update()

    def edit_callback(self, person):
        self._dirty = False
        self.update()

    def edit_person(self, obj):
        from gui.editors import EditPerson
        try:
            EditPerson(self.gui.dbstate, 
                       self.gui.uistate, [], 
                       self._dirty_person,
                       callback=self.edit_callback)
        except WindowActiveError:
            pass

    def edit_family(self, obj):
        from gui.editors import EditFamily
        try:
            EditFamily(self.gui.dbstate, 
                       self.gui.uistate, [], 
                       self._dirty_family)
        except WindowActiveError:
            pass
    
    def save_data_edit(self, obj):
        if self._dirty:
            person = self._dirty_person
            text = self.texteditor.get_text()
            self.note.set_styledtext(text)
            with DbTxn(_("Save Note"), self.dbstate.db) as trans:
                if not self.note.get_handle():
                    self.note.set_type(_("Person Note"))
                    self.dbstate.db.add_note(self.note, trans)
                    person.add_note(self.note.get_handle())
                    self.dbstate.db.commit_person(person, trans)
                else:
                    if not self.note.get_gramps_id():
                        self.note.set_gramps_id(self.dbstate.db.find_next_note_gramps_id())
                    self.dbstate.db.commit_note(self.note, trans)
        self._dirty = False
