#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020-       Gary Griffin
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
#

"""Sync Associations"""

#------------------------------------------------------------------------
#
# GNOME/GTK modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import GObject

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------

from gramps.gui.plug import tool
from gramps.gen.display.name import displayer as _nd
from gramps.gui.managedwindow import ManagedWindow
from gramps.gen.db import DbTxn
from gramps.gen.lib import PersonRef
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.sgettext

#-------------------------------------------------------------------------
#
# Constants
#
#-------------------------------------------------------------------------
ASSOC_LOOKUP = {
"cM": "cM",
"DNA": "DNA",
"Godfather": "Godchild",
"Godmother": "Godchild",
"Landlord": "Tenant"
}

#------------------------------------------------------------------------
#
# syncAssociations class
#
#------------------------------------------------------------------------
class syncAssociations(ManagedWindow):
    """
    Sync Associations by adding an Association for the person mentioned in another Association.
    """
    def __init__(self, dbstate, user, options_class, name, callback=None):
        self.dbstate = dbstate
        self.db = dbstate.db
        for person_handle in self.db.get_person_handles():
            person = self.db.get_person_from_handle(person_handle)
            for assoc in person.get_person_ref_list():
                oldRel = assoc.get_relation()
                if oldRel in ASSOC_LOOKUP:
                    associate = self.db.get_person_from_handle(assoc.ref)
                    update = True
                    for assoc_rev in associate.get_person_ref_list():
                        if assoc_rev.get_relation() == ASSOC_LOOKUP.get(assoc.get_relation()) and assoc_rev.ref == person_handle :
                            update = False
                    if update:
                        newRel = ASSOC_LOOKUP.get(assoc.get_relation())
                        personRef = PersonRef()
                        personRef.set_reference_handle(person_handle)
                        personRef.set_relation(newRel)
                        personRef.merge(assoc)
                        with DbTxn (_('Add %s reciprocal association' ) % _nd.display(associate), self.db) as self.trans:
                            associate.add_person_ref(personRef)
                            self.db.commit_person(associate, self.trans)

    def main(self):
        pass

#------------------------------------------------------------------------
#
# RemoveSpacesOptions
#
#------------------------------------------------------------------------
class syncAssociationsOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """
    def __init__(self, name, person_id=None):
        """ Initialize the options class """
        tool.ToolOptions.__init__(self, name, person_id)

