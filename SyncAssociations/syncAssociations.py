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
from gramps.gui.dialog import OkDialog
# -------------------------------------------------------------------------
# Internationalization
# -------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

#-------------------------------------------------------------------------
#
# Constants
#
#-------------------------------------------------------------------------
ASSOC_LOOKUP = {
"DNA": "DNA",
"Godparent": "Godchild",
"Godchild": "Godparent",
"Godson": "Godparent",
"Goddaughter": "Godparent",
"Godfather": "Godchild",
"Godmother": "Godchild",
"Namesake": "Eponym",
"Eponym": "Namesake",
"Slave Holder": "Enslaved",
"Enslaved": "Slave Holder",
"Bond Holder": "Indentured",
"Master": "Apprentice",
"Apprentice": "Master",
"Employer": "Employee",
"Employee": "Employer",
"Guardian": "Ward",
"Ward": "Guardian",
"Namesake": "Named After",
"Named After": "Namesake",
"Pallbearer": "Pallbearer for",
"Pallbearer for": "Pallbearer",
"Owned Slave": "Enslaved by",
"Enslaved by": "Owned Slave",
"Indentured Servant": "Bond Holder",
"Bond Holder": "Indentured Servant",
"Apprentice": "Apprenticed to",
"Apprenticed to": "Apprentice",
"Landlord": "Tenant",
"Tenant": "Landlord"
}
WIKI_HELP_PAGE = 'https://gramps-project.org/wiki/index.php/Addon:SyncAssociation'

#------------------------------------------------------------------------
#
# syncAssociations class
#
#------------------------------------------------------------------------
class syncAssociations(tool.BatchTool):
    """
    Sync Associations by adding an Association for the person mentioned in another Association.
    """
    def __init__(self, dbstate, user, options_class, name, callback=None):
        uistate = user.uistate
# Add Batch Tool check
        self._user = user
        tool.BatchTool.__init__(self, dbstate, user, options_class, name)
        if self.fail:
            return
# End Batch Tool check
        self.dbstate = dbstate
        self.db = dbstate.db
        count = 0
        has_assoc = False
        for person_handle in self.db.get_person_handles():
            person = self.db.get_person_from_handle(person_handle)
            for assoc in person.get_person_ref_list():
                has_assoc = True
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
                        count += 1
        if uistate:
            if count > 0:
                OkDialog(_("Sync Associations"),
                         _("{} Reciprocal associations created".format(count)),
                         parent = uistate.window)
            elif has_assoc:
                OkDialog(_("Sync Associations"),
                         _("All reciprocal associations exist, none created"),
                         parent = uistate.window)
            else:
                OkDialog(_("Sync Associations"),
                         _("No existing associations, so no reciprocal ones needed"),
                         parent = uistate.window)
        else:
            print("{} Reciprocal associations created".format(count))
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
