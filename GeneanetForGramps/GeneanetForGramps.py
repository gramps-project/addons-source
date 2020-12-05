#!/usr/bin/python3
#
# GeneanetForGramps
#
# Copyright (C) 2020  Bruno Cornec
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the Affero GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#

# $Id: $

"""
Geneanet Import Tool
Import into Gramps persons from Geneanet
"""
#-------------------------------------------------------------------------
#
# Used Python Modules
#
#-------------------------------------------------------------------------
import os
import time
import io
import sys
import re
import random
from lxml import html
import requests
import argparse
from datetime import datetime

#------------------------------------------------------------------------
#
# GTK modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import GObject

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------
import logging
from gramps.gen.config import config
from gramps.gen.db import DbTxn
from gramps.gen.dbstate import DbState
from gramps.cli.grampscli import CLIManager
from gramps.gen.lib import Person, Name, Surname, NameType, Event, EventType, Date, Place, EventRoleType, EventRef, PlaceName, Family, ChildRef, FamilyRelType, Url, UrlType

# Gramps GUI
from gramps.gen.const import URL_MANUAL_PAGE
from gramps.gen.display.name import displayer as name_displayer
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.display import display_help
from gramps.gui.plug import MenuToolOptions, PluginWindows
from gramps.gen.plug.menu import StringOption, PersonOption, BooleanOption, NumberOption, FilterOption, MediaOption
from gramps.gui.utils import ProgressMeter

LOG = logging.getLogger("GeneanetForGramps")

TIMEOUT = 5

# TODO: Is it useful ?
LANGUAGES = {
    'cs' : 'Czech', 'da' : 'Danish','nl' : 'Dutch',
    'en' : 'English','eo' : 'Esperanto', 'fi' : 'Finnish',
    'fr' : 'French', 'de' : 'German', 'hu' : 'Hungarian',
    'it' : 'Italian', 'lt' : 'Latvian', 'lv' : 'Lithuanian',
    'no' : 'Norwegian', 'po' : 'Polish', 'pt' : 'Portuguese',
    'ro' : 'Romanian', 'sk' : 'Slovak', 'es' : 'Spanish',
    'sv' : 'Swedish', 'ru' : 'Russian',
    }
WIKI_HELP_PAGE = '%s_-_Tools' % URL_MANUAL_PAGE
WIKI_HELP_SEC = _('manual|GeneanetForGramps')

# Global variables
db = None
gname = None
verbosity = 0
force = False
ascendants = False
descendants = False
spouses = False
LEVEL = 2
ROOTURL = 'https://gw.geneanet.org/'
GUIMODE = False
progress = None

CONFIG_NAME = "geneanetforgramps"
CONFIG = config.register_manager(CONFIG_NAME)
CONFIG.register("pref.ascendants", ascendants)
CONFIG.register("pref.descendants", descendants)
CONFIG.register("pref.spouses", spouses)
CONFIG.register("pref.level", LEVEL)
CONFIG.register("pref.force", force)
CONFIG.register("pref.verbosity", verbosity)
CONFIG.load()

def save_config():
    CONFIG.set("pref.ascendants", ascendants)
    CONFIG.set("pref.descendants", descendants)
    CONFIG.set("pref.spouses", spouses)
    CONFIG.set("pref.level", LEVEL)
    CONFIG.set("pref.force", force)
    CONFIG.set("pref.verbosity", verbosity)
    CONFIG.save()

save_config()

# Generic functions

def format_ca(date):
    """
    Change the 'ca' chain into the 'vers' chain for now in Geneanet analysis
    """
    # If ca for an about date, replace with vers (for now)
    if date[0:2] == "ca":
        date = _("about")+date[2:]
    return(date)

def format_year(date):
    """
    Remove potential empty month/day coming from Gramps (00)
    """
    if not date:
        return(date)
    if (date[-6:] == "-00-00"):
        return(date[0:-6])
    else:
        return(date)

def format_iso(date_tuple):
    """
    Format an iso date.
    """
    year, month, day = date_tuple
    # Format with a leading 0 if needed
    month = str(month).zfill(2)
    day = str(day).zfill(2)
    if year == None or year == 0:
       iso_date = ''
    elif month == None or month == 0:
       iso_date = str(year)
    elif day == None or day == 0:
        iso_date = '%s-%s' % (year, month)
    else:
        iso_date = '%s-%s-%s' % (year, month, day)
    return iso_date

def format_noniso(date_tuple):
    """
    Format an non-iso tuple into an iso date
    """
    day, month, year = date_tuple
    return(format_iso(year, month, day))

def convert_date(datetab):
    ''' Convert the Geneanet date format for birth/death/married lines
    into an ISO date format
    '''

    if verbosity >= 3:
        print(_("datetab received:"),datetab)

    if len(datetab) == 0:
        return(None)
    idx = 0
    if datetab[0] == 'en':
        # avoid a potential month
        if datetab[1].isalpha():
            return(datetab[2][0:4])
        # avoid a potential , after the year
        elif datetab[1].isnumeric():
            return(datetab[1][0:4])
    if (datetab[0][0:2] == _("about")[0:2] or datetab[0][0:2] ==  _("after")[0:2] or datetab[0][0:2] ==  _("before")[0:2]) and (len(datetab) == 2):
        return(datetab[0]+" "+datetab[1][0:4])
    # In case of french language remove the 'le' prefix
    if datetab[0] == 'le':
        idx = 1
    # In case of french language remove the 'er' prefix
    if datetab[idx] == "1er":
        datetab[idx] = "1"
    bd1 = datetab[idx]+" "+datetab[idx+1]+" "+datetab[idx+2][0:4]
    bd2 = datetime.strptime(bd1, "%d %B %Y")
    return(bd2.strftime("%Y-%m-%d"))
        
# GUI Part
class GeneanetForGrampsOptions(MenuToolOptions):
    """
    Defines options and provides handling interface.
    """
    def __init__(self, name, person_id=None, dbstate=None):
        """ Initialize the options class """
        if verbosity >= 3:
            print(_("Init Plugin Options"))
        MenuToolOptions.__init__(self, name, person_id, dbstate)

    def add_menu_options(self, menu):
        """
        Add all menu options to the tool window.
        """
        if verbosity >= 3:
            print(_("Add Plugin Menu Options"))
        #category_name = _("Options")
        category_name = _("Geneanet Import Options")

        self.__pid = PersonOption(_("Center Person"))
        self.__pid.set_help(_("The center person for the filter"))
        menu.add_option(category_name, "pid", self.__pid)

        if verbosity >= 3:
            print(_("Before URL"))
        self.__gui_url = StringOption(_("Geneanet URL for the selected person"), ROOTURL)
        self.__gui_url.set_help(_("URL on Geneanet of the person you have selected which will be used as an import base such as https://gw.geneanet.org/agnesy?lang=fr&n=queffelec&oc=17&p=marie+anne"))
        menu.add_option(category_name, "gui_url", self.__gui_url)

        if verbosity >= 3:
            print(_("Before ASC"))
        gui_asc = CONFIG.get('pref.ascendants')
        if verbosity >= 3:
            if gui_asc:
                print(_("ASC True"))
            else:
                print(_("ASC False"))
        self.__gui_asc = BooleanOption(_("Import ascendants"), gui_asc)
        self.__gui_asc.set_help(_("Import ascendants of the selected person up to level number"))
        menu.add_option(category_name, "gui_asc", self.__gui_asc)

        if verbosity >= 3:
            print(_("Before DSC"))
        gui_dsc = CONFIG.get('pref.descendants')
        if verbosity >= 3:
            if gui_dsc:
                print(_("DSC True"))
            else:
                print(_("DSC False"))
        self.__gui_dsc = BooleanOption(_("Import descendants"), gui_dsc)
        self.__gui_dsc.set_help(_("Import descendants of the selected person up to level number"))
        menu.add_option(category_name, "gui_dsc", self.__gui_dsc)

        if verbosity >= 3:
            print(_("Before SPO"))
        gui_spo = CONFIG.get('pref.spouses')
        if verbosity >= 3:
            if gui_spo:
                print(_("SPO True"))
            else:
                print(_("SPO False"))
        self.__gui_spo = BooleanOption(_("Import spouses"), gui_spo)
        self.__gui_spo.set_help(_("Import all spouses of the selected person"))
        menu.add_option(category_name, "gui_spo", self.__gui_spo)

        if verbosity >= 3:
            print(_("Before LVL"))
        gui_lvl = CONFIG.get('pref.level')
        if verbosity >= 3:
            print(_("LVL:"), gui_lvl)
        self.__gui_level = NumberOption(_("Level of Import"), gui_lvl, 1, 100)
        self.__gui_level.set_help(_("Maximum of upper or lower search done in the family tree - keep it small"))
        menu.add_option(category_name, "gui_level", self.__gui_level)

        if verbosity >= 3:
            print(_("Before FORCE"))
        gui_force = CONFIG.get('pref.force')
        if verbosity >= 3:
            if gui_force:
                print(_("FORCE True"))
            else:
                print(_("FORCE False"))
        self.__gui_force = BooleanOption(_("Force Import"), gui_force)
        self.__gui_force.set_help(_("Force import of existing persons"))
        menu.add_option(category_name, "gui_force", self.__gui_force)

        if verbosity >= 3:
            print(_("Before VRB"))
        gui_verb = CONFIG.get('pref.verbosity')
        if verbosity >= 3:
            print(_("VRB:"), gui_verb)
        self.__gui_verb = NumberOption(_("Verbosity"), gui_verb, 0, 3)
        self.__gui_verb.set_help(_("Verbosity level from 0 (minimal) to 3 (very verbose)"))
        menu.add_option(category_name, "gui_verb", self.__gui_verb)

        if verbosity >= 3:
            print(_("Menu Added"))

class GeneanetForGramps(PluginWindows.ToolManagedWindowBatch):
    """
    Plugin that gives simplified interface to the import from Geneanet
    """
    def __init__(self, dbstate, user, options_class, name, callback):
        if verbosity >= 3:
            print(_("Init Plugin itself"))
        PluginWindows.ToolManagedWindowBatch.__init__(self, dbstate, user, options_class, name, callback)

    def get_title(self):
        if verbosity >= 3:
            print(_("Plugin get_title"))
        return _("Geneanet Import Tool")  # tool window title

    def initial_frame(self):
        if verbosity >= 3:
            print(_("Plugin initial_frame"))
        return _("Geneanet Import Options")  # tab title

    def run(self):
        """
        Main function running the Geneanet Import Tool
        """
        global db
        global GUIMODE
        global progress

        if verbosity >= 3:
            print(_("Plugin run"))
        db = self.dbstate.db
        self.__get_menu_options()
        hdr = _('Importing from %s for user %s') % (self.purl,self.gid)
        msg = _('Geneanet Import into Gramps')
        progress = ProgressMeter(msg, hdr)
        #progress = ProgressMeter(msg, hdr, False, None, True, None)
        progress.set_pass(hdr,100,mode=ProgressMeter.MODE_ACTIVITY)
        if verbosity >= 2:
            print(msg)
        GUIMODE = True
        g2gaction(self.gid,self.purl)

    def __get_menu_options(self):
        """
        General menu option processing.
        """
        global force
        global ascendants
        global descendants
        global spouses
        global LEVEL
        global verbosity
        if verbosity >= 3:
            print(_("Plugin __get_menu_options"))

        menu = self.options.menu

        self.gid = self.options.menu.get_option_by_name('pid').get_value()
        if verbosity >= 3:
            print(_("GID:"),self.gid)
        self.purl = self.options.menu.get_option_by_name('gui_url').get_value()
        if verbosity >= 3:
            print(_("URL:"),self.purl)
        force = self.options.menu.get_option_by_name('gui_force').get_value()
        ascendants = self.options.menu.get_option_by_name('gui_asc').get_value()
        if verbosity >= 3:
            if ascendants:
                print(_("ASC True"))
            else:
                print(_("ASC False"))
        descendants = self.options.menu.get_option_by_name('gui_dsc').get_value()
        spouses = self.options.menu.get_option_by_name('gui_spo').get_value()
        LEVEL = self.options.menu.get_option_by_name('gui_level').get_value()
        verbosity = self.options.menu.get_option_by_name('gui_verb').get_value()
        if verbosity >= 3:
            print(_("LVL:"),LEVEL)
        save_config()

class GBase:

    def __init__(self):
        pass

    def _smartcopy(self,attr):
        '''
        Smart Copying an attribute from geneanet (g_ attrs) into attr
        Works for GPerson and GFamily
        '''
        if verbosity >= 3:
            print(_("Smart Copying Attributes"),attr)

        # By default do not copy as Gramps is the master reference
        scopy = False

        # Find the case where copy is to be done
        # Nothing yet
        if not self.__dict__[attr]:
            scopy = True

        # Empty field
        if self.__dict__[attr] and self.__dict__[attr] == "" and self.__dict__['g_'+attr] and self.__dict__['g_'+attr] != "":
            scopy = True

        # Force the copy
        if self.__dict__[attr] != self.__dict__['g_'+attr] and force:
            scopy = True

        # Managing sex, Gramps is always right except when unknown
        # Warn on conflict
        if attr == 'sex' and self.__dict__[attr] == 'U' and self.__dict__['g_'+attr] != 'U':
            scopy = True
            if (self.__dict__[attr] == 'F' and self.__dict__['g_'+attr] == 'M') \
            or (self.__dict__[attr] == 'M' and self.__dict__['g_'+attr] == 'F'):
                if verbosity >= 1:
                    print(_("WARNING: Gender conflict between Geneanet (%s) and Gramps (%s), keeping Gramps value")%(self.__dict__['g_'+attr],self.__dict__[attr]))
                scopy = False

        if attr == 'lastname' and self.__dict__[attr] != self.__dict__['g_'+attr]:
            if verbosity >= 1 and self.__dict__[attr] != "":
                print(_("WARNING: Lastname conflict between Geneanet (%s) and Gramps (%s), keeping Gramps value")%(self.__dict__['g_'+attr],self.__dict__[attr]))
        if attr == 'lastname' and self.__dict__[attr] == "":
            scopy = True

        if attr == 'firstname' and self.__dict__[attr] != self.__dict__['g_'+attr]:
            if verbosity >= 1 and self.__dict__[attr] != "":
                print(_("WARNING: Firstname conflict between Geneanet (%s) and Gramps (%s), keeping Gramps value")%(self.__dict__['g_'+attr],self.__dict__[attr]))
        if attr == 'firstname' and self.__dict__[attr] == "":
            scopy = True

        # Copy only if code is more precise
        match = re.search(r'code$', attr)
        if match:
            if not self.__dict__[attr]:
                scopy = True
            else:
                if not self.__dict__['g_'+attr]:
                    scopy = False
                else:
                    if int(self.__dict__[attr]) < int(self.__dict__['g_'+attr]):
                        scopy = True

        # Copy only if date is more precise
        match = re.search(r'date$', attr)
        if match:
            if not self.__dict__[attr]:
                scopy = True
            else:
                if not self.__dict__['g_'+attr]:
                    scopy = False
                else:
                    if self.__dict__[attr] == "" and self.__dict__['g_'+attr] != "":
                        scopy = True
                    elif self.__dict__[attr] < self.__dict__['g_'+attr]:
                        scopy = True

        if scopy:
            if verbosity >= 2:
                print(_("Copying Person attribute %s (former value %s newer value %s)")%(attr, self.__dict__[attr],self.__dict__['g_'+attr]))

            self.__dict__[attr] = self.__dict__['g_'+attr]
        else:
            if verbosity >= 3:
                print(_("Not Copying Person attribute (%s, value %s) onto %s")%(attr, self.__dict__[attr],self.__dict__['g_'+attr]))


    def get_or_create_place(self,event,placename):
        '''
        Create Place for Events or get an existing one based on the name
        '''
        try:
            pl = event.get_place_handle()
        except:
            place = Place()
            return(place)
    
        if pl:
            try:
                place = db.get_place_from_handle(pl)
                if verbosity >= 2:
                    print(_("Reuse Place from Event:"), place.get_name().value)
            except:
                place = Place()
        else:
            if placename == None:
                place = Place()
                return(place)
            keep = None
            # Check whether our place already exists
            for handle in db.get_place_handles():
                pl = db.get_place_from_handle(handle)
                explace = pl.get_name().value
                if verbosity >= 4:
                    print(_("DEBUG: search for ")+str(placename)+_(" in ")+str(explace))
                if str(explace) == str(placename):
                    keep = pl
                    break
            if keep == None:
                if verbosity >= 2:
                    print(_("Create Place:"), placename)
                place = Place()
            else:
                if verbosity >= 2:
                    print(_("Reuse existing Place:"), placename)
                place = keep
        return(place)
    
    def get_or_create_event(self,gobj,attr,tran):
        '''
        Create Birth and Death Events for a person 
        and Marriage Events for a family or get an existing one
        self is GPerson or GFamily
        gobj is a gramps object Person or Family
        '''
        
        event = None
        # Manages name indirection for person
        if gobj.__class__.__name__ == 'Person':
            role = EventRoleType.PRIMARY
            func = getattr(gobj,'get_'+attr+'_ref')
            reffunc = func()
            if reffunc:
                event = db.get_event_from_handle(reffunc.ref)
                if verbosity >= 2:
                    print(_("Existing ")+attr+_(" Event"))
        elif gobj.__class__.__name__ == 'Family':
            role = EventRoleType.FAMILY
            if attr == 'marriage':
                marev = None
                for event_ref in gobj.get_event_ref_list():
                    event = db.get_event_from_handle(event_ref.ref)
                    if (event.get_type() == EventType.MARRIAGE and
                            (event_ref.get_role() == EventRoleType.FAMILY or
                             event_ref.get_role() == EventRoleType.PRIMARY)):
                        marev = event
                if marev:
                    event = marev
                    if verbosity >= 2:
                        print(_("Existing ")+attr+_(" Event"))
        else:
            print(_("ERROR: Unable to handle class %s in get_or_create_all_event")%(gobj.__class__.__name__))
                    
        if event is None:
            event = Event()
            uptype = getattr(EventType,attr.upper())
            event.set_type(EventType(uptype))
            event.set_description('Imported from Geaneanet')
            db.add_event(event,tran)
    
            eventref = EventRef()
            eventref.set_role(role)
            eventref.set_reference_handle(event.get_handle())
            if gobj.__class__.__name__ == 'Person':
                func = getattr(gobj,'set_'+attr+'_ref')
                reffunc = func(eventref)
                db.commit_event(event,tran)
                db.commit_person(gobj,tran)
            elif gobj.__class__.__name__ == 'Family':
                eventref.set_role(EventRoleType.FAMILY)
                gobj.add_event_ref(eventref)
                if attr == 'marriage':
                    gobj.set_relationship(FamilyRelType(FamilyRelType.MARRIED))
                db.commit_event(event,tran)
                db.commit_family(gobj,tran)
            if verbosity >= 2:
                print(_("Creating ")+attr+" ("+str(uptype)+") "+_("Event"))
    
        if self.__dict__[attr+'date'] \
            or self.__dict__[attr+'place'] \
            or self.__dict__[attr+'placecode'] :
            # Get or create the event date
            date = event.get_date_object()
            if self.__dict__[attr+'date']:
                idx = 0
                mod = Date.MOD_NONE
                if self.__dict__[attr+'date'][0:2] == _("about")[0:2]:
                    idx = 1
                    mod = Date.MOD_ABOUT 
                elif self.__dict__[attr+'date'][0:2] == _("before")[0:2]:
                    idx = 1
                    mod = Date.MOD_BEFORE 
                elif self.__dict__[attr+'date'][0:2] == _("after")[0:2]:
                    idx = 1
                    mod = Date.MOD_AFTER 
                # Only in case of french language analysis
                elif self.__dict__[attr+'date'][0:2] == _("in")[0:2]:
                    idx = 1
                else:
                    pass
                if idx == 1:
                    # we need to removed the first word
                    string = self.__dict__[attr+'date'].split(' ',1)[1]
                else:
                    string = self.__dict__[attr+'date']
                # ISO string, put in a tuple, reversed
                tab = string.split('-')
                if len(tab) == 3:
                    date.set_yr_mon_day(int(tab[0]),int(tab[1]),int(tab[2]))
                elif len(tab) == 2:
                    date.set_yr_mon_day(int(tab[0]),int(tab[1]),0)
                elif len(tab) == 1:
                    date.set_year(int(tab[0]))
                elif len(tab) == 0:
                    print(_("WARNING: Trying to affect an empty date"))
                    pass
                else:
                    print(_("WARNING: Trying to affect an extra numbered date"))
                    pass
                if mod:
                    date.set_modifier(mod)
            if verbosity >= 2 and self.__dict__[attr+'date']:
                print(_("Update ")+attr+_(" Date to ")+self.__dict__[attr+'date'])
            event.set_date_object(date)
            db.commit_event(event,tran)
    
            if self.__dict__[attr+'place'] \
                or self.__dict__[attr+'placecode'] :
                if self.__dict__[attr+'place']:
                    placename = self.__dict__[attr+'place']
                else:
                    placename = ""
                place = self.get_or_create_place(event,placename)
                # TODO: Here we overwrite any existing value. 
                # Check whether that can be a problem
                place.set_name(PlaceName(value=placename))
                if self.__dict__[attr+'placecode']:
                    place.set_code(self.__dict__[attr+'placecode'])
                db.add_place(place,tran)
                event.set_place_handle(place.get_handle())
                db.commit_event(event,tran)
    
        db.commit_event(event,tran)
        return

    def get_gramps_date(self,evttype):
        '''
        Give back the date of the event related to the GPerson or GFamily
        as a string ISO formated
        '''
    
        if verbosity >= 4:
            print(_("EventType: %d")%(evttype))
    
        if not self:
            return(None)
    
        if evttype == EventType.BIRTH:
            ref = self.grampsp.get_birth_ref()
        elif evttype == EventType.DEATH:
            ref = self.grampsp.get_death_ref()
        elif evttype == EventType.MARRIAGE:
            eventref = None
            for eventref in self.family.get_event_ref_list():
                event = db.get_event_from_handle(eventref.ref)
                if (event.get_type() == EventType.MARRIAGE
                    and (eventref.get_role() == EventRoleType.FAMILY
                    or eventref.get_role() == EventRoleType.PRIMARY)):
                        break
            ref = eventref
        else:
            print(_("Didn't find a known EventType: "),evttype)
            return(None)
    
        if ref:
            if verbosity >= 4:
                print(_("Ref:"),ref)
            try:
                event = db.get_event_from_handle(ref.ref)
            except:
                print(_("Didn't find a known ref for this ref date: "),ref)
                return(None)
            if event:
                if verbosity >= 4:
                    print(_("Event")+":",event)
                date = event.get_date_object()
                moddate = date.get_modifier()
                tab = date.get_dmy()
                if verbosity >= 4:
                    print(_("Found date: "),tab)
                if len(tab) == 3:
                    tab = date.get_ymd()
                    if verbosity >= 4:
                        print(_("Found date2: "),tab)
                    ret = format_iso(tab)
                else:
                    ret = format_noniso(tab)
                if moddate == Date.MOD_BEFORE:
                    pref = _("before")+" "
                elif moddate == Date.MOD_AFTER:
                    pref = _("after")+" "
                elif moddate == Date.MOD_ABOUT:
                    pref = _("about")+" "
                else:
                    pref = ""
                if verbosity >= 3:
                    print(_("Returned date: ")+pref+ret)
                return(pref+ret)
            else:
                return(None)
        else:
            return(None)


class GFamily(GBase):
    '''
    Family as seen by Gramps and Geneanet
    '''
    def __init__(self,father,mother):
        # The 2 GPersons parents in this family should exist
        # and properties filled before we create the family
        # Gramps properties
        self.marriagedate = None
        self.marriageplace = None
        self.marriageplacecode = None
        self.gid = None
        # Pointer to the Gramps Family instance
        self.family = None
        # Geneanet properties
        self.g_marriagedate = None
        self.g_marriageplace = None
        self.g_marriageplacecode = None
        self.g_childref = []

        if verbosity >= 1:
            print(_("Creating GFamily: ")+father.firstname+" "+father.lastname+" - "+mother.firstname+" "+mother.lastname)
        self.url = father.url
        if self.url == "":
            self.url = mother.url
        # TODO: what if father or mother is None
        self.father = father
        self.mother = mother

    def create_grampsf(self):
        '''
        Create a Family in Gramps and return it
        '''
        with DbTxn("Geneanet import", db) as tran:
            grampsf = Family()
            db.add_family(grampsf,tran)
            self.gid = grampsf.gramps_id
            self.family = grampsf
            if verbosity >= 2:
                print(_("Create new Gramps Family: ")+self.gid)

    def find_grampsf(self):
        '''
        Find a Family in Gramps and return it
        '''
        if verbosity >= 2:
            print(_("Look for a Gramps Family"))
        f = None
        ids = db.get_family_gramps_ids()
        for i in ids:
            f = db.get_family_from_gramps_id(i)
            if verbosity >= 3:
                print(_("Analysing Gramps Family ")+f.gramps_id)
            # Do these people already form a family
            father = None
            fh = f.get_father_handle()
            if fh:
                father = db.get_person_from_handle(fh)
            mother = None
            mh = f.get_mother_handle()
            if mh:
                mother = db.get_person_from_handle(mh)
            if verbosity >= 3:
                if not father:
                    fgid = None
                else:
                    fgid = father.gramps_id
                if not fgid:
                    fgid = "None"
                sfgid = self.father.gid
                if not sfgid:
                    sfgid = "None"
                print(_("Check father ids: ")+fgid+_(" vs ")+sfgid)
                if not mother:
                    mgid = None
                else:
                    mgid = mother.gramps_id
                if not mgid:
                    mgid = "None"
                smgid = self.mother.gid
                if not smgid:
                    smgid = "None"
                print(_("Check mother ids: ")+mgid+_(" vs ")+smgid)
            if self.father and father and father.gramps_id == self.father.gid \
                and self.mother and mother and mother.gramps_id == self.mother.gid:
                return(f)
            #TODO: What about preexisting families not created in this run ?
        return(None)

    def from_geneanet(self):
        '''
        Initiate the GFamily from Geneanet data
        '''
        # Once we get the right spouses, then we can have the marriage info
        idx = 0
        for sr in self.father.spouseref:
            if verbosity >= 3:
                print(_("Comparing sr %s to %s (idx: %d)")%(sr,self.mother.url,idx))
            if sr == self.mother.url:
                if verbosity >= 2:
                    print(_("Spouse %s found (idx: %d)")%(sr,idx))
                break
            idx = idx + 1

        if idx < len(self.father.spouseref):
            # We found one
            self.g_marriagedate = self.father.marriagedate[idx]
            self.g_marriageplace = self.father.marriageplace[idx]
            self.g_marriageplacecode = self.father.marriageplacecode[idx]
            for c in self.father.childref[idx]:
                self.g_childref.append(c)

        if self.g_marriagedate and self.g_marriageplace and self.g_marriageplacecode:
            if verbosity >= 2:
                print(_("Geneanet Marriage found the %s at %s (%s)")%(self.g_marriagedate,self.g_marriageplace,self.g_marriageplacecode))


    def from_gramps(self,gid):
        '''
        Initiate the GFamily from Gramps data
        '''
        if verbosity >= 2:
            print(_("Calling from_gramps with gid: %s")%(gid))

        # If our gid was already setup and we didn't pass one
        if not gid and self.gid:
            gid = self.gid

        if verbosity >= 2:
            print(_("Now gid is: %s")%(gid))

        found = None
        try:
            found = db.get_family_from_gramps_id(gid)
            self.gid = gid
            self.family = found
            if verbosity >= 2:
                print(_("Existing gid of a Gramps Family: %s")%(self.gid))
        except:
            if verbosity >= 1:
                print(_("WARNING: Unable to retrieve id %s from the gramps db %s")%(gid,gname))

        if not found:
            # If we don't know which family this is, try to find it in Gramps 
            # This supposes that Geneanet data are already present in GFamily
            self.family = self.find_grampsf()
            if self.family:
                if verbosity >= 2:
                    print(_("Found an existing Gramps family ")+self.family.gramps_id)
                self.gid = self.family.gramps_id
            # And if we haven't found it, create it in gramps
            if self.family == None:
                self.create_grampsf()

        if self.family:
            self.marriagedate = self.get_gramps_date(EventType.MARRIAGE)
            if self.marriagedate == "":
                self.marriagedate = None
            for eventref in self.family.get_event_ref_list():
                event = db.get_event_from_handle(eventref.ref)
                if (event.get_type() == EventType.MARRIAGE
                and (eventref.get_role() == EventRoleType.FAMILY
                or eventref.get_role() == EventRoleType.PRIMARY)):
                    place = self.get_or_create_place(event,None)
                    self.marriageplace = place.get_name().value
                    self.marriageplacecode = place.get_code()
                    break

            if verbosity >= 2:
                if self.marriagedate and self.marriageplace and self.marriageplacecode:
                    print(_("Gramps Marriage found the %s at %s (%s)")%(self.marriagedate,self.marriageplace,self.marriageplacecode))

    def to_gramps(self):
        '''
        '''
        # Smart copy from Geneanet to Gramps inside GFamily
        self.smartcopy()
        with DbTxn("Geneanet import", db) as tran:
            # When it's not the case create the family
            if self.family == None:
                self.family = Family()
                db.add_family(self.family,tran)

            try:
                grampsp0 = db.get_person_from_gramps_id(self.father.gid)
            except:
                if verbosity >= 2:
                    print(_("No father for this family"))
                grampsp0 = None

            if grampsp0:
                try:
                    self.family.set_father_handle(grampsp0.get_handle())
                except:
                    if verbosity >= 2:
                        print(_("Can't affect father to the family"))

                db.commit_family(self.family,tran)
                grampsp0.add_family_handle(self.family.get_handle())
                db.commit_person(grampsp0,tran)

            try:
                grampsp1 = db.get_person_from_gramps_id(self.mother.gid)
            except:
                if verbosity >= 2:
                    print(_("No mother for this family"))
                grampsp1 = None

            if grampsp1:
                try:
                    self.family.set_mother_handle(grampsp1.get_handle())
                except:
                    if verbosity >= 2:
                        print(_("Can't affect mother to the family"))

                db.commit_family(self.family,tran)
                grampsp1.add_family_handle(self.family.get_handle())
                db.commit_person(grampsp1,tran)

            # Now celebrate the marriage ! (if needed)
            self.get_or_create_event(self.family,'marriage',tran)

    def smartcopy(self):
        '''
        Smart Copying GFamily
        '''
        if verbosity >= 2:
            print(_("Smart Copying Family"))
        self._smartcopy("marriagedate")
        self._smartcopy("marriageplace")
        self._smartcopy("marriageplacecode")

    def add_child(self,child):
        '''
        Adds a child GPerson child to the GFamily
        '''
        found = None
        i = 0
        # Avoid handling already processed children in Gramps
        for cr in self.family.get_child_ref_list():
            c = db.get_person_from_handle(cr.ref)
            if c.gramps_id == child.gid:
                found = child
                if verbosity >= 1:
                    print(_("Child already existing : ")+child.firstname+" "+child.lastname)
                break
            # Ensure that the child is part of the family

        if not found:
            if child:
                if verbosity >= 2:
                    print(_("Adding child: ")+child.firstname+" "+child.lastname)
                childref = ChildRef()
                if child.grampsp:
                    try:
                        childref.set_reference_handle(child.grampsp.get_handle())
                    except:
                        if verbosity >= 2:
                            print(_("No handle for this child"))
                    self.family.add_child_ref(childref)
                    with DbTxn("Geneanet import", db) as tran:
                        db.commit_family(self.family,tran)
                        child.grampsp.add_parent_family_handle(self.family.get_handle())
                        db.commit_person(child.grampsp,tran)

    def recurse_children(self,level):
        '''
        analyze recursively the children of the GFamily passed in parameter 
        '''
        try:
            cpt = len(self.g_childref)
        except:
            if verbosity >= 1:
                print(_("Stopping exploration as there are no more children for family ")+self.fater.firstname+" "+self.father.lastname+" - "+self.mother.firstname+" "+self.mother.lastname)
            return
        loop = False
        # Recurse while we have children urls and level not reached
        if level <= LEVEL and (cpt > 0):
            loop = True
            level = level + 1

            if not self.family:
                print(_("WARNING: No family found whereas there should be one :-("))
                return

            # Create a GPerson from all children mentioned in Geneanet
            for c in self.g_childref:
                child = geneanet_to_gramps(None,level-1,None,c)
                if verbosity >= 2:
                    print(_("=> Recursion on the child of ")+self.father.lastname+' - '+self.mother.lastname+': '+child.firstname+' '+child.lastname)
                self.add_child(child)

                fam = []
                if spouses:
                     fam = child.add_spouses(level)
                     if ascendants:
                         for f in fam:
                             if child.sex == 'M':
                                 f.mother.recurse_parents(level-1)
                             if child.sex == 'F':
                                 f.father.recurse_parents(level-1)
                     if descendants:
                         for f in fam:
                             f.recurse_children(level)
    
                if verbosity >= 2:
                    print(_("=> End of recursion on the child of ")+self.father.lastname+' - '+self.mother.lastname+': '+child.firstname+' '+child.lastname)

        if not loop:
            if cpt == 0:
                if verbosity >= 1:
                    print(_("Stopping exploration for family ")+self.father.firstname+" "+self.father.lastname+' - '+self.mother.firstname+" "+self.mother.lastname+_(" as there are no more children"))
                return
    
            if level > LEVEL:
                if verbosity >= 1:
                    print(_("Stopping exploration for family ")+self.father.firstname+" "+self.father.lastname+' - '+self.mother.firstname+" "+self.mother.lastname+_(" as we reached level ")+str(level))
        return
        
class GPerson(GBase):
    '''
    Generic Person common between Gramps and Geneanet
    '''
    def __init__(self,level):
        if verbosity >= 3:
            print(_("Initialize Person at level %d")%(level))
        # Counter
        self.level = level
        # Gramps
        self.firstname = ""
        self.lastname = ""
        self.sex = 'U'
        self.birthdate = None
        self.birthplace = None
        self.birthplacecode = None
        self.deathdate = None
        self.deathplace = None
        self.deathplacecode = None
        self.gid = None
        self.grampsp = None
        # Father and Mother and Spouses GPersons
        self.father = None
        self.mother = None
        self.spouse = []
        # GFamilies
        self.family = []
        # Geneanet
        self.g_firstname = ""
        self.g_lastname = ""
        self.g_sex = 'U'
        self.g_birthdate = None
        self.g_birthplace = None
        self.g_birthplacecode = None
        self.g_deathdate = None
        self.g_deathplace = None
        self.g_deathplacecode = None
        self.url = ""
        self.spouseref = []
        self.fref = ""
        self.mref = ""
        self.marriagedate = []
        self.marriageplace = []
        self.marriageplacecode = []
        self.childref = []

    def smartcopy(self):
        '''
        Smart Copying GPerson
        '''
        if verbosity >= 2:
            print(_("Smart Copying Person"),self.gid)
        self._smartcopy("firstname")
        self._smartcopy("lastname")
        self._smartcopy("sex")
        self._smartcopy("birthdate")
        self._smartcopy("birthplace")
        self._smartcopy("birthplacecode")
        self._smartcopy("deathdate")
        self._smartcopy("deathplace")
        self._smartcopy("deathplacecode")

    def from_geneanet(self,purl):
        ''' Use XPath to retrieve the details of a person
        Used example from https://gist.github.com/IanHopkinson/ad45831a2fb73f537a79
        and doc from https://www.w3schools.com/xml/xpath_axes.asp
        and https://docs.python-guide.org/scenarios/scrape/

        lxml can return _ElementUnicodeResult instead of str so cast
        '''

        # Needed as Geneanet returned relative links
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}


        if verbosity >= 3:
            print(_("Purl:"),purl)
        if not purl:
            return()
        try:
            if verbosity >= 1:
                print("-----------------------------------------------------------")
                print(_("Page considered:"),purl)
            page = requests.get(purl)
            if verbosity >= 3:
                print(_("Return code:"),page.status_code)
        except:
            print(_("We failed to reach the server at"),purl)
        else:
            if page.ok:
                try:
                    tree = html.fromstring(page.content)
                except:
                    print(_("Unable to perform HTML analysis"))
    
                self.url = purl
                # Wait after a Genanet request to be fair with the site 
                # between 2 and 7 seconds
                time.sleep(random.randint(2,7))
                try:
                    # Should return M or F
                    sex = tree.xpath('//div[@id="person-title"]//img/attribute::alt')
                    self.g_sex = sex[0]
                    # Seems we have a french codification on the site
                    if sex[0] == 'H':
                        self.g_sex = 'M'
                except:
                    self.g_sex = 'U'
                try:
                    name = tree.xpath('//div[@id="person-title"]//a/text()')
                    self.g_firstname = str(name[0])
                    self.g_lastname = str(name[1])
                except:
                    self.g_firstname = ""
                    self.g_lastname = ""
                if verbosity >= 1:
                    print(_("==> GENEANET Name (L%d): %s %s")%(self.level,self.g_firstname,self.g_lastname))
                if verbosity >= 2:
                    print(_("Sex:"), self.g_sex)
                try:
                    sstring = '//li[contains(., "'+_("Born")+'")]/text()'
                    if verbosity >= 3:
                        print("sstring: "+sstring)
                    birth = tree.xpath(sstring)
                except:
                    birth = [""]
                if verbosity >= 3:
                    print(_("birth")+": %s"%(birth))
                try:
                    sstring = '//li[contains(., "'+_("Deceased")+'")]/text()'
                    if verbosity >= 3:
                        print("sstring: "+sstring)
                    death = tree.xpath(sstring)
                except:
                    death = [""]
                if verbosity >= 3:
                    print(_("death")+": %s"%(death))
                try:
                    # sometime parents are using circle, somtimes disc !
                    parents = tree.xpath('//ul[not(descendant-or-self::*[@class="fiche_union"])]//li[@style="vertical-align:middle;list-style-type:disc" or @style="vertical-align:middle;list-style-type:circle"]')
                except:
                    parents = []
                try:
                    spouses = tree.xpath('//ul[@class="fiche_union"]/li')
                except:
                    spouses = []
                try:
                    ld = convert_date(birth[0].split('-')[0].split()[1:])
                    if verbosity >= 2:
                        print(_("Birth:"), ld)
                    self.g_birthdate = format_ca(ld)
                except:
                    self.g_birthdate = None
                try:
                    self.g_birthplace = str(' '.join(birth[0].split('-')[1:]).split(',')[0].strip())
                    if verbosity >= 2:
                        print(_("Birth place:"), self.g_birthplace)
                except:
                    self.g_birthplace = None
                try:
                    self.g_birthplacecode = str(' '.join(birth[0].split('-')[1:]).split(',')[1]).strip()
                    match = re.search(r'\d\d\d\d\d', self.g_birthplacecode)
                    if not match:
                        self.g_birthplacecode = None
                    else:
                        if verbosity >= 2:
                            print(_("Birth place code:"), self.g_birthplacecode)
                except:
                    self.g_birthplacecode = None
                try:
                    ld = convert_date(death[0].split('-')[0].split()[1:])
                    if verbosity >= 2:
                        print(_("Death:"), ld)
                    self.g_deathdate = format_ca(ld)
                except:
                    self.g_deathdate = None
                try:
                    self.g_deathplace = str(' '.join(death[0].split('-')[1:]).split(',')[0]).strip()
                    if verbosity >= 2:
                        print(_("Death place:"), self.g_deathplace)
                except:
                    self.g_deathplace = None
                try:
                    self.g_deathplacecode = str(' '.join(death[0].split('-')[1:]).split(',')[1]).strip()
                    match = re.search(r'\d\d\d\d\d', self.g_deathplacecode)
                    if not match:
                        self.g_deathplacecode = None
                    else:
                        if verbosity >= 2:
                            print(_("Death place code:"), self.g_deathplacecode)
                except:
                    self.g_deathplacecode = None

                s = 0
                sname = []
                sref = []
                marriage = []
                for spouse in spouses:
                    try:
                        sname.append(str(spouse.xpath('a/text()')[0]))
                        if verbosity >= 2:
                            print(_("Spouse name:"), sname[s])
                    except:
                        sname.append("")

                    try:
                        sref.append(str(spouse.xpath('a/attribute::href')[0]))
                        if verbosity >= 2:
                            print(_("Spouse ref:"), ROOTURL+sref[s])
                    except:
                        sref.append("")
                    self.spouseref.append(ROOTURL+sref[s])

                    try:
                        marriage.append(str(spouse.xpath('em/text()')[0]))
                    except: 
                        marriage.append(None)
                    try:
                        ld = convert_date(marriage[s].split(',')[0].split()[1:])
                        if verbosity >= 2:
                            print(_("Married:"), ld)
                        self.marriagedate.append(format_ca(ld))
                    except:
                        self.marriagedate.append(None)
                    try:
                        self.marriageplace.append(str(marriage[s].split(',')[1][1:]))
                        if verbosity >= 2:
                            print(_("Married place:"), self.marriageplace[s])
                    except:
                        self.marriageplace.append(None)
                    try:
                        marriageplacecode = str(marriage[s].split(',')[2][1:])
                        match = re.search(r'\d\d\d\d\d', marriageplacecode)
                        if not match:
                            self.marriageplacecode.append(None)
                        else:
                            if verbosity >= 2:
                                print(_("Married place code:"), self.marriageplacecode[s])
                            self.marriageplacecode.append(marriageplacecode)
                    except:
                        self.marriageplacecode.append(None)
    
                    cnum = 0
                    clist = []
                    for c in spouse.xpath('ul/li'):
                        try:
                            cname = c.xpath('a/text()')[0]
                            if verbosity >= 2:
                                print(_("Child %d name: %s")%(cnum,cname))
                        except:
                            cname = None
                        try:
                            cref = ROOTURL+str(c.xpath('a/attribute::href')[0])
                            if verbosity >= 2:
                                print(_("Child %d ref: %s")%(cnum,cref))
                        except:
                            cref = None
                        clist.append(cref)
                        cnum = cnum + 1
                    self.childref.append(clist)
                    s = s + 1
                    # End spouse loop
    
                self.fref = ""
                self.mref = ""
                prefl = []
                for p in parents:
                    if verbosity >= 3:
                        print(p.xpath('text()'))
                    if p.xpath('text()')[0] == '\n':
                        try:
                            pname = p.xpath('a/text()')[0]
                        except:
                            pname = ""
                            # if pname is ? ? then go to next one
                        try:
                            pref = p.xpath('a/attribute::href')[0]
                        except:
                            pref = ""
                        if verbosity >= 1:
                           print(_("Parent name: %s (%s)")%(pname,ROOTURL+pref))
                        prefl.append(ROOTURL+str(pref))
                try:
                    self.fref = prefl[0]
                except:
                    self.fref = ""
                try:
                    self.mref = prefl[1]
                except:
                    self.mref = ""
                if verbosity >= 2:
                    print("-----------------------------------------------------------")
    
            else:
                print(_("We failed to be ok with the server"))


    def create_grampsp(self):
        '''
        Create a Person in Gramps and return it
        '''
        with DbTxn("Geneanet import", db) as tran:
            grampsp = Person()
            db.add_person(grampsp,tran)
            self.gid = grampsp.gramps_id
            self.grampsp = grampsp
            if verbosity >= 1:
                print(_("Create new Gramps Person: ")+self.gid+' ('+self.g_firstname+' '+self.g_lastname+')')


    def find_grampsp(self):
        '''
        Find a Person in Gramps and return it
        The parameter precises the relationship with our person
        '''
        p = None
        ids = db.get_person_gramps_ids()
        for i in ids:
            if verbosity >= 3:
                print(_("DEBUG: Looking after ")+i)
            p = db.get_person_from_gramps_id(i)
            try:
                name = p.primary_name.get_name().split(', ')
            except:
                continue
            if len(name) == 0:
                continue
            elif len(name) == 1:
                name.append(None)
            if name[0]:
                lastname = name[0]
            else:
                lastname = ""
            if name[1]:
                firstname = name[1]
            else:
                firstname = ""
            # Assumption it's the right one
            self.grampsp = p
            bd = self.get_gramps_date(EventType.BIRTH)
            # Remove empty month/day if needed to compare below with just a year potentially
            bd = format_year(bd)
            dd = self.get_gramps_date(EventType.DEATH)
            dd = format_year(dd)
            if verbosity >= 3:
                print(_("DEBUG: firstname: ")+firstname+_(" vs g_firstname: ")+self.g_firstname)
                print(_("DEBUG: lastname: ")+lastname+_(" vs g_lastname: ")+self.g_lastname)
                if not bd:
                    pbd = "None"
                else:
                    pbd = bd
                if not dd:
                    pdd = "None"
                else:
                    pdd = dd
                if not self.g_birthdate:
                    g_pbd = "None"
                else:
                    g_pbd = self.g_birthdate
                if not self.g_deathdate:
                    g_pdd = "None"
                else:
                    g_pdd = self.g_deathdate
                print(_("DEBUG: bd: ")+pbd+_(" vs g_bd: ")+g_pbd)
                print(_("DEBUG: dd: ")+pdd+_(" vs g_dd: ")+g_pdd)
            if firstname != self.g_firstname or lastname != self.g_lastname:
                # it's not the right person finally
                self.grampsp = None
                continue
            if not bd and not dd and not self.g_birthdate and not self.g_deathdate:
                # we skip a person for which we have no date at all
                # this may create duplicates, but is the best apparoach
                self.grampsp = None
                continue
            if bd == self.g_birthdate or dd == self.g_deathdate:
                self.gid = p.gramps_id
                if verbosity >= 2:
                    print(_("Found a Gramps Person: ")+self.g_firstname+' '+self.g_lastname+ " ("+self.gid+")")
                # Found it we can exit
                break
            else:
                # still not found
                self.grampsp = None

    def to_gramps(self):
        '''
        Push into Gramps the GPerson
        '''

        # Smart copy from Geneanet to Gramps inside GPerson
        self.smartcopy()

        with DbTxn("Geneanet import", db) as tran:
            db.disable_signals()
            grampsp = self.grampsp
            if not grampsp:
                if verbosity >= 2:
                    print(_("ERROR: Unable sync unknown Gramps Person"))
                return

            if self.sex == 'M':
                grampsp.set_gender(Person.MALE)
            elif self.sex == 'F':
                grampsp.set_gender(Person.FEMALE)
            else:
                grampsp.set_gender(Person.UNKNOWN)

            n = Name()
            n.set_type(NameType(NameType.BIRTH))
            n.set_first_name(self.firstname)
            s = n.get_primary_surname()
            s.set_surname(self.lastname)
            grampsp.set_primary_name(n)
    
            # We need to create events for Birth and Death
            for ev in ['birth', 'death']:
                self.get_or_create_event(grampsp,ev,tran)

            # Store the importation place as an Internet note
            if self.url != "":
                found = False
                for u in grampsp.get_url_list():
                    if u.get_type() == UrlType.WEB_HOME \
                    and u.get_path() == self.url:
                        found = True
                if not found:
                    url = Url()
                    url.set_description("Imported from Geneanet")
                    url.set_type(UrlType.WEB_HOME)
                    url.set_path(self.url)
                    grampsp.add_url(url)
 
            db.commit_person(grampsp,tran)
            db.enable_signals()
            db.request_rebuild()
 
    def from_gramps(self,gid):
        '''
        Fill a GPerson with its Gramps data
        '''

        GENDER = ['F', 'M', 'U']

        if verbosity >= 2:
            print(_("Calling from_gramps with gid: %s")%(gid))

        # If our gid was already setup and we didn't pass one
        if not gid and self.gid:
            gid = self.gid

        if verbosity >= 3:
            print(_("Now gid is: %s")%(gid))

        found = None
        try:
            found = db.get_person_from_gramps_id(gid)
            self.gid = gid
            self.grampsp = found
            if verbosity >= 2 and self.gid:
                print(_("Existing Gramps Person: %s")%(self.gid))
        except:
            if verbosity >= 1:
                print(_("WARNING: Unable to retrieve id %s from the gramps db %s")%(gid,gname))

        if not found:
            # If we don't know who this is, try to find it in Gramps 
            # This supposes that Geneanet data are already present in GPerson
            self.find_grampsp()
            # And if we haven't found it, create it in gramps
            if self.grampsp == None:
                self.create_grampsp()

        if self.grampsp.gender:
            self.sex = GENDER[self.grampsp.gender]
            if verbosity >= 2:
                print(_("Gender:"),self.sex)

        try:
            name = self.grampsp.primary_name.get_name().split(', ')
        except:
            name = [None, None]

        if name[0]:
            self.firstname = name[1]
        if name[1]:
            self.lastname = name[0]
        if verbosity >= 2:
            print(_("===> Gramps Name of %s: %s %s")%(self.gid,self.firstname,self.lastname))

        try:
            bd = self.get_gramps_date(EventType.BIRTH)
            if bd:
                if verbosity >= 2:
                    print(_("Birth:"),bd)
                self.birthdate = bd
            else:
                if verbosity >= 2:
                    print(_("No Birth date"))
        except:
            if verbosity >= 1:
                print(_("WARNING: Unable to retrieve birth date for id %s")%(self.gid))

        try:
            dd = self.get_gramps_date(EventType.DEATH)
            if dd:
                if verbosity >= 2:
                    print(_("Death:"),dd)
                self.deathdate = dd
            else:
                if verbosity >= 2:
                    print(_("No Death date"))
        except:
            if verbosity >= 1:
                print(_("WARNING: Unable to retrieve death date for id %s")%(self.gid))
        
        # Deal with the parents now, as they necessarily exist
        self.father = GPerson(self.level+1)
        self.mother = GPerson(self.level+1)
        try:
            fh = self.grampsp.get_main_parents_family_handle()
            if fh:
                if verbosity >= 3:
                    print(_("Family:"),fh)
                fam = db.get_family_from_handle(fh)
                if fam:
                    if verbosity >= 3:
                        print(_("Family:"),fam)

                # find father from the family
                fh = fam.get_father_handle()
                if fh:
                    if verbosity >= 3:
                        print(_("Father H:"),fh)
                    father = db.get_person_from_handle(fh)
                    if father:
                        if verbosity >= 1:
                            print(_("Father name:"),father.primary_name.get_name())
                        self.father.gid = father.gramps_id

                # find mother from the family
                mh = fam.get_mother_handle()
                if mh:
                    if verbosity >= 3:
                        print(_("Mother H:"),mh)
                    mother = db.get_person_from_handle(mh)
                    if mother:
                        if verbosity >= 1:
                            print(_("Mother name:"),mother.primary_name.get_name())
                        self.mother.gid = mother.gramps_id

        except:
            if verbosity >= 1:
                print(_("NOTE: Unable to retrieve family for id %s")%(self.gid))

    def add_spouses(self,level):
        '''
        Add all spouses for this person, with corresponding families
        returns all the families created in a list
        '''
        i = 0
        ret = []
        while i < len(self.spouseref):
            spouse = None
            # Avoid handling already processed spouses
            for s in self.spouse:
                if s.url == self.spouseref[i]:
                    spouse = s
                    break
            if not spouse:
                spouse = geneanet_to_gramps(None,level,None,self.spouseref[i])
                if spouse:
                    self.spouse.append(spouse)
                    spouse.spouse.append(self)
                    # Create a GFamily with them and do a Geaneanet to Gramps for it
                    if verbosity >= 2:
                        print(_("=> Initialize Family of ")+self.firstname+" "+self.lastname+" & "+spouse.firstname+" "+spouse.lastname)
                if self.sex == 'M':
                    f = GFamily(self,spouse)
                elif self.sex == 'F':
                    f = GFamily(spouse,self)
                else:
                    if verbosity >= 1:
                        print(_("Unable to Initialize Family of ")+self.firstname+" "+self.lastname+_(" sex unknown"))
                        break

                f.from_geneanet()
                f.from_gramps(f.gid)
                f.to_gramps()
                self.family.append(f)
                if spouse:
                    spouse.family.append(f)
                ret.append(f)
            i = i + 1
        return(ret)

    def recurse_parents(self,level):
        '''
        analyze the parents of the person passed in parameter recursively
        '''
        loop = False
        # Recurse while we have parents urls and level not reached
        if level <= LEVEL and (self.fref != "" or self.mref != ""):
            loop = True
            level = level + 1

            if self.father:
                geneanet_to_gramps(self.father,level,self.father.gid,self.fref)
                if self.mother:
                    self.mother.spouse.append(self.father)

                if verbosity >= 2:
                    print(_("=> Recursing on the parents of ")+self.father.firstname+" "+self.father.lastname)
                self.father.recurse_parents(level)

                if verbosity >= 2:
                    print(_("=> End of recursion on the parents of ")+self.father.firstname+" "+self.father.lastname)

            if self.mother:
                geneanet_to_gramps(self.mother,level,self.mother.gid,self.mref)
                if self.father:
                    self.father.spouse.append(self.mother)
                if verbosity >= 2:
                    print(_("=> Recursing on the mother of ")+self.mother.firstname+" "+self.mother.lastname)
                self.mother.recurse_parents(level)

                if verbosity >= 2:
                    print(_("=> End of recursing on the mother of ")+self.mother.firstname+" "+self.mother.lastname)

            # Create a GFamily with them and do a Geaneanet to Gramps for it
            if verbosity >= 2:
                print(_("=> Initialize Parents Family of ")+self.firstname+" "+self.lastname)
            f = GFamily(self.father,self.mother)
            f.from_geneanet()
            f.from_gramps(f.gid)
            f.to_gramps()
            if self.father:
                self.father.family.append(f)
            if self.mother:
                self.mother.family.append(f)

            # Deal with other spouses
            if spouses:
                fam = self.father.add_spouses(level)
                if ascendants:
                    for ff in fam:
                        if ff.gid != f.gid:
                            ff.mother.recurse_parents(level)
                if descendants:
                    for ff in fam:
                        if ff.gid != f.gid:
                            ff.recurse_children(level)
                fam = self.mother.add_spouses(level)
                if ascendants:
                    for mf in fam:
                        if mf.gid != f.gid:
                            mf.father.recurse_parents(level)
                if descendants:
                    for mf in fam:
                        if mf.gid != f.gid:
                            mf.recurse_children(level)


            # Now do what is needed depending on options
            if descendants:
                f.recurse_children(level)
            else:
                f.add_child(self)
    
        if not loop:
            if level > LEVEL:
                if verbosity >= 2:
                    print(_("Stopping exploration as we reached level ")+str(level))
            else:
                if verbosity >= 1:
                    print(_("Stopping exploration as there are no more parents"))
        return


def geneanet_to_gramps(p, level, gid, url):
    '''
    Function to create a person from Geneanet into gramps
    '''
    global progress

    # Create the Person coming from Geneanet
    if not p:
        p = GPerson(level)
    p.from_geneanet(url)

    # Create the Person coming from Gramps
    # Done after so we can try to find it in Gramps with the Geneanet data
    p.from_gramps(gid)

    # Check we point to the same person
    if gid != None:
        if (p.firstname != p.g_firstname or p.lastname != p.g_lastname) and (not force):
            print(_("Gramps   person: %s %s")%(p.firstname,p.lastname))
            print(_("Geneanet person: %s %s")%(p.g_firstname,p.g_lastname))
            if not GUIMODE:
                db.close()
                sys.exit(_("Do not continue without force"))
            else:
                return(None)

        # Fix potential empty dates
        if p.g_birthdate == "":
            p.g_birthdate = None
        if p.birthdate == "":
            p.birthdate = None
        if p.g_deathdate == "":
            p.g_deathdate = None
        if p.deathdate == "":
            p.deathdate = None

        if p.birthdate == p.g_birthdate or p.deathdate == p.g_deathdate or force:
            pass
        else:
            print(_("Gramps   person birth/death: %s / %s")%(p.birthdate,p.deathdate))
            print(_("Geneanet person birth/death: %s / %s")%(p.g_birthdate,p.g_deathdate))
            if not GUIMODE:
                db.close()
                sys.exit(_("Do not continue without force"))
            else:
                print(_("Please fix the person in gramps"))
                return(None)

    # Copy from Geneanet into Gramps and commit
    p.to_gramps()
    if GUIMODE:
        progress.set_header(_("Adding Gramps Person %s %s (%s | %s)")%(p.firstname,p.lastname,p.birthdate,p.deathdate))
        progress.step()
    return(p)

def g2gaction(gid,purl):
    global progress

    # Create the first Person 
    gp = geneanet_to_gramps(None,0,gid,purl)
    
    if gp != None:
        if ascendants:
            gp.recurse_parents(0)
    
        fam = []
        if spouses:
            fam = gp.add_spouses(0)
        else:
            # TODO: If we don't ask for spouses, we won't get children at all
            pass

        if descendants:
            for f in fam:
                f.recurse_children(0)
    if GUIMODE:
        progress.close()
 
def main():

    # global allow local modification of these global variables
    global db
    global gname
    global verbosity
    global force
    global ascendants
    global descendants
    global spouses
    global LEVEL


    parser = argparse.ArgumentParser(description=_("Import Geneanet subtrees into Gramps"))
    parser.add_argument("-v", "--verbosity", action="count", default=0, help=_("Increase verbosity"))
    parser.add_argument("-a", "--ascendants", default=False, action='store_true', help=_("Includes ascendants (off by default)"))
    parser.add_argument("-d", "--descendants", default=False, action='store_true', help=_("Includes descendants (off by default)"))
    parser.add_argument("-s", "--spouses", default=False, action='store_true', help=_("Includes all spouses (off by default)"))
    parser.add_argument("-l", "--level", default=2, type=int, help=_("Number of level to explore (2 by default)"))
    parser.add_argument("-g", "--grampsfile", type=str, help=_("Full path of the Gramps database (under $HOME/.gramps/grampsdb)"))
    parser.add_argument("-i", "--id", type=str, help=_("ID of the person to start from in Gramps"))
    parser.add_argument("-f", "--force", default=False, action='store_true', help=_("Force processing"))
    parser.add_argument("searchedperson", type=str, nargs='?', help=_("Url of the person to search in Geneanet"))
    args = parser.parse_args()

    if args.searchedperson == None:
        #purl = 'https://gw.geneanet.org/agnesy?lang=fr&pz=hugo+mathis&nz=renard&p=marie+sebastienne&n=helgouach'
        #purl = 'https://gw.geneanet.org/agnesy?lang=fr&n=queffelec&oc=17&p=marie+anne'
        print(_("Please provide a person to search for"))
        sys.exit(-1)
    else:
        purl = args.searchedperson

    gname = args.grampsfile
    verbosity = args.verbosity
    force = args.force
    ascendants = args.ascendants
    descendants = args.descendants
    spouses = args.spouses
    LEVEL = args.level
	
    # TODO: do a backup before opening and remove fixed path
    if gname == None:
        #gname = "Test import"
        # To be searched in ~/.gramps/recent-files-gramps.xml
        #gname = "/users/bruno/.gramps/grampsdb/5ec17554"
        print(_("Please provide a grampsfile to search into"))
        sys.exit(-1)
    try:
        dbstate = DbState()
        climanager = CLIManager(dbstate, True, None)
        climanager.open_activate(gname)
        db = dbstate.db
    except:
        ErrorDialog(_("Opening the '%s' database") % gname,
                    _("An attempt to convert the database failed. "
                      "Perhaps it needs updating."), parent=self.top)
        sys.exit(-1)
    	
    gid = args.id
    if gid == None:
        gid = "0000"
    gid = "I"+gid
    
    ids = db.get_person_gramps_ids()
    for i in ids:
        if verbosity >= 3:
            print(_("DEBUG: existing gramps id:")+i)
    
    if verbosity >= 1 and force:
        print(_("WARNING: Force mode activated"))
        time.sleep(TIMEOUT)
    
    g2gaction(gid,purl)
   
    db.close()
    sys.exit(0)
    

if __name__ == '__main__':
    main()
