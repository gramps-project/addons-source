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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
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


### DB$: 08/05/2020 ########################################################################################
from gramps.gui.dialog import ErrorDialog, OkDialog
from datetime import datetime
import inspect, os

import logging
### DB$: 08/05/2020 ########################################################################################



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
# the following should be all the translations of "Form" in our po files
INTL_FORM = {"Form", "Formular", "Formulaire", "Obrazac", "Форма"}

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



### DB$: 10/05/2020 ########################################################################################
def DictFromKeyValueText(DefaultKey, KVTXT):
    """
        Create dictionary object from a string containing Key/Value pairs
        each separated by "; ".

        If the string doesn't contain an equal sign ("=") then the whole
        text string becomes assigned to a directionary object ontaining a single
        value keyed by "DefaultKey"

        Example 2 x key/value:
            Key1=SomeValue1; Key2=SomeValue1
    """
    if  '=' in KVTXT:
        #We have key value pairs, split it into 1 or more pairs
        d = dict(item.split("=", 1) for item in KVTXT.split('; '))
    else:
        # The whole string will be assigned to the default key
        d = { DefaultKey : KVTXT }
    #_LOG.debug('DictFromKeyValueText() <- "' + KVTXT + '" -> ' + str(d))
    return(d)

def DictGetAndRemove(d, KeyName, DefaultValue):
    """
       Returns a key's value or the default value if it is not in the dictionary.
       The Key is removed from the dictionary.
    """
    return d.pop(KeyName, DefaultValue)

def DictCheckForUnexpectedKeys(d, WhereText):
    """
       Expected Keys are removed by DictGetAndRemove(), what are left are
       user errors (misspelt keys etc).
    """
    if  len(d) == 0:
        # No keys left
        return ""
    else:
        # At least one key left, must be a user error
        _LOG.warning("[FORM ERROR] Unknown keys used in '%s': %s" % (WhereText, d.keys()))
        return str(d.keys())



def GetCallerDetails(relative_frame):
    """
        Gets the module, function and line number of the caller (or parent of) from the stack

        relative_frame is 0 for direct parent, or 1 for grand parent..
        https://stackoverflow.com/questions/24438976/python-debugging-get-filename-and-line-number-from-which-a-function-is-called
    """

    relative_frame      = relative_frame + 1                # Ignore THIS function details!
    total_stack         = inspect.stack()                   # total complete stack
    total_depth         = len(total_stack)                  # length of total stack
    frameinfo           = total_stack[relative_frame][0]    # info on rel frame
    relative_depth      = total_depth - relative_frame      # length of stack there

    func_name           = frameinfo.f_code.co_name
    filename            = os.path.basename(frameinfo.f_code.co_filename)
    line_number         = frameinfo.f_lineno                # of the call
    #func_firstlineno    = frameinfo.f_code.co_firstlineno

    DebugLocn           = "%s:%d@%s()" % (filename, line_number, func_name)
    return DebugLocn


def AppendCallerText(relative_frame):
    """ add text in a COMMON FORMAT to be displayed (or logged) to the user """
    return "\n\n" +_("LOCATION IN CODE") + "\n~~~~~~~~~~~~~~~~~~~~~~~~~\n" + GetCallerDetails(relative_frame + 1)

#def FormLogDebug(LogMe):
#    _LOG.debug(LogMe, stacklevel=2)         #Won't work, currently old Python in AIO Windows Installer

def GetObjectClass(SomeObject):
    """ Get the type of object given an instance of it """
    return type(SomeObject).__name__

def FormDlgDebug(ErrTitle, ErrText):
    """ Used While Debugging the program """
    #return
    TextStack = str(ErrText) + AppendCallerText(1)
    _LOG.debug('DEBUG DLG TITLE=%s, TEXT=%s' %(ErrTitle, TextStack))
    OkDialog(ErrTitle, TextStack)     #allow for list etc

def FormDlgError(ErrTitle, ErrText):
    """ Used to display an error of some type that the user probably can't do much about (the code location is appended) """
    _LOG.error('ERROR DLG TITLE=%s, TEXT=%s' % (ErrTitle, TextStack))
    TextStack = str(ErrText) + AppendCallerText(1)
    ErrorDialog(ErrTitle, TextStack)   #allow for list etc

def FormDlgInfo(ErrTitle, ErrText):
    """ Used to display non-critical information to the user (which is based on their input) """
    _LOG.warning('INFO DLG TITLE=%s, TEXT=%s' % (ErrTitle, ErrText))
    OkDialog(ErrTitle, ErrText)


def DisplayLogError(ErrTitle, ErrText):
    """ Raise an Exception after displaying the error to the user (log will contain the full stack trace) """
    TextStack = str(ErrText) + AppendCallerText(1)
    _LOG.critical('EXCEPTION DLG TITLE [raising exception]: %s, TEXT=%s' % (ErrTitle, TextStack))
    ErrorDialog(ErrTitle, TextStack)
    raise Exception("\n\n" + _("DIALOG TITLE") + "\n~~~~~~~~~~~~~~~~~~~~~~~~~\n" + ErrTitle + "\n\n"  + _("DIALOG TEXT") + "\n~~~~~~~~~~~~~~~~~~~~~~~~~\n"+ ErrText)

_LOG = logging.getLogger("Form Gramplet")
_LOG.debug('The "Form Gramplet" is loading...')
### DB$: 10/05/2020 ########################################################################################










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
        ### DB$: 09/05/2020 ########################################################################################
        self.__refs = {}
        self.__refLbls = {}
        self.__locns = {}
        self.__locnLbls = {}
        self.__dateROs = {}
        self.__dateLbls = {}
        ### DB$: 09/05/2020 ########################################################################################
        self.__dates = {}
        self.__headings = {}
        self.__sections = {}
        self.__columns = {}
        self.__types = {}
        self.__titles = {}
        self.__names = {}
        self.__section_types = {}

        ### DB$: 14/05/2020 ########################################################################################
        XmlPath = os.path.dirname(__file__)
        DefXml = definition_files
        UsrXml = os.getenv('G.FORMS')
        _LOG.debug('The environment variable "%s" contains: %s' % ('G.FORMS', UsrXml))
        if UsrXml:
           AllXml = UsrXml.split(';')
           AllXml.extend(DefXml)
        _LOG.debug('XML File List (not an error if missing): %s' % AllXml)
        _LOG.debug('Loading XML files from: "%s" (missing files ignored)' % XmlPath)
        for file_name in AllXml:
            full_path = os.path.join(os.path.dirname(__file__), file_name)
            if os.path.exists(full_path):
                _LOG.debug('FOUND XML FILE: %s' % file_name)
                self.__load_definitions(full_path)
        _LOG.debug('Finished Loading all XML files')
        ### DB$: 14/05/2020 ########################################################################################



    def __load_definitions(self, definition_file):
        ### DB$: 08/05/2020 ########################################################################################
        try:
           dom = xml.dom.minidom.parse(definition_file)
        except Exception as xArgs:
           self.DisplayLogError(_("XML SYNTAX ERROR") + ": " +  definition_file, str(xArgs))
        ### DB$: 08/05/2020 ########################################################################################



        top = dom.getElementsByTagName('forms')
        ### DB$: 08/05/2020 ########################################################################################
        if len(top) == 0:
           self.DisplayLogError(_("XML ERROR") + ": " +  definition_file, _("No '<form>' tags found!"))
        ### DB$: 08/05/2020 ########################################################################################


        for form in top[0].getElementsByTagName('form'):
            id = form.attributes['id'].value
            self.__names[id] = form.attributes['title'].value
            self.__types[id] = form.attributes['type'].value

            ### DB$: 13/05/2020 ########################################################################################
            if 'reference' in form.attributes:
                RefAttr = form.attributes['reference'].value.strip()
                if  RefAttr != '':
                    dkv    = DictFromKeyValueText('default', RefAttr)
                    RefVal = DictGetAndRemove(dkv, 'default', '')
                    RefLbl = DictGetAndRemove(dkv, 'label',   '')
                    DictCheckForUnexpectedKeys(dkv, 'reference')
                    if RefLbl != "": self.__refLbls[id] = RefLbl
                    if RefVal != "": self.__refs[id]    = RefVal

            if 'location' in form.attributes:
                LocnAttr = form.attributes['location'].value.strip()
                if  LocnAttr != '':
                    dkv     = DictFromKeyValueText('default', LocnAttr)
                    LocnVal = DictGetAndRemove(dkv, 'default', '')
                    LocnLbl = DictGetAndRemove(dkv, 'label',   '')
                    DictCheckForUnexpectedKeys(dkv, 'location')
                    if LocnLbl != '': self.__locnLbls[id] = LocnLbl
                    if LocnVal != '': self.__locns[id]    = LocnVal

            DateVal = ''
            ### DB$: 13/05/2020 ########################################################################################


            if 'date' in form.attributes:
                ### DB$: 09/05/2020 ########################################################################################
                #self.__dates[id] = form.attributes['date'].value
                DateAttr  = form.attributes['date'].value.strip()
                if  DateAttr != '':
                    dkv     = DictFromKeyValueText('default', DateAttr)
                    DateVal = DictGetAndRemove(dkv, 'default', '')
                    DateLbl = DictGetAndRemove(dkv, 'label',   '')
                    DateRO  = DictGetAndRemove(dkv, 'ro',      'Y')
                    DictCheckForUnexpectedKeys(dkv, 'date')
                    if  DateLbl != '': self.__dateLbls[id] = DateLbl

            # Was a default date specified?
            if  DateVal != "":
                # Have a default date, are we allowing the user to change it in the form?
                DateValRO = (DateRO.lower() == 'y')

                # Do we want to set today's date?
                TodayText = _('today')          #in local language, for "todays" date (should be lower case)
                _LOG.debug("Date was specified: '%s' (is it '%s'?)" % (DateVal, TodayText))
                if  DateVal == '.':             #Alias for "today"
                    DateVal = TodayText
                if  DateVal.lower() == TodayText.lower():
                    # 'today' specified (in any letter case)
                    DateVal   = TodayText           # Now in correct case
                _LOG.debug("Date Defaulting to '" + DateVal + "' (set date as read-only=" + str(DateValRO) + ')')
                self.__dateROs[id] = DateValRO
                self.__dates[id]   = DateVal
                ### DB$: 09/05/2020 ########################################################################################
            else:
                self.__dateROs[id] = False     #Editable
                self.__dates[id] = None        #No default date

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
            ### DB$: 08/05/2020 ########################################################################################
            if len(sections) == 0:
               self.DisplayLogError(_("XML ERROR") + ": " +  definition_file, _("No '<section>' tags found within a '<form>'!"))
            ### DB$: 08/05/2020 ########################################################################################
            for section in sections:
                if 'title' in section.attributes:
                    title = section.attributes['title'].value
                else:
                    title = ''

                ### DB$: 08/05/2020 ########################################################################################
                #role = section.attributes['role'].value
                try:
                   role = section.attributes['role'].value.strip()
                   if role == '':
                      self.DisplayLogError(_("XML ERROR") + ": " +  definition_file, _("A '<section>' has an EMPTY 'role=' attribute!"))
                except:
                   self.DisplayLogError(_("XML ERROR") + ": " +  definition_file, _("A '<section>' is missing the 'role=' attribute"))

                #section_type = section.attributes['type'].value
                try:
                   section_type = section.attributes['type'].value.lower()
                except:
                   self.DisplayLogError(_("XML ERROR") + ": " +  definition_file, _("A '<section>' is missing the 'type=' attribute"))

                if section_type != 'person' and section_type != 'multi' and section_type != 'family':
                   self.DisplayLogError(_("XML ERROR") + ": " +  definition_file, _("A '<section>' with Role") + "='" + role + "' " + _("has an invalid value of") + " '" + section_type + "' " + _("for the 'type=' attribute"))

                ### DB$: 08/05/2020 ########################################################################################


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
                        ### DB$: 09/05/2020 ########################################################################################
                        #OkDialog("SIZE SPECIFIED - size",      size)
                        #OkDialog("SIZE SPECIFIED - size_text", size_text)
                        ######## The size is ignored by the form app at the moment ###########
                        ### DB$: 09/05/2020 ########################################################################################
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



    ### DB$: 09/05/2020 ########################################################################################
    def get_dateRO(self, form_id):
        """ Return a true/false value (Is date editable by user?)"""
        return self.__dateROs[form_id]

    def get_dateLbl(self, form_id):
        """ Return replacement text for the Event "Date" label on the form """
        try:
            return self.__dateLbls[form_id]
        except:
            return _("Date")        #Default label text in form

    def get_refLbl(self, form_id):
        """ Return replacement text for the Event "Reference" label on the form """
        try:
            return self.__refLbls[form_id]
        except:
            return _("Reference")   #Default label text in form

    def get_ref(self, form_id):
        """ Return the default replacement """
        try:
            return self.__refs[form_id]
        except:
            return ""

    def get_locnLbl(self, form_id):
        """ Return replacement text for the Event "Location" label on the form """
        try:
            return self.__locnLbls[form_id]
        except:
            return _("Location")    #Default label text in form


    def get_locn(self, form_id):
        """ Return the default location value where it makes sense to have one """
        try:
            return self.__locns[form_id]
        except:
            return ""
    ### DB$: 09/05/2020 ########################################################################################



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
        ### DB$: 08/05/2020 ########################################################################################
        ### DB$: If 'title' wasn't specified, 'role' probably was...
        SectTitle = self.__titles[form_id][section]         #Grab the SECTION's 'title' tag
        if SectTitle == '':
           SectTitle = SectTitle = section.strip()
        if SectTitle == '':
           SectTitle = "??"                                 #Should never get here
        #OkDialog(_("DB$TEST DIALOG - get_section_title"), _(SectTitle))
        return SectTitle
        ### DB$: 08/05/2020 ########################################################################################


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

### DB$: 13/05/2020 ########################################################################################
def get_form_dateRO(form_id):
    """ Return a true/false value (Is date editable by user?) """
    DateRo = FORM.get_dateRO(form_id)
    if  DateRo:
        return DateRo
    else:
        return False

def get_form_dateLbl(form_id):
    """ Return the LABEL to be used on the form instead of "Date" """
    return FORM.get_dateLbl(form_id)

def get_form_locn(form_id):
    """ Return the default Location """
    return FORM.get_locn(form_id)

def get_form_locnLbl(form_id):
    """ Return the LABEL to be used on the form instead of "Location" """
    return FORM.get_locnLbl(form_id)

def get_form_refLbl(form_id):
    """ Return the LABEL to be used on the form instead of "Reference" """
    return FORM.get_refLbl(form_id)

def get_form_ref(form_id):
    """ Return the default Reference """
    return FORM.get_ref(form_id)
### DB$: 13/05/2020 ########################################################################################






def get_form_date(form_id):
    """
    Return the date for a given form.
    """
    date_str = FORM.get_date(form_id)
    if  date_str:
        ### DB$: 08/05/2020 ########################################################################################
        #OkDialog("date_str: BEFORE - get_form_date", date_str)
        #if date_str == '.':
        #   oNow = datetime.now()
        #   date_str = oNow.strftime('%d %B %Y')
        #   OkDialog(_("TODAY's DATE - get_form_date"), _(date_str))
        ### DB$: 08/05/2020 ########################################################################################

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
    DB$
    return FORM.get_section_title(form_id, section)
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
        if str(attr.get_type()) in INTL_FORM:
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
