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

import time
import logging
import platform
import os
from array import array
from uuid import uuid4
from threading import Thread
from gi.repository import Gtk
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
from gramps.gen.utils.db import get_timeperiod
import number
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
_LOG = logging.getLogger(__name__)
_LOG.info(platform.uname())
logging.basicConfig(filename='debug.log', level=logging.DEBUG)

#-------------------------------------------------------------------------
def t_one(dbstate, relationship, default_person, person):
    """
    Récupère une relation entre deux personnes.
    """
    _LOG.debug(f"Calculating relationship for {name_displayer.display(person)}")
    rel = relationship.get_one_relationship(dbstate.db, default_person, person)
    _LOG.debug(f"Relationship result: {rel}")
    return rel

#-------------------------------------------------------------------------
class RelationTab(tool.Tool, ManagedWindow):
    def __init__(self, dbstate, user, options_class, name, callback=None):
        uistate = user.uistate
        self.label = _("Relation and distances with root")
        self.dbstate = dbstate
        FilterClass = GenericFilterFactory('Person')
        self.path = '.'
        self.filter = FilterClass()
        tool.Tool.__init__(self, dbstate, options_class, name)
        self.relationship = get_relationship_calculator()
        self.stats_list = []

        if uistate:
            window = Gtk.Window()
            window.set_default_size(1000, 600)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            window.add(box)

            # Sélection du dossier de sauvegarde
            chooser = Gtk.FileChooserDialog(
                _("Folder Chooser"),
                parent=uistate.window,
                action=Gtk.FileChooserAction.SELECT_FOLDER,
                buttons=(
                    _('_Cancel'), Gtk.ResponseType.CANCEL,
                    _('_Select'), Gtk.ResponseType.OK
                )
            )
            chooser.set_tooltip_text(_("Please, select a folder"))
            status = chooser.run()
            if status == Gtk.ResponseType.OK:
                self.path = chooser.get_current_folder()
            chooser.destroy()

            ManagedWindow.__init__(self, uistate, [], self.__class__)

            # Configuration du TreeView
            self.titles = [
                (_('Rel_id'), 0, 40, INTEGER),
                (_('Relation'), 1, 300, str),
                (_('Name'), 2, 200, str),
                (_('up'), 3, 35, INTEGER),
                (_('down'), 4, 35, INTEGER),
                (_('Common MRA'), 5, 40, INTEGER),
                (_('Rank'), 6, 40, INTEGER),
                (_('Period'), 7, 40, str),
            ]
            treeview = Gtk.TreeView()
            self.model = ListModel(treeview, self.titles)
            s = Gtk.ScrolledWindow()
            s.add(treeview)
            box.pack_start(s, True, True, 0)

            # Bouton de sauvegarde
            button = Gtk.Button(label=_("Save"))
            button.connect("clicked", self.button_clicked)
            box.pack_end(button, False, True, 0)

        # Récupération des personnes filtrées
        max_level = config.get('behavior.generation-depth')
        plist = self.dbstate.db.iter_person_handles()
        length = self.dbstate.db.get_number_of_people()
        default_person = self.dbstate.db.get_default_person()

        if uistate:
            self.progress = ProgressMeter(self.label, can_cancel=True, parent=window)
        else:
            self.progress = ProgressMeter(self.label)

        if default_person:
            root_id = default_person.get_gramps_id()
            related = rules.person.IsRelatedWith([str(root_id)])
            self.filter.add_rule(related)
            _LOG.info("Filtering people related to the root person...")
            self.progress.set_pass(_('Please wait, filtering...'))
            self.filtered_list = self.filter.apply(self.dbstate.db, plist)
            _LOG.info(f"Found {len(self.filtered_list)} related people.")
        else:
            _LOG.error("No default person set.")
            WarningDialog(_("No default_person"))
            return

        # Traitement des personnes
        _LOG.info("Starting to process people...")
        self.process_people(max_level, uistate, window, default_person, length)
        _LOG.info("Finished processing people.")

        if uistate:
            window.show()
            self.set_window(window, None, self.label)
            self.show()

    #-------------------------------------------------------------------------
    def process_people(self, max_level, uistate, window, default_person, length):
        """Traite la liste des personnes filtrées."""
        count = 0
        filtered_people = len(self.filtered_list)
        self.progress.set_pass(_('Generating relation map...'), filtered_people)
        _LOG.debug(f"Processing {filtered_people} people.")
        if self.progress.get_cancelled():
            self.progress.close()
            return

        step_one = time.perf_counter()  # Remplace time.clock()

        for handle in self.filtered_list:
            count += 1
            self.progress.step()
            person = self.dbstate.db.get_person_from_handle(handle)
            _LOG.debug(f"Processing person: {name_displayer.display(person)}")

            dist = self.relationship.get_relationship_distance_new(
                self.dbstate.db, default_person, person, only_birth=True)

            # Récupère les infos de la relation
            rank = dist[0][0]
            _LOG.debug(f"Rank for this person: {rank}")
            if rank == -1 or rank > max_level:
                _LOG.debug("Skipping person (not related or too distant).")
                continue

            rel_a = dist[0][2]
            rel_b = dist[0][4]
            Ga = len(rel_a)
            Gb = len(rel_b)

            # Calcule mra
            mra = 1
            for letter in rel_a:
                if letter == 'm':
                    mra = mra * 2 + 1
                elif letter == 'f':
                    mra = mra * 2

            if rel_a and rel_a[-1] == "f" and Gb != 0:
                mra += 1

            # Calcule kekule
            kekule = number.get_number(Ga, Gb, rel_a, rel_b)
            if kekule == "u":
                kekule = 0
            elif kekule == "nb":
                kekule = -1
            try:
                kekule = int(kekule)
            except:
                kekule = 1

            # uuid = str(uuid4())
            # _LOG.info(f"Random UUID: {uuid}")

            # new_list = [int(kekule), int(Ga), int(Gb), int(mra), int(rank)]
            # if max_level > 7:
            #     line = (handle, array('l', new_list))
            # else:
            #     line = (handle, array('b', new_list))

            # Récupère la relation et la période
            rel = t_one(self.dbstate, self.relationship, default_person, person)
            period = get_timeperiod(self.dbstate.db, handle)
            name = name_displayer.display(person)

            # Header du ProgressMeter
            step_two = time.perf_counter()
            need = (step_two - step_one) / count
            wait = need * filtered_people
            remain = int(wait) - int(step_two - step_one)
            header = _("%d/%d \n %d/%d seconds \n %d/%d \n%f|\t%f"
                    % (count, filtered_people, remain, int(wait),
                    len(self.stats_list), length, float(need), float(0.025)))
            self.progress.set_header(header)

            # Ajoute les résultats
            self.stats_list.append((
                int(kekule), rel, name, int(Ga), int(Gb), int(mra), int(rank), str(period)
            ))

            if uistate:
                self.model.add((int(kekule), rel, name, int(Ga), int(Gb), int(mra), int(rank), str(period)), int(kekule))

            _LOG.debug(f"Added entry for {name} to stats_list.")

        self.progress.close()
        _LOG.info(f"Total processing time: {time.perf_counter() - step_one} seconds.")

    #-------------------------------------------------------------------------
    def save(self):
        """Enregistre les résultats dans un fichier ODS."""
        if not self.stats_list:
            _LOG.warning("No data to save.")
            return

        _LOG.info("Starting to save data to ODS file.")
        doc = ODSTab(len(self.stats_list))
        doc.creator(self.dbstate.db.get_researcher().get_name())
        filename = self.dbstate.db.get_default_person().get_handle() + '.ods'
        if self.path != '.':
            filename = os.path.join(self.path, filename)

        try:
            with open(filename, "w", encoding='utf8') as f:
                pass  # Le fichier sera rempli par ODSTab
        except (PermissionError, IsADirectoryError) as e:
            _LOG.error(f"Failed to create file: {e}")
            WarningDialog(_("You do not have write rights on this folder"))
            return

        spreadsheet = TableReport(filename, doc)
        new_titles = [title for title in self.titles if title[0] != 'sort']
        spreadsheet.initialize(len(new_titles))
        spreadsheet.write_table_head(new_titles)

        for index, entry in enumerate(self.stats_list):
            spreadsheet.set_row(index % 2)
            spreadsheet.write_table_data(entry)

        spreadsheet.finalize()
        _LOG.info(f"Data successfully saved to {filename}.")

    #-------------------------------------------------------------------------
    def button_clicked(self, button):
        """Appelé quand le bouton 'Save' est cliqué."""
        _LOG.info("Save button clicked.")
        self.save()

    #-------------------------------------------------------------------------
    def build_menu_names(self, obj):
        return (self.label, None)

#-------------------------------------------------------------------------
class TableReport:
    """Classe pour gérer l'export des données dans un tableau ODS."""
    def __init__(self, filename, doc):
        self.filename = filename
        self.doc = doc

    def initialize(self, cols):
        _LOG.debug(f"Initializing ODS file: {self.filename}")
        self.doc.open(self.filename)
        self.doc.start_page()

    def finalize(self):
        _LOG.debug("Finalizing ODS file.")
        self.doc.end_page()
        self.doc.close()

    def write_table_data(self, data):
        self.doc.start_row()
        for item in data:
            self.doc.write_cell(str(item))
        self.doc.end_row()

    def set_row(self, val):
        self.row = val + 2

    def write_table_head(self, data):
        headers = [header[0] for header in data]
        self.doc.start_row()
        for header in headers:
            self.doc.write_cell(header)
        self.doc.end_row()

#-------------------------------------------------------------------------
class RelationTabOptions(tool.ToolOptions):
    """Options pour l'outil RelationTab."""
    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
