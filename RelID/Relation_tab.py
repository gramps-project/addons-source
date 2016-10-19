#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2006  Donald N. Allingham
# Copyright (C) 2008       Brian G. Matherly
# Copyright (C) 2010       Jakim Friant
# Copyright (C) 2012       Doug Blank
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
Relations tab.

"""
from gi.repository import Gtk
import time
from uuid import uuid4
import logging
import platform, os

from gramps.gui.listmodel import ListModel, INTEGER
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.utils import ProgressMeter
from gramps.gui.plug import tool
from gramps.gui.dialog import WarningDialog
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.relationship import get_relationship_calculator
from gramps.gen.filters import GenericFilterFactory, rules
from gramps.gen.config import config
from gramps.gen.utils.docgen import ODSTab
import number
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

_LOG = logging.getLogger('.Reltab')
_LOG.info(platform.uname())
#_LOG.info("Number of CPU available: %s" % len(os.sched_getaffinity(0)))
#_LOG.info("Scheduling policy for CPU-intensive processes: %s" % os.SCHED_BATCH)
#try:
    #_LOG.info(os.system('lscpu'))
#except:
    #pass

#-------------------------------------------------------------------------
#
#
#
#-------------------------------------------------------------------------
class RelationTab(tool.Tool, ManagedWindow):

    def __init__(self, dbstate, user, options_class, name, callback=None):
        uistate = user.uistate
        self.label = _("Relation and distances with root")
        self.dbstate = dbstate
        FilterClass = GenericFilterFactory('Person')
        self.path = '.'
        filter = FilterClass()

        tool.Tool.__init__(self, dbstate, options_class, name)
        if uistate:

            window = Gtk.Window()
            window.set_default_size(880, 600)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            window.add(box)

            # dirty work-around for Gtk.HeaderBar() and FolderChooser

            chooser = Gtk.FileChooserDialog(_("Folder Chooser"),
                                  parent = uistate.window,
                                  action = Gtk.FileChooserAction.SELECT_FOLDER,
                                  buttons = (_('_Cancel'),
                                           Gtk.ResponseType.CANCEL,
                                          _('_Select'),
                                          Gtk.ResponseType.OK))
            chooser.set_tooltip_text(_("Please, select a folder"))
            status = chooser.run()
            if status == Gtk.ResponseType.OK:
                # work-around 'IsADirectoryError' with self()
                # TypeError: invalid file: gi.FunctionInfo()
                self.path = chooser.get_current_folder()
            chooser.destroy()

            ManagedWindow.__init__(self, uistate, [],
                                                 self.__class__)
            self.titles = [
                (_('Rel_id'), 0, 75, INTEGER), # would be INTEGER
                (_('Relation'), 1, 300, str),
                (_('Name'), 2, 200, str),
                (_('up'), 3, 35, INTEGER),
                (_('down'), 4, 35, INTEGER),
                (_('Common MRA'), 5, 75, INTEGER),
                (_('Rank'), 6, 75, INTEGER),
                ]

            treeview = Gtk.TreeView()
            model = ListModel(treeview, self.titles)
            s = Gtk.ScrolledWindow()
            s.add(treeview)
            box.pack_start(s, True, True, 0)

            button = Gtk.Button(label="Save")
            button.connect("clicked", self.button_clicked)
            box.pack_end(button, False, True, 0)

        self.stats_list = []

        # behavior can be different according to CPU and generation depth

        max_level = config.get('behavior.generation-depth')
        # compact and interlinked tree
        # single core 2.80 Ghz needs +/- 0.1 second per person
        if max_level >= 15:
            var = max_level * 0.01
        elif 10 <= max_level < 15:
            var = max_level * 0.02
        else:
            var = max_level * 0.025

        plist = self.dbstate.db.iter_person_handles()
        length = self.dbstate.db.get_number_of_people()
        default_person = self.dbstate.db.get_default_person()
        if uistate:
            self.progress = ProgressMeter(self.label, can_cancel=True,
                                     parent=window)
        else:
            self.progress = ProgressMeter(self.label)

        if default_person: # rather designed for run via GUI...
            root_id = default_person.get_gramps_id()
            ancestors = rules.person.IsAncestorOf([str(root_id), True])
            descendants = rules.person.IsDescendantOf([str(root_id), True])
            related = rules.person.IsRelatedWith([str(root_id)])

            # filtering people can be useful on some large data set
            # counter on filtering pass was not efficient
            # Not the proper solution, but a lazy one providing expected message

            filter.add_rule(related)
            self.progress.set_pass(_('Please wait, filtering...'))
            filtered_list = filter.apply(self.dbstate.db, plist)

            relationship = get_relationship_calculator()
        else: # TODO: provide selection widget for CLI and GUI
            WarningDialog(_("No default_person"))
            return

        count = 0
        filtered_people = len(filtered_list)
        self.progress.set_pass(_('Generating relation map...'), filtered_people)
        if self.progress.get_cancelled():
            self.progress.close()
            return
        step_one = time.clock() # init for counters
        for handle in filtered_list:
            nb = len(self.stats_list)
            count += 1
            self.progress.step()
            step_two = time.clock()
            start = 99
            if count > start: # provide a basic interface for counters
                need = (step_two - step_one) / count
                wait = need * filtered_people
                remain = int(wait) - int(step_two - step_one)
                header = _("%d/%d \n %d/%d seconds \n %d/%d \n%f|\t%f" % (count, filtered_people, remain, int(wait), nb, length, float(need), float(var)))
                self.progress.set_header(header)
                if self.progress.get_cancelled():
                    self.progress.close()
                    return
            person = dbstate.db.get_person_from_handle(handle)
            timeout_one = time.clock() # for delta and timeout estimations
            dist = relationship.get_relationship_distance_new(
                        dbstate.db, default_person, person, only_birth=True)
            timeout_two = time.clock()

            rank = dist[0][0]
            if rank == -1 or rank > max_level: # not related and ignored people
                continue

            limit = timeout_two - timeout_one
            expect = (limit - var) / max_level
            if limit > var:
                n = name_displayer.display(person)
                _LOG.debug("Sorry! '%s' needs %s second, variation = '%s')" % (n, limit, expect))
                continue
            else:
                _LOG.debug("variation = '%s')" % limit) # delta, see above max_level 'wall' section
                rel = relationship.get_one_relationship(
                                            dbstate.db, default_person, person)
                rel_a = dist[0][2]
                Ga = len(rel_a)
                rel_b = dist[0][4]
                Gb = len(rel_b)
                mra = 1

                # m: mother; f: father
                if Ga > 0:
                    for letter in rel_a:
                        if letter == 'm':
                            mra = mra * 2 + 1
                        if letter == 'f':
                            mra = mra * 2
                    # design: mra gender will be often female (m: mother)
                    if rel_a[-1] == "f" and Gb != 0: # male gender, look at spouse
                        mra = mra + 1

                name = name_displayer.display(person)
                # pseudo privacy; sample for DNA stuff and mapping
                import hashlib
                no_name = hashlib.sha384(name.encode() + handle.encode()).hexdigest()
                _LOG.info(no_name) # own internal password via handle

                kekule = number.get_number(Ga, Gb, rel_a, rel_b)

                # workaround - possible unique ID and common numbers
                uuid = str(uuid4().int)
                _LOG.info("Random UUID: %s" % uuid)

                if kekule == "u": # TODO: cousin(e)s need a key
                    kekule = 0
                if kekule == "nb": # non-birth
                    kekule = -1
                try:
                    test = int(kekule)
                except: # 1: related to mother; 0.x : no more girls lineage
                    kekule = 1

                self.stats_list.append((int(kekule), rel, name, int(Ga),
                                    int(Gb), int(mra), int(rank)))
        self.progress.close()

        _LOG.debug("total: %s" % nb)
        for entry in self.stats_list:
            if uistate:
                model.add(entry, entry[0])
            else:
                print(entry)
        if uistate:
            window.show()
            self.set_window(window, None, self.label)
            self.show()

    def save(self):
        doc = ODSTab(len(self.stats_list))
        doc.creator(self.db.get_researcher().get_name())
        name = self.dbstate.db.get_default_person().get_handle() + '.ods'
        if self.path != '.':
            name = os.path.join(self.path, name)
        try:
            import io
            io.open(name, "w", encoding='utf8')
        except PermissionError or IsADirectoryError:
            WarningDialog(_("You do not have write rights on this folder"))
            return

        spreadsheet = TableReport(name, doc)

        new_titles = []
        skip_columns = []
        index = 0
        for title in self.titles:
            if title == 'sort':
                skip_columns.append(index)
            else:
                new_titles.append(title)
            index += 1
        spreadsheet.initialize(len(new_titles))

        spreadsheet.write_table_head(new_titles)

        index = 0
        for top in self.stats_list:
            spreadsheet.set_row(index%2)
            index += 1
            spreadsheet.write_table_data(top, skip_columns)

        spreadsheet.finalize()

    def build_menu_names(self, obj):
        return (self.label, None)

    def button_clicked(self, button):
        self.save()

class TableReport:
    """
    This class provides an interface for the spreadsheet table
    used to save the data into the file.
    """

    def __init__(self, filename, doc):
        self.filename = filename
        self.doc = doc

    def initialize(self, cols):
        self.doc.open(self.filename)
        self.doc.start_page()

    def finalize(self):
        self.doc.end_page()
        self.doc.close()

    def write_table_data(self, data, skip_columns=[]):
        self.doc.start_row()
        index = -1
        for item in data:
            index += 1
            if index not in skip_columns:
                self.doc.write_cell(str(item))
        self.doc.end_row()

    def set_row(self,val):
        self.row = val + 2

    def write_table_head(self, data):
        head = []
        for column in data:
            (header, ID, length, TYPE) = column
            head.append(header)
        self.doc.start_row()
        list(map(self.doc.write_cell, head))
        self.doc.end_row()

#------------------------------------------------------------------------
#
#
#
#------------------------------------------------------------------------
class RelationTabOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
