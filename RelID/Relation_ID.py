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
        count = 0
        default_person = self.dbstate.db.get_default_person()
        #home = name_displayer.display(default_person)
        plist = self.dbstate.db.get_person_handles(sort_handles=True)
        #default_str = "Default:" + str(home) + "\n"
        #self.set_text(default_str)
        
        #now determine the relation
        relationship = get_relationship_calculator()
        relationship.connect_db_signals(self.dbstate)
        
        for handle in plist:
            person = self.dbstate.db.get_person_from_handle(handle)
            name = name_displayer.display(person)
            if person:
                #rank, handle person,rel_str_orig,rel_fam_orig,rel_str_other,rel_fam_str
                dist = relationship.get_relationship_distance_new(
                      self.dbstate.db, default_person, person, only_birth=True)
                rel_a = dist[0][2]
                Ga = len(rel_a)
                rel_b = dist[0][4]
                Gb = len(rel_b)
                yield True
                #kekule = ID._get(person, default_person, 'rel', Ga, Gb, rel_a, rel_b)
                kekule = number.get_number(Ga, Gb, rel_a, rel_b)
                value = name
                value = value + " -----> " + kekule
                count += 1
                # title, handletype, handle
                self.link(str(value) , 'Person', handle)
                self.append_text("\n")
                self.append_text("", scroll_to='begin')
            if count == 25:
                yield False
