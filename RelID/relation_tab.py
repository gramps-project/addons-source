#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2006  Donald N. Allingham
# Copyright (C) 2008       Brian G. Matherly
# Copyright (C) 2010       Jakim Friant
# Copyright (C) 2011       Robert Cheramy
# Copyright (C) 2012       Doug Blank
# Copyright (C) 2017       Jerome Rapinat
# Copyright (C) 2025       Jerome Rapinat with Mistral AI (Codestral 25.08)
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
from functools import lru_cache
#from uuid import uuid4
#from threading import Thread
from gi.repository import Gtk
from gramps.gui.filters import build_filter_model
from gramps.gui.listmodel import ListModel, INTEGER
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.utils import ProgressMeter
from gramps.gui.plug import tool
from gramps.gen.plug.menu import StringOption, FilterOption, PersonOption, \
    EnumeratedListOption
import gramps.gen.plug.report.utils as ReportUtils
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
def get_relationship_between_people(dbstate, relationship_calculator, root_person, target_person):
    """
    Retrieves and logs the relationship between the root person and the target person.

    Args:
        dbstate: The database state.
        relationship_calculator: The relationship calculator instance.
        root_person: The root person (default person) in the database.
        target_person: The person to find the relationship with.

    Returns:
        The relationship string between the root and target person.
    """
    target_person_name = name_displayer.display(target_person)
    _LOG.debug(f"Calculating relationship for {target_person_name}")

    relationship = relationship_calculator.get_one_relationship(
        dbstate.db, root_person, target_person
    )
    _LOG.debug(f"Relationship result for {target_person_name}: {relationship}")

    return relationship

#-------------------------------------------------------------------------
def test_family_path_metrics():
    # Test extract_relationship_paths
    mock_result = [[0, 1, "mfm", 2, "ffm", 3]]
    rel_a, rel_b = FamilyPathMetrics.extract_relationship_paths(mock_result)
    assert rel_a == "mfm"
    assert rel_b == "ffm"

    # Test calculate_relationship_path_lengths
    Ga, Gb = FamilyPathMetrics.calculate_relationship_path_lengths("mfm", "ffm")
    assert Ga == 3
    assert Gb == 3

    # Test calculate_mra
    assert FamilyPathMetrics.calculate_mra("mfm") == 15
    assert FamilyPathMetrics.calculate_mra("ff") == 5

    # Test calculate_kekule_number
    assert FamilyPathMetrics.calculate_kekule_number(2, 2, "mm", "ff") == 0  # Exemple hypothétique

#-------------------------------------------------------------------------
class FamilyPathMetrics:
    """
    Classe dédiée au calcul des métriques de relation entre individus dans un arbre généalogique.
    """

    @staticmethod
    def extract_relationship_paths(relationship_distance_result):
        """
        Extrait les chemins de relation (rel_a et rel_b) à partir du résultat de la distance de relation.
        """
        rel_a = relationship_distance_result[0][2]
        rel_b = relationship_distance_result[0][4]
        return rel_a, rel_b

    @staticmethod
    def calculate_relationship_path_lengths(rel_a, rel_b):
        """
        Calcule les longueurs des chemins de relation (Ga et Gb).
        """
        Ga = len(rel_a)
        Gb = len(rel_b)
        return Ga, Gb

    @staticmethod
    def calculate_mra(rel_a):
        """
        Calcule le "Most Recent Ancestor" (MRA) en fonction du chemin de relation rel_a.
        """
        # design: mra gender will be often female (m: mother) ; f: father
        # mra will be also always an unpair number
        mra = 1
        for letter in rel_a:
            if letter == 'm':
                mra = mra * 2 + 1
            elif letter == 'f':
                mra = mra * 2
        if rel_a and rel_a[-1] == "f": # male gender, look at spouse
            mra += 1
        return mra

    @staticmethod
    def calculate_kekule_number(Ga, Gb, rel_a, rel_b):
        """
        Calcule le nombre de Kekulé en fonction des longueurs des chemins de relation et des chemins eux-mêmes.
        """
        # male ancestors will be pair ; female ancestors will be unpair ; see number.py
        kekule = number.get_number(Ga, Gb, rel_a, rel_b)
        if kekule == "u": # TODO: cousin(e)s need a key
            kekule = 0
        elif kekule == "nb": # non-birth
            kekule = -1
        try:
            kekule = int(kekule)
        except (ValueError, TypeError):
            kekule = 1
        return kekule

    @staticmethod
    @lru_cache(maxsize=128)
    def calculate_shared_subtree_size(db, person1_handle, person2_handle):
        """
        Calcule le nombre d'individus dans le sous-arbre commun à deux personnes.
        """
        person1 = db.get_person_from_handle(person1_handle)
        person2 = db.get_person_from_handle(person2_handle)

        relationship_calculator = get_relationship_calculator()
        dist = relationship_calculator.get_relationship_distance_new(db, person1, person2)
        if not dist or dist[0][0] == -1:
            return 0  # Pas de relation trouvée

        common_ancestor_handle = dist[0][1]
        common_ancestor = db.get_person_from_handle(common_ancestor_handle)

        descendants = set()
        stack = [common_ancestor]

        while stack:
            current_person = stack.pop()
            descendants.add(current_person.get_handle())

            for family_handle in current_person.get_family_handle_list():
                family = db.get_family_from_handle(family_handle)
                for child_ref in family.get_child_ref_list():
                    child = db.get_person_from_handle(child_ref.get_reference_handle())
                    stack.append(child)

        return len(descendants)

    @staticmethod
    @lru_cache(maxsize=128)
    def calculate_family_network_centrality(db, person_handle):
        """
        Calcule un score de centralité pour un individu dans le réseau familial.
        """
        person = db.get_person_from_handle(person_handle)

        # Compter les descendants
        descendants = set()
        stack = [person]

        while stack:
            current_person = stack.pop()
            descendants.add(current_person.get_handle())

            for family_handle in current_person.get_family_handle_list():
                family = db.get_family_from_handle(family_handle)
                for child_ref in family.get_child_ref_list():
                    child = db.get_person_from_handle(child_ref.get_reference_handle())
                    stack.append(child)

        num_descendants = len(descendants) - 1

        # Compter les ancêtres
        ancestors = set()
        stack = [person]

        while stack:
            current_person = stack.pop()
            ancestors.add(current_person.get_handle())

            for family_handle in current_person.get_parent_family_handle_list():
                family = db.get_family_from_handle(family_handle)
                for parent_ref in [family.get_father_handle(), family.get_mother_handle()]:
                    if parent_ref:
                        parent = db.get_person_from_handle(parent_ref)
                        stack.append(parent)

        num_ancestors = len(ancestors) - 1

        # Compter les liens de couple
        num_unions = len(person.get_family_handle_list())

        return num_descendants + num_ancestors + num_unions

    @staticmethod
    @lru_cache(maxsize=128)
    def count_unique_ancestors(db, person_handle, generations=5):
        """
        Compte le nombre d'ancêtres uniques dans un nombre donné de générations.

        Args:
            db: Base de données Gramps.
            person_handle: Handle de la personne.
            generations: Nombre de générations à considérer.

        Returns:
            int: Nombre d'ancêtres uniques.
        """
        person = db.get_person_from_handle(person_handle)
        ancestors = set()
        stack = [(person, 0)]

        while stack:
            current_person, generation = stack.pop()
            if generation > generations:
                continue
            ancestors.add(current_person.get_handle())

            for family_handle in current_person.get_parent_family_handle_list():
                family = db.get_family_from_handle(family_handle)
                for parent_ref in [family.get_father_handle(), family.get_mother_handle()]:
                    if parent_ref:
                        parent = db.get_person_from_handle(parent_ref)
                        stack.append((parent, generation + 1))

        return len(ancestors)

    @staticmethod
    @lru_cache(maxsize=128)
    def calculate_surname_diversity(db, person_handle, generations=5):
        """
        Calcule la diversité des noms de famille dans les ancêtres d'un individu.

        Args:
            db: Base de données Gramps.
            person_handle: Handle de la personne.
            generations: Nombre de générations à considérer.

        Returns:
            float: Indice de diversité des noms de famille.
        """
        person = db.get_person_from_handle(person_handle)
        surnames = set()
        total_ancestors = 0
        stack = [(person, 0)]

        while stack:
            current_person, generation = stack.pop()
            if generation > generations:
                continue
            total_ancestors += 1
            surname = current_person.get_primary_name().get_surname()
            if surname:
                surnames.add(surname)
            for family_handle in current_person.get_parent_family_handle_list():
                family = db.get_family_from_handle(family_handle)
                for parent_ref in [family.get_father_handle(), family.get_mother_handle()]:
                    if parent_ref:
                        parent = db.get_person_from_handle(parent_ref)
                        stack.append((parent, generation + 1))
        if not surnames:
            return 0.0
        return len(surnames) / total_ancestors


#-------------------------------------------------------------------------
class RelationTab(tool.Tool, ManagedWindow):
    # Variable de classe pour activer/désactiver les métriques de réseau familial
    ENABLE_NETWORK_METRICS = True

    def __init__(self, dbstate, user, options_class, name, callback=None):
        # Initialiser la classe parente tool.Tool
        tool.Tool.__init__(self, dbstate, options_class, name)
        # Récupère les options depuis options_class
        self.options = options_class

        # Vérifie que self.options est bien une instance et non la classe
        if hasattr(self.options, 'options_dict'):
            RelationTab.ENABLE_NETWORK_METRICS = self.options.options_dict.get('enable_network_metrics', True)
        else:
            _LOG.warning("options_class n'est pas une instance de RelationTabOptions. Utilisation de la valeur par défaut.")

        uistate = user.uistate
        self.label = _("Relation and distances with root")
        self.dbstate = dbstate
        FilterClass = GenericFilterFactory('Person')
        self.path = None
        self.filter = FilterClass()
        self.relationship = get_relationship_calculator()
        self.stats_list = []

        # Initialiser window et progress avant de les utiliser
        window = None

        #self.filter_option =  self.options.menu.get_option_by_name('filter')
        #self.filter = self.filter_option.get_filter() # the actual filter

        if uistate:
            window = Gtk.Window()
            window.set_default_size(1200, 600)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            window.add(box)

            ManagedWindow.__init__(self, uistate, [], self.__class__)
            self.set_window(window, None, self.label)

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

            if RelationTab.ENABLE_NETWORK_METRICS:
                self.titles.extend([
                    (_('Shared Subtree'), 8, 80, INTEGER),
                    (_('Centrality'), 9, 60, INTEGER),
                    (_('Unique Ancestors'), 10, 80, INTEGER),
                    (_('Surname Diversity'), 11, 80, str),  # Affiché comme pourcentage ou ratio
                ])

            treeview = Gtk.TreeView()
            self.model = ListModel(treeview, self.titles)
            s = Gtk.ScrolledWindow()
            s.add(treeview)
            box.pack_start(s, True, True, 0)

            # Bouton de sauvegarde
            button = Gtk.Button(label=_("Save"))
            button.connect("clicked", self.button_clicked)
            box.pack_end(button, False, True, 0)

            # Bouton pour quitter
            quit = Gtk.Button(label=_("Quit"))
            quit.connect("clicked",self.quit_clicked)
            box.pack_end(quit, False, False, 0)

        # Récupération des personnes filtrées
        max_level = config.get('behavior.generation-depth')
        plist = self.dbstate.db.iter_person_handles()
        length = self.dbstate.db.get_number_of_people()
        default_person = self.dbstate.db.get_default_person()

        if default_person is not None:
            root_id = default_person.get_gramps_id()
            ancestors = rules.person.IsAncestorOf([str(root_id), True])
            descendants = rules.person.IsDescendantOf([str(root_id), True])
            related = rules.person.IsRelatedWith([str(root_id)])
            self.filter.add_rule(related)
            _LOG.info("Filtering people related to the root person...")
            self.filtered_list = self.filter.apply(self.dbstate.db, plist)
            _LOG.info(f"Found {len(self.filtered_list)} related people.")
        else:
            _LOG.debug("No default person set.")
            if uistate:
                WarningDialog(_("No default person set."), parent=uistate.window)
            return

        if uistate:
            self.progress = ProgressMeter(self.label, can_cancel=False, parent=uistate.window)
        else:
            self.progress = ProgressMeter(self.label)
        self.progress.set_pass(_('Please wait, filtering...'))

        # Traitement des personnes
        _LOG.info("Starting to process people...")
        self.process_people(max_level, uistate, window, default_person, length)
        _LOG.info("Finished processing people.")

        if uistate and default_person:
            window.show_all()
            self.set_window(window, None, self.label)
            self.show()

    def get_title(self):
        return _("Relationships Map and Tab")

    def initial_frame(self):
        return _("Options")

    def add_menu_options(self, menu):
        """Add the options."""
        category_name = _("Options")
        self.__filter = FilterOption(_("Person Filter"), 0)
        self.__filter.set_help(_("Select filter to restrict people"))
        menu.add_option(category_name, "filter", self.__filter)
        self.__filter.connect('value-changed', self.update_filter_logic)

        self.__fid = PersonOption(_("Filter Person"))
        self.__fid.set_help(_("The center person for the filter"))
        menu.add_option(category_name, "fid", self.__fid)
        self.__fid.connect('value-changed', self.update_filter_logic)
        self.__update_filters()

        filter_rule = EnumeratedListOption(_("Filter rule"), 0)
        filter_rule.add_item(0, _("Ancestors"))
        filter_rule.add_item(1, _("Descendants"))
        filter_rule.add_item(2, _("Related"))
        filter_rule.set_help(_("Select the filter rule"))
        menu.add_option(category_name, "filter_rule", filter_rule)
        filter_rule.connect('value-changed', self.update_filter_logic)
        self.__filter_rule = filter_rule

        deep_gen_text = StringOption(_("Deep generations"), "")
        deep_gen_text.set_help(_("How deep should we go?"))
        menu.add_option(category_name, "deep_gen_text", deep_gen_text)
        self.__deep_gen_text = deep_gen_text

        # Ajoute une option pour activer/désactiver les métriques réseau
        network_metrics_option = EnumeratedListOption(_("Network Metrics"), RelationTab.ENABLE_NETWORK_METRICS)
        network_metrics_option.add_item(True, _("Enabled"))
        network_metrics_option.add_item(False, _("Disabled"))
        network_metrics_option.set_help(_("Enable or disable family network metrics"))
        menu.add_option(category_name, "network_metrics", network_metrics_option)
        network_metrics_option.connect('value-changed', self.__update_network_metrics_option)
        self.__update_filter_rule()

    def __update_network_metrics_option(self):
        """Mets à jour ENABLE_NETWORK_METRICS en fonction de l'option sélectionnée."""
        network_metrics_option = self.options.menu.get_option_by_name('network_metrics')
        RelationTab.ENABLE_NETWORK_METRICS = network_metrics_option.get_value()
        _LOG.info(f"Network metrics option updated: {RelationTab.ENABLE_NETWORK_METRICS}")

    def update_filter_logic(self):
        """Centralise la logique de mise à jour des filtres."""
        filter_rule = self.__filter_rule.get_value()
        filter_value = self.__filter.get_value()

        # Mise à jour de la disponibilité des options en fonction des règles de filtre
        if filter_rule == 0:  # Ancestors
            self.__fid.set_available(True)
        else:
            self.__fid.set_available(False)

        # Mise à jour de la liste des filtres en fonction de la personne sélectionnée
        person = self.__fid.get_value()
        if person:
            filter_list = ReportUtils.get_person_filters(person, False)
            self.__filter.set_filters(filter_list)
        else:
            self.__filter.set_filters(0)

        # Gestion des filtres spécifiques à une personne
        if filter_value in [1, 2, 3, 4]:
            self.__fid.set_available(True)
        else:
            self.__fid.set_available(False)


    #-------------------------------------------------------------------------
    def long_running_task(self, default_person, person):
        # Exemple de tâche longue
        dist = self.relationship.get_relationship_distance_new(
            self.dbstate.db, default_person, person, only_birth=True)
        # Traitement des résultats...


    #-------------------------------------------------------------------------
    def process_people(self, max_level, uistate, window, default_person, length):
        """Traite la liste des personnes filtrées."""
        count = 0
        filtered_people = len(self.filtered_list)
        self.progress.set_pass(_('Generating relation map...'), filtered_people)
        _LOG.debug(f"Processing {filtered_people} people.")
        step_one = time.perf_counter()

        # Utilisation d'un générateur pour traiter les personnes
        def generate_results():
            for handle in self.filtered_list:
                self.progress.step()
                try:
                    # 1. Récupération de la personne une seule fois
                    person = self.dbstate.db.get_person_from_handle(handle)
                    if not person:
                        _LOG.warning(f"Person with handle {handle} not found.")
                        continue

                    #thread = Thread(target=self.long_running_task, args=(default_person, person,))
                    #thread.start()

                    # 2. Calcul de la distance de relation (une seule fois)
                    dist = self.relationship.get_relationship_distance_new(
                            self.dbstate.db, default_person, person, only_birth=True)
                    rank = dist[0][0]
                    if rank == -1 or rank > max_level:
                        _LOG.debug("Skipping person (not related or too distant).")
                        continue

                    # 3. Extraction et calcul des métriques de base
                    rel_a, rel_b = FamilyPathMetrics.extract_relationship_paths(dist)
                    Ga, Gb = FamilyPathMetrics.calculate_relationship_path_lengths(rel_a, rel_b)
                    mra = FamilyPathMetrics.calculate_mra(rel_a)
                    kekule = FamilyPathMetrics.calculate_kekule_number(Ga, Gb, rel_a, rel_b)

                    # 4. Calcul des métriques réseau uniquement si activé
                    if RelationTab.ENABLE_NETWORK_METRICS:
                        shared_subtree_size = FamilyPathMetrics.calculate_shared_subtree_size(
                            self.dbstate.db, default_person.get_handle(), person.get_handle())
                        centrality = FamilyPathMetrics.calculate_family_network_centrality(
                            self.dbstate.db, person.get_handle())
                        unique_ancestors = FamilyPathMetrics.count_unique_ancestors(
                            self.dbstate.db, person.get_handle(), generations=max_level)
                        surname_diversity = FamilyPathMetrics.calculate_surname_diversity(
                            self.dbstate.db, person.get_handle(), generations=max_level)

                    # 5. Récupération de la relation et de la période (une seule fois)
                    relationship = get_relationship_between_people(
                        self.dbstate, self.relationship, default_person, person)
                    period = get_timeperiod(self.dbstate.db, handle)
                    # Affichage du nom et pseudo-anonymisation
                    name = name_displayer.display(person)
                    # Pseudo privacy; sample for DNA stuff and mapping
                    import hashlib, re
                    # cleanup ; special characters
                    handle = re.sub(r'[^\w\-_]', '_', handle)
                    no_name = hashlib.sha384(name.encode() + handle.encode()).hexdigest()
                    _LOG.info(no_name)

                    # 6. Construction de l'entrée de résultat
                    result_entry = (
                        int(kekule), relationship, name, int(Ga), int(Gb), int(mra), int(rank), str(period)
                    )
                    if RelationTab.ENABLE_NETWORK_METRICS:
                        result_entry += (
                            int(shared_subtree_size),
                            int(centrality),
                            int(unique_ancestors),
                            f"{surname_diversity:.2f}"  # Convertir en chaîne de caractères
                        )
                    yield result_entry, name  # On retourne le résultat et le nom pour les logs
                except Exception as e:
                    _LOG.error(f"Error processing person with handle {handle}: {e}")
                    continue

        # Traitement des résultats avec le générateur
        for result_entry, name in generate_results():
            # Ajoute le résultat à la liste et au modèle
            count += 1
            self.stats_list.append(result_entry)
            if uistate:
                self.model.add(result_entry, int(result_entry[0]))

        # Log toutes les 100 personnes pour éviter de surcharger les logs
        if count % 100 == 0:
            step_two = time.perf_counter()
            need = (step_two - step_one) / count
            wait = need * filtered_people
            remain = int(wait) - int(step_two - step_one)
            #lazy tooltip
            documentation = _("\nFiltering\tTime process\tCurrent match\tTime per entry\n")
            header = _("%d/%d \t %d/%d seconds \t %d/%d \t\t%f"
                  % (count, filtered_people, remain, int(wait),
                  len(self.stats_list), length, float(need)))
            self.progress.set_header(header)
            _LOG.debug(f"Processed {count}/{filtered_people} people.")

        self.progress.close()

        if uistate is None:
            # Afficher un aperçu des résultats dans la console
            print("\nAperçu des résultats :")
            print("-" * 100)
            print(f"{_('ID Kekulé'):<10} | {_('Relation'):<20} | {_('Nom'):<30} | {'Ga':<5} | {'Gb':<5} | {'MRA':<5} | {_('Rang'):<5} | {_('Période'):<15}")
            if RelationTab.ENABLE_NETWORK_METRICS:
                print(f" | {_('Sous-arbre partagé'):<15} | {_('Centralité'):<10} | {_('Ancêtres uniques'):<15} | {_('Diversité noms'):<15}")
            print()  # Saut de ligne
            print("-" * 150)

            for entry in self.stats_list[:max_level * 2]:  # Afficher les premières entrées
                kekule, relation, name, Ga, Gb, mra, rank, period = entry[:8]
                print(f"{kekule:<10} | {relation[:18]:<20} | {name[:28]:<30} | {Ga:<5} | {Gb:<5} | {mra:<5} | {rank:<5} | {period[:13]:<15}", end="")
                if RelationTab.ENABLE_NETWORK_METRICS and len(entry) > 8:
                    shared_subtree_size, centrality, unique_ancestors, surname_diversity = entry[8:12]
                    print(f" | {shared_subtree_size:<15} | {centrality:<10} | {unique_ancestors:<15} | {surname_diversity}")
                else:
                    print()
            print("-" * 150)
            print(f"Total des entrées traitées : {len(self.stats_list)}\n")
        _LOG.info(f"Total processing time: {time.perf_counter() - step_one} seconds.")


    #-------------------------------------------------------------------------
    def save(self):
        """Enregistre les résultats dans un fichier ODS."""
        # Sélection du dossier de sauvegarde
        chooser = Gtk.FileChooserDialog(
            _("Folder Chooser"),
            parent=None,
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
        if status == Gtk.ResponseType.CANCEL:
            _LOG.debug(f"Skip folder selection?")
            WarningDialog(_("Foldername need"), _("Foldername will be used for saving the content."))
        chooser.destroy()
        if not self.stats_list:
            _LOG.warning("No data to save.")
            return
        _LOG.info("Starting to save data to ODS file.")
        doc = ODSTab(len(self.stats_list))
        doc.creator(self.dbstate.db.get_researcher().get_name())
        filename = self.dbstate.db.get_default_person().get_handle() + '.ods'
        if self.path is None:
            _LOG.debug(f"Failed to get the foldername, maybe you did not set one?")
            WarningDialog(_("Did you set a foldername?"), _("Cannot set a valid location."))
            return
        else:
            filename = os.path.join(self.path, filename)
        try:
            with open(filename, "w", encoding='utf8') as f:
                pass
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

        # Afficher un message indiquant où le fichier a été enregistré
        print(f"Le fichier a été enregistré sous : {filename}")
        _LOG.info(f"Data successfully saved to {filename}.")


    #-------------------------------------------------------------------------
    def button_clicked(self, button):
        """Appelé quand le bouton 'Save' est cliqué."""
        _LOG.info("Save button clicked.")
        self.save()

    #-------------------------------------------------------------------------
    def quit_clicked(self, quit):
        """Appelé quand le bouton 'Quit' est cliqué."""
        _LOG.info("Quit button clicked.")
        self.close()

    #-------------------------------------------------------------------------
    def build_menu_names(self, obj):
        return (self.label, None)

    #-------------------------------------------------------------------------
    def close_progress_meter(self):
        """Ferme le ProgressMeter s'il est ouvert."""
        if hasattr(self, 'progress') and self.progress:
            self.progress.close()

    #-------------------------------------------------------------------------
    def on_delete_event(self, window, event):
        """Gère l'événement de fermeture de la fenêtre."""
        self.close_progress_meter()  # Ferme le ProgressMeter
        self.close()  # Ferme la fenêtre
        return True  # Indique que l'événement a été géré

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
    def __init__(self, name, person_id=None, dbstate=None):
        tool.ToolOptions.__init__(self, name, person_id)
        self.options_dict = {
            'filter': 0,
            #'fid': ,
            'filter_rule': 0,
            'deep_gen_text': 15,
            'enable_network_metrics': True,  # Option pour activer les métriques de réseau
        }
        self.options_help = {
            'enable_network_metrics': (
                _("Enable family network metrics"),
                "bool",
                _("Whether to calculate and display family network metrics."),
                None,
                True
            ),
        }
