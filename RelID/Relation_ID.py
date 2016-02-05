#
# Gramps - a GTK+/GNOME based genealogy program
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

"""
Display person objects
"""

#-------------------------------------------------------------------------
#
# gramps modules
#
#-------------------------------------------------------------------------

from gramps.gen.lib import Person
from gen.display.name import displayer as name_displayer
from gen.plug import Gramplet
from gramps.gen.relationship import get_relationship_calculator
import number

#------------------------------------------------------------------------
#
# The Gramplet
#
#------------------------------------------------------------------------
class IDGramplet(Gramplet):

    def init(self):
        self.set_use_markup(True)
        self.set_tooltip("Double-click on object for details")
        self.set_text("No Family Tree loaded.")

    def db_changed(self):
        self.dbstate.db.connect('person-rebuild', self.update)

    def main(self):
        self.set_text("Processing..." + "\n")
        yield True
        self.set_text("Person objects" + "\n")

        ancestors = {}
        count = 0
        default_person = self.dbstate.db.get_default_person()
        plist = self.dbstate.db.get_person_handles(sort_handles=True)
        total = len(plist)

        if default_person:
            home = name_displayer.display(default_person)
            count += 1
            root_str = str(home) + "\n"
            self.set_text(root_str)
        
        #now determine the relation
        relationship = get_relationship_calculator()
        relationship.connect_db_signals(self.dbstate)
        
        for handle in plist:

            person = self.dbstate.db.get_person_from_handle(handle)
            name = name_displayer.display(person)
            #if person and person != default_person and person.gender == Person.FEMALE:
            if person and person != default_person:
                #self.set_text("%s/%s\n" % (count + 1, total))
                #rank, handle person, rel_str_orig, rel_fam_orig, rel_str_other, rel_fam_str
                dist = relationship.get_relationship_distance_new(
                      self.dbstate.db, default_person, person, only_birth=True)
                rel_a = dist[0][2]
                Ga = len(rel_a)
                rel_b = dist[0][4]
                Gb = len(rel_b)
                mra = 1
                rank = dist[0][0]

                if rank == -1: # not related people
                    continue

                for letter in rel_a:
                    if letter == 'f':
                        mra = mra * 2
                    if letter == 'm':
                        mra = mra * 2 + 1
                yield True
                kekule = number.get_number(Ga, Gb, rel_a, rel_b)
                value = name

                mothers = []
                mothers.append((kekule, value, Ga))

                n = 3 # starting key (mother value on sosa/kekule)
                max_level = 6 # number of generations
                # sequence = from n to wall

                ancestors[kekule] = handle

                for (key, value, level) in mothers:
                    if key != "0" and (rank / 2) <= max_level:
                        if rank == 2 and Ga == 1: # same relations
                            self.append_text("\nSibling: %s" % value)
                            continue
                        for i in range(1, max_level):
                            if level == i:
                                gen = Ga * "_"
                                down = Gb * "\t"
                                self.append_text("\n")
                                self.link(down + key + ". " + gen + str(value), 'Person', handle)
                    if key == "0" and Ga <= max_level: # cousin(e)s
                        gen = Ga * "|"
                        down = Gb * "\t"
                        self.append_text("\n%s%s" % (down, gen))
                        self.link(str(value) + str(Ga) , 'Person', handle)
                        if str(mra) in ancestors:
                            self.append_text(" via: ")
                            self.link(str(mra) , 'Person', ancestors.get(str(mra)))
                        else:
                            self.append_text(" via %s." % mra)
                if kekule.startswith('0.') or kekule == '1': # 1: related to root mother
                    self.append_text("\n")
                    value = "%s. %s on level[%s]" % (value, kekule, Gb)
                    self.link(str(value) , 'Person', handle)
                    if str(mra) in ancestors:
                        self.append_text(" via: ")
                        self.link(str(mra) , 'Person', ancestors.get(str(mra)))
                    else:
                        self.append_text(" via %s." % mra)
                    #yield False
                count += 1
                ## title, handletype, handle
                #self.link(str(value) , 'Person', handle)
                self.append_text("", scroll_to='begin')
                if count == int(total/max_level):
                    #self.set_text("Too large database for such test")
                    yield False
