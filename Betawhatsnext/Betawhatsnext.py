# encoding: utf-8
#
# "What's Next?" Gramplet, a modular plugin for Gramps
# (Gramps - the genealogy software suite built on GTK+/GNOME)
#
# Copyright (C) 2008 Reinhard Mueller
# Copyright (C) 2010 Jakim Friant
# Copyright (C) 2023, 2024 Brian McCullough
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of version 2 of the GNU General Public License as
# published by the Free Software Foundation.
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
# For the Gramps-Project volunteer community's contact information, visit:
# https://gramps-project.org/wiki/index.php/Contact

# ------------------------------------------------------------------------
#
# Gramps modules
#
# ------------------------------------------------------------------------
from gi.repository import Gtk
from gramps.gen.lib import EventType, FamilyRelType
from gramps.gen.plug import Gramplet
from gramps.gen.display.name import displayer as name_displayer
import inspect
from gramps.gen.errors import ValidationError, WindowActiveError
from gramps.gen.plug.report import utils
from gramps.gen.const import GRAMPS_LOCALE as glocale

_ = glocale.translation.sgettext

verbose_suggestions = True
show_diagnostic = False

initial_message = _(
    "\n ⛔ A local Genealogical Tree database has not yet been loaded.\n\n"
)
if verbose_suggestions:
    initial_message += _(" 👣 Next Steps:\n")
    initial_message += _('  •  From the "Family Trees" menu,')
    initial_message += _(' use the "Manage Family Trees..." option to')
    initial_message += _(" create a New (or to select an existing) Tree database.\n")
    initial_message += _('  •  Click the "Load Family Tree" button to begin')
    initial_message += _(" working with the selected genealogical tree.\n\n")
    initial_message += _("Create and load an empty new tree to import a backup (or")
    initial_message += _(" GEDCOM file) from another genealogical tool.\n\n")

# ------------------------------------------------------------------------
#
# The Gramplet
#
# ------------------------------------------------------------------------


class BetaWhatNextGramplet(Gramplet):

    def init(self):
        self.set_tooltip(
            _(
                'Use the "Configure" in the "View" menu to'
                " change the Gramplet options."
            )
        )
        self.set_text(initial_message)

    def build_options(self):
        """
        Build the configuration options.
        """
        from gramps.gen.plug.menu import NumberOption, EnumeratedListOption

        self.opts = []

        # Minimum number of lines we want to see. Further lines with the same
        # distance to the main person will be added on top of this.
        name = _("Seach Quota ")
        opt = NumberOption(name, self.__todos_wanted, 1, 300)
        self.opts.append(opt)

        # How many generations of descendants to process before we go up to the
        # next level of ancestors.
        name = _("Depth per loop")
        opt = NumberOption(name, self.__downs_per_up, 1, 15)
        self.opts.append(opt)

        # After an ancestor was processed, how many extra rounds to delay until
        # the descendants of this ancestor are processed.
        name = _("Pause search expansion")
        opt = NumberOption(name, self.__ancestor_delay, 1, 10)
        self.opts.append(opt)

        # Tag to use to indicate that this person has no further marriages, if
        # the person is not tagged, warn about this at the time the marriages
        # for the person are processed.
        name = _("Completed Person")
        opt = EnumeratedListOption(name, self.__person_complete_tag)
        self.opts.append(opt)

        # Tag to use to indicate that there are no further children in this
        # family, if this family is not tagged, warn about this at the time the
        # children of this family are processed.
        name = _(" Completed offspring Families")
        opt = EnumeratedListOption(name, self.__family_complete_tag)
        self.opts.append(opt)

        # Tag to use to specify people and families to ignore. In this way,
        # hopeless cases can be marked separately and don't clutter up the list.
        name = _("Ignore Person or Family")
        opt = EnumeratedListOption(name, self.__ignore_tag)
        self.opts.append(opt)

        self.opts[3].add_item("", "")
        self.opts[4].add_item("", "")
        self.opts[5].add_item("", "")
        if self.dbstate.db.is_open():
            for tag_handle in self.dbstate.db.get_tag_handles(sort_handles=True):
                tag = self.dbstate.db.get_tag_from_handle(tag_handle)
                tag_name = tag.get_name()
                self.opts[3].add_item(tag_name, tag_name)
                self.opts[4].add_item(tag_name, tag_name)
                self.opts[5].add_item(tag_name, tag_name)

        list(map(self.add_option, self.opts))

    def save_options(self):
        """
        Save gramplet configuration data.
        """
        self.__todos_wanted = int(self.opts[0].get_value())
        self.__downs_per_up = int(self.opts[1].get_value())
        self.__ancestor_delay = int(self.opts[2].get_value())
        self.__person_complete_tag = self.opts[3].get_value()
        self.__family_complete_tag = self.opts[4].get_value()
        self.__ignore_tag = self.opts[5].get_value()

    def save_update_options(self, obj):
        """
        Save a gramplet's options to file.
        """
        self.save_options()
        self.gui.data = [
            self.__todos_wanted,
            self.__downs_per_up,
            self.__ancestor_delay,
            self.__person_complete_tag,
            self.__family_complete_tag,
            self.__ignore_tag,
        ]
        self.update()

    def on_load(self):
        """
        Load stored configuration data.
        """
        if len(self.gui.data) == 6:
            self.__todos_wanted = int(self.gui.data[0])
            self.__downs_per_up = int(self.gui.data[1])
            self.__ancestor_delay = int(self.gui.data[2])
            self.__person_complete_tag = self.gui.data[3]
            self.__family_complete_tag = self.gui.data[4]
            self.__ignore_tag = self.gui.data[5]
        else:
            self.__todos_wanted = 10
            self.__downs_per_up = 1
            self.__ancestor_delay = 5
            self.__person_complete_tag = ""
            self.__family_complete_tag = ""
            self.__ignore_tag = ""

    def db_changed(self):

        self.connect(self.dbstate.db, "home-person-changed", self.update)
        # self.connect(self.dbstate.db, 'active_changed', self.update)
        self.connect(self.dbstate.db, "person-add", self.update)
        self.connect(self.dbstate.db, "person-delete", self.update)
        self.connect(self.dbstate.db, "person-update", self.update)
        self.connect(self.dbstate.db, "family-add", self.update)
        self.connect(self.dbstate.db, "family-delete", self.update)
        self.connect(self.dbstate.db, "family-update", self.update)
        self.connect(self.dbstate.db, "person-rebuild", self.update)
        self.connect(self.dbstate.db, "event-add", self.update)
        self.connect(self.dbstate.db, "event-delete", self.update)
        self.connect(self.dbstate.db, "event-update", self.update)
        self.connect(self.dbstate.db, "event-rebuild", self.update)
        self.connect(self.dbstate.db, "family-add", self.update)
        self.connect(self.dbstate.db, "family-delete", self.update)
        self.connect(self.dbstate.db, "family-update", self.update)
        self.connect(self.dbstate.db, "family-rebuild", self.update)

    def _no_db(self):
        super()._no_db()
        # print("No database open at this point")
        self.set_text(initial_message)

    def main(self):
        self.label = Gtk.Label()
        self.label.set_text("")
        self.label.set_margin_left(2)
        self.label.set_margin_right(2)
        # Fail gracefully if no database is loaded; warn or no entry ⚠ ☡ ⛔ 🚫 🛑 🚧 🚨 👣
        if not self.dbstate.db.is_open():
            self.label.set_text(
                "What's next for this session of Gramps genealogy research'"
            )
            #            self.label.set_text(initial_message)
            #            self.add(self.label)
            return

        # complain if database is empty
        people = self.dbstate.db.get_number_of_people()
        if not people:
            # Set padding/margin
            initial_message = _("\n ⛔ The current Tree database contains no people.\n")
            if verbose_suggestions:
                initial_message += _(
                    "\n 👣 Next Steps:"
                    "\n Add a Family and a person in that family:"
                    '\n  • A Family may be added via the "Add" menu'
                    '\n  • A person may be added by pressing the "+"'
                    ' (plus) in the spouse ("Father/partner1" or'
                    ' "Mother/partner2") panels or "Children" tab.'
                    "\n\nOr Import People from an external file:"
                    "\n  • An external file may be used to populate the"
                    ' tree via "Import..." in the "Family Trees" menu.'
                    # "\n\n After adding at least 1 person, go to the People view, then"
                    # ' select someone to make them the "Active Person", and set'
                    # ' them as the focal "Home Person" via the Edit menu.'
                )
            self.set_text(initial_message)
            return

        # complain if no Active Person  - not critical. Gramplet focus is on Home Person
        #        active_person = self.dbstate.get_active("Person")
        #        if active_person:  # will be empty string in none active, else person handle  len(active_person) == 0:
        #           self.set_text(_("\nThere is currently no person selected to be the Active Person."
        #                           "\n\nGo to the People view, then clicking a row will"
        #                           " select someone to make them the \"Active Person\"."))
        #           return

        # complain if no Home Person
        default_person = self.dbstate.db.get_default_person()
        if default_person is None:
            initial_message = _(
                '\n ⛔ No Person has been chosen as the focal "Home Person".\n'
            )
            if verbose_suggestions:
                initial_message += _(
                    "\n 👣 Next Steps:"
                    "\n  •  Select the People view icon in the Navigator sidebar."
                    '\n  •  Select someone to make them the "Active Person".'
                    '\n  •  Choose "Set Home Person" from the Edit menu or from the'
                    " (right-click) context menu."
                    '\n\n This sets them as the focal "Home Person".'
                )
            self.set_text(initial_message)
            return

        self.set_tooltip(_("Double-click color text to edit details"))
        self.__person_complete_handle = None
        self.__family_complete_handle = None
        self.__ignore_handle = None

        if self.__person_complete_tag:
            tag = self.dbstate.db.get_tag_from_name(self.__person_complete_tag)
            if tag is not None:
                self.__person_complete_handle = tag.get_handle()

        if self.__family_complete_tag:
            tag = self.dbstate.db.get_tag_from_name(self.__family_complete_tag)
            if tag is not None:
                self.__family_complete_handle = tag.get_handle()

        if self.__ignore_tag:
            tag = self.dbstate.db.get_tag_from_name(self.__ignore_tag)
            if tag is not None:
                self.__ignore_handle = tag.get_handle()

        self.__counter = 0

        self.set_text("")
        base_message = " focal Home Person.\n"
        self.__missing_link(default_person, base_message)
        self.__counter = 0

        # List of already processed persons and families, to avoid recursing
        # back down to ourselves or meeting the same person through different
        # paths.
        self.__processed_persons = {default_person.get_handle(): True}
        self.__processed_families = {}

        # List of lists of ancestors in currently processed generation. We go
        # up one generation in each round.
        # The lists are separated into my own ancestors, the ancestors of my
        # spouses, the ancestors of my children's spouses, the ancestors of my
        # parent's other spouses, the ancestors of my grandchildren's spouses,
        # the ancestors of my sibling's spouses etc.
        ancestors = [[default_person]]
        ancestors_queue = [[[default_person]]] + [
            [] for i in range(self.__ancestor_delay)
        ]

        # List of lists of families of relatives in currently processed
        # distance. We go up one level of distance in each round.
        # For example, at the end of the third round, this is (potentially) a
        # list of 4 lists:
        # 1. my own great-grandchildren
        # 2. grandchildren of my parents (= my nephews and nieces)
        # 3. children of my grandparents (= my uncles and aunts)
        # 4. my great-grandparents
        # At the beginning of the fourth round, the other families of my
        # great-grandparents are added (if they were married more than once).
        # The separation into these levels is done to allow the spouses of the
        # earlier level to be listed before the kins of the later level, e.g.
        # the spouses of my nephews and nieces are listed before my uncles and
        # aunts.
        # Not that this may slightly vary with the parameters given at the
        # beginning of this class definition, but the principle remains the
        # same.
        families = []
        families_queue = [[] for i in range(self.__ancestor_delay)]

        # List of spouses to add to ancestors list so we track ancestors of
        # spouses, too, but delayed as defined by the parameter.
        spouses = []
        spouses_queue = []

        while ancestors or families:
            # (Other) families of parents
            for ancestor_group in ancestors_queue.pop(0):
                new_family_group = []
                new_spouses_group = []
                for person in ancestor_group:
                    for family in self.__get_families(person):
                        spouse = self.__get_spouse(person, family)
                        if spouse is UnknownPerson:
                            self.__missing_spouse(person)
                        elif spouse is not None:
                            self.__process_person(spouse, new_spouses_group)
                        self.__process_family(family, person, spouse, new_family_group)
                    self.__process_person_2(person)
                if new_family_group:
                    families.append(new_family_group)
                if new_spouses_group:
                    spouses.append(new_spouses_group)
            show_diagnostic and self.append_text(
                f"Line {inspect.currentframe().f_lineno} quota test: (Other) families of parents:{self.__counter}/{self.__todos_wanted}\n"
            )
            if self.__counter >= self.__todos_wanted:
                break

            # Next generation of children
            if self.__downs_per_up:

                for down in range(self.__downs_per_up):
                    new_families = []
                    for family_group in families:
                        children = []
                        for family, person, spouse in family_group:
                            for child in self.__get_children(family):
                                self.__process_person(child, children)
                            self.__process_family_2(family, person, spouse)
                        show_diagnostic and self.append_text(
                            f"Line {inspect.currentframe().f_lineno} quota test: Family Group in Families:{self.__counter}/{self.__todos_wanted}\n"
                        )
                        if self.__counter >= self.__todos_wanted:
                            break

                        # Families of children
                        new_family_group = []
                        new_spouses_group = []
                        for person in children:
                            show_diagnostic and self.append_text(
                                f"Line {inspect.currentframe().f_lineno} quota test: children: {self.__counter}/{self.__todos_wanted}\n"
                            )
                            if self.__counter >= self.__todos_wanted:
                                break
                            for family in self.__get_families(person):
                                spouse = self.__get_spouse(person, family)
                                if spouse is UnknownPerson:
                                    self.__missing_spouse(person)
                                elif spouse is not None:
                                    self.__process_person(spouse, new_spouses_group)
                                self.__process_family(
                                    family, person, spouse, new_family_group
                                )
                            self.__process_person_2(person)
                        if new_family_group:
                            new_families.append(new_family_group)
                        if new_spouses_group:
                            spouses.append(new_spouses_group)
                        show_diagnostic and self.append_text(
                            f"Line {inspect.currentframe().f_lineno} quota test: Families of children: {self.__counter}/{self.__todos_wanted}\n"
                        )
                        if self.__counter >= self.__todos_wanted:
                            break
                    families = new_families
                    spouses_queue.append(spouses)
                    spouses = []
                    show_diagnostic and self.append_text(
                        f"Line {inspect.currentframe().f_lineno} quota test: Spouses: {self.__counter}/{self.__todos_wanted}\n"
                    )
                    if self.__counter >= self.__todos_wanted:
                        break
                show_diagnostic and self.append_text(
                    f"Line {inspect.currentframe().f_lineno} quota test: Next generation of children: {self.__counter}/{self.__todos_wanted}\n"
                )
                if self.__counter >= self.__todos_wanted:
                    break

            # Parents
            new_ancestors = []
            new_families = []
            for ancestor_group in ancestors:
                new_ancestor_group_1 = []
                new_ancestor_group_2 = []
                new_family_group = []
                for person in ancestor_group:
                    (father, mother, family) = self.__get_parents(person)
                    if family is UnknownFamily:
                        self.__missing_parents(person)
                    elif family is not None:
                        if father is UnknownPerson:
                            self.__missing_father(person)
                        elif father is not None:
                            self.__process_person(father, new_ancestor_group_1)
                        if mother is UnknownPerson:
                            self.__missing_mother(person)
                        elif mother is not None:
                            if father is None:
                                self.__process_person(mother, new_ancestor_group_1)
                            else:
                                self.__process_person(mother, new_ancestor_group_2)
                        self.__process_family(family, father, mother, new_family_group)
                if new_ancestor_group_1 or new_ancestor_group_2:
                    new_ancestors.append(new_ancestor_group_1 + new_ancestor_group_2)
                if new_family_group:
                    new_families.append(new_family_group)
                show_diagnostic and self.append_text(
                    f"Line {inspect.currentframe().f_lineno} quota test: ancestor_group in ancestors: {self.__counter}/{self.__todos_wanted}\n"
                )
                if self.__counter >= self.__todos_wanted:
                    break
            ancestors = new_ancestors + spouses_queue.pop(0)
            ancestors_queue.append(ancestors)
            families_queue.append(new_families)
            families += families_queue.pop(0)
            show_diagnostic and self.append_text(
                f"Line {inspect.currentframe().f_lineno} quota test: Parents: {self.__counter}/{self.__todos_wanted}\n"
            )
            if self.__counter >= self.__todos_wanted:
                break

            # Separator between rounds
            if self.__counter > 0:
                show_diagnostic and self.append_text(
                    f"Line {inspect.currentframe().f_lineno} quota test: New Round of Generations {self.__counter}\n"
                )
                self.append_text("\n")

        self.append_text("", scroll_to="begin")

    def __process_person(self, person, append_list):

        if person.get_handle() in self.__processed_persons:
            return

        self.__processed_persons[person.get_handle()] = True

        missingbits = []

        primary_name = person.get_primary_name()

        if not primary_name.get_first_name():
            missingbits.append(_("first name unknown"))

        if not primary_name.get_surname():
            missingbits.append(_("surname unknown"))

        name = name_displayer.display_name(primary_name)
        if not name:
            name = _("(person with unknown name)")

        has_birth = False

        for event_ref in person.get_primary_event_ref_list():
            event = self.dbstate.db.get_event_from_handle(event_ref.ref)
            if event.get_type() not in [EventType.BIRTH, EventType.DEATH]:
                continue
            missingbits.extend(self.__process_event(event))
            if event.get_type() == EventType.BIRTH:
                has_birth = True

        if not has_birth:
            base_message = _("Birth event missing.")
            suggestion_message = _("Add via the Events tab of the Edit Person dialog.")
            if verbose_suggestions:
                base_message = f"{base_message}\n  👣{suggestion_message}\n"
            missingbits.append(base_message)

        if missingbits:
            self.link(name, "Person", person.get_handle())
            self.append_text(
                _(": %(list)s\n") % {"list": _(", ").join(missingbits)}
            )  # Arabic OK
            self.__counter += 1

        append_list.append(person)

    def __process_person_2(self, person):

        missingbits = []

        primary_name = person.get_primary_name()
        name = name_displayer.display_name(primary_name)
        if not name:
            name = _("(person with unknown name)")

        if (
            self.__person_complete_handle is not None
            and self.__person_complete_handle not in person.get_tag_list()
        ):
            missingbits.append(
                _(f"{inspect.currentframe().f_lineno} person not complete")
            )

        if missingbits:
            self.link(name, "Person", person.get_handle())
            self.append_text(
                _(": %(list)s\n") % {"list": _(", ").join(missingbits)}
            )  # Arabic OK
            self.__counter += 1

    def __process_family(self, family, person1, person2, append_list):

        if family.get_handle() in self.__processed_families:
            return

        self.__processed_families[family.get_handle()] = True

        missingbits = []

        if person1 is UnknownPerson or person1 is None:
            name1 = _("(unknown person)")
        else:
            name1 = name_displayer.display(person1)
            if not name1:
                name1 = _("(person with unknown name)")

        if person2 is UnknownPerson or person2 is None:
            name2 = _("(unknown person)")
        else:
            name2 = name_displayer.display(person2)
            if not name2:
                name2 = _("(person with unknown name)")

        name = _("%(name1)s and %(name2)s") % {"name1": name1, "name2": name2}

        has_marriage = False

        for event_ref in family.get_event_ref_list():
            event = self.dbstate.db.get_event_from_handle(event_ref.ref)
            if event.get_type() not in [EventType.MARRIAGE, EventType.DIVORCE]:
                continue
            missingbits.extend(self.__process_event(event))
            if event.get_type() == EventType.MARRIAGE:
                has_marriage = True

        if family.get_relationship() == FamilyRelType.MARRIED:
            if not has_marriage:
                missingbits.append(_("marriage event missing"))
        elif family.get_relationship() == FamilyRelType.UNKNOWN:
            missingbits.append(_("relationship type unknown"))

        if missingbits:
            self.link(name, "Family", family.get_handle())
            self.append_text(
                _(": %(list)s\n") % {"list": _(", ").join(missingbits)}
            )  # Arabic OK
            self.__counter += 1

        append_list.append((family, person1, person2))
        suggestion_message = _("Add via the Events tab of the Edit Family dialog.")

    #        if verbose_suggestions:
    #            base_message = f"{base_message}\n  👣{suggestion_message}\n"

    def __process_family_2(self, family, person1, person2):

        missingbits = []

        if person1 is UnknownPerson or person1 is None:
            name1 = _("(unknown person)")
        else:
            name1 = name_displayer.display(person1)
            if not name1:
                name1 = _("(person with unknown name)")

        if person2 is UnknownPerson or person2 is None:
            name2 = _("(unknown person)")
        else:
            name2 = name_displayer.display(person2)
            if not name2:
                name2 = _("(person with unknown name)")

        name = _("%(name1)s and %(name2)s") % {"name1": name1, "name2": name2}

        if (
            self.__family_complete_handle is not None
            and self.__family_complete_handle not in family.get_tag_list()
        ):
            missingbits.append(_("591 family not complete"))

        if missingbits:
            self.link(name, "Family", family.get_handle())
            self.append_text(
                _(": %(list)s\n") % {"list": _(", ").join(missingbits)}
            )  # Arabic OK
            self.__counter += 1

    def __process_event(self, event):

        missingbits = []

        date = event.get_date_object()
        if date.is_empty():
            missingbits.append(_("date unknown"))
        elif not date.is_regular():
            missingbits.append(_("date incomplete"))

        place_handle = event.get_place_handle()
        if not place_handle:
            missingbits.append(_("place unknown for the Event"))

        if missingbits:
            # translators: needed for French, ignore otherwise
            return [
                _("%(str1)s: %(str2)s")
                % {"str1": event.get_type(), "str2": _(", ").join(missingbits)}
            ]  # Arabic OK
        else:
            return []

    def __missing_spouse(self, person):
        self.__missing_link(
            person, _("A partner relationship exists but the spouse is missing")
        )
        suggestion_message = _("Add missing partner using the Edit Family dialog.")

    def __missing_father(self, person):
        self.__missing_link(person, _("Father missing from the parent family"))
        suggestion_message = _("Add missing partner using the Edit Family dialog.")

    def __missing_mother(self, person):
        self.__missing_link(person, _("Mother missing from the parent family"))
        suggestion_message = _("Add missing partner using the Edit Family dialog.")

    def __missing_parents(self, person):
        base_message = _("Parent family is unknown.")
        suggestion_message = _(
            '"Add New/Existing Parents" from the Edit menu of the Relationships view.'
        )

    def __missing_link(self, person, text):

        name = name_displayer.display(person)
        self.link(name, "Person", person.get_handle())
        self.append_text(_(": %s\n") % text)
        #        self.append_text(_(": %s\n") % (text, self.__counter))
        show_diagnostic and self.append_text(
            f"\nLine {inspect.currentframe().f_lineno} quota test: Missing Link: count {self.__counter} \n"
        )
        self.__counter += 1

    def __get_spouse(self, person, family):

        spouse_handle = utils.find_spouse(person, family)
        if not spouse_handle:
            if family.get_relationship() == FamilyRelType.MARRIED:
                return UnknownPerson
            else:
                return None
        spouse = self.dbstate.db.get_person_from_handle(spouse_handle)
        if (
            self.__ignore_handle is not None
            and self.__ignore_handle in spouse.get_tag_list()
        ):
            return None
        else:
            return spouse

    def __get_children(self, family):

        for child_ref in family.get_child_ref_list():
            child = self.dbstate.db.get_person_from_handle(child_ref.ref)
            if (
                self.__ignore_handle is not None
                and self.__ignore_handle in child.get_tag_list()
            ):
                continue
            yield child

    def __get_families(self, person):

        for family_handle in person.get_family_handle_list():
            if family_handle in self.__processed_families:
                continue
            family = self.dbstate.db.get_family_from_handle(family_handle)
            if (
                self.__ignore_handle is not None
                and self.__ignore_handle in family.get_tag_list()
            ):
                continue
            yield family

    def __get_parents(self, person):

        family_handle = person.get_main_parents_family_handle()
        if not family_handle:
            return (UnknownPerson, UnknownPerson, UnknownFamily)
        if family_handle in self.__processed_families:
            return (None, None, None)

        family = self.dbstate.db.get_family_from_handle(family_handle)
        if (
            self.__ignore_handle is not None
            and self.__ignore_handle in family.get_tag_list()
        ):
            return (None, None, None)

        father_handle = family.get_father_handle()
        if not father_handle:
            if family.get_relationship() == FamilyRelType.MARRIED:
                father = UnknownPerson
            else:
                father = None
        else:
            father = self.dbstate.db.get_person_from_handle(father_handle)
            if (
                self.__ignore_handle is not None
                and self.__ignore_handle in father.get_tag_list()
            ):
                father = None

        mother_handle = family.get_mother_handle()
        if not mother_handle:
            mother = UnknownPerson
        else:
            mother = self.dbstate.db.get_person_from_handle(mother_handle)
            if (
                self.__ignore_handle is not None
                and self.__ignore_handle in mother.get_tag_list()
            ):
                mother = None

        return (father, mother, family)


class UnknownPersonClass:
    pass


class UnknownFamilyClass:
    pass


UnknownPerson = UnknownPersonClass()
UnknownFamily = UnknownFamilyClass()
