"""Merge via the command line"""
#
# CliMerge - Merge primary objects from the command line
#
# Copyright (C) 2011      Michiel D. Nauta
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
# $Id$
#

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
import gramps.gen.lib
from gramps.gen.errors import MergeError
from gramps.gui.plug import tool

#------------------------------------------------------------------------
#
# CliMerge class
#
#------------------------------------------------------------------------
class CliMerge(tool.Tool):
    def __init__(self, dbstate, uistate, options_class, name, callback=None):
        tool.Tool.__init__(self, dbstate, options_class, name)
        self.dbstate = dbstate
        self.run_tool()

    def run_tool(self):
        obj_type = self.options.handler.options_dict['type']
        primary_id = self.options.handler.options_dict['primary']
        secondary_id = self.options.handler.options_dict['secondary']
        if not primary_id or not secondary_id:
            raise MergeError("Both primary and secondary object IDs need to "
                "be specified.")

        if not obj_type:
            id2type = {'I':'Person', 'F':'Family', 'E':'Event', 'P': 'Place',
                       'C': 'Citation', 'S':'Source', 'R':'Repository', 
                       'O':'Media', 'N':'Note'}
            obj_type = id2type[primary_id[0]]

        database = self.dbstate.db
        primary = database.get_from_name_and_gramps_id(obj_type, primary_id)
        secondary = database.get_from_name_and_gramps_id(obj_type, secondary_id)
        if not primary or not secondary:
            raise MergeError("Can't get object from ID.")
        
        if type(primary) != type(secondary):
            raise MergeError("Primary and secondary object need to be of "
                "the same type.")


        if obj_type == 'Person':
            from gramps.gen.merge import MergePersonQuery
            query = MergePersonQuery(database, primary, secondary)
        elif obj_type == 'Family':
            # TODO make sure father_handle is in phoenix or titanic
            father_handle = self.options.handler.options_dict['father_h']
            mother_handle = self.options.handler.options_dict['mother_h']
            from gramps.gen.merge import MergeFamilyQuery
            query = MergeFamilyQuery(database, primary, secondary,
                                     father_handle, mother_handle)
        elif obj_type == 'Event':
            from gramps.gen.merge import MergeEventQuery
            query = MergeEventQuery(self.dbstate, primary, secondary)
        elif obj_type == 'Place':
            from gramps.gen.merge import MergePlaceQuery
            query = MergePlaceQuery(self.dbstate, primary, secondary)
        elif obj_type == 'Citation':
            from gramps.gen.merge import MergeCitationQuery
            query = MergeCitationQuery(self.dbstate, primary, secondary)
        elif obj_type == 'Source':
            from gramps.gen.merge import MergeSourceQuery
            query = MergeSourceQuery(self.dbstate, primary, secondary)
        elif obj_type == 'Repository':
            from gramps.gen.merge import MergeRepositoryQuery
            query = MergeRepositoryQuery(self.dbstate, primary, secondary)
        elif obj_type == 'Media':
            from gramps.gen.merge import MergeMediaQuery
            query = MergeMediaQuery(self.dbstate, primary, secondary)
        elif obj_type == 'Note':
            from gramps.gen.merge import MergeNoteQuery
            query = MergeNoteQuery(self.dbstate, primary, secondary)
        else:
            raise MergeError(("Merge for %s not implemented.") % \
                    str(type(primary)))

        query.execute()

#------------------------------------------------------------------------
#
# CliMergeOptions class
#
#------------------------------------------------------------------------
class CliMergeOptions(tool.ToolOptions):
    """
    Defines options.
    """
    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)

        self.options_dict = {
                'primary'   : '',
                'secondary'   : '',
                'type'      : '',
                'father_h'  : '',
                'mother_h'  : '',
                }
        self.options_help = {
                'primary'   : ("=str", "ID of the object that will "
                               "receive data form the secondary object.", "ID"),
                'secondary' : ("=str", "ID of the object that is merged "
                               "into the primary object.", "ID"),
                'type'      : ("=str", "type of objects to merge", "Person"),
                'father_h'  : ("=str", "Database handle of the father that will"
                               "survive the family merger.", "handle"),
                'mother_h'  : ("=str", "Database handle of the mother that will"
                               "survive the family merger.", "handle"),
                }
