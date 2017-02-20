#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2017  Paul R Culley <paulr2787_at_gmail.com>
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

"""Tools/Database Processing/Birth Order"""

#-------------------------------------------------------------------------
#
# GNOME libraries
#
#-------------------------------------------------------------------------
from gi.repository import Gtk

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from gramps.gen.db import DbTxn
from gramps.gen.utils.db import get_birth_or_fallback
from gramps.gui.utils import ProgressMeter
from gramps.gui.plug import tool
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.datehandler import displayer
from gramps.gui.dialog import OkDialog
from gramps.gui.display import display_url
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.glade import Glade
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.sgettext

#-------------------------------------------------------------------------
#
# Constants
#
#-------------------------------------------------------------------------

WIKI_PAGE = 'https://gramps-project.org/wiki/index.php?title=BirthOrderTool'
TITLE = _("Sort Children in Birth order")
CSS = """
*:insensitive {
  background-color: @theme_bg_color;
  color: @theme_fg_color;
}
"""


#-------------------------------------------------------------------------
#
# The Actual tool.
#
#-------------------------------------------------------------------------
class BirthOrder(tool.Tool, ManagedWindow):
    """ Sort children in a fmily in the order of birth """

    def __init__(self, dbstate, user, options_class, name, callback=None):
        uistate = user.uistate

        tool.Tool.__init__(self, dbstate, options_class, name)
        ManagedWindow.__init__(self, uistate, [], self.__class__)
        self.db = dbstate.db
        self.uistate = uistate
        self.map = {}
        self.list = []
        self.index = 0
        self.fam_h = self.fam_iter = self.family = self.progress = None
        self.update = callback

        self.top = Glade()

        self.fam_liststore = self.top.get_object("fam_liststore")
        self.ch_liststore = self.top.get_object("ch_liststore")
        self.ch_liststore_s = self.top.get_object("ch_liststore_s")
        self.fam_view = self.top.get_object("Families_treeview")
        self.ch_view = self.top.get_object("children_treeview")
        self.ch_view_s = self.top.get_object("children_treeview_s")
        chs_style_cntx = self.ch_view.get_style_context()
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(CSS.encode('utf8'))
        chs_style_cntx.add_provider(
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        window = self.top.toplevel
        self.set_window(window, None, TITLE)
        # self.setup_configs('interface.birthordertool', 750, 520)

        self.top.connect_signals({
            "on_close"              : self.close,
            "on_help_clicked"       : self.on_help_clicked,
            "on_delete_event"       : self.close,
            "on_accept_clicked"     : self.on_accept,
            "on_easy_clicked"       : self.on_easy,
            "on_accept_all_clicked" : self.on_accept_all,
            "on_up_btn_clicked"     : self.on_up,
            "on_down_btn_clicked"   : self.on_down})

        self.fam_sel = self.fam_view.get_selection()
        self.fam_sel.connect('changed', self.on_fam_row_changed)
        self.ch_s_sel = self.ch_view_s.get_selection()
        self.show()

        self.find_potentials()

        if len(self.fam_liststore) == 0:
            self.kill_buttons()
            OkDialog(
                _("No families need sorting"),
                _("No children were out of birth order."),
                parent=self.window)

    def build_menu_names(self, obj):
        return (TITLE, TITLE)

    def kill_buttons(self):
        self.top.get_object("AcceptAll").set_sensitive(False)
        self.top.get_object("AcceptAllEasy").set_sensitive(False)
        self.top.get_object("accept").set_sensitive(False)
        self.top.get_object("up_btn").set_sensitive(False)
        self.top.get_object("down_btn").set_sensitive(False)

    def on_help_clicked(self, dummy):
        """ Button: Display the relevant portion of GRAMPS manual"""
        display_url(WIKI_PAGE)

    def on_accept(self, dummy):
        """ Button: Accept the single family as shown """
        orig_ref_list = self.family.get_child_ref_list()
        child_ref_list = []
        for child_iter in self.ch_liststore_s:
            child_ref_list.append(orig_ref_list[child_iter[2]])
        self.family.set_child_ref_list(child_ref_list)
        with DbTxn(_("Edit Family"), self.db) as trans:
            self.db.commit_family(self.family, trans)
        self.fam_liststore.remove(self.fam_iter)
        if len(self.fam_liststore) == 0:
            self.kill_buttons()
            self.ch_liststore.clear()
            self.ch_liststore_s.clear()
        else:
            if not self.fam_sel.get_selected()[1]:
                self.fam_sel.select_path(Gtk.TreePath.new_first())

    def on_accept_all(self, dummy, easy=False):
        """ Button: Accept all or all the 'easy' ones, depending """
        self.progress = ProgressMeter(TITLE, '',
                                      parent=self.window)
        length = self.easy_count if easy else len(self.fam_liststore)

        self.progress.set_pass(_("Processing..."), length)
        with DbTxn(_("Edit Families"), self.db) as trans:
            for row in self.fam_liststore:
                self.progress.step()
                if easy and not row[0]:
                    continue
                self.fam_h = row[4]
                self.family = self.db.get_family_from_handle(self.fam_h)
                dummy, sorted_ch_list = self.sort_family_pr(self.fam_h)
                orig_refs = self.family.get_child_ref_list()
                sort_ref_list = list(orig_refs[ch[3]] for ch in sorted_ch_list)
                self.family.set_child_ref_list(sort_ref_list)
                self.db.commit_family(self.family, trans)
                self.fam_liststore.remove(row.iter)
        self.progress.close()
        spath = Gtk.TreePath.new_first()
        self.fam_sel.select_path(spath)
        if len(self.fam_liststore) == 0:
            self.kill_buttons()
            self.ch_liststore.clear()
            self.ch_liststore_s.clear()

    def on_easy(self, obj):
        """ Button: Accept all the 'easy' ones """
        self.on_accept_all(obj, easy=True)

    def on_fam_row_changed(self, *obj):
        """ Signal: update lower panes when the family pane row changes """
        if not obj:
            return
        self.fam_iter = obj[0].get_selected()[1]
        if not self.fam_iter:
            return
        self.fam_h = self.fam_liststore[self.fam_iter][4]
        self.family = self.db.get_family_from_handle(self.fam_h)
        ch_list, sorted_ch_list = self.sort_family_pr(self.fam_h)
        self.ch_liststore.clear()
        self.ch_liststore_s.clear()
        for indx in range(len(ch_list)):
            ch_row = (ch_list[indx][0], ch_list[indx][1])
            ch_row_s = (sorted_ch_list[indx][0], sorted_ch_list[indx][1],
                        sorted_ch_list[indx][3])
            self.ch_liststore.append(row=ch_row)
            self.ch_liststore_s.append(row=ch_row_s)
        self.ch_s_sel.select_path(Gtk.TreePath.new_first())

    def ch_sorted_index(self):
        """ get the index of current sorted view pane selected row """
        ch_path = self.ch_view_s.get_selection().get_selected_rows()[1][0]
        return int(str(ch_path))

    def on_up(self, dummy):
        """ Button: move the selected sorted view row up """
        pos = self.ch_sorted_index()
        new_order = list(range(len(self.ch_liststore_s)))
        if pos > 0:
            new_order[pos] = pos - 1
            new_order[pos - 1] = pos
            self.ch_liststore_s.reorder(new_order)

    def on_down(self, dummy):
        """ Button: move the selected sorted view row down """
        pos = self.ch_sorted_index()
        new_order = list(range(len(self.ch_liststore_s)))
        if pos >= 0 and pos < len(self.ch_liststore_s) - 1:
            new_order[pos] = pos + 1
            new_order[pos + 1] = pos
            self.ch_liststore_s.reorder(new_order)

    def find_potentials(self):
        """ look for possible out of order families """
        self.progress = ProgressMeter(TITLE,
                                      _('Looking for children birth order'),
                                      parent=self.window)
        length = self.db.get_number_of_families()

        self.progress.set_pass(_('Pass 1: Building preliminary lists'),
                               length)
        self.easy_count = 0
        for fam_h in self.db.iter_family_handles():
            self.progress.step()
            fam = self.db.get_family_from_handle(fam_h)
            child_ref_list = fam.get_child_ref_list()
            prev_date = 0
            need_sort = False
            easy = '*'
            for child_ref in child_ref_list:
                child = self.db.get_person_from_handle(child_ref.ref)
                b_date = 0
                birth = get_birth_or_fallback(self.db, child)
                if birth:
                    b_date = birth.get_date_object().get_sort_value()
                if not b_date:
                    easy = ''
                    continue
                elif b_date >= prev_date:
                    prev_date = b_date
                    continue
                else:   # we need to put this one in list
                    need_sort = True
            if not need_sort:
                continue
            if easy:
                self.easy_count += 1
            fam_f = fam.get_father_handle()
            fam_m = fam.get_mother_handle()
            if fam_f:
                father = self.db.get_person_from_handle(fam_f)
                father_name = name_displayer.display(father)
            else:
                father_name = ''
            if fam_m:
                mother = self.db.get_person_from_handle(fam_m)
                mother_name = name_displayer.display(mother)
            else:
                mother_name = ''
            fam_data = (easy, fam.get_gramps_id(), father_name,
                        mother_name, fam_h)
            self.fam_liststore.append(row=fam_data)
        if len(self.fam_liststore) != 0:
            spath = Gtk.TreePath.new_first()
            self.fam_sel.select_path(spath)
            self.ch_s_sel.select_path(spath)
        self.progress.close()

    def sort_family_pr(self, fam_h):
        """ This prepares the family; list of children and the proposed list
            of sorted children.  It also returns an indicator of 'easy', i.e.
            if all children have valid dates.
        """
        fam = self.db.get_family_from_handle(fam_h)
        child_ref_list = fam.get_child_ref_list()
        children = []
        for index, child_ref in enumerate(child_ref_list):
            child = self.db.get_person_from_handle(child_ref.ref)
            birth = get_birth_or_fallback(self.db, child)
            if birth:
                b_date_s = birth.get_date_object().get_sort_value()
                birth_str = displayer.display(birth.get_date_object())
            else:
                b_date_s = 0
                birth_str = ""
            children.append((name_displayer.display(child), birth_str,
                             b_date_s, index))
        sorted_children = sorted(children, key=lambda child: child[2])
        return (children, sorted_children)


#------------------------------------------------------------------------
#
#
#
#------------------------------------------------------------------------
class BirthOrderOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)

        # Options specific for this report
        self.options_dict = {}
        self.options_help = {}
