# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010  Heinz Brinker <heinzbrinker@yahoo.de>
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

# $Id: RelativeRelations.py 15814 2010-08-25 04:25:08Z dsblank $

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
import posixpath

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gen.display.name import displayer as name_displayer
from gen.plug import Gramplet
from gen.ggettext import sgettext as _
from Utils import media_path_full
import Relationship
import DateHandler
import gen

#------------------------------------------------------------------------
#
# Gramplet class
#
#------------------------------------------------------------------------
class RelatedRelativesGramplet(Gramplet):
    def init(self):
        self.set_text(_("No Family Tree loaded."))
#         self.set_tooltip(_("Double-click item to see matches"))

    def db_changed(self):
        self.dbstate.db.connect('person-add', self.update)
#         self.dbstate.db.connect('person-edit', self.update)
        self.dbstate.db.connect('person-delete', self.update)
        self.dbstate.db.connect('family-add', self.update)
        self.dbstate.db.connect('family-delete', self.update)
        self.dbstate.db.connect('person-rebuild', self.update)
        self.dbstate.db.connect('family-rebuild', self.update)
#
    def addDescendants(self, ancestorHandle):
        if ancestorHandle not in self.person_handle_list:
            self.person_handle_list.append(ancestorHandle)
#             self.append_text(" +")
            ancestor = self.dbstate.db.get_person_from_handle(ancestorHandle)
            if ancestor:
#                 pname = name_displayer.display(ancestor)
#                 self.append_text(" %s " % pname)
                for family_handle in ancestor.get_family_handle_list():
                    if family_handle:
                        family = self.dbstate.db.get_family_from_handle(family_handle)
                        if family:
                            childlist = family.get_child_ref_list()[:]
                            for child_ref in childlist:
                                self.addDescendants(child_ref.ref)
#         else:
#             self.append_text(" .")


    def main(self):
        self.set_text("Relations of related people in your database:")
        database = self.dbstate.db
        rel_calc = Relationship.get_relationship_calculator()
        family_handle_list = [] # Will keep list of families with no ancestors
        nf = 0
#         self.append_text("Searching base families...\n")
        # Find the base families with no ancestors
        flist = database.iter_family_handles()
        for familyhandle in flist:
            family = database.get_family_from_handle(familyhandle)
            nf += 1
#             self.append_text("Checking family %d\n" % nf)
            # Check if mother of this family is child of another family
            ancestorHandle = family.get_mother_handle()
            if ancestorHandle:
                mother = database.get_person_from_handle(ancestorHandle)
                parent_handle_list = mother.get_parent_family_handle_list()
                if parent_handle_list:
#                     self.append_text(" Has Ancesctors\n")
                    continue
            # Check if father of this family is child of another family
            ancestorHandle = family.get_father_handle()
            if ancestorHandle:
                father = database.get_person_from_handle(ancestorHandle)
                parent_handle_list = father.get_parent_family_handle_list()
                if parent_handle_list:
#                   self.append_text(" Has Ancesctors\n")
                  continue
            # Members of this family have no ancestors. Add family
            family_handle_list.append(familyhandle)
#             self.append_text("Processing to be done for family %d\n" % nf)
            yield True

        # Iterate found families and find all descendants for each family
#         self.append_text("Iterating base families...\n")
        # The family_list contains all families with no ancestors.
        pair_p1_list = []
        pair_p2_list = []
        for familyhandle in family_handle_list:
#             self.append_text("\n***** Next family *****\n")
            self.person_handle_list = []
            family = database.get_family_from_handle(familyhandle)
            # Add all descendants of the father
            father_handle = family.get_father_handle()
            if father_handle:
                father = database.get_person_from_handle(father_handle)
                fathername = name_displayer.display(father)
#                 self.append_text("Father: %s" % fathername)
                self.addDescendants(father_handle)
            mother_handle = family.get_mother_handle()
            # Add all descendants of the mother
            if mother_handle:
                mother = database.get_person_from_handle(mother_handle)
                mothername = name_displayer.display(mother)
#                 self.append_text(" Mother: %s" % mothername)
                self.addDescendants(mother_handle)
#             self.append_text("\n")
            # List of descendants for this family is complete
#             self.append_text(" %d Persons in tree\n" % len(self.person_handle_list))
            # Check every person in the tree for partner that is part of this tree
            for checkHandle in self.person_handle_list:
                person = database.get_person_from_handle(checkHandle)
                if person:
                    pname = name_displayer.display(person)
#                     self.append_text("\n Check person %s \n" % pname)
                    pfamily_handle_list = person.get_family_handle_list()
                    if pfamily_handle_list:
                        for family_handle in pfamily_handle_list:
                            if family_handle in family_handle_list:
#                                 self.append_text("  Skipped own family\n")
                                continue
                            family = database.get_family_from_handle(family_handle)
                            father_handle = family.get_father_handle()
                            mother_handle = family.get_mother_handle()
                            if checkHandle == father_handle:
                                handlepartner = mother_handle
                            else:
                                handlepartner = father_handle
                            if handlepartner in self.person_handle_list:
                                newEntry = True;
#                                 self.append_text("\n*M*A*T*C*H*\n")
                                for ii in range(len(pair_p1_list)):
                                    if checkHandle == pair_p1_list[ii]:
                                        if  handlepartner == pair_p2_list[ii]:
                                            newEntry = False
                                    if checkHandle == pair_p2_list[ii]:
                                        if handlepartner == pair_p1_list[ii]:
                                            newEntry = False
                                if newEntry:
                                    pair_p1_list.append(checkHandle)
                                    pair_p2_list.append(handlepartner)
                                    partner = self.dbstate.db.get_person_from_handle(handlepartner)
                                    p1name = name_displayer.display(person)
#                                     self.append_text("\n\n %s " % p1name)
                                    self.append_text("\n\n")
                                    self.link(p1name, 'Person', checkHandle)
                                    p2name = name_displayer.display(partner)
#                                     self.append_text(" und %s " % p2name)
                                    self.append_text(" & ")
                                    self.link(p2name, 'Person', handlepartner)
                                    self.append_text(":")
                                    rel_strings, common_an = rel_calc.get_all_relationships(database, person, partner)
                                    rel_strings1, common_an = rel_calc.get_all_relationships(database, partner, person)
                                    if rel_strings:
                                        for relstring in rel_strings:
                                            for relstring1 in rel_strings1:
                                                self.append_text("\n%s" % relstring)
                                                self.append_text(" & %s" % relstring1)
                        yield True
        if len(pair_p1_list) == 0:
            self.append_text("\nNo relatives in a relation found.\n")
        self.append_text("\n\nEND\n")
        yield False
