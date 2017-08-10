# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2017       Paul Culley <paulr2787@gmail.com>
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
#
# $Id: $
#

#------------------------------------------------------------------------
#
# python modules
#
#------------------------------------------------------------------------
from copy import deepcopy
#import datetime
import time
import re
import locale
import ctypes
import os
#-------------------------------------------------------------------------
#
# GNOME libraries
#
#-------------------------------------------------------------------------
from gi.repository import Gtk

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
#from gramps.gen.display.name import displayer as global_name_display
from gramps.gen.merge.diff import diff_items, to_struct
from gramps.gen.dbstate import DbState
from gramps.gen.utils.db import get_participant_from_event
from gramps.gen.db import DbTxn
from gramps.gui.plug import tool
from gramps.gui.display import display_url
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.dialog import ErrorDialog, OkDialog
from gramps.gui.utils import ProgressMeter
from gramps.gui.editors import EditObject
from gramps.gen.db.utils import import_as_dict
from gramps.gen.simple import SimpleAccess
from gramps.gui.glade import Glade
from gramps.gen.lib import (Person, Family, Event, Source, Place, Citation,
                            Media, Repository, Note, Tag, GrampsType)
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.constfunc import win, mac
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
ngettext = _trans.ngettext

#-------------------------------------------------------------------------
#
# Constants
#
#-------------------------------------------------------------------------

WIKI_PAGE = 'https://gramps-project.org/wiki/index.php?title=Import_Merge_Tool'
TITLE = _("Import and merge a Gramps XML")
STATUS = 0
OBJ_TYP = 1
GID = 2
NAME = 3
SORT = 4
HNDL = 5
ACTION = 6
ACTION_INT = 7
S_MISS = _("Missing")
S_MISS_SO = 16
S_ADD = _("Added")
S_ADD_SO = 32
S_DIFFERS = _("Different")
S_DIFFERS_SO = 0
GENBTN = 99    # code for reneral use add/del/replace button
# The following pertains to actions that my be perfomed on the differences
A_NONE = 0
A_DEL = 1      # _("Delete original")
A_IGNORE = 2   # _("Ignore")
A_ADD = 3      # _("Add Import")
A_MERGE_L = 4  # _("Merge into original")
A_MERGE_R = 5  # _("Merge into import")
A_REPLACE = 6  # _("Replace with import")
A_KEEP = 7     # _("Keep original")

# The following lists must be in the same order as the A_* above
A_LST = ['',
         _("Delete original"),
         _("Ignore"),
         _("Add Import"),
         _("Merge into original"),
         _("Merge into import"),
         _("Replace with import"),
         _("Keep original")]
HINTS = [_("Use buttons below to set the 'Action' for each difference.  No "
           "changes will be made to your tree until you press 'Done' and "
           "confirm."),
         _("This item will be deleted from your tree.  Any "
           "referenced items were also marked for deletion."),
         _("This item will not be changed in your tree.  Any referenced items "
           "were also marked for Ignore."),
         _("This item will be added to your tree.  Any "
           "referenced items were also marked for adding."),
         _("This item will be merged, saving data from your tree.  Any "
           "referenced items were also marked for merging or adding."),
         _("This item will be merged, using data from the import.  Any "
           "referenced items were also marked for merging or adding."),
         _("The import data will entirely replace the data in your tree.  Any "
           "referenced items were also marked for replacement or removal."),
         _("This item will not be changed in your tree.  Any referenced items "
           "were also marked to keep.")]
# The following table translates actions to actions for specific lists
# (Added, missing, differs) lists...
ACT_ACT = [(A_NONE, A_NONE, A_NONE),
           (None, A_DEL, A_REPLACE),
           (A_IGNORE, A_IGNORE, A_IGNORE),
           (A_ADD, None, A_MERGE_R),
           (A_ADD, A_KEEP, A_MERGE_L),
           (A_ADD, A_KEEP, A_MERGE_R),
           (A_ADD, A_DEL, A_REPLACE)]

OBJ_LST = ['Family', 'Person', 'Citation', 'Event', 'Media', 'Note', 'Place',
           'Repository', 'Source', 'Tag']
# The following is so the translations file will contain the main object names
OBJ_XLT = [_('Family'), _('Person'), _('Citation'), _('Event'), _('Media'),
           _('Note'), _('Place'), _('Repository'), _('Source'), _('Tag')]
SPN_MONO = "<span font_family='monospace'>"
SPN_ = "</span>"


#------------------------------------------------------------------------
#
# Local Functions
#
#------------------------------------------------------------------------
def todate(tim):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tim))


#------------------------------------------------------------------------
#
# ImportMerge
#
#------------------------------------------------------------------------
class ImportMerge(tool.BatchTool, ManagedWindow):
    '''
    Create the ImportMerge Gui and run it.
    '''
    def __init__(self, dbstate, user, options_class, name, callback=None):
        uistate = user.uistate
        self._user = user

        tool.BatchTool.__init__(self, dbstate, user, options_class, name)
        if self.fail:
            return
        # we run modal so that the current db cannot change from under us
        ManagedWindow.__init__(self, uistate, [], self.__class__, modal=True)
        self.db1 = dbstate.db
        self.uistate = uistate
        # some diagnostic data saved to print at end
        self.classes = set()  # set of classes encountered
        self.nokey = set()  # list of missing keys
        self.notitle = set()  # list of objects/keys with no title
        # used in result display
        self.item1_hndls = {}  # handles found in current difference of db
        self.item2_hndls = {}  # handles found in current difference of import

        self.top = Gtk.Builder()
        # Found out that Glade does not support translations for plugins, so
        # have to do it manually.
        base = os.path.dirname(__file__)
        glade_file = base + os.sep + "importmerge.glade"
        # This is needed to make gtk.Builder work by specifying the
        # translations directory in a separate 'domain'
        try:
            localedomain = "addon"
            localepath = base + os.sep + "locale"
            if hasattr(locale, 'bindtextdomain'):
                libintl = locale
            elif win():  # apparently wants strings in bytes
                localedomain = localedomain.encode('utf-8')
                localepath = localepath.encode('utf-8')
                libintl = ctypes.cdll.LoadLibrary('libintl-8.dll')
            else:  # mac, No way for author to test this
                libintl = ctypes.cdll.LoadLibrary('libintl.dylib')

            libintl.bindtextdomain(localedomain, localepath)
            libintl.textdomain(localedomain)
            libintl.bind_textdomain_codeset(localedomain, "UTF-8")
            # and finally, tell Gtk Builder to use that domain
            self.top.set_translation_domain("addon")
        except (OSError, AttributeError):
            # Will leave it in English
            print("Localization of ImportMerge failed!")

        # start with a file name dialog
        self.top.add_objects_from_file(glade_file, ["filechooserdialog1",
                                                    "filefilter1"])
        # self.top = Glade(toplevel="filechooserdialog1",
        #                  also_load=["filefilter1"])
        window = self.top.get_object("filechooserdialog1")
        self.set_window(window, None, None)
        self.setup_configs('interface.importmergetoolfileopen', 750, 520)
        self.show()
        response = self.window.run()
        if response != Gtk.ResponseType.OK:
            if self.opened:
                # if user deleted the dialog it is already closed
                ManagedWindow.close(self, 0)
            window.destroy()
            return
        else:
            self.filename = self.window.get_filename()
            window.destroy()
        #self.filename = (r"d:\users\prc\documents\Gramps\data\tests\imp"
        #                 "_sample.gramps")

        # bring up the main screen and fill it
        self.top.add_objects_from_file(
            glade_file, ["main", "res_treeview", "res_liststore",
                         "diffs_liststore", "actionlabel"])
        # self.top = Glade(toplevel="main",
        #                  also_load=["res_treeview", "res_liststore",
        #                             "diffs_liststore", "actionlabel"])
        window = self.top.get_object("main")
        self.set_window(window, None, TITLE)
        self.window = window
        self.setup_configs('interface.importmergetool', 760, 560)
        self.top.connect_signals({
            "on_merge_l_clicked"    : (self.on_btn, A_MERGE_L),
            "on_merge_r_clicked"    : (self.on_btn, A_MERGE_R),
            "on_ignore_clicked"     : (self.on_btn, A_IGNORE),
            "on_unmark_clicked"     : (self.on_btn, A_NONE),
            "on_gen_clicked"        : (self.on_btn, GENBTN),
            "on_help_clicked"       : self.on_help_clicked,
            "on_edit_clicked"       : self.on_edit,
            "on_details_toggled"    : self.on_details,
            "on_delete_event"       : self.close,
            "on_close"              : self.done})

        self.merge_l_btn = self.top.get_object("merge_l_btn")
        self.merge_r_btn = self.top.get_object("merge_r_btn")
        self.edit_btn = self.top.get_object("edit_btn")
        self.gen_btn = self.top.get_object("gen_btn")
        self.ignore_btn = self.top.get_object("ignore_btn")
        self.unmark_btn = self.top.get_object("unmark_btn")
        self.parent_fam_btn = self.top.get_object("parent_fam_btn")
        self.fam_btn = self.top.get_object("fam_btn")
        self.more_details_btn = self.top.get_object("more_details_btn")
        self.more_details = False
        self.hint_lbl = self.top.get_object("hint")
        # diff_list = (status, _(obj_type), gid, name, sort, hndl,
        #              action_txt, action)
        self.diff_list = self.top.get_object("diffs_liststore")
        self.diff_list.set_sort_column_id(4, Gtk.SortType.ASCENDING)
        self.diff_list.set_sort_func(99, sort_name, None)
        self.res_list = self.top.get_object("res_liststore")
        self.res_view = self.top.get_object("res_treeview")
        self.diff_view = self.top.get_object("Diffs_treeview")
        self.diff_view.set_search_equal_func(search_func, None)
        self.diff_sel = self.diff_view.get_selection()
        self.diff_iter = None
        self.diffs = {}    # dict with hndl key and self.diff_list iters
        self.missing = {}  # dict with hndl key and self.diff_list iters
        self.added = {}    # dict with hndl key and self.diff_list iters
        self.my_families = True      # wether to automark my families
        self.parent_families = True  # wether to automark parent families
        self.res_mode = False
        self._progress = None
        self.show()
        self.diff_sel.connect('changed', self.on_diff_row_changed)
        if not self.find_diffs():
            self.close(0)
            return

    def close(self, *args):
        # print(self.classes, '\n', self.notitle, '\n', self.nokey, '\n')
        if hasattr(self, 'db2'):
            self.db2.disconnect_all()
            self.db2.close()
        ManagedWindow.close(self, *args)

    def progress_step(self, percent):
        ''' a hack to allow import XML callback progress to work since its
        step uses percentages instead of step per call'''
        self._progress._ProgressMeter__pbar_index = percent - 1.0
        self._progress.step()

    def find_diffs(self):
        ''' Load import file, and search for diffs. '''
        self._progress = ProgressMeter(_('Import and Merge tool'),
                                       _('Importing data...'),
                                       parent=self.window)
        # importxml uses the user.callback(percentage) for progress
        # not compatible with usual user progress. So bypass step()
        self._user.callback_function = \
            self.progress_step
        self.db2 = import_as_dict(self.filename, self._user)
        if self.db2 is None:
            self._progress.close()
            ErrorDialog(_("Import Failure"), parent=self.window)
            return False
        self.sa = [MySa(self.db1), MySa(self.db2)]
        self._user.parent = self.window  # so progress is right
        self._progress.set_pass(_('Searching...'),
                                self.db1.get_total() + self.db2.get_total())
        for sort, obj_type in enumerate(OBJ_LST):

            hndls_func1 = self.db1.get_table_metadata(obj_type)["handles_func"]
            hndls_func2 = self.db2.get_table_metadata(obj_type)["handles_func"]
            handle_func1 = self.db1.get_table_metadata(obj_type)["handle_func"]
            handle_func2 = self.db2.get_table_metadata(obj_type)["handle_func"]

            handles1 = sorted([handle for handle in hndls_func1()])
            handles2 = sorted([handle for handle in hndls_func2()])
            p_1 = 0
            p_2 = 0
            while p_1 < len(handles1) or p_2 < len(handles2):
                if p_1 != len(handles1) and p_2 != len(handles2) and \
                        handles1[p_1] == handles2[p_2]:  # in both
                    # compare the two items for equality
                    diff = diff_items(obj_type,
                                      to_struct(handle_func1(handles1[p_1])),
                                      to_struct(handle_func2(handles2[p_2])))
                    hndl = handles1[p_1]
                    self._progress.step()
                    self._progress.step()
                    p_1 += 1
                    p_2 += 1
                    if not diff:
                        continue  # same!
                    item = self.db1.get_from_name_and_handle(obj_type, hndl)
                    gid, name = self.sa[0].describe(item)
                    data = (S_DIFFERS, _(obj_type), gid, name,
                            sort, hndl, "", 0)
                    d_iter = self.diff_list.append(row=data)
                    self.diffs[hndl] = d_iter
                elif p_1 != len(handles1) and (p_2 == len(handles2) or
                                               handles1[p_1] < handles2[p_2]):
                    # p_1 is missing in p_2 (missing)
                    hndl = handles1[p_1]
                    item = self.db1.get_from_name_and_handle(obj_type, hndl)
                    gid, name = self.sa[0].describe(item)
                    data = (S_MISS, _(obj_type), gid, name,
                            S_MISS_SO + sort, hndl, "", 0)
                    d_iter = self.diff_list.append(row=data)
                    self.missing[hndl] = d_iter
                    self._progress.step()
                    p_1 += 1
                elif p_2 != len(handles2) and (p_1 == len(handles1) or
                                               handles1[p_1] > handles2[p_2]):
                    # p_2 is missing in p_1 (added)
                    hndl = handles2[p_2]
                    item = self.db2.get_from_name_and_handle(obj_type, hndl)
                    gid, name = self.sa[1].describe(item)
                    data = (S_ADD, _(obj_type), gid, name,
                            S_ADD_SO + sort, hndl, "", 0)
                    d_iter = self.diff_list.append(row=data)
                    self.added[hndl] = d_iter
                    self._progress.step()
                    p_2 += 1
        self._progress.close()
        if len(self.diff_list) != 0:
            spath = Gtk.TreePath.new_first()
            self.diff_sel.select_path(spath)
            self.diff_iter = self.diff_sel.get_selected()[1]
            return True
        else:
            OkDialog(_("Your Tree and import are the same."),
                     parent=self.window)
            return False

    def format_struct_path(self, path):
        ''' clean up path text for better readability '''
        retval = ""
        parts = path.split(".")
        for part in parts:
            if retval:
                retval += ", "
            if "[" in part and "]" in part:
                part, index = re.match(r"(.*)\[(\d*)\]", part).groups()
                retval += "%s #%s" % (part.replace("_", " "), int(index) + 1)
            else:
                retval += part
        return retval

    def report_details(self, path, diff1, diff2, diff3):
        ''' report out the detailed difference for two items '''
        if isinstance(diff1, bool):
            desc1 = repr(diff1)
        else:
            desc1 = str(diff1) if diff1 is not None else ""
        if isinstance(diff2, bool):
            desc2 = repr(diff2)
        else:
            desc2 = str(diff2) if diff2 is not None else ""
        if isinstance(diff3, bool):
            desc3 = repr(diff3)
        else:
            desc3 = str(diff3) if diff3 is not None else ""
        if path.endswith(_("Last changed")):
            diff1 = todate(diff1)
            diff2 = todate(diff2)
            diff3 = todate(diff3)
            desc1 = diff1
            desc2 = diff2
            desc3 = diff3
        if diff1 == diff2:
            return
        obj_type = self.item1_hndls.get(desc1)
        if obj_type:
            hndl_func = self.db1.get_table_metadata(obj_type)["handle_func"]
            gname = self.sa[0].describe(hndl_func(desc1))
            text = _("your tree ")
            desc1 = "%s%s: [%s] %s" % (text, _(obj_type), gname[0], gname[1])
        else:
            obj_type = self.item2_hndls.get(desc2)

        if self.item2_hndls.get(desc2):
            if self.added.get(desc2):
                text = _("imported ")
            else:
                text = _("your tree ")
            hndl_func = self.db2.get_table_metadata(obj_type)["handle_func"]
            gname = self.sa[1].describe(hndl_func(desc2))
            desc2 = "%s%s: [%s] %s" % (text, _(obj_type), gname[0], gname[1])
        if self.item2_hndls.get(desc3):
            if self.added.get(desc3):
                text = _("imported ")
            else:
                text = _("your tree ")
            hndl_func = self.db2.get_table_metadata(obj_type)["handle_func"]
            gname = self.sa[1].describe(hndl_func(desc3))
            desc3 = "%s%s: [%s] %s" % (text, _(obj_type), gname[0], gname[1])
        elif self.item1_hndls.get(desc3):
            if self.added.get(desc3):
                text = _("imported ")
            else:
                text = _("your tree ")
            hndl_func = self.db1.get_table_metadata(obj_type)["handle_func"]
            gname = self.sa[0].describe(hndl_func(desc3))
            desc3 = "%s%s: [%s] %s" % (text, _(obj_type), gname[0], gname[1])
        path = self.format_struct_path(path)
        text = SPN_MONO + _("Original") + " >> " + SPN_ + desc1 + "\n"
        text += SPN_MONO + _("Imported") + " >> " + SPN_ + desc2
        if self.res_mode:
            text += "\n" + SPN_MONO + _("Result  ") + " >> " + SPN_ + desc3
        self.res_list.append((path, text))

    def report_diff(self, path, item1, item2, item3=None):
        '''
        Compare two struct objects and report differences.
        '''
        # if to_struct(item1) == to_struct(item2):
        #     return   # _eq_ doesn't work on Gramps objects for this purpose
        if item1 is None and item2 is None:
            return
        elif (isinstance(item1, (list, tuple)) or
              isinstance(item2, (list, tuple))):
            #assert not (isinstance(item1, tuple) or
            # if (isinstance(item1, tuple) or isinstance(item2, tuple)):
            #     pass  # yes there are tuples
            len1 = len(item1) if isinstance(item1, (list, tuple)) else 0
            len2 = len(item2) if isinstance(item2, (list, tuple)) else 0
            len3 = 0
            if item3 and isinstance(item3, (list, tuple)):
                len3 = len(item3)
            for pos in range(max(len1, len2, len3)):
                val1 = item1[pos] if pos < len1 else None
                val2 = item2[pos] if pos < len2 else None
                val3 = item3[pos] if pos < len3 else None
                self.report_diff(path + ("[%d]" % pos), val1, val2, val3)
        elif hasattr(item1, '__dict__') or hasattr(item2, '__dict__'):
            # dealing with Gramps object.  Note: we assume that Gramps class
            # objects attached to an another object are always the same type

            val1 = val2 = val3 = None
            if item1 is None:
                class_name = item2.__class__.__name__
                schema = item2.get_schema()
                val2 = schema.get('title', class_name)
            else:
                class_name = item1.__class__.__name__
                schema = item1.get_schema()
            self.classes.add(class_name)  # diagnostic data
            if schema.get('title') is None:
                self.notitle.add(class_name)  # diagnostic data
            if not self.more_details:
                # test if we have added/deleted and only list the class info
                if item2 is None:
                    val1 = schema.get('title', class_name)
                if item1 is None or item2 is None:
                    val3 = schema.get('title', class_name) \
                        if item3 is not None else None
                    self.report_details(path, val1, val2, val3)
                    return
                assert item1.__class__.__name__ == item2.__class__.__name__

            item = item1 if item2 is None else item2
            keys = []
            if isinstance(item, GrampsType):
                keys.append('string')
            for key in item.__dict__.keys():
                if not key.startswith('_'):
                    keys.append(key)
            for key, value in item.__class__.__dict__.items():
                if isinstance(value, property):
                    if key != 'year':
                        keys.append(key)
            for key in keys:
                val1 = getattr(item1, key) if item1 is not None else None
                val2 = getattr(item2, key) if item2 is not None else None
                val3 = getattr(item3, key) if item3 is not None else None
                if key == "dict":  # a raw dict, not a struct
                    self.report_details(path, val1, val2, val3)
                else:  # if not key.startswith('_'):
                    key_ = key.replace('_' + class_name + '__', '')
                    if schema['properties'].get(key_) is None:
                        self.nokey.add(class_name + ':' + key)  # diagnostic
                        continue
                    if schema['properties'][key_].get('title') is None:
                        self.notitle.add(class_name + ':' + key_)  # diagnostic
                    key_ = schema['properties'][key_].get('title', key_)
                    self.report_diff(path + "." + key_, val1, val2, val3)
        else:
            self.report_details(path, item1, item2, item3)

    def mark_refs(self, status, obj_type, hndl, mark, old_mrk, clear):
        '''Mark other additions, differs, or missing that are referenced by the
        current primary object.  This is a recursive operation, if a new
        object is found, we also mark it and go on down.  We avoid potental
        loops in the object references by not marking an object already marked.
        If we need to change a mark, we clear the previous mark first, using
        the original mark info.  This avoids issues with different mark types
        that follow different paths through the tree.

        status: str used to figure out which list we are marking
        obj_type: for object to check
        hndl: handle for object to check
        mark: index into A_LST action strings
        old_mrk: Previous mark of main item, used to decide if we should
                override priority
        clear:  Indicates we are clearing a previous auto mark
        '''
        # do markup of referenced items
        if status == S_ADD:
            # we need to check added and differs lists
            obj = self.db2.get_from_name_and_handle(obj_type, hndl)
            # don't automark families unless user wants.
            # So get family handles we DON't want to automark
            not_list = []
            if obj_type == 'Person':
                if not self.parent_families:
                    not_list = obj.parent_family_list[:]
                if not self.my_families:
                    not_list.extend(obj.family_list)
            for dummy, handle in obj.get_referenced_handles_recursively():
                d_iter = self.added.get(handle)
                self.mark_it(d_iter, not_list, handle, mark, old_mrk, clear)
                d_iter = self.diffs.get(handle)
                self.mark_it(d_iter, not_list, handle, mark, old_mrk, clear)
        elif status == S_MISS:
            # we need to check missing and differs lists
            obj = self.db1.get_from_name_and_handle(obj_type, hndl)
            # don't automark families unless user wants.
            # So get family handles we DON't want to automark
            not_list = []
            if obj_type == 'Person':
                if not self.parent_families:
                    not_list = obj.parent_family_list[:]
                if not self.my_families:
                    not_list.extend(obj.family_list)
            for dummy, handle in obj.get_referenced_handles_recursively():
                d_iter = self.missing.get(handle)
                self.mark_it(d_iter, not_list, handle, mark, old_mrk, clear)
                d_iter = self.diffs.get(handle)
                self.mark_it(d_iter, not_list, handle, mark, old_mrk, clear)
        else:  # differs list:
            # we need to check all three lists
            if not clear:  # use result object references
                item1, dummy, obj = self.diff_result(xlt_act(mark, status),
                                                     obj_type, hndl)
            else:
                # we are clearing previous mark, so need to use old references
                item1, dummy, obj = self.diff_result(xlt_act(old_mrk, status),
                                                     obj_type, hndl)
            # don't automark families unless user wants.
            # So get family handles we DON't want to automark
            not_list = []
            if obj_type == 'Person':
                if not self.parent_families:
                    not_list = obj.parent_family_list[:]
                if not self.my_families:
                    not_list.extend(obj.family_list)
            r_lst = obj.get_referenced_handles_recursively()
            for dummy, handle in r_lst:
                d_iter = self.added.get(handle)
                self.mark_it(d_iter, not_list, handle, mark, old_mrk, clear)
                if xlt_act(mark, S_MISS) != A_DEL:
                    d_iter = self.missing.get(handle)
                self.mark_it(d_iter, not_list, handle, mark, old_mrk, clear)
                d_iter = self.diffs.get(handle)
                self.mark_it(d_iter, not_list, handle, mark, old_mrk, clear)
            # if we have something in differs list that is replaced, we
            # actually want to mark up the refs in the missing list that are
            # no longer in the object.
            if xlt_act(mark, S_MISS) == A_DEL:
                set1 = set(item1.get_referenced_handles_recursively())
                set2 = set(r_lst)
                for dummy, handle in set1 - set2:
                    d_iter = self.missing.get(handle)
                    self.mark_it(d_iter, not_list, handle, mark, old_mrk,
                                 clear)

    def mark_it(self, d_iter, not_list, handle, mark, old_mrk, clear):
        ''' Common code for mark_refs routine '''
        if d_iter is None:
            return  # not in the list of differences
        if handle in not_list:
            return  # family handle we don't want to mark.
        cur_mark = self.get_act(d_iter, None)
        if clear:  # if clearing previous marks
            if cur_mark == A_NONE:
                return  # already marked (prevents infinite recursion)
        else:  # auto marking
            if cur_mark == mark or cur_mark + 10 == mark:
                return  # already marked (prevents infinite recursion)
        # if the previous mark is same as this, user changed mind, allow
        # if new mark is higher priority, allow.  if never marked, allow
        status = self.diff_list[d_iter][STATUS]
        if cur_mark == old_mrk - 10 or \
                mark - 10 > cur_mark or cur_mark == A_NONE:
            obj_type = OBJ_LST[self.diff_list[d_iter][SORT] & 15]
            if cur_mark or clear:
                # we are changing the mark, need to clear using old mark first
                self.set_act(d_iter, A_NONE, '', status)
                self.mark_refs(status, obj_type, handle, mark, old_mrk, True)
                # now we can mark up according to new mark
            if not clear:
                # mark conflict if priority allows a mark
                auto = '?' if mark - 10 > cur_mark else '*'
                self.set_act(d_iter, mark, auto, status)
                self.mark_refs(status, obj_type, handle, mark, old_mrk, False)
        elif cur_mark < 0:  # no conflict for manual marks
            # not marked by priority, but show conflict
            self.set_act(d_iter, cur_mark + 10, '?', status)

    def done(self, *dummy):
        '''User is finished with tool, time to save work.'''

        top = Glade(toplevel='savedialog').toplevel
        top.set_transient_for(self.window)
        parent_modal = self.window.get_modal()
        if parent_modal:
            self.window.set_modal(False)
        top.show()
        response = top.run()
        top.destroy()
        if self.window and parent_modal:
            self.window.set_modal(True)
        if response == Gtk.ResponseType.CANCEL:
            return
        if response == Gtk.ResponseType.NO:
            self.close(0)
            return
        # response == Gtk.ResponseType.YES:

        self._progress = ProgressMeter(_('Import and Merge tool'),
                                       parent=self.window)
        self._progress.set_pass(_("Processing..."), len(self.diff_list))
        with DbTxn(_("Import and Merge"), self.db1, batch=True) as trans:

            d_iter = self.diff_list.get_iter_first()
            while d_iter:
                self._progress.step()
                status, hndl = self.diff_list.get(d_iter, STATUS, HNDL)
                obj_type = OBJ_LST[self.diff_list[d_iter][SORT] & 15]
                action = self.get_act(d_iter, status)
                d_iter = self.diff_list.iter_next(d_iter)
                self.do_commits(status, obj_type, hndl, action, trans)
        self._progress.close()
        self.close(0)

    def do_commits(self, status, obj_type, hndl, action, trans):
        ''' To make sure db will be consistent, we check all result objects
        to make sure referenced items are something valid.  User may have
        excluded something that an included item referenced.
        For differs items, we create the result object according to action.
          For each handle in referenced items, we check if it is
        1) in added list and marked for Exclusion (Ignore).
        2) in missing list and marked for deletion.
        3) a Person or Family, and in differs list and marked for exclusion
          (see below)
        If any are true, we remove reference from object.

        For Added list we use added item if marked for inclusion.
          For each handle in referenced items, we check if it is
        1) in added list and marked for Exclusion (Ignore).
        2) a Person or Family, and in differs list and marked for exclusion
          (see below)
        If any are true, we remove reference from object.

        For items in missing list, if an item action specifies exclusion we
        can safely delete it, other items that reference it will have
        references removed.  If it specifies inclusion it's already in current
        db, but another item in the differs list could sill be referencing it.
          For each handle in referenced items, we check if it is
        1) in missing list and marked for Exclusion (delete).
        2) a Person or Family, and in differs list and marked for exclusion
          (see below)
        If any are true, we remove reference from object.

        For items in the differs list, Person or Family, we need to make a
        more careful check.  The Person/Family links are bi-directional.
        A Person has a link to his and/or his parents family, and the family
        has links back to the Person.  So we need to establish the actual final
        object layout of the referenced item, and then check for handle
        presense in the correct place.

        We need to make sure that we don't reuse GIDs on add/merge.

        Once checks are complete, we do the commit if there are any changes.

        It would be nice if we always had a generic object method API call.
        Since we don't, I make the method call up as a string and then use
        getattr to get the actual method and append the () to call it.
        '''
        changed = False
        if status == S_MISS and action == A_DEL:
            getattr(self.db1, 'remove_' + obj_type.lower())(hndl, trans)
            return
        elif status == S_MISS and action != A_DEL:
            item = self.db1.get_from_name_and_handle(obj_type, hndl)
            r_hndls = item.get_referenced_handles_recursively()
            for r_objtype, r_hndl in r_hndls:
                # now check the differences list for a match
                if self.check_diffs(r_objtype, r_hndl, obj_type, item):
                    changed = True
                    continue
                # now check the missing list for a match
                changed += self.check_miss(r_objtype, r_hndl, item)
            # finally commit it
            if changed:
                getattr(self.db1, 'commit_' + obj_type.lower())(item, trans)
            return
        elif status == S_DIFFERS:
            item1, dummy, item = self.diff_result(action, obj_type, hndl)
            if action == A_NONE or action == A_IGNORE:
                item = item1
            else:
                changed = True
            r_hndls = item.get_referenced_handles_recursively()
            for r_objtype, r_hndl in r_hndls:
                # now check the differences list for a match
                if self.check_diffs(r_objtype, r_hndl, obj_type, item):
                    changed = True
                    continue
                # check the added list for a match
                if self.check_added(r_objtype, r_hndl, item):
                    changed = True
                    continue
                # now check the missing list for a match
                changed += self.check_miss(r_objtype, r_hndl, item)
            # check for GID conflict
            if item.gramps_id != item1.gramps_id:
                if getattr(self.db1, 'has_' + obj_type.lower() +
                           '_gramps_id')(item.gramps_id):
                    item.gramps_id = getattr(self.db1, 'find_next_' +
                                             obj_type.lower() +
                                             '_gramps_id')()
                    changed = True
        else:  # status == S_ADD:
            if action != A_ADD:
                return
            changed = True
            item = self.db2.get_from_name_and_handle(obj_type, hndl)
            r_hndls = item.get_referenced_handles_recursively()
            for r_objtype, r_hndl in r_hndls:
                # check the added list for a match
                if self.check_added(r_objtype, r_hndl, item):
                    continue
                # now check the differences list for a match
                self.check_diffs(r_objtype, r_hndl, obj_type, item)
            # check for GID conflict
            if getattr(self.db1, 'has_' + obj_type.lower() +
                       '_gramps_id')(item.gramps_id):
                item.gramps_id = getattr(self.db1, 'find_next_' +
                                         obj_type.lower() +
                                         '_gramps_id')()
                changed = True

        # finally commit it
        if changed:
            getattr(self.db1, 'commit_' + obj_type.lower())(item, trans)

    def check_miss(self, r_objtype, r_hndl, item):
        ''' Check the missing list for a non-included reference,
        if found remove it from item and return True '''
        d_iter = self.missing.get(r_hndl)
        if d_iter:
            action = self.get_act(d_iter, S_MISS)
            if action == A_DEL:  # remove it
                item.remove_handle_references(r_objtype, [r_hndl])
                return True
        return False

    def check_added(self, r_objtype, r_hndl, item):
        ''' Check the added list for a non-included reference,
        if found remove it from item and return True '''
        d_iter = self.added.get(r_hndl)
        if d_iter:
            action = self.get_act(d_iter, S_ADD)
            if action != A_ADD:  # ignore it
                item.remove_handle_references(r_objtype, [r_hndl])
                return True
        return False

    def check_diffs(self, r_objtyp, r_hndl, obj_type, item):
        ''' Only need to check for the bi-directional Person<=>Family
        references on the diff list.  These could be included or not depending
        on the type of merge action.
        If we make a change, return True
        '''
        d_iter = self.diffs.get(r_hndl)
        if d_iter and (r_objtyp == 'Person' or r_objtyp == 'Family'):
            action = self.get_act(d_iter, S_DIFFERS)
            dummy, dummy, r_item = self.diff_result(action, r_objtyp, r_hndl)
            if obj_type == 'Person' and r_objtyp == 'Family':
                for fam_h in item.family_list:
                    if fam_h == r_item.handle and (
                            item.handle == r_item.father_handle or
                            item.handle == r_item.mother_handle):
                        return False
                for fam_h in item.parent_family_list:
                    if fam_h == r_item.handle:
                        for child in r_item.child_ref_list:
                            if child.ref == item.handle:
                                return False
            elif obj_type == 'Family' and r_objtyp == 'Person':
                for fam_h in r_item.family_list:
                    if fam_h == item.handle and (
                            r_item.handle == item.father_handle or
                            r_item.handle == item.mother_handle):
                        return False
                for fam_h in r_item.parent_family_list:
                    if fam_h == item.handle:
                        for child in item.child_ref_list:
                            if child.ref == r_item.handle:
                                return False
            else:  # another type of reference, (Person assoc), don't care
                return False
            item.remove_handle_references(r_objtyp, [r_hndl])
            return True

    def on_diff_row_changed(self, *obj):
        ''' Signal: update lower panes when the diff pane row changes '''
        if len(self.diff_list) == 0 or not obj:
            return
        self.diff_iter = obj[0].get_selected()[1]
        if not self.diff_iter:
            return
        status = self.diff_list[self.diff_iter][STATUS]
        self.fix_btns(status)
        self.show_results()

    def fix_btns(self, status):
        ''' Update the buttons depending on status'''
        if status == S_DIFFERS:
            self.gen_btn.set_label(_("Replace"))
            self.edit_btn.set_sensitive(True)
            self.merge_l_btn.set_sensitive(True)
            self.merge_r_btn.set_sensitive(True)
        elif status == S_ADD:
            self.gen_btn.set_label(_("Add"))
            self.edit_btn.set_sensitive(True)
            self.merge_l_btn.set_sensitive(False)
            self.merge_r_btn.set_sensitive(False)
        else:
            self.gen_btn.set_label(_("Delete"))
            self.edit_btn.set_sensitive(False)
            self.merge_l_btn.set_sensitive(False)
            self.merge_r_btn.set_sensitive(False)

    def show_results(self):
        ''' update the lower pane '''
        self.more_details = self.more_details_btn.get_active()
        status = self.diff_list[self.diff_iter][STATUS]
        obj_type = OBJ_LST[self.diff_list[self.diff_iter][SORT] & 15]
        action = self.get_act(self.diff_iter, status)
        hndl = self.diff_list[self.diff_iter][HNDL]
        self.hint_lbl.set_text(HINTS[action])
        self.res_mode = action != 0
        self.res_list.clear()
        if status == S_DIFFERS:
            item1, item2, item3 = self.diff_result(action, obj_type, hndl)
            self.item1_hndls = {i[1]: i[0] for i in
                                item1.get_referenced_handles_recursively()}
            self.item2_hndls = {i[1]: i[0] for i in
                                item2.get_referenced_handles_recursively()}
            self.report_diff(_(obj_type), item1, item2, item3)
        elif status == S_ADD:
            item = self.db2.get_from_name_and_handle(obj_type, hndl)
            self.item2_hndls = {i[1]: i[0] for i in
                                item.get_referenced_handles_recursively()}
            if self.more_details:
                if action == A_ADD:
                    self.report_diff(_(obj_type), None, item, item)
                else:
                    self.report_diff(_(obj_type), None, item, None)
                return
            desc1 = ""
            desc2 = '[%s] %s' % self.sa[1].describe(item)
            if action == A_ADD:
                desc3 = desc2
            else:  # action == A_IGNORE:
                desc3 = desc1
            text = SPN_MONO + _("Original") + " >> " + SPN_ + desc1 + "\n"
            text += SPN_MONO + _("Imported") + " >> " + SPN_ + desc2
            if self.res_mode:
                text += "\n" + SPN_MONO + _("Result  ") + " >> " + SPN_ + desc3
            self.res_list.append((_(obj_type), text))
        else:  # status == S_MISS:
            item = self.db1.get_from_name_and_handle(obj_type, hndl)
            self.item1_hndls = {i[1]: i[0] for i in
                                item.get_referenced_handles_recursively()}
            if self.more_details:
                if action == A_IGNORE:
                    self.report_diff(_(obj_type), item, None, item)
                else:
                    self.report_diff(_(obj_type), item, None, None)
                return
            desc1 = '[%s] %s' % self.sa[0].describe(item)
            desc2 = ""
            if action == A_IGNORE or action == A_KEEP:
                desc3 = desc1
            else:  # action == A_DEL
                desc3 = "<s>" + desc1 + "</s>"
            text = SPN_MONO + _("Original") + " >> " + SPN_ + desc1 + "\n"
            text += SPN_MONO + _("Imported") + " >> " + SPN_ + desc2
            if self.res_mode:
                text += "\n" + SPN_MONO + _("Result  ") + " >> " + SPN_ + desc3
            self.res_list.append((_(obj_type), text))

    def diff_result(self, action, obj_type, hndl):
        ''' this creates all three objects, the last of which is the actual
        result when dealing with the differs list.  Result depends on action,
        for merges we create the merged object (use deepcopy to avoid messing
        up our source).  For ignore and replace we can refer to original
        objects. '''
        item1 = self.db1.get_from_name_and_handle(obj_type, hndl)
        item2 = self.db2.get_from_name_and_handle(obj_type, hndl)
        item3 = None
        if action == A_REPLACE:
            item3 = item2
        elif action == A_IGNORE or action == A_NONE:
            item3 = item1
        elif action == A_MERGE_L:
            item3 = deepcopy(item1)
            item_m = deepcopy(item2)
            item_m.gramps_id = None
            item3.merge(item_m)
        elif action == A_MERGE_R:
            item3 = deepcopy(item2)
            item_m = deepcopy(item1)
            item_m.gramps_id = None
            item3.merge(item_m)
        else:
            raise AssertionError("Unexpected action")
        return item1, item2, item3

    def on_edit(self, dummy):
        ''' deal with edit import button press '''
        if not self.diff_iter:
            return
        hndl = self.diff_list[self.diff_iter][HNDL]
        obj_type = OBJ_LST[self.diff_list[self.diff_iter][SORT] & 15]
        # Not sure if changes affect automark, so clear them
        self.on_btn(None, A_NONE)
        dbstate = DbState()
        dbstate.db = self.db2
        self.connect_everything()
        EditObject(dbstate, self.uistate, self.track, obj_type, prop='handle',
                   value=hndl)

    def edit_callback(self, *args):
        ''' This gets called by db signals during the edit operation
        args = (obj_type, operation, list_of_handles)
        If operation is an update and handle is in self.added group, or
        self.diffs group, just refresh lower pane.
        If operation is an update and handle is NOT in one of above groups,
        then it must be in original db.  We need to make a new diffs group
        entry.
        if operation is add, handle is not in either group, then we need to add
        an entry to added group; means user added something new.
        Since changes in any list could affect the automark we should redo
        auto mark for current entry in likely case he added a new referenced
        item.  It's possible he added a new primary object that is not
        referenced, this will end up with no action initially.
        Should never get a delete operation'''
        edit_hndl = self.diff_list[self.diff_iter][HNDL]
        obj_type = args[0].capitalize()
        if args[1] == 'update':
            for hndl in args[2]:
                if self.added.get(hndl) or self.diffs.get(hndl):
                    continue
                item1 = self.db1.get_from_name_and_handle(obj_type, hndl)
                item2 = self.db2.get_from_name_and_handle(obj_type, hndl)
                diff = diff_items(obj_type, to_struct(item1), to_struct(item2))
                if diff:
                    item = self.db1.get_from_name_and_handle(obj_type, hndl)
                    gid, name = self.sa[0].describe(item)
                    sort = OBJ_LST.index(obj_type) + S_DIFFERS_SO
                    data = (S_DIFFERS, _(obj_type), gid, name,
                            sort, hndl, "", 0)
                    d_iter = self.diff_list.append(row=data)
                    self.diffs[hndl] = d_iter

        elif args[1] == 'add':
            for hndl in args[2]:
                item = self.db2.get_from_name_and_handle(obj_type, hndl)
                gid, name = self.sa[1].describe(item)
                sort = OBJ_LST.index(obj_type) + S_ADD_SO
                data = (S_ADD, _(obj_type), gid, name, sort, hndl, "", 0)
                d_iter = self.diff_list.append(row=data)
                self.added[hndl] = d_iter

        else:  # delete
            raise AssertionError("User deleted something unexpectedly")
        if args[1] == 'update':
            for hndl in args[2]:
                if hndl == edit_hndl:
                    # update of original edit, should be last one so refresh
                    self.show_results()  # lower pane

    def on_btn(self, dummy, action):
        ''' deal with general action button press '''
        self.parent_families = self.parent_fam_btn.get_active()
        self.my_families = self.fam_btn.get_active()
        if not self.diff_iter:
            return
        old_act = self.get_act(self.diff_iter, None)
        if old_act < 0:  # for manual change, we ignore automark
            old_act += 10
        hndl = self.diff_list[self.diff_iter][HNDL]
        status = self.diff_list[self.diff_iter][STATUS]
        obj_type = OBJ_LST[self.diff_list[self.diff_iter][SORT] & 15]
        # note that GENBTN really a multi mode button.
        if action == GENBTN:
            action = A_DEL if status == S_MISS else \
                A_ADD if status == S_ADD else A_REPLACE
        if action == A_NONE or old_act:
            # we are changing the mark, need to clear using old mark first
            self.set_act(self.diff_iter, A_NONE, '', status)
            self.mark_refs(status, obj_type, hndl, action, old_act, True)
        if action != A_NONE:
            self.set_act(self.diff_iter, action, '', status)
            self.mark_refs(status, obj_type, hndl, action, old_act, False)
        self.show_results()

    def on_details(self, dummy):
        ''' deal with button press '''
        self.show_results()

    def on_help_clicked(self, dummy):
        ''' Button: Display the relevant portion of GRAMPS manual'''
        display_url(WIKI_PAGE)

    def build_menu_names(self, obj):
        ''' So ManagedWindow is happy '''
        return (TITLE, TITLE)

    def connect_everything(self):
        ''' Make connections to all db signals of import db '''
        for sname in OBJ_LST:
            for etype in ['add', 'delete', 'update']:
                sig_name = sname.lower() + '-' + etype
                sig_func = sname.lower() + '_' + etype
                my_func = make_function(sig_name)
                my_func.__name__ = sig_func
                my_func.__doc__ = sig_func
                setattr(ImportMerge, sig_func, my_func)
                self.db2.connect(sig_name, getattr(self, sig_func))

    def get_act(self, d_iter, status):
        ''' return the action for the current entry.  If status is provided,
        we give translated action specifically for the list involved.'''
        action = self.diff_list[d_iter][ACTION_INT]
        if status:
            if action < 0:
                action += 10  # don't care about automark for final action
            if status == S_ADD:
                action = ACT_ACT[action][0]
            elif status == S_MISS:
                action = ACT_ACT[action][1]
            else:  # status == S_DIFFERS
                action = ACT_ACT[action][2]
        return action

    def set_act(self, d_iter, action, auto, status):
        ''' set the action for the current entry.  Since we have both text and
        int versions of action, update both.  The text version shows the
        translated action appropriate to the specific list.'''
        self.diff_list[d_iter][ACTION_INT] = action - (10 if auto else 0)
        if status == S_ADD:
            action = ACT_ACT[action][0]
        elif status == S_MISS:
            action = ACT_ACT[action][1]
        else:  # status == S_DIFFERS
            action = ACT_ACT[action][2]
        self.diff_list[d_iter][ACTION] = auto + A_LST[action]


def xlt_act(action, status):
    ''' do a list specific translation of the action.'''
    if status:
        if action < 0:
            action += 10  # don't care about automark for final action
    if status == S_ADD:
        action = ACT_ACT[action][0]
    elif status == S_MISS:
        action = ACT_ACT[action][1]
    else:  # status == S_DIFFERS
        action = ACT_ACT[action][2]
    return action


def make_function(sig_name):
    """ This is here to support the dynamic function creation.  This creates
    the signal function (a method, to be precise).
    """
    def myfunc(self, *args):
        obj_type, action = sig_name.split('-')
        self.edit_callback(obj_type, action, *args)

    return myfunc


def sort_name(model, iter1, iter2, dummy):
    ''' This supports the Gtk sort for the name field.  We group the sorted
    names by object type.'''
    item1 = model[iter1][OBJ_TYP] + model[iter1][NAME]
    item2 = model[iter2][OBJ_TYP] + model[iter2][NAME]
    return (item1 > item2) - (item1 < item2)


def search_func(model, column, key, _iter, dummy):
    ''' This supports the Gtk 'find'.  Allows user to find in name field or
    ID field.  We ignore the column (from glade) and use our own.'''
    if key.startswith('#'):
        return key[1:].lower() not in model[_iter][GID].lower()
    else:
        return key.lower() not in model[_iter][NAME].lower()


#------------------------------------------------------------------------
#
# MySa extended SimpleAccess for more info
#
#------------------------------------------------------------------------
class MySa(SimpleAccess):
    ''' Extended SimpleAccess '''

    def __init__(self, dbase):
        SimpleAccess.__init__(self, dbase)

    def describe(self, obj, prop=None, value=None):
        '''
        Given a object, return a string describing the object.
        '''
        if prop and value:
            if self.dbase.get_table_metadata(obj):
                obj = self.dbase.get_table_metadata(obj)[prop + "_func"](value)
        if isinstance(obj, Person):
            return (self.gid(obj), trunc(self.name(obj)))
        elif isinstance(obj, Event):
            return (self.gid(obj), trunc("%s: %s" % (
                self.event_type(obj),
                get_participant_from_event(self.dbase, obj.handle))))
        elif isinstance(obj, Family):
            return (self.gid(obj), trunc(
                "%s/%s" % (self.name(self.mother(obj)),
                           self.name(self.father(obj)))))
        elif isinstance(obj, Media):
            return (self.gid(obj), trunc(obj.desc))
        elif isinstance(obj, Source):
            return (self.gid(obj), trunc(self.title(obj)))
        elif isinstance(obj, Citation):
            return (self.gid(obj), trunc(obj.page))
        elif isinstance(obj, Place):
            place_title = trunc(place_displayer.display(self.dbase, obj))
            return (self.gid(obj), place_title)
        elif isinstance(obj, Repository):
            return (self.gid(obj), trunc(obj.name))
        elif isinstance(obj, Note):
            return (self.gid(obj), trunc(obj.get()))
        elif isinstance(obj, Tag):
            return ("", obj.name)
        else:
            return ("", "Error: incorrect object class in describe: '%s'"
                    % type(obj))


def trunc(content):
    ''' A simple truncation to make for shorter name/description '''
    length = 120
    content = ' '.join(content.split())
    if len(content) <= length:
        return content
    else:
        return content[:length - 3] + '...'


#------------------------------------------------------------------------
#
# ImportMergeOptions
#
#------------------------------------------------------------------------
class ImportMergeOptions(tool.ToolOptions):
    ''' Options for the ImportMerge '''

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)

        # Options specific for this report
        self.options_dict = {}
        self.options_help = {}
