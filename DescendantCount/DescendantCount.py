# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009  Douglas S. Blank <doug.blank@gmail.com>
# Copyright (C) 2016  Serge Noiraud <serge.noiraud@free.fr>
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

import sys

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.plug import Gramplet
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
from gramps.gui.plug.quick import QuickTable, run_quick_report_by_name
from gramps.gen.simple import SimpleAccess, SimpleDoc
from gramps.gen.constfunc import handle2internal

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

    def db_changed(self):
        self.dbstate.db.connect('person-add', self.update)
        self.dbstate.db.connect('person-delete', self.update)

    def active_changed(self, handle):
        self.update()

#------------------------------------------------------------------------
#
# Functions
#
#------------------------------------------------------------------------
def countem(db, person_handle):
    local_list = []
    person = db.get_person_from_handle(person_handle)
    for fam_handle in person.get_family_handle_list():
        fam = db.get_family_from_handle(fam_handle)
        for child_ref in fam.get_child_ref_list():
            if child_ref.ref not in local_list:
                local_list.append(child_ref.ref)
            new_list = countem(db, child_ref.ref)
            for elem in new_list:
                if elem not in local_list:
                    local_list.append(elem)
    return local_list

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
    sdoc.title(_("Descendant Count"))
    sdoc.paragraph("")
    stab.columns(_("Person"), _("Number of Descendants"))
    people = database.get_person_handles(sort_handles=True)
    for person_handle in people:
        result = countem(database, handle2internal(person_handle))
        cache[person_handle] = len(result)
    matches = 0
    for person_handle in cache:
        person = database.get_person_from_handle(person_handle)
        stab.row(person, cache[person_handle])
        matches += 1
    sdoc.paragraph(_("There are %d people.\n") % matches)
    stab.write(sdoc)
                    
