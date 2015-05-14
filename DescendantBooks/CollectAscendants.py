#
# Copyright (C) 2011 Matt Keenan <matt.keenan@gmail.com>
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

#------------------------------------------------------------------------
#
# standard python modules
#
#------------------------------------------------------------------------
import copy

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.lib import Person
from gramps.gen.relationship import get_relationship_calculator
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext


#------------------------------------------------------------------------
#
#
#
#------------------------------------------------------------------------
class CollectAscendants():
    def __init__(self, database, user, title):
        self.database = database
        self.user = user
        self.title = title

    def print_person(self, handle):
        """
        print person name from provided handle
        """
        self.print_person_from_handles([handle])

    def print_person_from_handles(self, handles):
        """
        Given a list of people handles, print their gramps_id and name
        """
        for person_handle in handles:
            person = self.database.get_person_from_handle(person_handle)
            print(person.gramps_id, person.get_primary_name().get_name())

    def __get_mate_handles(self, person):
        """
        Given a person, return a list of mate handles
        """
        mate_handles = list()

        for family_handle in person.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)
            if person.get_gender() == Person.MALE:
                mate_handle = family.get_mother_handle()
            else:
                mate_handle = family.get_father_handle()
         
            if mate_handle:
                mate_handles.append(mate_handle)

        return mate_handles

    def __get_parent_handles(self, person_handle):
        """
        Retrieve mother and father handles for person
        """
        person = self.database.get_person_from_handle(person_handle)
        family_handle = person.get_main_parents_family_handle()
        if family_handle:
            family = self.database.get_family_from_handle(family_handle)
            father_handle = family.get_father_handle()
            mother_handle = family.get_mother_handle()
        else:
            father_handle = None
            mother_handle = None
        return (father_handle, mother_handle)

    def __process_ascendants(self, person_handle):
        """
        For this person handle, traverse to the top most ascendants and add
        these to ascendants list if not on the list already.
        """
        father_handle, mother_handle = self.__get_parent_handles(person_handle)

        person = self.database.get_person_from_handle(person_handle)
        family_handle = person.get_main_parents_family_handle()
        if father_handle or mother_handle:
            if father_handle:
                self.__process_ascendants(father_handle)
            if mother_handle:
                self.__process_ascendants(mother_handle)
        else:
            if person_handle not in self.ascendants:
                self.ascendants.append(person_handle)

    def __process_descendants(self, person_handle):
        """
        Simply add all the descendants of this person to self.descendants
        """
        person = self.database.get_person_from_handle(person_handle)
        for family_handle in person.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)
            for child_ref in family.get_child_ref_list():
                if child_ref.ref not in self.descendants:
                    self.descendants.append(child_ref.ref)
                    self.__process_descendants(child_ref.ref)

    def __remove_descendants_from_ascendants(self, person_handle):
        """
        Process persons descendants, removing from self.ascendants if they
        are there.
        """
        person = self.database.get_person_from_handle(person_handle)
        for family_handle in person.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)
            for child_ref in family.get_child_ref_list():
                if child_ref.ref in self.ascendants:
                    self.ascendants.remove(child_ref.ref)
                # Check if any of the childs spouses are remove them also
                for mate_handle in self.__get_mate_handles( \
                        self.database.get_person_from_handle(child_ref.ref)):
                    if mate_handle in self.ascendants:
                        self.ascendants.remove(mate_handle)
                self.__remove_descendants_from_ascendants(child_ref.ref)

    def __deep_rel_calc(self, person, mate):
        """
        Check if person is related to anyone else in the ascendants list
        """
        for asc_handle in self.ascendants:
            asc_person = self.database.get_person_from_handle(asc_handle)

            # We know they are related to their mate, lets not return this
            if asc_person == mate:
                continue

            person_related = self.rel_calc.get_one_relationship(self.database,
                                                                asc_person,
                                                                person)
            if person_related:
                return person_related

        return ""

    def __prune_ascendants(self, deep_prune):
        """
        Process self.ascendants pruning out unneeded mates

        We need to prune down the ancestors
          - Remove mates's
            - if two mates and one of them has parents who is in
              ascendants, then can remove both mates from ancestral list
            - If two mates and neither have parents, we can still
              remove one of them.
                 Remove the one that is "not related to center person"
              or
                 Remove mother.... potentially sexist I know
        """
        if deep_prune:
            self.user.begin_progress(self.title,
                _('Deep pruning ascendants from %s people...') %
                (len(self.ascendants)), len(self.ascendants))
        else:
            self.user.begin_progress(self.title,
                _('Pruning ascendants from %s people...') %
                (len(self.ascendants)), len(self.ascendants))

        asc_copy = copy.deepcopy(self.ascendants)
        for person_handle in asc_copy:
            self.user.step_progress()
            person = self.database.get_person_from_handle(person_handle)
            person_father, person_mother = \
                self.__get_parent_handles(person_handle)

            if (person_father and person_father in self.ascendants) or \
               (person_mother and person_mother in self.ascendants):
                person_parents_exist = True
            else:
                person_parents_exist = False

            for mate_handle in self.__get_mate_handles(person):
                mate = self.database.get_person_from_handle(mate_handle)
                mate_father, mate_mother = \
                    self.__get_parent_handles(mate_handle)

                if (mate_father and mate_father in self.ascendants) or \
                   (mate_mother and mate_mother in self.ascendants):
                    mate_parents_exist = True
                else:
                    mate_parents_exist = False

                # Either person or mates parents are in ascendants, we
                # can safely remove both of them
                if person_parents_exist or mate_parents_exist:
                    # a set of parents exists, so we should
                    # remove both of these now
                    if person_handle in self.ascendants:
                        self.ascendants.remove(person_handle)
                        self.persons_pruned.append(person_handle)

                    if mate_handle in self.ascendants:
                        self.ascendants.remove(mate_handle)
                        self.persons_pruned.append(mate_handle)

                # Neither person or mate have parents in ascendants
                else:
                    if deep_prune:
                        person_related = self.__deep_rel_calc(person, None)
                        mate_related = self.__deep_rel_calc(mate, person)
                    else:
                        person_related = self.rel_calc.get_one_relationship(
                                                        self.database,
                                                        self.center_person,
                                                        person)
                        mate_related = self.rel_calc.get_one_relationship(
                                                        self.database,
                                                        self.center_person,
                                                        mate)
                    # rel_calc does not return "Me" if the center_person
                    # is the same as the person checking if related to.
                    if not person_related and self.center_person == person:
                        person_related = "Me"

                    if not mate_related and self.center_person == mate:
                        mate_related = "Me"

                    if person_related and mate_related:
                        # Both related, so remove the female
                        # Remove the mate if person_related is "me" otherwise
                        # Remove the female side
                        if person_related == "Me":
                            if mate_handle in self.ascendants:
                                self.ascendants.remove(mate_handle)
                        else:
                            if person.get_gender() == Person.FEMALE:
                                if person_handle in self.ascendants:
                                    self.ascendants.remove(person_handle)
                                    self.persons_pruned.append(person_handle)
                            else:
                                if mate_handle in self.ascendants:
                                    self.ascendants.remove(mate_handle)

                    elif person_related:
                        # Remove mate if they are present
                        if mate_handle in self.ascendants:
                            self.ascendants.remove(mate_handle)
                            self.persons_pruned.append(mate_handle)
                    elif mate_related:
                        # mate related so remove person
                        if person_handle in self.ascendants:
                            self.ascendants.remove(person_handle)
                            self.persons_pruned.append(person_handle)
                    else:
                        # Just remove the female
                        if person.get_gender() == Person.FEMALE:
                            if person_handle in self.ascendants:
                                self.ascendants.remove(person_handle)
                                self.persons_pruned.append(person_handle)
                        else:
                            if mate_handle in self.ascendants:
                                self.ascendants.remove(mate_handle)
                                self.persons_pruned.append(mate_handle)
        self.user.end_progress()

    def __get_preferred_handle(self, person_handle, mate_handle):
        """
        Look at this persons mates, and for all 
        """
        person = self.database.get_person_from_handle(person_handle)

        # Process this persons other mates, if one of the other mates
        # Is in the current desdencants tree, then we need to add this person
        for new_mate in self.__get_mate_handles(person):
            if new_mate != mate_handle and new_mate in self.descendants:
                return person_handle

        # If we got here then it's the mate we want to add
        return mate_handle

    def collect_data(self, filter, center_person):
        """
        This method runs through the data, and collects all the people to be
        processed
        """
        self.center_person = center_person

        # Get all people in Database
        people = self.database.iter_person_handles()

        # Apply the preferred people filter
        self.user.begin_progress(self.title, _('Applying Filter...'), 
            self.database.get_number_of_people())
        people_handles = filter.apply(self.database, people,
            self.user.step_progress)
        self.user.end_progress()

        entire_database = False

        self.rel_calc = get_relationship_calculator()

        if len(people_handles) == self.database.get_number_of_people():
            entire_database = True

            # For everyone in entire database, get top most ascendants
            self.ascendants = list()
            self.user.begin_progress(self.title,
                _('Getting ascendants from %s people...') %
                (len(people_handles)), len(people_handles))
            for person_handle in people_handles:
                self.user.step_progress()
                self.__process_ascendants(person_handle)
            self.user.end_progress()

            # If we have all ascendants from all families, getting descendants
            # For all these people should result in the entire database
            self.descendants = list()
            self.user.begin_progress(self.title,
                _('Verifying descendants from %s people...') %
                (len(self.ascendants)), len(self.ascendants))
            for person_handle in self.ascendants:
                self.user.step_progress()
                if person_handle not in self.descendants:
                    self.descendants.append(person_handle)
                self.__process_descendants(person_handle)
            self.user.end_progress()


            # For this run all descendants count should be the same
            # as total people handle count
            if len(people_handles) != len(self.descendants):
                # If this is the case then we must have some orphans
                # This should never be the case, but either way.
                # Lets get them and add them to ascendants.
                self.user.begin_progress(self.title,
                    _('Getting missing descendants from %s people...') %
                    (len(people_handles)), len(people_handles))
                for person_handle in people_handles:
                    self.user.step_progress()
                    if person_handle not in self.descendants:
                        self.ascendants.append(person_handle)
                        self.descendants.append(person_handle)
                self.user.end_progress()

            # Prune the ascendants
            self.persons_pruned = list()
            self.__prune_ascendants(False)
            self.__prune_ascendants(True)

            # Ultimate test get all descendants of ascendants after pruning
            # We will get most of entire tree but we won't get the partners
            # that we just pruned out.
            self.descendants = list()
            self.user.begin_progress(self.title,
                _('Verifying descendants from %s people after pruning...') %
                (len(self.ascendants)), len(self.ascendants))
            for person_handle in self.ascendants:
                self.user.step_progress()
                if person_handle not in self.descendants:
                    self.descendants.append(person_handle)
                self.__process_descendants(person_handle)
            self.user.end_progress()

            if len(people_handles) != \
               (len(self.descendants) + len(self.persons_pruned)):
                # If this is the case then we must have some orphans
                # This is likely to occur where a non related spouse
                # Has other spouses. Normal detailed desdendant tree
                # Does not show these.
                self.user.begin_progress(self.title,
                    _('Getting missing descendants from %s people ...') %
                    (len(people_handles)), len(people_handles))
                for person_handle in people_handles:
                    self.user.step_progress()
                    if person_handle not in self.descendants:
                        person = \
                            self.database.get_person_from_handle(person_handle)
                        for mate_handle in self.__get_mate_handles(person):
                            if mate_handle not in self.descendants:
                                # Determine which person should be added 
                                # person_handle or mate_handle.
                                # For this person check if other mates are
                                # are in our descendants, if they are that's
                                # the person we want.
                                add_handle = self.__get_preferred_handle(
                                                person_handle, mate_handle)

                                if add_handle not in self.ascendants:
                                    self.ascendants.append(add_handle)
                                    self.__remove_descendants_from_ascendants(
                                                                person_handle)
                                if add_handle not in self.descendants:
                                    self.descendants.append(add_handle)
                                    self.__process_descendants(add_handle)
                self.user.end_progress()
        else:
            # If not processing entire database, then list should be
            # the result of the filter itself.
            self.ascendants = list()
            self.user.begin_progress(self.title,
                _('Getting ascendants from %s people...') %
                (len(people_handles)), len(people_handles))
            for person_handle in people_handles:
                self.user.step_progress()

                person = self.database.get_person_from_handle(person_handle)
                person_father, person_mother = \
                    self.__get_parent_handles(person_handle)

                if person_father and person_father in people_handles:
                    continue

                if person_mother and person_mother in people_handles:
                    continue

                # Person's parent does not exist in people_handles so 
                # add to ascendants if not there.
                if person_handle not in self.ascendants:
                    self.ascendants.append(person_handle)
            self.user.end_progress()

            # Prune ascendants of unecessary mates
            self.persons_pruned = list()
            self.__prune_ascendants(False)
            self.__prune_ascendants(True)

        return self.ascendants
