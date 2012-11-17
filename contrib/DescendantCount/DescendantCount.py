# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009  Douglas S. Blank <doug.blank@gmail.com>
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

# $Id$

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.plug import Gramplet
from gramps.gen.utils.trans import get_addon_translator
_ = get_addon_translator().ugettext
from gramps.gui.plug.quick import QuickTable, run_quick_report_by_name
from gramps.gen.simple import SimpleAccess, SimpleDoc

cache = {}

#------------------------------------------------------------------------
#
# Gramplet class
#
#------------------------------------------------------------------------
class DescendantCountGramplet(Gramplet):
    def main(self):
        run_quick_report_by_name(self.gui.dbstate, 
                                 self.gui.uistate, 
                                 "Descendant Count Quickview",
                                 "None", # dummy handle value
                                 container=self.gui.textview)

#------------------------------------------------------------------------
#
# Functions
#
#------------------------------------------------------------------------
def countem(db, person_handle, count):
    global cache
    if person_handle not in cache:
        total = count
        person = db.get_person_from_handle(person_handle)
        for fam_handle in person.get_family_handle_list():
            fam = db.get_family_from_handle(fam_handle)
            for child_ref in fam.get_child_ref_list():
                total += countem(db, child_ref.ref, 1)
        cache[person_handle] = total
    else:
        total = cache[person_handle]
    return total

def run(database, document, person):
    """
    Loops through the families that the person is a child in, and display
    the information about the other children.
    """
    global cache
    cache = {}
    # setup the simple access functions
    sdb = SimpleAccess(database)
    sdoc = SimpleDoc(document)
    stab = QuickTable(sdb)
    # display the title
    sdoc.title(_("Descendent Count"))
    sdoc.paragraph("")
    stab.columns(_("Person"), _("Number of Descendants"))
    people = database.get_person_handles(sort_handles=False)
    for person_handle in people:
        countem(database, person_handle, 1)
    matches = 0
    for person_handle in cache:
        person = database.get_person_from_handle(person_handle)
        stab.row(person, cache[person_handle] - 1) # remove self
        matches += 1
    sdoc.paragraph(_("There are %d people.\n") % matches)
    stab.write(sdoc)
                    
