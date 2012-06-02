# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2011  Heinz Brinker
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
from TransUtils import get_addon_translator
_ = get_addon_translator().gettext
from Utils import media_path_full
import Relationship
import gen.datehandler
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

#
# Register database triggers for updates
#
    def db_changed(self):
        self.dbstate.db.connect('person-add', self.update)
        self.dbstate.db.connect('person-delete', self.update)
        self.dbstate.db.connect('family-add', self.update)
        self.dbstate.db.connect('family-delete', self.update)
        self.dbstate.db.connect('person-rebuild', self.update)
        self.dbstate.db.connect('family-rebuild', self.update)

#
#   Function that recursively adds all descendants of a person to the
#   person_handle_list
#
    def addDescendants(self, ancestorHandle):
        # If this person is not yet in the list, add person (and its descendants
        # to descendants list.
        if ancestorHandle not in self.person_handle_list:
            self.person_handle_list.append(ancestorHandle)
#           Check if person is father or mother in a family
            ancestor = self.dbstate.db.get_person_from_handle(ancestorHandle)
            if ancestor:
                for family_handle in ancestor.get_family_handle_list():
                    if family_handle:
                        family = self.dbstate.db.get_family_from_handle(family_handle)
                        if family:
#                           Add all children of the person  to the list by
#                           recursively calling this function for each one.
                            childlist = family.get_child_ref_list()[:]
                            for child_ref in childlist:
                                self.addDescendants(child_ref.ref)

#
#   Main function, called when the gramplet is opened or updated
#
    def main(self):
        # Write heading text to gramplet
        self.set_text(_("Relations of related people in your database:"))
        # Define basic variables
        database = self.dbstate.db
        rel_calc = Relationship.get_relationship_calculator()
        family_handle_list = [] # Will keep list of families with no ancestors

        # Find all base families with no ancestors in the database.
        flist = database.iter_family_handles()
        for familyhandle in flist:
            family = database.get_family_from_handle(familyhandle)
            # Check if mother of this family is child of another family
            # If this is the case, skip this family
            ancestorHandle = family.get_mother_handle()
            if ancestorHandle:
                mother = database.get_person_from_handle(ancestorHandle)
                parent_handle_list = mother.get_parent_family_handle_list()
                if parent_handle_list:
                    continue
            # Check if father of this family is child of another family
            # If this is the case, skip this family
            ancestorHandle = family.get_father_handle()
            if ancestorHandle:
                father = database.get_person_from_handle(ancestorHandle)
                parent_handle_list = father.get_parent_family_handle_list()
                if parent_handle_list:
                  continue
            # Members of this family have no ancestors. Add family to base
            # family handle list
            family_handle_list.append(familyhandle)
            yield True

        # The base family handle list now contains all families that have
        # no ancestors. Now iterate through found families. For each family
        # first find all descendants and then check if one person in this
        # family tree is partner of another person in the same tree.
        #
        # Related relatives may be found more than once from different base
        # families. Therefore we hold a list of all found pairs to avoid
        # listing them more than once
        pair_p1_list = [] # List of all 1st related partners for all families
        pair_p2_list = [] # List of all 2nd related partners for all families
        for familyhandle in family_handle_list:
            # Build list of all related persons (descendants) of this family.
            self.person_handle_list = []
            family = database.get_family_from_handle(familyhandle)
            # Add all descendants of the father to person list of this family
            father_handle = family.get_father_handle()
            if father_handle:
                father = database.get_person_from_handle(father_handle)
                # Add all descendants of the father
                self.addDescendants(father_handle)
            mother_handle = family.get_mother_handle()
            # Add all descendants of the mother to person list of this family
            if mother_handle:
                mother = database.get_person_from_handle(mother_handle)
                # Add all descendants of the mother
                self.addDescendants(mother_handle)

            # The person list of all descendants for this family is complete.
            # Now check for every person in the list if it has a partner that
            # is also in this list
            for checkHandle in self.person_handle_list:
                person = database.get_person_from_handle(checkHandle)
                if person:
                    pfamily_handle_list = person.get_family_handle_list()
                    if pfamily_handle_list:
                        for family_handle in pfamily_handle_list:
                            # Skip the family if it is listed in the base
                            # families list (which should be quite short).
                            if family_handle in family_handle_list:
                                continue

                            # If current person is father or mother in a family
                            # find the handle of the partner
                            family = database.get_family_from_handle(family_handle)
                            father_handle = family.get_father_handle()
                            mother_handle = family.get_mother_handle()
                            if checkHandle == father_handle:
                                handlepartner = mother_handle
                            else:
                                handlepartner = father_handle

                            # If the partner is in our list of persons of this
                            # family tree, both are related.
                            if handlepartner in self.person_handle_list:
                                newEntry = True;
                                # Check if this pair is already in the lists of
                                # related partners. A and B will also appear as
                                # B and A. So we have to cross check
                                for ii in range(len(pair_p1_list)):
                                    if checkHandle == pair_p1_list[ii]:
                                        if  handlepartner == pair_p2_list[ii]:
                                            newEntry = False
                                    if checkHandle == pair_p2_list[ii]:
                                        if handlepartner == pair_p1_list[ii]:
                                            newEntry = False

                                # If this pair is not yet listed, add them to
                                # the list and show their relationship in the
                                # gramplet window.
                                if newEntry:
                                    # Add pair to list of found related relatives
                                    pair_p1_list.append(checkHandle)
                                    pair_p2_list.append(handlepartner)
                                    partner = self.dbstate.db. \
                                        get_person_from_handle(handlepartner)
                                    # Find relation between the partners by use
                                    # of the relationship calculator. Print all
                                    # relationships A to B and B to A.
                                    rel_strings, common_an = \
                                        rel_calc.get_all_relationships(database,
                                                                       person,
                                                                       partner)
                                    rel_strings1, common_an1 = \
                                        rel_calc.get_all_relationships(database,
                                                                       partner,
                                                                       person)
                                    if len(rel_strings) > 1:
                                        # Output names of both partners as links
                                        p1name = name_displayer.display(person)
                                        self.append_text("\n\n")
                                        self.link(p1name, 'Person', checkHandle)
                                        p2name = name_displayer.display(partner)
                                        self.append_text(" " + _("and") + " ")
                                        self.link(p2name, 'Person', handlepartner)
                                        self.append_text(" " + \
                                                         _("are partners and") + \
                                                         ":")
                                        # Omit the first relationship from list
                                        for x in range(1, len(rel_strings)):
                                            self.append_text("\n%s" %
                                                             rel_strings[x])
                                            try:
                                                self.append_text(" & %s" %
                                                                 rel_strings1[x])
                                            except:
                                                continue
                                            # Print list of common ancestors for
                                            # the found relation.
                                            # Remove duplicate ancestors
                                            anc_list = list(set(common_an[x]))
                                            for anc in anc_list:
                                                person = database. \
                                                    get_person_from_handle(anc)
                                                if person:
                                                    # Print ancestor as link
                                                    pname = name_displayer. \
                                                        display(person)
                                                    self.append_text("\n\t" \
                                                        + _("Common ancestor") \
                                                        + " ")
                                                    self.link(pname, 'Person',
                                                              anc)

                        # After the check for each persons family allow other
                        # threads to do some work.
                        yield True
        # If the list of related pairs is empty we did not find any related
        # relatives in the database.
        if len(pair_p1_list) == 0:
            self.append_text("\n" + _("No relatives in a relation found") + ".\n")
        self.append_text("\n\n" + _("END") + "\n")
        return
