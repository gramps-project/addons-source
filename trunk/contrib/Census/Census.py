#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009 Nick Hall
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

"""
Census add-on definitions.
"""
#---------------------------------------------------------------
#
# Python imports
#
#---------------------------------------------------------------
import os
import xml.dom.minidom

#---------------------------------------------------------------
#
# Gramps imports
#
#---------------------------------------------------------------
from gramps.gen.datehandler import parser

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.get_addon_translator(__file__).gettext

#------------------------------------------------------------------------
#
# Census definitions
#
#------------------------------------------------------------------------

# The attribute used to store the order of people on the census.
ORDER_ATTR = _('Order')

# The key of the data item in a source to define it as a census source.
CENSUS_TAG = _('Census')

# Files which may contain census definitions
definition_files = ['census.xml', 'test.xml', 'custom.xml']

#------------------------------------------------------------------------
#
# Census class
#
#------------------------------------------------------------------------
class Census():
    """
    A class to read census definitions from an XML file.
    """
    def __init__(self):
        self.__dates = {}
        self.__headings = {}
        self.__columns = {}

        for file_name in definition_files:
            census_file = os.path.join(os.path.dirname(__file__), file_name)
            if os.path.exists(census_file):
                self.__load_definitions(census_file)

    def __load_definitions(self, census_file):
        dom = xml.dom.minidom.parse(census_file)
        top = dom.getElementsByTagName('censuses')

        for census in top[0].getElementsByTagName('census'):
            id = census.attributes['id'].value
            self.__dates[id] = census.attributes['date'].value

            headings = census.getElementsByTagName('heading')
            self.__headings[id] = []
            for heading in headings:
                attr = heading.getElementsByTagName('_attribute')
                attr_text = _(attr[0].childNodes[0].data)
                self.__headings[id].append(attr_text)

            columns = census.getElementsByTagName('column')
            self.__columns[id] = []
            for column in columns:
                attr = column.getElementsByTagName('_attribute')
                size = column.getElementsByTagName('size')
                longname = column.getElementsByTagName('_longname')
                attr_text = _(attr[0].childNodes[0].data)
                size_text = size[0].childNodes[0].data
                if longname:
                    long_text = _(longname[0].childNodes[0].data)
                else:
                    long_text = attr_text
                self.__columns[id].append((attr_text,
                                           long_text,
                                           int(size_text)))
        dom.unlink()

    def get_census_ids(self):
        """ Return a list of census ids for all census definitions. """
        return self.__dates.keys()
        
    def get_date(self, census_id):
        """ Return a textual census date for a given census id. """
        return self.__dates[census_id]
        
    def get_columns(self, census_id):
        """ Return a list of column definitions for a given census id. """
        return self.__columns[census_id]
        
    def get_headings(self, census_id):
        """ Return a list of heading definitions for a given census id. """
        return self.__headings[census_id]

#------------------------------------------------------------------------
#
# Helper functions
#
#------------------------------------------------------------------------
CENSUS = Census()

def get_census_ids():
    """
    Return a list of ids for all census definitions.
    """
    return CENSUS.get_census_ids()

def get_census_date(census_id):
    """
    Return the date for a given census.
    """
    return parser.parse(CENSUS.get_date(census_id))
        
def get_census_columns(census_id):
    """
    Return a list of columns for a given census.
    """
    return [x[0] for x in CENSUS.get_columns(census_id)]
    
def get_report_columns(census_id):
    """
    Return a list of column definitions for a given census.  These will be used
    to construct the census report.  Each entry is a tuple containing the
    name and size of the column.
    """
    return [(x[1], x[2]) for x in CENSUS.get_columns(census_id)]

def get_census_id(source):
    """
    Return the census id attach to the given source.
    """
    return source.get_data_map().get(CENSUS_TAG)
            
def get_census_citation(db, event):
    """
    Return the citation for this census event.  If there is more
    than one census source for this event then the first is returned.
    """
    for citation_handle in event.get_citation_list():
        citation = db.get_citation_from_handle(citation_handle)
        source_handle = citation.get_reference_handle()
        source = db.get_source_from_handle(source_handle)
        census_id = get_census_id(source)
        if census_id in get_census_ids():
            return citation
    return None
        
def get_census_sources(db):
    """
    Return a list of census sources.  Each item in the list is a list
    comtaining a source handle, source title and a census id.
    """
    source_list = []
    for handle in db.get_source_handles():
        source = db.get_source_from_handle(handle)
        census_id = get_census_id(source)
        if census_id in get_census_ids():
            source_list.append([handle, source.get_title(), census_id])

    sorted_list = sorted(source_list, key=lambda s: s[1])
    return sorted_list
