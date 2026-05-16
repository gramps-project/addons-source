#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2006  Donald N. Allingham
# Copyright (C) 2008       Brian G. Matherly
# Copyright (C) 2010       Jakim Friant
# Copyright (C) 2011       Robert Cheramy
# Copyright (C) 2012       Doug Blank
# Copyright (C) 2017-2025  Jerome Rapinat
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

"""
Relations tab ; refactored with help of Mistral AI (Codestral 25.08)
"""

import time
import logging
import platform
import os
from functools import lru_cache
from collections import deque
from gi.repository import Gtk, GLib

from gramps.gui.filters import build_filter_model
from gramps.gui.listmodel import ListModel, INTEGER
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.utils import ProgressMeter
from gramps.gui.plug import tool
from gramps.gen.plug.menu import StringOption, FilterOption, PersonOption, EnumeratedListOption
import gramps.gen.plug.report.utils as ReportUtils
from gramps.gui.dialog import WarningDialog, OkDialog
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

# -------------------------------------------------------------------------
#
# Constants
#
# -------------------------------------------------------------------------

MAX_LEVEL = config.get('behavior.generation-depth')

#-------------------------------------------------------------------------
def get_relationship_between_people(dbstate, relationship_calculator, root_person, target_person):
    """
    Retrieves and logs the relationship between the root person and the target person.
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
        rel_a = relationship_distance_result[0][2]
        rel_b = relationship_distance_result[0][4]
        return rel_a, rel_b

    @staticmethod
    def calculate_relationship_path_lengths(rel_a, rel_b):
        Ga = len(rel_a)
        Gb = len(rel_b)
        return Ga, Gb

    @staticmethod
    def calculate_mra(rel_a):
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
        # male ancestors will be pair ; female ancestors will be unpair ; see number.py
        kekule = number.get_number(Ga, Gb, rel_a, rel_b)
        if kekule == "u": # TODO: cousin(e)s need a key
            kekule = f"cousin_{Ga}_{Gb}_{rel_a}_{rel_b}"
        elif kekule == "nb": # non-birth
            kekule = -1
        try: # TODO: batch_to_gtk_model needs a number
            kekule = int(kekule)
        except (ValueError, TypeError):
            kekule = 1
        return kekule

    @staticmethod
    @lru_cache(maxsize=128)
    def calculate_shared_subtree_size(db, person1_handle, person2_handle):
        person1 = db.get_person_from_handle(person1_handle)
        person2 = db.get_person_from_handle(person2_handle)
        relationship_calculator = get_relationship_calculator()
        dist = relationship_calculator.get_relationship_distance_new(db, person1, person2)
        if not dist or dist[0][0] == -1:
            return 0 # Pas de relation trouvée
        common_ancestor_handle = dist[0][1]
        common_ancestor = db.get_person_from_handle(common_ancestor_handle)
        descendants = set()
        stack = deque([common_ancestor])
        while stack:
            current_person = stack.popleft()
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
        person = db.get_person_from_handle(person_handle)
        # Compter les descendants
        descendants = set()
        stack = deque([person])
        while stack:
            current_person = stack.popleft()
            descendants.add(current_person.get_handle())
            for family_handle in current_person.get_family_handle_list():
                family = db.get_family_from_handle(family_handle)
                for child_ref in family.get_child_ref_list():
                    child = db.get_person_from_handle(child_ref.get_reference_handle())
                    stack.append(child)
        num_descendants = len(descendants) - 1
        # Compter les ancêtres
        ancestors = set()
        stack = deque([person])
        while stack:
            current_person = stack.popleft()
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
        person = db.get_person_from_handle(person_handle)
        ancestors = set()
        stack = deque([(person, 0)])
        while stack:
            current_person, generation = stack.popleft()
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
        person = db.get_person_from_handle(person_handle)
        surnames = set()
        total_ancestors = 0
        stack = deque([(person, 0)])
        while stack:
            current_person, generation = stack.popleft()
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
class RelationFilterManager:
    """Gère la création, la mise à jour et l'application des filtres."""
    RULE_BUILDERS = {
        0: lambda person: rules.person.IsAncestorOf([str(person.get_gramps_id()), True]),
        1: lambda person: rules.person.IsDescendantOf([str(person.get_gramps_id()), True]),
        2: lambda person: rules.person.IsRelatedWith([str(person.get_gramps_id())]),
    }

    def __init__(self, dbstate):
        self.dbstate = dbstate
        self.filter = GenericFilterFactory('Person')()
        self.current_rules = []
        self.last_applied_handles = None
        self.last_applied_rules = None
        self.last_filtered_list = []

    def update_rules(self, filter_rule, person_handle=None):
        """Met à jour les règles du filtre."""
        self.filter.clear()
        self.current_rules = []
        if person_handle and filter_rule in self.RULE_BUILDERS:
            person = self.dbstate.db.get_person_from_handle(person_handle)
            rule = self.RULE_BUILDERS[filter_rule](person)
            self.filter.add_rule(rule)
            self.current_rules.append(rule)

    def apply_filter(self, person_handles):
        """Applique le filtre et met en cache le résultat si possible."""
        rules_hash = hash(tuple(str(rule) for rule in self.current_rules))
        if (self.last_applied_handles == person_handles and
            self.last_applied_rules == rules_hash):
            _LOG.debug("Using cached filter result.")
            return self.last_filtered_list
        _LOG.debug("Applying filter...")
        self.last_filtered_list = self.filter.apply(self.dbstate.db, person_handles)
        self.last_applied_handles = person_handles
        self.last_applied_rules = rules_hash
        return self.last_filtered_list

#-------------------------------------------------------------------------
class RelationTab(tool.Tool, ManagedWindow):
    # Variable de classe pour activer/désactiver les métriques de réseau familial
    ENABLE_NETWORK_METRICS = True

    def __init__(self, dbstate, user, options_class, name, callback=None):
        # Initialiser la classe parente tool.Tool
        tool.Tool.__init__(self, dbstate, options_class, name)
        # Récupère les options depuis options_class
        self.options = options_class

        uistate = user.uistate
        self.label = _("Relation and distances with root")
        self.dbstate = dbstate
        try:
            self.path = os.path.dirname(__file__)
        except:
            self.path = os.getcwd()
        _LOG.info(self.path)
        self.relationship = get_relationship_calculator()
        self.stats_list = []

        # Initialisation des options de menu
        category_name = _("Options")
        self.__filter = FilterOption(_("Person Filter"), 0)
        self.__filter.set_help(_("Select filter to restrict people"))

        self.__fid = PersonOption(_("Filter Person"))
        self.__fid.set_help(_("The center person for the filter"))

        self.__filter_rule = EnumeratedListOption(_("Filter rule"), 0)
        self.__filter_rule.add_item(0, _("Ancestors"))
        self.__filter_rule.add_item(1, _("Descendants"))
        self.__filter_rule.add_item(2, _("Related"))
        self.__filter_rule.set_help(_("Select the filter rule"))

        self.__deep_gen_text = StringOption(_("Deep generations"), str(MAX_LEVEL))
        self.__deep_gen_text.set_help(_("How deep should we go?"))

        # Initialisation du gestionnaire de filtres
        self.filter_manager = RelationFilterManager(dbstate)
        self.filter_pass = 0

        # Initialisation de la fenêtre et des widgets GTK
        window = None
        if uistate:
            window = Gtk.Window()
            window.set_default_size(1200, 600)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            window.add(box)
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
            if RelationTab.ENABLE_NETWORK_METRICS:
                self.titles.extend([
                    (_('Shared Subtree'), 8, 80, INTEGER), # Taille du sous-arbre commun
                    (_('Centrality'), 9, 60, INTEGER), # Score de centralité
                    (_('Unique Ancestors'), 10, 80, INTEGER), # Nombre d'ancêtres uniques
                    (_('Surname Diversity'), 11, 80, str), # Affiché comme pourcentage ou ratio
                ])

            treeview = Gtk.TreeView()
            self.model = ListModel(treeview, self.titles)
            s = Gtk.ScrolledWindow()
            s.add(treeview)
            box.pack_start(s, True, True, 0)

            # Boutons
            save_button = Gtk.Button(label=_("Save"))
            save_button.connect("clicked", self.button_clicked)
            box.pack_end(save_button, False, True, 0)

            quit_button = Gtk.Button(label=_("Quit"))
            quit_button.connect("clicked", self.quit_clicked)
            box.pack_end(quit_button, False, False, 0)

        # Récupération de la personne par défaut
        default_person = self.dbstate.db.get_default_person()
        if default_person is None:
            _LOG.debug("No default person set.")
            if uistate:
                WarningDialog(_("No default person set."), parent=uistate.window)
            return

        if uistate:
            self.progress = ProgressMeter(self.label, can_cancel=False, parent=uistate.window)
            #window.show_all()
            self.set_window(window, None, self.label)
        else:
            self.progress = ProgressMeter(self.label)

        # Initialiser le ProgressMeter dans tous les cas ; MODE_ACTIVITY = 1
        self.progress.set_pass(_('Please wait, filtering...'), mode=1 )

        # Initialisation du filtre par défaut
        root_id = default_person.get_gramps_id()
        related = rules.person.IsRelatedWith([str(root_id)])
        self.filter_manager.filter.add_rule(related)

        # Récupération des personnes à filtrer
        plist = list(self.dbstate.db.iter_person_handles())
        length = len(plist)

        # Application du filtre initial
        self.filtered_list = self.filter_manager.apply_filter(plist)

        # Traitement des personnes
        _LOG.info("Starting to process people...")
        self.process_people(MAX_LEVEL, uistate, window, default_person, length)
        _LOG.info("Finished processing people.")

    #--- Méthodes de gestion des filtres ---
    def on_filter_rule_changed(self, *args):
        """Met à jour les règles du filtre lorsque la règle change."""
        filter_rule = self.__filter_rule.get_value()
        person_handle = self.__fid.get_value()
        self.filter_manager.update_rules(filter_rule, person_handle)
        self.apply_and_update_filter()

    def on_filter_person_changed(self, *args):
        """Met à jour les règles du filtre lorsque la personne change."""
        self.on_filter_rule_changed()

    def apply_and_update_filter(self):
        """Applique le filtre et met à jour l'UI."""
        filter_start = time.perf_counter()
        plist = list(self.dbstate.db.iter_person_handles())
        self.filtered_list = self.filter_manager.apply_filter(plist)
        filter_end = time.perf_counter()
        self.filter_pass = filter_end - filter_start
        self.progress.set_header(f"{self.filter_pass}")
        _LOG.info(f"Found {len(self.filtered_list)} related people in {self.filter_pass} seconds.")
        default_person = self.dbstate.db.get_default_person()
        if default_person:
            self.process_people(MAX_LEVEL, self.uistate, self.window, default_person, len(plist))

    #--- Autres méthodes ---
    def add_menu_options(self, menu):
        """Ajoute les options de menu."""
        category_name = _("Options")
        menu.add_option(category_name, "filter", self.__filter)
        self.__filter.connect('value-changed', self.update_filter_logic)

        menu.add_option(category_name, "fid", self.__fid)
        self.__fid.connect('value-changed', self.on_filter_person_changed)

        menu.add_option(category_name, "filter_rule", self.__filter_rule)
        self.__filter_rule.connect('value-changed', self.on_filter_rule_changed)

        menu.add_option(category_name, "deep_gen_text", self.__deep_gen_text)

        network_metrics_option = EnumeratedListOption(_("Network Metrics"), RelationTab.ENABLE_NETWORK_METRICS)
        network_metrics_option.add_item(True, _("Enabled"))
        network_metrics_option.add_item(False, _("Disabled"))
        network_metrics_option.set_help(_("Enable or disable family network metrics"))
        menu.add_option(category_name, "network_metrics", network_metrics_option)
        network_metrics_option.connect('value-changed', self.__update_network_metrics_option)

    def __update_network_metrics_option(self, *args):
        """Met à jour ENABLE_NETWORK_METRICS en fonction de l'option sélectionnée."""
        network_metrics_option = self.options.menu.get_option_by_name('network_metrics')
        RelationTab.ENABLE_NETWORK_METRICS = network_metrics_option.get_value()
        _LOG.info(f"Network metrics option updated: {RelationTab.ENABLE_NETWORK_METRICS}")

    def update_filter_logic(self, *args):
        """Met à jour la logique des filtres."""
        filter_rule = self.__filter_rule.get_value()
        if filter_rule in (0, 1, 2):
            self.__fid.set_available(True)
        else:
            self.__fid.set_available(False)

    def process_people(self, max_level, uistate, window, default_person, length):
        """Traite la liste des personnes filtrées et calcule les métriques de relation.
        Args:
            max_level: Nombre maximum de générations à considérer.
            uistate: État de l'interface utilisateur (pour les mises à jour GTK).
            window: Fenêtre GTK principale.
            default_person: Personne racine pour les calculs de relation.
            length: Nombre total de personnes dans la base.
        """
        # Vérification que ProgressMeter est initialisé (sécurité)
        if not hasattr(self, 'progress'):
            _LOG.error("ProgressMeter not initialized.")
            return
        count = 0
        filtered_people = len(self.filtered_list)
        # (MODE_FRACTION = 0) by default
        self.progress.set_pass(_('Generating relation map...'), filtered_people, 0)
        _LOG.debug(f"Processing {filtered_people} people.")

        step_one = time.perf_counter()

        # Utilisation d'un générateur pour traiter les personnes une par une
        def generate_results():
            for handle in self.filtered_list:
                self.progress.step()
                # Log après 10 personnes pour éviter de surcharger les logs
                if count % 100 == 10:
                    step_two = time.perf_counter()
                    need = step_two - step_one
                    #lazy tooltip
                    documentation = _("\nFiltering\tCurrent match\t\tTime of pass\n")
                    header = _("%d/%d \t\t %d/%d \t\t%f") % (
                        count, filtered_people, len(self.stats_list), length, float(need))
                    self.progress.set_header(documentation + header)
                    _LOG.debug(f"Processed {count}/{filtered_people} people.")
                # Log uniquement les 10 personnes pour éviter de surcharger les logs
                elif count % 100 < 10:
                    self.progress.set_header("%d/%d" % (count, len(self.filtered_list)))

                try:
                    # 1. Récupération de la personne une seule fois
                    person = self.dbstate.db.get_person_from_handle(handle)
                    if not person:
                        _LOG.warning(f"Person with handle {handle} not found.")
                        continue

                    # 2. Calcul de la distance de relation (une seule fois)
                    dist = self.relationship.get_relationship_distance_new(
                        self.dbstate.db, default_person, person, only_birth=True)
                    _LOG.debug(f"Relationship distance result for {person.get_handle()}: {dist}")
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
                            f"{surname_diversity:.2f}" # Convertir en chaîne de caractères
                        )
                    yield result_entry, name # On retourne le résultat et le nom pour les logs
                except Exception as e:
                    _LOG.error(f"Error processing person with handle {handle}: {e}")
                    continue

        # Traitement des résultats avec le générateur
        count = 0
        batch_size = 50  # Taille du lot pour les mises à jour par batch
        batch_entries = []

        # Traitement des résultats avec le générateur
        for result_entry, name in generate_results():
            # Ajoute le résultat à la liste et au modèle
            count += 1
            self.stats_list.append(result_entry)

            if uistate:
                batch_entries.append((result_entry, int(result_entry[0])))
                # Mise à jour par lots pour améliorer les performances
                if len(batch_entries) >= batch_size:
                    GLib.idle_add(self._add_batch_to_model, batch_entries)
                    batch_entries = []

                # Mise à jour de la progression
                if count % 100 == 0:
                    self.progress.set_header("%d/%d" % (count, len(self.filtered_list)))

        # Ajouter les entrées restantes (si le batch n'est pas plein)
        if uistate and batch_entries:
            GLib.idle_add(self._add_batch_to_model, batch_entries)
            self.show()

        self.progress.close()

        if uistate is None:
            # Afficher un aperçu des résultats dans la console
            print("\nResults preview:")
            print("-" * 100)
            print(f"{_('Rel_id'):<10} | {_('Relation'):<20} | {_('Name'):<30} | {'Ga':<5} | {'Gb':<5} | {'MRA':<5} | {_('Rank'):<5} | {_('Period'):<15}")
            if RelationTab.ENABLE_NETWORK_METRICS:
                print(f" | {_('Shared Subtree'):<15} | {_('Centrality'):<10} | {_('Unique Ancestors'):<15} | {_('Surname Diversity'):<15}")
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
            print(_(f"Total of handled entries : {len(self.stats_list)}\n"))
        _LOG.info(f"Total processing time: {time.perf_counter() - step_one} seconds.")

    def _add_batch_to_model(self, batch):
        """Ajoute un lot d'entrées au modèle GTK."""
        for entry, sort_key in batch:
            self.model.add(entry, sort_key)
        return False  # Indique que le callback ne doit pas être rappelé

    def save(self, *args):
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
        chooser.set_current_folder(self.path)
        status = chooser.run()
        if status == Gtk.ResponseType.OK:
            self.path = chooser.get_current_folder()
        if status == Gtk.ResponseType.CANCEL:
            _LOG.debug(f"Skip folder selection?")
            OkDialog(_("Foldername need"), _("Foldername will be used for saving the content."))
            chooser.destroy()
            return
        chooser.destroy()

        if not self.stats_list:
            _LOG.warning("No data to save.")
            return

        default_person = self.dbstate.db.get_default_person()
        if not default_person or not self.path:
            _LOG.debug("Failed to get the foldername or default person.")
            WarningDialog(_("Did you set a foldername?"), _("Cannot set a valid location."))
            return

        filename = os.path.join(self.path, default_person.get_handle() + '.ods')
        try:
            doc = ODSTab(len(self.stats_list))
            doc.creator(self.dbstate.db.get_researcher().get_name())
            spreadsheet = TableReport(filename, doc)
            new_titles = [title for title in self.titles if title[0] != 'sort']
            spreadsheet.initialize(len(new_titles))
            spreadsheet.write_table_head(new_titles)
            for index, entry in enumerate(self.stats_list):
                spreadsheet.set_row(index % 2)
                spreadsheet.write_table_data(entry)
            spreadsheet.finalize()
            if os.access(self.path, os.R_OK | os.W_OK | os.X_OK) and self.uistate:
                # Afficher un message indiquant où le fichier a été enregistré
                OkDialog(_(f"Data saved to : {filename}"))
                _LOG.info(f"Data successfully saved to {filename}.")
        except (FileNotFoundError or IsADirectoryError) as e:
            _LOG.error(f"Failed to save data: {e}")
            WarningDialog(_("Failed to save data."), str(e))

    def button_clicked(self, button):
        """Appelé quand le bouton 'Save' est cliqué."""
        _LOG.info("Save button clicked.")
        self.save()

    def quit_clicked(self, quit):
        """Appelé quand le bouton 'Quit' est cliqué."""
        _LOG.info("Quit button clicked.")
        self.close()

    def get_title(self):
        return _("Relationships Map and Tab")

    def initial_frame(self):
        return _("Options")

    def build_menu_names(self, obj):
        return (self.label, None)

    def close_progress_meter(self):
        """Ferme le ProgressMeter s'il est ouvert."""
        if hasattr(self, 'progress') and self.progress:
            self.progress.close()

    def on_delete_event(self, window, event):
        """Gère l'événement de fermeture de la fenêtre."""
        self.close_progress_meter() # Ferme le ProgressMeter
        self.close() # Ferme la fenêtre
        return True # Indique que l'événement a été géré

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
        try:
            self.doc.close()
        except:
            # check whether the dir has rwx permissions
            if not os.access(os.getcwd(), os.R_OK | os.W_OK | os.X_OK):
                ErrorDialog(
                    _("Permission problem"),
                    _(
                        "You do not have permission to write "
                        "under the directory %s\n\n"
                        "Please select another directory or correct "
                        "the permissions."
                    )
                    % self.path,
                    parent=None,
                )
            else:
                return

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
            'fid': 2,
            'filter_rule': 0,
            'deep_gen_text': MAX_LEVEL,
            'enable_network_metrics': True, # Option pour activer les métriques de réseau
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
