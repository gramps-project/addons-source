#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009-2015 Nick Hall
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
Form definitions.
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
from gramps.gen.config import config

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation

_ = _trans.gettext

#------------------------------------------------------------------------
#
# Form definitions
#
#------------------------------------------------------------------------

# The attribute used to store the order of people on the form.
ORDER_ATTR = _('Order')

# The key of the data item in a source to define it as a form source.
DEFINITION_KEY = _('Form')

# Prefixes for family attributes.
GROOM = _('Groom')
BRIDE = _('Bride')

# Files which may contain form definitions
definition_files = ['form_be.xml', 'form_ca.xml', 'form_dk.xml', 'form_fr.xml',
                    'form_gb.xml', 'form_pl.xml', 'form_us.xml',
                    'test.xml', 'custom.xml']

#------------------------------------------------------------------------
#
# Configuration file
#
#------------------------------------------------------------------------
CONFIG = config.register_manager('form')
CONFIG.register('interface.form-width', 600)
CONFIG.register('interface.form-height', 400)
CONFIG.register('interface.form-horiz-position', -1)
CONFIG.register('interface.form-vert-position', -1)

CONFIG.init()

#------------------------------------------------------------------------
#
# From class
#
#------------------------------------------------------------------------
class Form():
    """
    A class to read form definitions from an XML file.
    """
    def __init__(self):
        self.__dates = {}
        self.__headings = {}
        self.__sections = {}
        self.__columns = {}
        self.__types = {}
        self.__titles = {}
        self.__names = {}
        self.__section_types = {}

        for file_name in definition_files:
            full_path = os.path.join(os.path.dirname(__file__), file_name)
            if os.path.exists(full_path):
                self.__load_definitions(full_path)

    def __load_definitions(self, definition_file):
        dom = xml.dom.minidom.parse(definition_file)
        top = dom.getElementsByTagName('forms')

        for form in top[0].getElementsByTagName('form'):
            id = form.attributes['id'].value
            self.__names[id] = form.attributes['title'].value
            self.__types[id] = form.attributes['type'].value
            if 'date' in form.attributes:
                self.__dates[id] = form.attributes['date'].value
            else:
                self.__dates[id] = None

            headings = form.getElementsByTagName('heading')
            self.__headings[id] = []
            for heading in headings:
                attr = heading.getElementsByTagName('_attribute')
                attr_text = _(attr[0].childNodes[0].data)
                self.__headings[id].append(attr_text)

            sections = form.getElementsByTagName('section')
            self.__sections[id] = []
            self.__columns[id] = {}
            self.__titles[id] = {}
            self.__section_types[id] = {}
            for section in sections:
                if 'title' in section.attributes:
                    title = section.attributes['title'].value
                else:
                    title = ''
                role = section.attributes['role'].value
                section_type = section.attributes['type'].value
                self.__sections[id].append(role)
                self.__titles[id][role] = title
                self.__section_types[id][role] = section_type
                self.__columns[id][role] = []
                columns = section.getElementsByTagName('column')
                for column in columns:
                    attr = column.getElementsByTagName('_attribute')
                    size = column.getElementsByTagName('size')
                    longname = column.getElementsByTagName('_longname')
                    attr_text = _(attr[0].childNodes[0].data)
                    if size:
                        size_text = size[0].childNodes[0].data
                    else:
                        size_text = '0'
                    if longname:
                        long_text = _(longname[0].childNodes[0].data)
                    else:
                        long_text = attr_text
                    self.__columns[id][role].append((attr_text,
                                                     long_text,
                                                     int(size_text)))
        dom.unlink()

    def get_form_ids(self):
        """ Return a list of ids for all form definitions. """
        return self.__dates.keys()

    def get_title(self, form_id):
        """ Return the title for a given form. """
        return self.__names[form_id]

    def get_date(self, form_id):
        """ Return a textual date for a given form. """
        return self.__dates[form_id]

    def get_type(self, form_id):
        """ Return a textual event type for a given form. """
        return self.__types[form_id]

    def get_headings(self, form_id):
        """ Return a list of headings for a given form. """
        return self.__headings[form_id]

    def get_sections(self, form_id):
        """ Return a list of sections for a given form. """
        return self.__sections[form_id]

    def get_section_title(self, form_id, section):
        """ Return the title for a given section. """
        return self.__titles[form_id][section]

    def get_section_type(self, form_id, section):
        """ Return the section type for a given section. """
        return self.__section_types[form_id][section]

    def get_section_columns(self, form_id, section):
        """ Return a list of column definitions for a given section. """
        return self.__columns[form_id][section]

#------------------------------------------------------------------------
#
# Helper functions
#
#------------------------------------------------------------------------
FORM = Form()

def get_form_ids():
    """
    Return a list of ids for all form definitions.
    """
    return FORM.get_form_ids()

def get_form_title(form_id):
    """
    Return the title for a given form.
    """
    return FORM.get_title(form_id)

def get_form_date(form_id):
    """
    Return the date for a given form.
    """
    date_str = FORM.get_date(form_id)
    if date_str:
        return parser.parse(date_str)
    else:
        return None

def get_form_type(form_id):
    """
    Return the type for a given form.
    """
    return FORM.get_type(form_id)

def get_form_headings(form_id):
    """
    Return a list of headings for a given form.
    """
    return FORM.get_headings(form_id)

def get_form_sections(form_id):
    """
    Return a list of sections for a given form.
    """
    return FORM.get_sections(form_id)

def get_section_title(form_id, section):
    """
    Return the title for a given section.
    """
    return FORM.get_section_title(form_id, section)

def get_section_type(form_id, section):
    """
    Return the type for a given section.
    """
    return FORM.get_section_type(form_id, section)

def get_section_columns(form_id, section):
    """
    Return a list of column definitions for a given section.
    """
    return FORM.get_section_columns(form_id, section)

def get_form_id(source):
    """
    Return the form id attached to the given source.
    """
    for attr in source.get_attribute_list():
        if str(attr.get_type()) == DEFINITION_KEY:
            return attr.get_value()
    return None

def get_form_citation(db, event):
    """
    Return the citation for this form event.  If there is more
    than one form source for this event then the first is returned.
    """
    for citation_handle in event.get_citation_list():
        citation = db.get_citation_from_handle(citation_handle)
        source_handle = citation.get_reference_handle()
        source = db.get_source_from_handle(source_handle)
        form_id = get_form_id(source)
        if (form_id in get_form_ids() and
                event.get_type().xml_str() == get_form_type(form_id)):
            return citation
    return None

def get_form_sources(db):
    """
    Return a list of form sources.  Each item in the list is a list
    comtaining a source handle, source title and a form id.
    """
    source_list = []
    for handle in db.get_source_handles():
        source = db.get_source_from_handle(handle)
        form_id = get_form_id(source)
        if form_id in get_form_ids():
            source_list.append([handle, source.get_title(), form_id])

    sorted_list = sorted(source_list, key=lambda s: s[1])
    return sorted_list
