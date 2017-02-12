# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2017
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

"""Tools/Database Check Place Titles"""

#-------------------------------------------------------------------------
#
# gnome/gtk
#
#-------------------------------------------------------------------------
from gi.repository import Gtk

#-------------------------------------------------------------------------
#
# gramps modules
#
#-------------------------------------------------------------------------
from gramps.gen.db import DbTxn
from gramps.gen.const import URL_MANUAL_PAGE
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.display import display_help
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.lib import (Note, NoteType, StyledText, StyledTextTag,
                            StyledTextTagType, Tag)
from gramps.gui.dialog import OkDialog
from gramps.gui.plug import tool
from gramps.gui.utils import ProgressMeter
from gramps.gui.listmodel import ListModel
from gramps.gui.glade import Glade
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

WIKI_HELP_PAGE = '%s_-_Tools' % URL_MANUAL_PAGE
WIKI_HELP_SEC = _('manual|Check_place_titles')


#-------------------------------------------------------------------------
#
# CheckPlaceTiltes
#
#-------------------------------------------------------------------------
class CheckPlaceTitles(tool.BatchTool, ManagedWindow):
    """
    Agreed with displayed Place Titles?
    """

    def __init__(self, dbstate, user, options_class, name, callback=None):
        uistate = user.uistate
        self.label = _('Check Place title')
        tool.BatchTool.__init__(self, dbstate, user, options_class, name)
        if self.fail:
            return

        ManagedWindow.__init__(self,uistate,[], self.__class__)
        self.set_window(Gtk.Window(),Gtk.Label(),'')

        # retrieve options CLI?
        #copy = self.options.handler.options_dict['copy']
        #clean = self.options.handler.options_dict['clean']

        self.db = dbstate.db

        self.total = self.db.get_number_of_places()
        self.progress = ProgressMeter(_('Checking Place Titles'), '')
        self.progress.set_pass(_('Looking for place fields'),
                               self.total)

        self.name_list = []
        count = 0
        for handle in self.db.get_place_handles(True):
            self.progress.step()
            place = self.db.get_place_from_handle(handle)
            title = place.title
            descr = place_displayer.display(self.db, place)
            if title == ("" or descr):
                count += 1
            if title != "":
                self.name_list.append((handle.decode('utf8'), title, descr))

        self.progress.close()

        if self.name_list:
            self.display()
            OkDialog(_('Differences'),
                     '%s/%s' % (count, self.total),
                     parent=uistate.window)
        else:
            self.progress.close()
            self.close()
            OkDialog(_('No need modifications'),
                     _("No changes need."),
                     parent=uistate.window)

    def display(self):

        top_dialog = Glade()

        top_dialog.connect_signals({
            "destroy_passed_object" : self.close,
            "on_ok_clicked" : self.on_ok_clicked,
            "on_help_clicked" : self.on_help_clicked,
            "on_delete_event"   : self.close,
            })

        window = top_dialog.toplevel
        self.set_window(window, top_dialog.get_object('title'), self.label)
        self.setup_configs('interface.changenames', 500, 450)

        self.clear_button = top_dialog.get_object('checkbutton1')
        self.copy_button = top_dialog.get_object('checkbutton2')
        self.tag_button = top_dialog.get_object('checkbutton3')

        self.treeview = top_dialog.get_object("list")

        self.r = Gtk.CellRendererToggle()
        self.r.set_property('activatable', True)
        self.r.set_property('radio', True)
        self.r.connect('toggled', self.toggled)

        c = Gtk.TreeViewColumn(_('Select'), self.r, active=1)
        self.treeview.append_column(c)

        c = Gtk.TreeViewColumn(_('Database'),
                               Gtk.CellRendererText(),text=2)
        self.treeview.append_column(c)

        c = Gtk.TreeViewColumn(_('Display'),
                               Gtk.CellRendererText(),text=3)
        self.treeview.append_column(c)

        self.selection = self.treeview.get_selection()

        self.model = Gtk.ListStore(str, bool, str, str)

        self.treeview.set_model(self.model)

        self.progress.set_pass(_('Building display'), len(self.name_list))
        for handle, title, descr in self.name_list:
            self.model.append([handle, title == descr, title, descr])
            self.progress.step()
        self.progress.close()

        self.show()

    def toggled(self, cell, path):
        self.model[path][1] = not self.model[path][1]

    def build_menu_names(self, obj):
        return (self.label, None)

    def on_help_clicked(self, obj):
        """Display the relevant portion of GRAMPS manual"""
        display_help(WIKI_HELP_PAGE , WIKI_HELP_SEC)

    def on_ok_clicked(self, obj):

        clean = self.clear_button.get_active()
        copy = self.copy_button.get_active()
        tag = self.tag_button.get_active()
        if not (copy or clean or tag):
            return

        self.db.disable_signals()

        if tag:
            tag_name = _('Legacy place')
            # start the db transaction
            with DbTxn("Tag for place titles", self.db) as self.tag_trans:

                mark = self.db.get_tag_from_name(tag_name)
                if not mark:
                    # create the tag if it doesn't already exist
                    mark = Tag()
                    mark.set_name(tag_name)
                    mark.set_priority(self.db.get_number_of_tags())
                    tag_handle = self.db.add_tag(mark, self.tag_trans)
                else:
                    tag_handle = mark.get_handle()

        with DbTxn(_("Modify Place titles"), self.db, batch=True) as trans:
            for row in self.model:
                if row[1] == True:
                    place = self.db.get_place_from_handle(row[0])
                    if copy:
                        self.create_note(place, row[2], trans)
                    if clean:
                        place.set_title("")
                    if tag:
                        place.add_tag(tag_handle)
                    self.db.commit_place(place, trans)

        self.db.enable_signals()
        self.db.request_rebuild()
        self.close()

    def create_note(self, place, data, trans):
        new_note = Note()
        tag = StyledTextTag(StyledTextTagType.FONTFACE, 'Monospace',
                            [(0, len(data))])
        text = StyledText(data, [tag])
        new_note.set_styledtext(text)
        note_type = NoteType()
        note_type.set((NoteType.CUSTOM, _("Place titles")))
        new_note.set_type(note_type)
        handle = self.db.add_note(new_note, trans)
        place.add_note(handle)

#------------------------------------------------------------------------
#
#
#
#------------------------------------------------------------------------
class CheckPlaceTitlesOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """
    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)

        # Options specific for this tool
        self.options_dict = {
            'copy'   : True,
            'clean'  : True,
            'tag'    : False,
        }
        self.options_help = {
            'copy' : ("=True/False",
                           "copy old place titles to a new note",
                           "true/false"),
            'clean' : ("=True/False",
                           "remove legacy content for place titles",
                           "true/false"),
            'tag' : ("=True/False", "assign a tag and mark places",
                     "true/fasle"),
            }
