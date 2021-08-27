# Pedigree - Classes for creating and managing pedigrees
#
# Copyright (C) 2021  Hans Boldt
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
Module pedigree.py

Services for creating and managing pedigrees

Exports:

class Pedigree
class PedigreeAncestor

"""

#-------------------#
# Python modules    #
#-------------------#
from itertools import combinations
from math import log

#-------------------#
# Gramps modules    #
#-------------------#
from gramps.gen.relationship import get_relationship_calculator
from gramps.gen.lib import Person, ChildRefType # , EventType
from gramps.gen.config import config

#---------------------#
# Module constants    #
#---------------------#
PEDIGREE_CACHE_SIZE = 30





class SimpleCache:
    """
    A simple cache with maximum size.
    """
    def __init__(self, cache_size):
        """
        __init()
        """
        self.cache = list()
        self.cache_size = cache_size

    def find(self, key):
        """
        Find item with specified key
        """
        for entry in self.cache:
            if entry[0] == key:
                self.cache.remove(entry)
                self.cache.insert(0, entry)
                return entry[1]
        return None

    def add(self, key, item):
        """
        Add item to cache.
        """
        self.cache.insert(0, (key, item))
        if len(self.cache) > self.cache_size:
            self.cache.pop()

    def clear(self):
        """
        Clear cache.
        """
        self.cache = list()




#---------------------------------------#
#                                       #
# PedigreeAncestor class                #
#                                       #
#---------------------------------------#
class PedigreeAncestor:
    """
    One item in a pedigree
    """

    person_cache = dict()
    relcalc = get_relationship_calculator()

    __slots__ = ['db',
                 'pedigree',
                 'ancestor_numbers',
                 'gender',
                 'person_handle',
                 'family_handle',
                 'father_handle',
                 'mother_handle']


    @classmethod
    def get_birth_parents(cls, db, person):
        """
        Method that returns the birthparents of a person as tuple
        (mother handle, father handle), if no known birthparent, the
        handle is replaced by None
        (Like the function in relationship.py, except that this returns the
        family handle as well)
        """
        mom_handle = None
        dad_handle = None

        for fam_handle in person.get_parent_family_handle_list():
            family = db.get_family_from_handle(fam_handle)
            if not family:
                continue

            childrel = [(ref.get_mother_relation(), ref.get_father_relation())
                        for ref in family.get_child_ref_list()
                        if ref.ref == person.handle][0]

            if childrel[0] == ChildRefType.BIRTH:
                mom_handle = family.get_mother_handle()
            if childrel[1] == ChildRefType.BIRTH:
                dad_handle = family.get_father_handle()

            if mom_handle or dad_handle:
                return (dad_handle, mom_handle, fam_handle)

        return None


    @classmethod
    def get_person_from_handle(cls, db, person_handle):
        """
        Get person from handle
        """
        if person_handle in cls.person_cache:
            return cls.person_cache[person_handle]
        person = db.get_person_from_handle(person_handle)
        if person:
            parent_info = cls.get_birth_parents(db, person)
            if parent_info:
                info = (person, parent_info[0], parent_info[1], parent_info[2])
            else:
                info = (person, None, None, None)

            cls.person_cache[person_handle] = info
            return info
        return None


    @classmethod
    def clear_person_cache(cls):
        """
        Clear person cache.
        """
        cls.person_cache = dict()


    def __init__(self, pedigree, anc_number,
                 person_handle=None,
                 family_handle=None):
        """
        __init__()
        """
        self.pedigree = pedigree
        self.db = pedigree.db
        self.ancestor_numbers = []
        self.father_handle = None
        self.mother_handle = None
        self.gender = Person.UNKNOWN
        self.family_handle = family_handle
        self.add_ancestor_number(anc_number)
        self.set_person_handle(person_handle)


    def add_ancestor_number(self, anc_num):
        """
        Add to the list of ancestor numbers for this ancestor.
        """
        self.ancestor_numbers.append(anc_num)


    def get_primary_ancestor_number(self):
        """
        Get primary ancestor number, which is the first in the list.
        """
        return self.ancestor_numbers[0]


    def get_ancestor_numbers(self):
        """
        Return list of all ancestor numbers for this ancestor.
        """
        return self.ancestor_numbers


    def get_person_handle(self):
        """
        Get gramps person handle for this ancestor
        """
        return self.person_handle


    def set_person_handle(self, person_handle):
        """
        Set the gramps person handle for this ancestor. Also record handles
        for the person's parents.
        """
        self.person_handle = person_handle
        if person_handle:
            person_info = self.get_person_from_handle(self.db, person_handle)
            self.gender = person_info[0].get_gender()
            self.father_handle = person_info[1]
            self.mother_handle = person_info[2]
            self.family_handle = person_info[3]


    def get_father_handle(self):
        """
        Return the father handle for this ancestor
        """
        return self.father_handle


    def get_mother_handle(self):
        """
        Return the mother handle for this ancestor.
        """
        return self.mother_handle


    def get_pedigree(self):
        """
        Return the pedigree that this person is in.
        """
        return self.pedigree


    def is_male(self):
        """
        Is this ancestor male?
        """
        return self.gender == Person.MALE


    def is_female(self):
        """
        Is this ancestor female?
        """
        return self.gender == Person.FEMALE



#---------------------------------------#
#                                       #
# Pedigree class                        #
#                                       #
#---------------------------------------#
class Pedigree:
    """
    A pedigree.

    Exports:
        Class Methods:

        make_pedigree(person1_handle, person2_handle, unlimited)
        clear_pedigree_cache()
        clear_ancestor_cache()
        set_max_generations(use_gramps_default, explicit_limit)
        iter_down_descendants(ancestor_number)
        iter_down_desc_pair(anc_num_a, anc_num_b)

        Instance Methods:

        get_ancestor_by_number(ancestor_number)
        has_pedigree_collapse()
        __iter__()
        __next__()
        get_pedigree()
        determine_pedigree_collapse(filter_number)
        order_ancestor_list(ancestors)

    """

    __slots__ = ['db',
                 'pedigree',
                 'ancestor_by_handle',
                 'ancestor_by_number',
                 'pedigree_collapse_found',
                 'depth_limit_reached',
                 'unlimited',
                 'iter_index']

    max_depth = config.get('behavior.generation-depth')
    max_pedigree_number = 2 ** (max_depth+1) - 1
    pedigree_cache = SimpleCache(PEDIGREE_CACHE_SIZE)


    @classmethod
    def make_pedigree(cls, db, person1_handle=None, person2_handle=None,
                      unlimited=False):
        """
        Get pedigree for specified persons(s). Check if we have a cached
        pedigree already.
        """
        if person2_handle:
            cache_key = (person1_handle, person2_handle)
        else:
            cache_key = person1_handle

        # Check if we have a cached pedigree already
        pedigree = cls.pedigree_cache.find(cache_key)
        if pedigree:
            return pedigree

        # Create new pedigree
        pedigree = Pedigree(db, person1_handle, person2_handle, unlimited)
        cls.pedigree_cache.add(cache_key, pedigree)
        return pedigree


    @classmethod
    def clear_pedigree_cache(cls):
        """
        Clear pedigree cache.
        """
        cls.pedigree_cache.clear()


    @classmethod
    def clear_ancestor_cache(cls):
        """
        Clear ancestor cache
        """
        PedigreeAncestor.clear_person_cache()


    @classmethod
    def set_max_generations(cls, use_gramps_default, explicit_limit=50):
        """
        Set the maximum number of generations for each pedigree
        """
        if use_gramps_default:
            cls.max_depth = config.get('behavior.generation-depth')
        else:
            cls.max_depth = explicit_limit
        cls.max_pedigree_number = 2** (cls.max_depth+1) - 1


    @classmethod
    def iter_down_descendants(cls, anc_num):
        """
        Given an ancestor number, iterate down through descendant numbers.
        """
        anc_num = anc_num // 2
        while anc_num:
            yield anc_num
            anc_num = anc_num // 2


    @classmethod
    def iter_down_desc_pair(cls, anc_num_a, anc_num_b):
        """
        Given a pair of ancestor numbers, iterate down the pair, finishing at (1,1)
        """
        anc_num_a = anc_num_a // 2
        anc_num_b = anc_num_b // 2
        while anc_num_a and anc_num_b:
            yield (anc_num_a, anc_num_b)
            if anc_num_a > anc_num_b:
                anc_num_a = anc_num_a // 2
            else:
                anc_num_b = anc_num_b//2


    def __init__(self, db, person1_handle=None, person2_handle=None,
                 unlimited=False):
        """
        __init__
        """
        self.db = db
        self.unlimited = unlimited
        self.pedigree_collapse_found = False
        self.depth_limit_reached = False
        if person1_handle:
            self._load_pedigree(person1_handle, person2_handle)
        self.iter_index = 0


    def _load_pedigree(self, person1_handle, person2_handle=None):
        """
        Load the pedigree for the specified person(s).

        Note: If two person handles are specified, they will be added as
        ancestors #2 and #3, with a dummy #1
        """

        self.pedigree = list()
        self.ancestor_by_handle = dict()
        self.ancestor_by_number = dict()

        # Prime the parent queue with person(s). The parent_queue is a first-come,
        # first-served list of ancestors to process.
        if not person2_handle:
            # One person given. That person is #1 in the pedigree
            parent_queue = [(1, person1_handle)]

        else:
            # Two people given. They are #2 and #3 in the pedigree, with a
            # dummy child as #1
            dummy_root = PedigreeAncestor(self, 1)
            self.pedigree.append(dummy_root)
            self.ancestor_by_number[1] = dummy_root
            person1 = self.db.get_person_from_handle(person1_handle)
            person1_gender = person1.get_gender()

            # Make sure ancestor #2 is male
            if person1_gender == Person.MALE:
                parent_queue = [(2, person1_handle), (3, person2_handle)]
            else:
                parent_queue = [(2, person2_handle), (3, person1_handle)]

        # Do a breadth-first search through the person's ancestry.
        while parent_queue:
            # Save this person into pedigree
            (anc_number, anc_handle) = parent_queue.pop(0)
            ancestor = self._process_ancestor(anc_number, anc_handle)

            # Push parents on queue (if they exist)
            father_handle = ancestor.get_father_handle()
            mother_handle = ancestor.get_mother_handle()
            if father_handle or mother_handle:
                if not self.unlimited and anc_number*2 > self.max_pedigree_number:
                    self.depth_limit_reached = True
                else:
                    parent_queue.append((anc_number*2, father_handle))
                    parent_queue.append((anc_number*2+1, mother_handle))


    def _process_ancestor(self, anc_number, anc_handle):
        """
        Process one ancestor in this pedigree
        """
        # Are we adding a real person? or an unknown dummy ancestor?
        if anc_handle:
            # Has this person already been added to the tree?
            if anc_handle in self.ancestor_by_handle:
                # Yes, person is already in the pedigree. We have pedigree collapse
                self.pedigree_collapse_found = True
                ancestor = self.ancestor_by_handle[anc_handle]
                ancestor.add_ancestor_number(anc_number)

            else:
                # This is a new person in the pedigree, add person to pedigree
                ancestor = PedigreeAncestor(self, anc_number, person_handle=anc_handle)
                self.pedigree.append(ancestor)
                self.ancestor_by_handle[anc_handle] = ancestor
        else:
            # We're adding an unknown dummy ancestor. Use the child's family
            # handle to identify the unknown ancestor. (At least one of the
            # parents will be known.)
            child_number = anc_number//2
            fam_handle = self.ancestor_by_number[child_number].family_handle
            if fam_handle in self.ancestor_by_handle:
                # Yes, person is already in the pedigree. We have pedigree collapse
                self.pedigree_collapse_found = True
                ancestor = self.ancestor_by_handle[fam_handle]
                ancestor.add_ancestor_number(anc_number)

            else:
                # This is a new person in the pedigree, add person to pedigree
                # using the family handle to identify the ancestor.
                ancestor = PedigreeAncestor(self, anc_number, family_handle=fam_handle)
                self.pedigree.append(ancestor)
                self.ancestor_by_handle[fam_handle] = ancestor

        self.ancestor_by_number[anc_number] = ancestor
        return ancestor


    def get_ancestor_by_number(self, anc_num):
        """
        Return the ancestor by the specified ancestor number.
        """
        if anc_num in self.ancestor_by_number:
            return self.ancestor_by_number[anc_num]
        return None


    def has_pedigree_collapse(self):
        """
        Return True if there is pedigree collapse in this pedigree.
        """
        return self.pedigree_collapse_found


    def __iter__(self):
        """
        Iterator to loop through all ancestors in this pedigree.
        """
        self.iter_index = 0
        return self

    def __next__(self):
        """
        Get next ancestor from this iterator
        """
        if self.iter_index < len(self.pedigree):
            anc = self.pedigree[self.iter_index]
            self.iter_index += 1
            return anc
        raise StopIteration


    def get_pedigree(self):
        """
        Iterator to loop through the ancestors in this pedigree. This is
        different from the __iter__() function in that redundant entries in
        the pedigree are removed.

        Returns: a tuple of 3 items:
                   1: True: this is a primary ancestor
                   2: Ancestor number
                   3: Primary ancestor number (used if 1 is False)
        """

        saved_duplicates = list()
        redirected_numbers = list()

        for ancestor in self.pedigree:
            # Get ancestor. Ignore if it is a dummy entry
            anc_handle = ancestor.get_person_handle()
            if not anc_handle:
                continue

            # Process ancestor number. If we have a list with more than
            # one number, return first number and save others for later
            # processing
            anc_numbers = ancestor.get_ancestor_numbers()

            # Do we have saved redirections that needs to be returned
            # first?
            while saved_duplicates and saved_duplicates[0][0] < anc_numbers[0]:
                (anc_num, primary) = saved_duplicates.pop(0)
                # Print redirection, but only if child isn't already redirected
                if (anc_num // 2) not in redirected_numbers:
                    yield (False, anc_num, primary)

                redirected_numbers.append(anc_num)

            # Save rest of ancestor number list for future processing
            for anc_num in anc_numbers[1:]:
                saved_duplicates.append((anc_num, anc_numbers[0]))
                saved_duplicates.sort()

            yield (True, anc_numbers[0], 0)

        # Print out remaining ancestor numbers
        while saved_duplicates:
            (anc_num, primary) = saved_duplicates.pop(0)
            # Print redirection, but only if child isn't already redirected
            if (anc_num // 2) not in redirected_numbers:
                yield (False, anc_num, primary)

            redirected_numbers.append(anc_num)


    def _find_ped_collapse_ancestors(self):
        """
        Find pedigree items where pedigree collapse occurs.

        Returns: List of ancestors where ancestral lines converge
        """
        res = list()

        # Loop through all ancestors
        for ancestor in self.pedigree:
            # For each ancestor, if the number of pedigree numbers is an
            # increase from one generation to the next, we have pedigree
            # collapse
            ancestor_numbers = ancestor.get_ancestor_numbers()
            if len(ancestor_numbers) == 1:
                continue

            # Look at child of ancestor
            ancnum = ancestor.get_primary_ancestor_number()
            child = self.ancestor_by_number[ancnum//2]
            child_numbers = child.get_ancestor_numbers()
            if len(child_numbers) < len(ancestor_numbers):
                # We have pedigree collapse.
                res.append(ancestor)

        return res


    def _find_common_descendants(self, ancestor, filter_number=None):
        """
        For one instance of pedigree collapse, find the descendants where
        the lines of descent merge.

        Returns: List of tuples:
                 0: ancestor number of common descendant
                 1: ancestor tuple of common ancestors
        """

        descendants = list()
        anc_nums = ancestor.ancestor_numbers

        # For each pair-wise combination of ancestor numbers, look for
        # the common descendant down both lines of descendant.
        for (aix, bix) in combinations(range(len(anc_nums)), 2):

            # Loop downwards through both lines of descent. If we find the
            # same number in both lines, we've found our common descendant.
            desc_number = None
            for (desc_a, desc_b) in self.iter_down_desc_pair(anc_nums[aix],
                                                             anc_nums[bix]):
                if desc_a == desc_b:
                    desc_number = desc_a
                    break
                if self.ancestor_by_number[desc_a] \
                        is self.ancestor_by_number[desc_b]:
                    break

            # Found our common descendant?
            if desc_number:
                if not filter_number or desc_number == filter_number:
                    # For common descendant, add ancestor number tuple
                    # to list of common ancestors
                    anc_tuple = (desc_number, (anc_nums[aix], anc_nums[bix]))
                    descendants.append(anc_tuple)

        return descendants


    def _find_all_common_descendants(self, ped_collapse_ancestors,
                                     filter_number=None):
        """
        For all pedigree collapse ancestors, determine common descendants for
        all ancestors in list.

        Returns: Dictionary indexed by the number of the common descendant.
                Each item is a list of tuples of the common ancestors for
                that descendant
        """
        resdict = dict()
        for pedcollanc in ped_collapse_ancestors:
            common_descendants = self._find_common_descendants(pedcollanc,
                                                               filter_number)

            for (common_desc, common_ancs) in common_descendants:
                if common_desc in resdict:
                    resdict[common_desc].append(common_ancs)
                else:
                    resdict[common_desc] = [common_ancs]

        return resdict


    @classmethod
    def _merge_spouses(cls, common_descendants):
        """
        For each item in the common descendants, merge together the spouses.
        """
        for (comm_desc, comm_anc_list) in common_descendants.items():
            # Divide list into male and female ancestors
            ancs = sorted(comm_anc_list)
            male_ancestors = [x for x in ancs if x[0]%2 == 0]
            female_ancestors = [x for x in ancs if x[0]%2 == 1]

            # Loop through both male and female lists, merging couples
            new_anc_list = list()
            while male_ancestors and female_ancestors:
                male_nums = male_ancestors[0]
                female_nums = female_ancestors[0]
                if male_nums[0]+1 == female_nums[0] \
                and male_nums[1]+1 == female_nums[1]:
                    new_anc_list.append((male_nums, female_nums))
                    male_ancestors.pop(0)
                    female_ancestors.pop(0)
                elif male_nums < female_nums:
                    new_anc_list.append((male_nums,))
                    male_ancestors.pop(0)
                else:
                    new_anc_list.append((female_nums,))
                    female_ancestors.pop(0)
            while male_ancestors:
                new_anc_list.append((male_ancestors.pop(0),))
            while female_ancestors:
                new_anc_list.append((female_ancestors.pop(0),))

            common_descendants[comm_desc] = new_anc_list


    def determine_pedigree_collapse(self, filter_number=None):
        """
        Get summary of the pedigree collapse.

        Returns: Dictionary. For each common descendant, indicated by ancestor
                number, a list of common ancestors. Each ancestor is a pair of
                ancestor numbers, each going down a different path to the common
                descendant.
                None - if no pedigree collapse.
        """
        # Get list of ancestor(s) where pedigree collapse occurs
        ped_collapse_ancestors = self._find_ped_collapse_ancestors()
        if not ped_collapse_ancestors:
            return None

        # For each pair of ancestors, find the common descendant(s)
        common_descendants = self._find_all_common_descendants \
                    (ped_collapse_ancestors, filter_number)

        # Merge spouses
        self._merge_spouses(common_descendants)
        return common_descendants


    def order_ancestor_list(self, ancestors):
        """
        Order the list of common ancestors. First, by primary ancestor numbers.
        Second, by relationship.

        Returns: A dictionary indexed by a tuple of primary ancestors numbers.
                Each item is a dictionary indexed by a tuple of number of
                generations down each path to common descendant. Each item of
                that dictionary is a list of tuples of ancestor numbers.
        """

        # First, order by primary ancestor numbers
        ordered_ancestors = dict()
        for commanc in ancestors:
            prim_ancnums = tuple()
            for comm in commanc:
                anc = self.ancestor_by_number[comm[0]]
                primary = anc.get_primary_ancestor_number()
                prim_ancnums += (primary,)

            if prim_ancnums in ordered_ancestors:
                ordered_ancestors[prim_ancnums].append(commanc)
            else:
                ordered_ancestors[prim_ancnums] = [commanc]

        # Next, order the items in each by generations
        res_ordered_ancs = dict()
        for (key, commanc) in ordered_ancestors.items():
            generations = dict()
            for anc in commanc:
                (anc_a, anc_b) = anc[0]
                gens = (int(log(anc_a, 2)), int(log(anc_b, 2)))
                if gens in generations:
                    generations[gens].append(anc)
                else:
                    generations[gens] = [anc]

            res_ordered_ancs[key] = generations

        return res_ordered_ancs
