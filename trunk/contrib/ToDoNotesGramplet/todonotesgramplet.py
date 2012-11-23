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

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.plug import Gramplet        
from gramps.gen.filters import GenericFilterFactory, rules
from gramps.gui.widgets import SimpleButton
from gramps.gen.utils.trans import get_addon_translator
_ = get_addon_translator(__file__).gettext

#------------------------------------------------------------------------
#
# TODOGramplet class
#
#------------------------------------------------------------------------
class TODONotesGramplet(Gramplet):
    
    def init(self):
        
        # default state
        self.current = 0
               
        vbox = Gtk.VBox()
        hbox = Gtk.HBox()
        
        # area
        
        self.import_text = Gtk.TextView()
        
        self.import_text.set_wrap_mode(Gtk.WrapMode.WORD)
        self.import_text.set_editable(False)
        
        self.text = Gtk.TextBuffer()
        if self.gui.data:
            self.text.set_text(self.gui.data[0])
        else:
            self.text.set_text(_("Edit a TODO Note."))
        self.import_text.set_buffer(self.text)
        
        vbox.pack_start(self.import_text, True, True, 0)
        
        # buttons
              
        hbox = Gtk.HBox()
        
        self.left = SimpleButton(Gtk.STOCK_GO_BACK, self.previous_button)
        self.left.set_sensitive(False)
        hbox.pack_start(self.left, False, False, 0)
        
        edit_button = Gtk.Button(_(_("Edit")))
        edit_button.connect("clicked", self.edit)
        hbox.pack_start(edit_button, False, False, 0)
        
        self.right = SimpleButton(Gtk.STOCK_GO_FORWARD, self.next_button)
        self.right.set_sensitive(False)
        hbox.pack_start(self.right, False, False, 0)
        
        self.page = Gtk.Label()
        hbox.pack_end(self.page, False, False, 10)
        
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(vbox)
        
        vbox.pack_start(hbox, False, False, 0)
        
        vbox.show_all()
        
        # 'DbBsddbRead' object has no attribute 'tag_map'
        if self.dbstate.db.db_is_open:
            self.load(self.current)
        
    def load(self, current):
        self.current = current
        self.page.set_text('')
        nlist = self.dbstate.db.get_note_handles()
        FilterClass = GenericFilterFactory('Note')
        filter = FilterClass()
        filter.add_rule(rules.note.HasTag([_("ToDo")]))
        notes_list = filter.apply(self.dbstate.db, nlist)
        if len(notes_list) == 0:
            self.create_note()
            return
        else:
            self.page.set_text(_('%(current)d of %(total)d') % {'current':self.current + 1,
                                                'total':len(notes_list)})
            # more than 1 Note; enable navigation
            if len(notes_list) > 1 :
                self.left.set_sensitive(True)
                self.right.set_sensitive(True)
                
            # first entry; cannot go back
            if self.current == 0:
                self.left.set_sensitive(False)
                            
            # last entry; cannot go further
            if self.current == len(notes_list) - 1:
                self.right.set_sensitive(False)
                       
            # index
            self.load_notes(notes_list, self.current)

    def post_init(self):
        self.disconnect("active-changed")
        
    def load_notes(self, notes_list, current):
        """
        Maybe should move to Gramplet?
         see also Notes gramplet
        """
        self.current = current
                       
        self.note = self.dbstate.db.get_note_from_handle(notes_list[self.current])
        if self.note:
            self.text.set_text(self.note.get())
            
    def create_note(self):
        from gramps.gen.lib import Note
        
        self.note = Note()
        #obj.set_tag(_("ToDo"))
        
        if self.gui.data:
            self.note.set(self.gui.data[0])
        
    def previous_button(self, button):
        # index - 1
        self.load(self.current -1)
        
    def edit(self, obj):
        from gramps.gui.editors import EditNote
        try:
            EditNote(self.gui.dbstate, 
                       self.gui.uistate, [], 
                       self.note,)
        except AttributeError:
            pass
        
    def next_button(self, button):
        # index + 1
        self.load(self.current + 1)
        
        
       
