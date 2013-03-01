# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C)2007-2009  B. Malengier
# Copyright (C) 2012       Eric Doutreleau
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


"Check and suggest edits to places"

#------------------------------------------------------------------------
#
# standard python modules
#
#------------------------------------------------------------------------
import os
import stat
import re

#------------------------------------------------------------------------
#
# GTK/GI modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import Gdk

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.mime import *
from gramps.gui.glade import Glade
from gramps.gui.plug import tool as Tool
from gramps.gui.plug import PluginWindows
from gramps.gui.display import display_url
from gramps.gui.managedwindow import ManagedWindow
from gramps.gen.lib import Location
from gramps.gen.db import DbTxn
from gramps.gen.filters import GenericFilterFactory, rules
GenericPlaceFilter = GenericFilterFactory('Place')

from gramps.gen.filters.rules.place import *
from gramps.gui.dialog import OkDialog, WarningDialog
from gramps.gen.utils.place import conv_lat_lon
from gramps.gen.errors import WindowActiveError

from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.get_addon_translator(__file__).gettext

from gramps.gen.constfunc import cuni, lin

import gramps.gui.utils
if hasattr(gramps.gui.utils, "ProgressMeter"):
    ProgressMeter = gramps.gui.utils.ProgressMeter
else:
    raise ImportError("can't find ProgressMeter")

#------------------------------------------------------------------------
#
# 
#
#------------------------------------------------------------------------
class PlaceCompletion(Tool.Tool, ManagedWindow):

    def __init__(self, dbstate, uistate, options_class, name, callback=None):

        Tool.Tool.__init__(self, dbstate, options_class, name)

        self.dbstate = dbstate
        self.callback = callback
        self.active_name = _("Place Completion by parsing, file lookup and"
                             " batch setting of place attributes")

        ManagedWindow.__init__(self, uistate, [], self.__class__)
        base = os.path.dirname(__file__)
        glade_file = base + os.sep + "placecompletion.glade"

        if lin:
            import locale
            #locale.setlocale(locale.LC_ALL, '')
            # This is needed to make gtk.Builder work by specifying the
            # translations directory
            locale.bindtextdomain("addon", base + "/locale")
            
            self.glade = Gtk.Builder()
            self.glade.set_translation_domain("addon")
            
            from gi.repository import GObject
            GObject.GObject.__init__(self.glade)
            
            self.glade.add_from_file(glade_file)
        else:
            self.glade = Glade(glade_file)

        window = self.glade.get_object("top")
            
        self.tree = self.glade.get_object("tree1")
        self.tree.set_headers_visible(False)
            
        self.glade.connect_signals({
            "destroy_passed_object" : self.close,
            "on_help_clicked"       : self.on_help_clicked,
            "on_find_clicked"       : self.on_find_clicked,
            "on_apply_clicked"      : self.on_apply_clicked,
            "on_google_maps_clicked": self.on_google_clicked,
            })
                
        self.set_window(window,None,self.active_name)
            
        renderer = Gtk.CellRendererText()
        #following does not work with foreground (KDE issue??), so set background
        col = Gtk.TreeViewColumn('',renderer,text=0,background=3)
        self.tree.append_column(col)
        
        self.tree.connect('event',self.button_press_event)
        #some colors from X11/rgb.txt
        self.colornormal = "white" #"black"
        self.coloroverwrite = "orange"
             
        #widgets we need to query
        self.filter = self.glade.get_object("filter")
        self.countryfilter = self.glade.get_object("countryfilter")
        self.statefilter = self.glade.get_object("statefilter")
        self.countyfilter = self.glade.get_object("countyfilter")
        self.cityfilter = self.glade.get_object("cityfilter")
        self.parishfilter = self.glade.get_object("parishfilter")
        self.rectlatfilter= self.glade.get_object("rectlat")
        self.rectlonfilter= self.glade.get_object("rectlon")
        self.rectwidthfilter= self.glade.get_object("rectwidth")
        self.rectheightfilter= self.glade.get_object("rectheight")
        self.latlonfile = self.glade.get_object("filecmb")
        self.latlonfind = self.glade.get_object("cmbe_latlon_find")
        self.cmbetitleregex = self.glade.get_object("cmbe_titleregex")
        self.titleconstruct = self.glade.get_object("titleconstruct")
        self.titleconstruct_custom = self.glade.get_object("titleconstruct_custom")
        self.latlonconv = self.glade.get_object("latlonconv")
        self.countryset = self.glade.get_object("countryset")
        self.stateset = self.glade.get_object("stateset")
        self.countyset = self.glade.get_object("countyset")
        self.cityset = self.glade.get_object("cityset")
        self.parishset = self.glade.get_object("parishset")
        self.zipset = self.glade.get_object("zipset")
        
        #load options from previous call and set up combo boxes
        filter_num = max(0,self.options.handler.options_dict['filternumber'])
        filters = self.options.get_report_filters()
        if filter_num > len(filters)-1 :
            filter_num = 0  # 0 filter will be all places
        self.placefilter = filters[filter_num]
        self.fill_combobox_index(self.filter, 
                        [fil.get_name() for fil in filters], filter_num)
        self.countryfilter.set_text(
                        self.options.handler.options_dict['countryfilter'])
        self.statefilter.set_text(
                        self.options.handler.options_dict['statefilter'])
        self.countyfilter.set_text(
                        self.options.handler.options_dict['countyfilter'])
        self.cityfilter.set_text(
                        self.options.handler.options_dict['cityfilter'])
        self.parishfilter.set_text(
                        self.options.handler.options_dict['parishfilter'])
        self.rectlatfilter.set_text(
                        self.options.handler.options_dict['centerlat'])
        self.rectlonfilter.set_text(
                        self.options.handler.options_dict['centerlon'])
        self.rectwidthfilter.set_text(
                        self.options.handler.options_dict['rectwidth'])
        self.rectheightfilter.set_text(
                        self.options.handler.options_dict['rectheight'])
        self.fill_comboboxentry(self.latlonfind, _options.latlonfind,
                    self.options.handler.options_dict['latlonfind'])
        if self.options.handler.options_dict['latlonfile'] not in ['', 
                                                        None, 'None'] : 
            #print 'file', self.options.handler.options_dict['latlonfile'], \
                    #self.options.handler.options_dict['latlonfile'] == 'None'
            self.latlonfile.set_filename(
                self.options.handler.options_dict['latlonfile'])
        self.fill_comboboxentry(self.cmbetitleregex, _options.titleregex,
                    self.options.handler.options_dict['titleregex'])
        self.fill_combobox(self.titleconstruct,_options.titleconstruct,
            self.options.handler.options_dict['titleconstruct'])
        self.titleconstruct_custom.set_text(
                        self.options.handler.options_dict['titleconstruct_custom'])
        self.fill_combobox(self.latlonconv,_options.latlonconv,
            self.options.handler.options_dict['latlonconv'])
        self.countryset.set_text(
                        self.options.handler.options_dict['countryset'])
        self.stateset.set_text(
                        self.options.handler.options_dict['stateset'])
        self.countyset.set_text(
                        self.options.handler.options_dict['countyset'])
        self.cityset.set_text(
                        self.options.handler.options_dict['cityset'])
        self.parishset.set_text(
                        self.options.handler.options_dict['parishset'])
        self.zipset.set_text(
                        self.options.handler.options_dict['zipset'])
                
        #set up the possible checks, a check contains:
        #   check[0] the method to call on place, returns text, oldval, newval
        self.placechecklist = [self.find_latlon, self.match_regex_title,
                    self.construct_title, self.convert_latlon, self.set_data
                    ]
        self.regextitlegroups = [('street'), ('city'), ('parish'), 
                    ('county'), ('state'), ('country'), ('zip'), ('title')]
        
        #some extra init of needed datafields
        self.latlonfile_datastr = None
        self.county_lookup = {}

#set translated labels
        labelids = ['label28', 'label29','label30', 'label31', 'label32', 'label33', 'label34', 'label35'
                          , 'label36', 'label37', 'label38', 'label39', 'label40', 'label41'
                          , 'label42', 'label43', 'label16', 'label20', 'label19', 'label45'
                          , 'label18', 'label22', 'label23', 'label24', 'label25',  'label1', 'label44'  ]
        for labelid in labelids:
             try:
                 label = self.glade.get_object(labelid)
             except:
                 continue
             label.set_text(_(label.get_text()))
       
        self.show()
        
    def group_get(self, place, group):
        ''' Get the value corresponding to a group
            The special groupname #latlon is allowed, returning lat/lon
        '''
        if group == ('title') :
            return place.get_title()
        elif group == ('latitude') :
            return place.get_latitude()
        elif group == ('longitude') :
            return place.get_longitude()
        elif group == '#latlon' :
            return (place.get_latitude() , place.get_longitude())
        else :
            loc = place.get_main_location()
            if group == ('city') :
                return loc.get_city()
            elif group == ('country') :
                return loc.get_country()
            elif group == ('county') :
                return loc.get_county()
            elif group == ('state') :
                return loc.get_state()
            elif group == ('street') :
                return loc.get_street()
            elif group == ('parish') :
                return loc.get_parish()
            elif group == ('zip') :
                return loc.get_postal_code()
            else :
                ErrorDialog(_("Error in PlaceCompletion.py"),
                        _("Non existing group used in get"))
                return '';
            
    def group_set(self, place, group, val):
        ''' Sets the group in place with value val
            returns place
            Allow special group #latlon, for which val[0] is lat, val[1] is lon 
        '''
        if not group :
            return place
        if group == ('title') :
            place.set_title(val)
        elif group == ('latitude') :
            place.set_latitude(val)
        elif group == ('longitude') :
            place.set_longitude(val)
        elif group == '#latlon' :
            place.set_latitude(val[0])
            place.set_longitude(val[1])
        else :
            loc = place.get_main_location()
            if loc == None :
                loc = Location()
            if group == ('city') :
                loc.set_city(val)
            elif group == ('country') :
                loc.set_country(val)
            elif group == ('county') :
                loc.set_county(val)
            elif group == ('state') :
                loc.set_state(val)
            elif group == ('street') :
                loc.set_street(val)
            elif group == ('parish') :
                loc.set_parish(val)
            elif group == ('zip') :
                loc.set_postal_code(val)
            else :
                ErrorDialog(_("Error in PlaceCompletion.py"),
                        _("Non existing group used in set"))
            place.set_main_location(loc)
        return place
            
    def fill_combobox(self, cmb, namelistopt, default) :
        store = Gtk.ListStore(str)
        cell = Gtk.CellRendererText()
        cmb.pack_start(cell,True)
        cmb.add_attribute(cell,'text',0)
        cmb.set_model(store)
        index = 0
        for item in namelistopt:
            store.append(row=[item[2]])
            if item[0] == default:
                cmb.set_active(index)
            index = index + 1
            
    def fill_combobox_index(self, cmb, namelistind, defaultindex) :
        store = Gtk.ListStore(str)
        cell = Gtk.CellRendererText()
        cmb.pack_start(cell,True)
        cmb.add_attribute(cell,'text',0)
        index = 0
        for item in namelistind:
            store.append(row=[item])
        cmb.set_model(store)    
        cmb.set_active(defaultindex)
        return cmb
    
    def fill_comboboxentry(self, cmbe, namelistopt, default) :
        '''
            default is the key in the combobox, or a text with what should 
            be in the text field
        '''
        store = Gtk.ListStore(str,str)
        index = 0
        indexactive = None
        for data in namelistopt:
            if data:
                store.append(row=[data[0], data[2]])
                if data[0] == default : 
                    indexactive=index
                index += 1
        
        cmbe.set_model(store)
        cmbe.set_entry_text_column(1)
        #completion = Gtk.EntryCompletion()
        #completion.set_model(store)
        #completion.set_minimum_key_length(1)
        #completion.set_text_column(0)
        #cmbe.get_child().set_completion(completion)
        if indexactive != None :
            cmbe.set_active(indexactive)
        else :
            if default :
                cmbe.get_child().set_text(default)
        
    def build_menu_names(self,obj):
        return (self.active_name,_("Places tool"))
    
    def on_help_clicked(self,obj):
        """Display the relevant portion of GRAMPS manual"""
        display_url('http://www.gramps-project.org/wiki/index.php?title=Place_completion_tool')
        #display_help('tools-ae')
        
    def on_google_clicked(self,obj):
        self.google()

    def on_find_clicked(self,obj):
        #save entries in the options dir
        self.options.handler.options_dict['filternumber'] \
                = self.filter.get_active()
        self.options.handler.options_dict['countryfilter'] \
                = self.countryfilter.get_text()
        self.options.handler.options_dict['statefilter'] \
                = self.statefilter.get_text()
        self.options.handler.options_dict['countyfilter'] \
                = self.countyfilter.get_text()
        self.options.handler.options_dict['cityfilter'] \
                = self.cityfilter.get_text()
        self.options.handler.options_dict['parishfilter'] \
                = self.parishfilter.get_text()
        self.options.handler.options_dict['centerlat'] \
                = self.rectlatfilter.get_text()
        self.options.handler.options_dict['centerlon'] \
                = self.rectlonfilter.get_text()
        self.options.handler.options_dict['rectwidth'] \
                = self.rectwidthfilter.get_text()
        self.options.handler.options_dict['rectheight'] \
                = self.rectheightfilter.get_text()
        activefind = self.latlonfind.get_active()
        entryfind = self.latlonfind.get_child().get_text()
        findregex = None
        self.options.handler.options_dict['latlonfind'] = ''
        if activefind != -1 :
            #first entry is 'Don't search'
            if activefind != 0 :
                findregex = _options.latlonfind[activefind][3]
                self.options.handler.options_dict['latlonfind'] = _options.latlonfind[activefind][0]
        elif entryfind :
            findregex = entryfind
            self.options.handler.options_dict['latlonfind'] = findregex
        self.options.handler.options_dict['latlonfile'] = \
                self.latlonfile.get_filename()
                
        activetitleregex = self.cmbetitleregex.get_active()
        entrytitleregex = self.cmbetitleregex.get_child().get_text()
        titleregex = None
        self.options.handler.options_dict['titleregex'] = ''
        if activetitleregex != -1 :
            titleregex = _options.titleregex[activetitleregex][3]
            self.options.handler.options_dict['titleregex'] = \
                _options.titleregex[activetitleregex][0]
        elif entrytitleregex :
            titleregex = entrytitleregex
            self.options.handler.options_dict['titleregex'] = titleregex
        self.options.handler.options_dict['titleconstruct'] = \
                _options.titleconstruct[self.titleconstruct.get_active()][0]
        self.options.handler.options_dict['titleconstruct_custom'] \
                = cuni(self.titleconstruct_custom.get_text())
        self.options.handler.options_dict['latlonconv'] = \
                _options.latlonconv[self.latlonconv.get_active()][0]
        
        self.options.handler.options_dict['countryset'] \
                = cuni(self.countryset.get_text())
        self.options.handler.options_dict['stateset'] \
                = cuni(self.stateset.get_text())
        self.options.handler.options_dict['countyset'] \
                = cuni(self.countyset.get_text())
        self.options.handler.options_dict['cityset'] \
                = cuni(self.cityset.get_text())
        self.options.handler.options_dict['parishset'] \
                = cuni(self.parishset.get_text())
        self.options.handler.options_dict['zipset'] \
                = cuni(self.zipset.get_text())
                 
        # Save options
        self.options.handler.save_options()
        
        # Compile title regex
        self.matchtitle = None
        if titleregex :
            try:
                #compile regex aware of locale and unicode
                self.matchtitle = re.compile(titleregex,re.U|re.L)
                #set groups mentioned in the regex
                self.matchtitlegroups =[]
                for group in self.regextitlegroups :
                    if titleregex.find(r'(?P<'+group+r'>') != -1 :
                        self.matchtitlegroups.append(group)
            except:
                self.matchtitle = None
                WarningDialog(_('Non Valid Title Regex'),
                    _('Non valid regular expression given to match title. Quiting.'),
                    self.window)
                return
        
        # Compile Regex file search partially
        self.matchlatlon = None
        self.extrafindgroup = []  #find always finds lat/lon, what extra groups?
        possibleextrafindgroups=[('county'), ('state')]
        if findregex :
            try:
                #compile regex aware of locale and unicode
                self.matchlatlon = re.compile(findregex,re.U|re.L|re.M)
                latlongroup = ['lat', 'lon'] 
                for group in latlongroup :
                    if findregex.find(r'(?P<'+group+r'>') == -1 :
                        WarningDialog(_('Missing regex groups in match lat/lon'),
                    _('Regex groups %(lat)s and %(lon)s must be present in lat/lon match. Quiting') 
                                % {'lat' : latlongroup[0], 'lon' : latlongroup[1]},
                            self.window)
                        return
                    #check if extra data can be extracted from file
                    for group in possibleextrafindgroups :
                        if findregex.find(r'(?P<'+group+r'>') != -1 :
                            self.extrafindgroup.append(group)
            except:
                self.matchlatlon = None
                WarningDialog(_('Non valid regex for match lat/lon'),
                    _('Non valid regular expression given to find lat/lon. Quiting.'),
                    self.window)
                return
        if not (self.matchlatlon and 
                self.options.handler.options_dict['latlonfile']) :
            # no need to try to lookup lat and lon
            self.matchlatlon = None
            
            
        #populate the tree
        self.make_new_model()
        
    def make_new_model(self):
        # model contains 4 colums: text to show, place handle, action, color
        self.model = Gtk.TreeStore(str, object, object, str)
        self.tree.set_model(self.model)
        self.populate_tree()
        self.tree.expand_all()

    def populate_tree(self):
        generic_filter = GenericPlaceFilter()
        filters = self.options.get_report_filters()
        #index 0 is all places
        if (self.options.handler.options_dict['filternumber'] == 0) :
            generic_filter.add_rule(rules.place.AllPlaces([]))
        #index 1 is nolatlon
        elif (self.options.handler.options_dict['filternumber'] == 1):
            generic_filter.add_rule(rules.place.HasNoLatOrLon([]))
        #other index are custom filters
        else :
            try:
                filter = filters[self.options.handler.options_dict['filternumber']]
                rule = MatchesFilter([filter.get_name()])
                generic_filter.add_rule(rule)
            except IndexError :
                pass

        cof = cuni(self.options.handler.options_dict['countryfilter']).strip()
        stf = cuni(self.options.handler.options_dict['statefilter']).strip()
        cuf = cuni(self.options.handler.options_dict['countyfilter']).strip()
        cif = cuni(self.options.handler.options_dict['cityfilter']).strip()
        paf = cuni(self.options.handler.options_dict['parishfilter']).strip()
        if (cof or stf or cuf or cif or paf):
            # Name, Street, Locality, City, County, State, Country, ZIP/Postal Code, Church Parish
            rule = HasPlace(['','','',cif,cuf,stf,cof,'',paf])
            generic_filter.add_rule(rule)  
        rclat = cuni(self.options.handler.options_dict['centerlat']).strip()
        rclon = cuni(self.options.handler.options_dict['centerlon']).strip()
        rwid = cuni(self.options.handler.options_dict['rectwidth']).strip()
        rhei = cuni(self.options.handler.options_dict['rectheight']).strip()
        if (rclat or rwid  or rclon or rhei):
            rule = InLatLonNeighborhood([rclat,rclon,rhei,rwid])
            generic_filter.add_rule(rule)
            
        ind_list = self.db.get_place_handles(sort_handles=True)
        
        self.nrplaces_in_tree = len(ind_list)
        # Populating might take a while, add a progress bar
        progress = ProgressMeter(
                                _("Finding Places and appropriate changes"),'')
        #apply the filter
        progress.set_pass(_('Filtering'),1)
        progress.step()
        ind_list = generic_filter.apply(self.db,ind_list)
        #
        #load latlonfile
        if self.matchlatlon :
            filename = self.options.handler.options_dict['latlonfile']
            if self.check_errors(filename):
                return
            # check if file is a text file is not possible, assume it is
            progress.set_pass(_('Loading lat/lon file in Memory...'),1)
            self.load_latlon_file(filename)
            self.load_counties_file()
            progress.step()
            
        #do all the checks and fill up model
        progress.set_pass(_('Examining places'),self.nrplaces_in_tree)
        
        sib_id = None
        for handle in ind_list :
            progress.step()
            place = self.db.get_place_from_handle(handle)
            sib_id = self.insert_place_in_tree(sib_id, place)
                
        progress.close()
    
    def set_parent_model_text(self, id, place) :
        text = ''
        if place.get_title() :
            text += place.get_title()
        if place.get_main_location().get_city().strip() or \
                place.get_main_location().get_state().strip() or \
                place.get_main_location().get_country().strip() :
            text += ' ('
            div = ''
            if place.get_main_location().get_city().strip() :
                text += _('City')+': '+place.get_main_location().get_city()
                div = ', '
            if place.get_main_location().get_state().strip() :
                text += div + _('State')+': '+ \
                            place.get_main_location().get_state()
                div = ', '
            if place.get_main_location().get_country().strip() :
                text += div + _('Country')+': '+ \
                        place.get_main_location().get_country()
                div = ', '
            text += ')'
        self.model.set(id, 0, text)
        self.model.set(id, 1, place.get_handle())
        self.model.set(id, 2, '')
        self.model.set(id, 3, self.colornormal)
        
    def set_child_model_text(self, id, place, action, olddata) :
        groupname = action[0]
        newval = action[1]
        if newval == None :
            # a line of text, do nothing
            newval = 'no change'
        if groupname == '#latlon' :
            self.model.set(id, 0, ('lat')+r'/'+('lon') + ' :' \
                                + olddata
                                + ' -> ' + newval[0]+r'/'+newval[1])
        else :
            self.model.set(id, 0, groupname + ' :' \
                                + olddata\
                                + ' -> ' + newval)
        self.model.set(id, 1, place.handle)
        self.model.set(id, 2, action)
        overwrite = False
        if olddata.strip() != '' :
            self.model.set(id, 3, self.coloroverwrite)
            overwrite = True
        else : 
            self.model.set(id, 3, self.colornormal)
        return overwrite
        
    def insert_place_in_tree(self, prev_id, place) :
        sib_id = self.model.insert_after(None, prev_id)
        self.set_parent_model_text(sib_id, place)
        prev_id = None
        overwrite = False
        # the filters are applied progressively, updating the place as changed
        #  by the filter that ran before it.
        for placecheck in self.placechecklist :
            oldval, newval, action, place = placecheck(place)
            prev_id, overwrite = self.add_check_to_tree(sib_id, 
                        prev_id, place, 
                        oldval, newval, action )
        if overwrite :
            self.model.set(sib_id, 3, self.coloroverwrite)
        else :
            self.model.set(sib_id, 3, self.colornormal)
        
        return sib_id
            
    def add_check_to_tree(self, parent_id, sib_id, place, 
                                oldval, newval, action):
        overwrite = False
        for dataold, datanew, dataaction in  \
                zip(oldval,newval,action) :
            if dataold != datanew :
                old = dataold
                if dataold.strip() == '' :
                    old = r"' '"
                elif dataold == None :
                    old = ''
                sib_id = self.model.insert_after(parent_id, sib_id)
                overwrite =  \
                        self.set_child_model_text(sib_id, place
                                            ,dataaction,dataold)
        return sib_id, overwrite
    
    def button_press_event(self,obj,event):
        from gramps.gui.editors import EditPlace

        if event.type == getattr(Gdk.EventType, "2BUTTON_PRESS") and event.button == 1:
            store, node = self.tree.get_selection().get_selected()
            if node:
                #only when non empty tree view you are here
                place_handle = store.get_value(node, 1)
                place = self.db.get_place_from_handle(place_handle)
                action = store.get_value(node,2)
                if action :
                    if action[1] != None :
                        place = self.group_set(place, action[0], action[1] )
                else :
                    #we are in a parent node, go over children nodes if present
                    index = 0
                    while store.iter_nth_child(node, index):
                        nodechild = store.iter_nth_child(node, index)
                        action = store.get_value(nodechild,2)
                        if action :
                            if action[1] != None :
                                place = self.group_set(place, 
                                                action[0], action[1] )
                        index += 1
                            
                try :
                    EditPlace(self.dbstate, self.uistate, self.track, place,
                           self.this_callback)
                except WindowActiveError :
                    pass
                        
        if event.type == getattr(Gdk.EventType, "KEY_PRESS") and \
                event.keyval == Gtk.keysyms.Delete:
            selection = self.tree.get_selection()
            store, node = selection.get_selected()
            if node :
                path = store.get_path(node)
                store.remove(node)
                # set selection to the next item
                selection.select_path(path)
                # if last of a path was deleted, the above gave no result
                # select next item if not empty list
                if not selection.path_is_selected(path):
                    row = path[0]-1
                    # test case for empty lists
                    if row >= 0:
                        selection.select_path((row,))
                        
        if event.type == getattr(Gdk.EventType, "KEY_PRESS") and \
                event.keyval == Gtk.keysyms.Tab:
            #call up google maps
            self.google()
            
                
            
    def google(self):
        from gramps.gui.display import display_url

        store, node = self.tree.get_selection().get_selected()
        if node:
            #only when non empty tree view you are here
            place_handle = store.get_value(node, 1)
            place = self.db.get_place_from_handle(place_handle)
            action = store.get_value(node,2)
            if action :
                #do the action on the place, this will set the new lat/lon
                if action[1] != None :
                    place = self.group_set(place, action[0], action[1] )
            descr = place.get_title()
            longitude = place.get_longitude()
            latitude = place.get_latitude()
            latitude,longitude = conv_lat_lon(latitude,longitude,"D.D8")
            city = place.get_main_location().get_city()
            country = place.get_main_location().get_country()

            if longitude and latitude:
                path = "http://maps.google.com/?sll=%s,%s&z=15" % (latitude,longitude)
            elif city and country:
                path = "http://maps.google.com/maps?q=%s,%s" % (city,country)
            else:
                path = "http://maps.google.com/maps?q=%s" % '+'.join(descr.split())
            display_url(path)
                
    def on_apply_clicked(self,obj):
        '''execute all the actions in the treeview
        '''
        modified = 0
        save_place = False

        with DbTxn(_("Set Tag"), self.db, batch=True) as self.trans:
            self.db.disable_signals()
            progress = ProgressMeter(_('Doing Place changes'),'')
            #we do not know how many places in the treeview, and counting would
            # mean transversing the tree. Set the progress to the possible maximum
            progress.set_pass('',self.db.get_number_of_places())

            store = self.tree.get_model()
            if store:
                node  = store.get_iter_first()
            else:
                node = None
            while node :
                save_place = False
                place_handle = store.get_value(node, 1)
                place = self.db.get_place_from_handle(place_handle)
                action = store.get_value(node,2)
                if action :
                    #action None means do nothing
                    if action[1] != None :
                        place = self.group_set(place, action[0], action[1] )
                        save_place = True
                else :
                    #we are in a parent node, go over children nodes if present
                    index = 0
                    while store.iter_nth_child(node, index):
                        nodechild = store.iter_nth_child(node, index)
                        action = store.get_value(nodechild,2)
                        if action :
                            if action[1] != None :
                                place = self.group_set(place, action[0], action[1] )
                                save_place = True
                        index += 1
            
                if save_place:
                    modified += 1
                    self.db.commit_place(place,self.trans)
                    progress.step()
                #go to next on same level
                node = store.iter_next(node)
                
            progress.close()
            self.db.enable_signals()
            self.db.request_rebuild()
        
        if modified == 0:
            msg = _("No place record was modified.")
        elif modified == 1:
            msg = _("1 place record was modified.")
        else:
            msg = _("%d place records were modified.") % modified
        OkDialog(_('Change places'),msg,self.window)
        
        #populate the tree --> CHANGE !! empty the tree model instead!
        #self.make_new_model()
        self.tree.set_model(None)

    def this_callback(self, obj):
        '''after edit place, this is called: remake the tree place entry with
            the stored actions (new values remain the same, old can change)
        '''
        self.callback()
        handle = obj.get_handle()
        node = self.find_place_in_model(handle)
        store = self.tree.get_model()
        if node :
            # we rerun the actions on this model and change the rows if needed
            self.set_parent_model_text(node,obj)
            overwrite = False
            index = 0
            while store.iter_nth_child(node, index):
                nodechild = store.iter_nth_child(node, index)
                action = store.get_value(nodechild,2)
                if action : 
                    dataold = self.group_get(obj, action[0])
                    #check if still something is changing or not :
                    if dataold == action[1] :
                        #remove this line as nothing changes anymore
                        store.remove(nodechild)
                        #go to next child, index remains the same due to deletion
                        continue
                    if action[1] == None :
                        #remove this line, the line was text, user must do 
                        # find again to have the text reappear correctly
                        store.remove(nodechild)
                        #go to next child, index remains the same due to deletion
                        continue
                    if action[0] == '#latlon' :
                        dataold = dataold[0]+r'/'+dataold[1]
                    overw = self.set_child_model_text(nodechild
                                    , obj, action, dataold)
                    if overw : overwrite = True
                    # update the object in memory
                    if action[1] != None :
                        obj = self.group_set(obj, action[0], action[1] )
                    index += 1
            # if overwrite, set color of parent node
            if overwrite :
                self.model.set(node, 3, self.coloroverwrite)
        #self.make_new_model()
        
    def find_place_in_model(self, handle) :
        ''' returns a treeiter pointing at parent node corresponding to handle
            or None if not found
        '''
        store = self.tree.get_model()
        node  = store.get_iter_first()
        while node:
            handleparent = store.get_value(node,1)
            if handleparent == handle :
                return node
            node = store.iter_next(node)
        return None
        
    def check_errors(self,filename):
        """
        This methods runs common error checks and returns True if any found.
        In this process, warning dialog can pop up.
        """
        if len(filename) == 0:
            return True
        elif os.path.isdir(filename):
            QuestionDialog.ErrorDialog(
                _('Cannot open file'), 
                _('The selected file is a directory, not '
                  'a file.'))
            return True
        elif os.path.exists(filename):
            if not os.access(filename, os.R_OK):
                QuestionDialog.ErrorDialog(
                    _('Cannot open file'), 
                    _('You do not have read access to the selected '
                      'file.'))
                return True
            elif not stat.S_ISREG(os.stat(filename)[stat.ST_MODE]):
                QuestionDialog.ErrorDialog(
                    _('Cannot open file'), 
                    _('The file you want to access is not a regular file.'))
                return True
        else :
            # file does not exist
            QuestionDialog.ErrorDialog(
                    _('Cannot open file'), 
                    _('The file does not exist.'))
            return True

        return False
        
    def load_counties_file(self):
        import codecs
        filename = os.path.join(os.path.dirname(__file__), 'counties.txt')
        county_file = codecs.open(filename, 'r', 'utf-8')
        line = county_file.readline()
        while line:
            fields = line.replace('\n', '').split('\t')
            if (not line.startswith('#')) and (len(fields) > 1):
                county = fields[0]
                codes = fields[1].split(',')
                self.county_lookup[county] = codes
            line = county_file.readline()
        county_file.close()

    def load_latlon_file(self, filename):
        import codecs
        if self.latlonfile_datastr :
            # free the space in memory  --- HOW ???
            self.latlonfile_datastr = None
        #codecs.open( "someFile", "r", "utf-8" )
        try :
            infile = codecs.open(filename, 'r',"utf-8")
            self.latlonfile_datastr = infile.read()
        except UnicodeDecodeError, reason :
            #mention problem, and try to continu:
            print reason
            msg = 'There was a problem reading the file: '+str(reason)+'\n' \
                    +'A second attempt will be made, ignoring errors...'
            OkDialog(_('Problem reading file'),msg,self.window)
            infile = codecs.open(filename, 'r',"utf-8",errors='ignore')
            self.latlonfile_datastr = infile.read()
        infile.close()
    
    def match_regex_title(self,place) :
        valoud = []
        valnew = []
        valaction = []
        if self.matchtitle :
            vals = self.matchtitle.match(place.get_title())
            if vals :
                for groupname in self.matchtitlegroups :
                    valoud.append(self.group_get(place, groupname))
                    valnew.append(vals.group(groupname))
                    valaction.append([groupname, vals.group(groupname)])
                    #do the action on the place in memory:
                    place = self.group_set(place, groupname, 
                                    vals.group(groupname))
        return valoud, valnew, valaction, place
    
    def find_latlon(self, place) :
        valoud = []
        valnew = []
        valaction = []
        if not self.matchlatlon :
            return valoud, valnew, valaction, place
        # we need to lookup the latitude and longitude, construct regex:
        pattern = self.matchlatlon.pattern
        loc = place.get_main_location()
        if re.search(('CITY'),pattern) :
            if loc.get_city().strip() == '' :
                return valoud, valnew, valaction, place
            pattern = re.sub(('CITY'), loc.get_city().strip(), pattern)
        if re.search(('TITLEBEGIN'),pattern) :
            tit = place.get_title().strip()
            titb= tit.split(',')[0].strip()
            if titb == '' :
                return valoud, valnew, valaction, place
            pattern = re.sub(('TITLEBEGIN'), titb, pattern)
        if re.search(('TITLE'),pattern) :
            if place.get_title().strip() == '' :
                return valoud, valnew, valaction, place
            pattern = re.sub(('TITLE'), loc.get_title().strip(), pattern)
        if re.search(('STATE'),pattern) :
            if place.get_state().strip() == '' :
                return valoud, valnew, valaction, place
            pattern = re.sub(('STATE'), loc.get_state().strip(), pattern)
        if re.search(('PARISH'),pattern) :
            if loc.get_parish().strip() == '' :
                return valoud, valnew, valaction, place
            pattern = re.sub(('PARISH'), loc.get_parish().strip(), pattern)
        if re.search(('COUNTY'), pattern):
            if loc.get_county().strip() not in self.county_lookup:
                return valoud, valnew, valaction, place
            codes = self.county_lookup[loc.get_county().strip()]
            pattern = re.sub(('COUNTY'), '(' + '|'.join(codes) + ')', pattern)
        #print 'DEBUG info: pattern for search is ' , pattern
        regexll = re.compile(pattern,re.U|re.L|re.M)
        latlongroup = ['lat', 'lon'] 
        #find all occurences in the data file
        iterator = regexll.finditer(self.latlonfile_datastr)
        for result in iterator : 
            lato =self.group_get(place, ('latitude'))
            lono =self.group_get(place, ('longitude'))
                       
            lat = result.group(latlongroup[0])
            lon = result.group(latlongroup[1])
            if not(lat and lon):
                continue
            if lato or lono :
                valoud.append(lat+r'/'+ lon)
            else : 
                valoud.append('') 
            valnew.append(lat+r'/' +lon)
            valaction.append(['#latlon',(lat,lon)])
            # do the action in memory
            place = self.group_set(place,'#latlon', (lat,lon))
            # check for other groups present in the regex :
            for groupname in self.extrafindgroup :
                valoud.append(self.group_get(place, groupname))
                valnew.append(result.group(groupname))
                valaction.append([groupname, result.group(groupname)])
                #do the action on the place in memory:
                place = self.group_set(place, groupname, 
                                            result.group(groupname))
        return valoud, valnew, valaction, place
        
    def convert_latlon(self,place) :
        valoud = []
        valnew = []
        valaction = []
        lat = place.get_latitude()
        lon = place.get_longitude()
        convtype = self.options.handler.options_dict['latlonconv'] 
        if convtype == "None" :
            return valoud, valnew, valaction, place
        elif convtype == "DGtDC" :
            type = "D.D8"
        elif convtype == "DCtDG" :
            type = "DEG"
        elif convtype == "-DGtDG" :
            type = "DEG"
        else :
            return valoud, valnew, valaction, place
        #convert all to decimal 8 notation
        if convtype == "-DGtDG" :
            latnew, lonnew = conv_min_deg(lat,lon, type)
        elif convtype == 'DGtDC' :
            latnew, lonnew = conv_lat_lon(lat,lon, type)
            #remove trailing zeros :
            if latnew : latnew = str(float(latnew))
            if lonnew : lonnew = str(float(lonnew))
        else :
            latnew, lonnew = conv_lat_lon(lat,lon, type)

        if latnew != None and latnew != lat :
            valoud.append(lat)
            valnew.append(latnew)
            valaction.append([('latitude'),latnew])
            #do the action in memory
            place = self.group_set(place, ('latitude'),latnew)
        elif lat != '' and latnew == None :
            valoud.append(_('invalid lat or lon value, %(lat)s, %(lon)s') 
                        % {'lat' : lat, 'lon' : lon})
            valnew.append(None)
            #do nothing
            valaction.append([('latitude'), None])
        if lonnew != None and lonnew != lon :
            valoud.append(lon)
            valnew.append(lonnew)
            valaction.append([('longitude'),lonnew])
            #do the action in memory
            place = self.group_set(place, ('longitude'),lonnew)
        elif lon != '' and lonnew == None :
            valoud.append(_('invalid lat or lon value, %(lat)s, %(lon)s') 
                        % {'lat' : lat, 'lon' : lon})
            valnew.append(None)
            valaction.append([('longitude'), None])
        return valoud, valnew, valaction, place
    
    def construct_title_custom(self, place, title_format):
        val = ['city',
               'street',
               'locality',
               'parish',
               'county',
               'state',
               'country',
               'postal_code']
        tf = title_format.lower()
        empty_result = True
        for v in val:
            value = eval("place.get_main_location().get_"+v+"()")
            if tf.count(v) > 0:
                empty_result = False
            tf = tf.replace(v, value)
        if not empty_result:
            return tf
        return ''

    def construct_title(self, place) :
        valoud = []
        valnew = []
        valaction = []
        type = self.options.handler.options_dict['titleconstruct']
        custom = self.options.handler.options_dict['titleconstruct_custom']
        if custom != '' and self.construct_title_custom(place, custom):
            valoud.append(place.get_title())
            new = self.construct_title_custom(place, custom)
            valnew.append(new)
            valaction.append([('title'),new])
            #do the action in memory
            place = self.group_set(place, ('title'),new)
        elif type == "None" :
            pass
        elif type == "CS" :
            valoud.append(place.get_title())
            new = place.get_main_location().get_city()
            if place.get_main_location().get_state() :
                new += ', ' + place.get_main_location().get_state()
            valnew.append(new)
            valaction.append([('title'),new])
            #do the action in memory
            place = self.group_set(place, ('title'),new)
        elif type == "CZC" :
            # City,PostalCode,Country
            valoud.append(place.get_title())
            city    = place.get_main_location().get_city()
            pcode   = place.get_main_location().get_postal_code()
            country = place.get_main_location().get_country()
            new = city + ',' + pcode + ',' + country
            valnew.append(new)
            valaction.append([('title'),new])
            #do the action in memory
            place = self.group_set(place, ('title'),new)
        elif type == "CSLPZC" :
            # City[(Street;Locality;Parish)],PostalCode,Country
            valoud.append(place.get_title())
            city     = place.get_main_location().get_city()
            street   = place.get_main_location().get_street()
            locality = place.get_main_location().get_locality()
            parish   = place.get_main_location().get_parish()
            pcode      = place.get_main_location().get_postal_code()
            country  = place.get_main_location().get_country()
            address  = ''
            if street or locality or parish:
                address = '(' + street + ';' + locality + ';' + parish + ')'
            new = city + address + ',' + pcode + ',' + country
            valnew.append(new)
            valaction.append([('title'),new])
            #do the action in memory
            place = self.group_set(place, ('title'),new)
        elif type == "T1CS" :
            old = place.get_title()
            valoud.append(old)
            old = old.split(',')[0]
            new = place.get_main_location().get_city()
            if old != new :
                new = old + ', ' + new
            if place.get_main_location().get_state() :
                new += ', ' + place.get_main_location().get_state()
            valnew.append(new)
            valaction.append([('title'),new])
            #do the action in memory
            place = self.group_set(place, ('title'),new)
        elif type == "T1CCSC" :
            old = place.get_title()
            valoud.append(old)
            old = old.split(',')[0]
            new = place.get_main_location().get_city()
            if old != new :
                new = old + ', ' + new
            if place.get_main_location().get_county() :
                new += ', ' + place.get_main_location().get_county()
            else:
                new +=', '
            if place.get_main_location().get_state() :
                new += ', ' + place.get_main_location().get_state()
            else:
                new +=', '
            if place.get_main_location().get_country() :
                new += ', ' + place.get_main_location().get_country()
            valnew.append(new)
            valaction.append([('title'),new])
            #do the action in memory
            place = self.group_set(place, ('title'),new)
        elif type == "T1CCCSC" :
            old = place.get_title()
            valoud.append(old)
            old = old.split(',')[0]
            old = old.split(' - ')[0]
            new = place.get_main_location().get_city()
            if old != new :
                new = "[" + old + "] - " + new
            if place.get_main_location().get_postal_code() :
                new += ', ' + place.get_main_location().get_postal_code()
            else:
                new +=', '
            if place.get_main_location().get_county() :
                new += ', ' + place.get_main_location().get_county()
            else:
                new +=', '
            if place.get_main_location().get_state() :
                new += ', ' + place.get_main_location().get_state()
            else:
                new +=', '
            if place.get_main_location().get_country() :
                new += ', ' + place.get_main_location().get_country()
            valnew.append(new)
            valaction.append([('title'),new])
            #do the action in memory
            place = self.group_set(place, ('title'),new)
            
        return valoud, valnew, valaction, place
        
    def set_data(self, place) :
        valoud = []
        valnew = []
        valaction = []
        
        for newval in [(self.options.handler.options_dict['countryset'],('country')),
                (self.options.handler.options_dict['stateset'],('state')),
                (self.options.handler.options_dict['countyset'],('county')),
                (self.options.handler.options_dict['cityset'],('city')),
                (self.options.handler.options_dict['parishset'],('parish')),
                (self.options.handler.options_dict['zipset'],('zip'))] :
            #we allow ' ' to mean store '':
            if newval[0] : 
                nv = newval[0].strip()
                valoud.append(self.group_get(place,newval[1]))
                valnew.append(nv)
                valaction.append([newval[1],nv])
                #do the action in memory
                place = self.group_set(place, newval[1], nv)
                
        return valoud, valnew, valaction, place

#------------------------------------------------------------------------
#
# Constant options items
#
#------------------------------------------------------------------------

class _options:
    # internal ID, english option name (for cli), localized option name (for gui)
    latlonconv = (
        ("None", "No lat/lon conversion", _("No lat/lon conversion")),
        ("DCtDG", "All in degree notation", _("All in degree notation")),
        ("DGtDC", "All in decimal notation", _("All in decimal notation")),
        ("-DGtDG", "Correct -50° in 50°S", _("Correct -50° in 50°S")),
    )
    
    titleconstruct = (
        ("None", "No changes", _("No changes")),
        ("CS", "City[, State]", _("City[, State]")),
        ("CZC", "City,PostalCode,Country",
                _("City,PostalCode,Country")),
        ("CSLPZC", "City[(Street;Locality;Parish)],PostalCode,Country",
                _("City[(Street;Locality;Parish)],PostalCode,Country")),
        ("T1CS", "TitleStart [, City] [, State]", 
                _("TitleStart [, City] [, State]")),
        ("T1CCSC", "TitleStart [, City] [, County] [, State] [, Country]", 
                _("TitleStart [, City] [, County] [, State] [, Country]")),
        ("T1CCCSC", "TitleStart [, City] [, Zip] [, County] [, State] [, Country]", 
                _("TitleStart [, City] [, Zip] [, County] [, State] [, Country]")),
    )
    
    # geonames : http://download.geonames.org/export/dump/
    # geonet : ftp://ftp.nga.mil/pub/gns_data
    #lat_translated = _('lat')
    #lon_translated = _('lon')
    #city_translated = _('city')
    #county_translated = _('county')
    #state_translated = _('state')
    #country_translated = _('country')
    CITY_transl = ('CITY')
    TITLE_transl = ('TITLE')
    TITLEBEGIN_transl = ('TITLEBEGIN')
    STATE_transl = ('STATE')
    PARISH_transl = ('PARISH')
    COUNTY_transl = ('COUNTY')
    latgr = r'(?P<'+'lat' +r'>'
    longr = r'(?P<'+'lon' +r'>'
    citygr = r'(?P<'+'city' +r'>'
    countygr = r'(?P<'+'county' +r'>'
    countrygr = r'(?P<'+'country' +r'>'
    stategr = r'(?P<'+'state' +r'>'
    titleregex = (
        ("citystate", "City [,|.] State", _("City [,|.] State")
            , r'\s*'+citygr +r'.+?)\s*[.,]\s*'+stategr+r'.+?)\s*$'),
        ("citycountry", "City [,|.] Country", _("City [,|.] Country")
            , r'\s*'+citygr +r'.+?)\s*[.,]\s*'+countrygr+r'.+?)\s*$'),
        ("city(country)", "City (Country)", _("City (Country)")
            , r'\s*'+citygr+r'.*?)\s*\(\s*'+countrygr+r'[^\)]+)\s*\)\s*$'),
        ("city", "City", _("City")
            , r'\s*'+citygr+r'.*?)\s*$'),
    )
    latlonfind = (
        ("None", "Don't search", _("Don't search"), ''),
        # for feature classes (P,H, ...) see http://www.geonames.org/export/codes.html
        ("GeoNames_c", "GeoNames country file, city search"
            , _("GeoNames country file, city search")
            , r'\t'+CITY_transl +r'\t[^\t]*\t[^\t]*\t' +latgr + \
                r'[\d+-][^\t]*)\t' + \
                longr + r'[\d+-][^\t]*)\tP'),
        ("GeoNames_cv", "GeoNames country file, city localized variants search"
            , _("GeoNames country file, city localized variants search")
            , r'[\t,]'+CITY_transl+r'[,\t][^\t\d]*\t?' +latgr + \
                r'[\d+-][^\t]*)\t' + \
                longr + r'[\d+-][^\t]*)\tP'),
        ("GeoNames_cc", "GeoNames country file, county/city search"
            , _("GeoNames country file, county/city search")
            , r'\t'+CITY_transl +r'\t[^\t]*\t[^\t]*\t' +latgr + \
                r'[\d+-][^\t]*)\t' + longr + \
                r'[\d+-][^\t]*)\tP\t[^\t]*\t[^\t]*\t[^\t]*\t[^\t]*\t' + \
                COUNTY_transl + r'\t'),
        #Parish search no use, no datain files
        #("GeoNames", "GeoNames country file, parish search"
        #    , _("GeoNames country file, parish search")
        #    , r'\t'+PARISH_transl +r'\t[^\t]*\t[^\t]*\t' +latgr + \
        #        r'[\d+-][^\t]*)\t' + \
        #        longr + r'[\d+-][^\t]*)\tA\tPRSH'),
        ("GeoNames_tb", "GeoNames country file, title begin, general search"
            , _("GeoNames country file, title begin, general search")
            , r'\t'+TITLEBEGIN_transl +r'\t[^\t]*\t[^\t]*\t' +latgr + \
                r'[\d+-][^\t]*)\t' + \
                longr + r'[\d+-][^\t]*)\t[PSTV]'),
        ("GeoNames_usa_c", "GeoNames USA state file, city search"
            , _("GeoNames USA state file, city search")
            , r'\|'+CITY_transl+r'\|Populated Place\|[^\|]*\|[^\|]*\|'\
                + countygr + r'[^\|]*)' \
                + r'\|[^\|]*\|[^\|]*\|[^\|]*\|' +latgr + \
                r'[\d+-][^\|]*)\|' + \
                longr + r'[\d+-][^\|]*)'),
        #("GeoNames_usa_c", "GeoNames USA state file, city search"
        #    , _("GeoNames USA state file, city search")
        #    , r'\t'+CITY_transl+r'\tPopulated Place\t[^\t]*\t[^\t]*\t'\
        #        + countygr + r'[^\t]*)' \
        #        + r'\t[^\t]*\t[^\t]*\t[^\t]*\t' +latgr + \
        #        r'[\d+-][^\t]*)\t' + \
        #        longr + r'[\d+-][^\t]*)'),
        ("GeoNet_c", "GNS Geonet country file, city search", 
                _("GNS Geonet country file, city search"), 
                r'\t'+latgr+r'[\d+-.][^\t]*)\t'+longr+r'[\d+-.][^\t]*)'\
                + r'\t[^\t]*\t[^\t]*\t[^\t]*\t[^\t]*\tP\t[^\t]*\t[^\t]*'\
                + r'\t[^\t]*\t[^\t]*\t[^\t]*\t[^\t]*\t[^\t]*\t[^\t]*\t[^\t]*'\
                + r'\t[^\t]*\t[^\t]*\t[^\t]*' \
                + r'\t'+CITY_transl+r'\t'),
        ("GeoNet_cc", "GNS Geonet country file, county/city search", 
                _("GNS Geonet country file, county/city search"), 
                r'\t'+latgr+r'[\d+-.][^\t]*)\t'+longr+r'[\d+-.][^\t]*)'\
                + r'\t[^\t]*\t[^\t]*\t[^\t]*\t[^\t]*\tP' \
                + r'\t[^\t]*\t[^\t]*\t[^\t]*\t' + COUNTY_transl \
                + r'\t[^\t]*\t[^\t]*\t[^\t]*\t[^\t]*\t[^\t]*' \
                + r'\t[^\t]*\t[^\t]*\t[^\t]*\t' + CITY_transl + r'\t'),
        # Geonet fields and classes: http://de.wikipedia.org/wiki/Wikipedia:GEOnet_Names_Server
        ("GeoNet_tb", "GNS Geonet country file, title begin search", 
                _("GNS Geonet country file, title begin, general search")
                , 
                r'\t'+latgr+r'[\d+-.][^\t]*)\t'+longr+r'[\d+-.][^\t]*)'\
                + r'\t[^\t]*\t[^\t]*\t[^\t]*\t[^\t]*\t[PLSTV]\t[^\t]*\t[^\t]*'\
                + r'\t[^\t]*\t[^\t]*\t[^\t]*\t[^\t]*\t[^\t]*\t[^\t]*\t[^\t]*'\
                + r'\t[^\t]*\t[^\t]*\t[^\t]*' \
                + r'\t'+TITLEBEGIN_transl+r'\t'),
        ("Wikipedia CSV Dump", "Wikipedia CSV Dump",
                _("Wikipedia CSV Dump"),
                r'^[^;]*;[^;]*;[^;]*;"' + TITLEBEGIN_transl +
                r'";[^;]*;[^;]*;[^;]*;[^;]*;[^;]*;[^;]*;[^;]*;[^;]*;[^;]*;"'+
                latgr + r'[\d\.]+)";"' + longr + r'[\d\.]+)";'),
    )

#helper function
def conv_min_deg(latorig, lonorig, text="DEG") :
    '''
        convert latorig and lonorig to text notation
        Allow the input to be of positive/negative degree input without
        N/S/W/E nominator
    '''
    #see if it converts, if so, return original values, no minus present
    lat, lon = conv_lat_lon(latorig,lonorig, text)
    if lat and lon :
        return latorig, lonorig
    lat = latorig; lon = lonorig
    
    lat = lat.replace(r'\s*', r'')
    lon = lon.replace(r'\s*', r'')
    rm = re.compile(r'\s*-[^-]*$')
    rp = re.compile(r'\s*\+[^\+]*$')
    minuslat = False; minuslon = False
    latnotdeg = False; lonnotdeg = False
    #see if lat starts with - value, if so, add S
    if lat.find(r'°') != -1 :
        if rm.match(lat) :
            lat = lat.replace(r'-',r'')
            lat = lat + 'S'
            minuslat = True
        else :
            if rp.match(lat):
                lat = lat.replace(r'+',r'')
    else : 
        latnotdeg = True
    #see if lon starts with - value, if so, add W
    if lon.find(r'°') != -1 :
        if rm.match(lon) :
            lon = lon.replace(r'-',r'')
            lon = lon + 'W'
            minuslon = True
        else :
            if rp.match(lon):
                lon = lon.replace(r'+',r'')
    else :
        lonnotdeg = True
    if latnotdeg and lonnotdeg :
        return latorig, lonorig
    # see if in converts ok now
    lattest, lontest = conv_lat_lon(lat,lon, text)
    if lattest and lontest :
        return lattest, lontest
    if lattest == None :
        # if positive, try adding the N 
        if minuslat == False : 
            lat = lat + 'N' 
    if lontest == None :
        if minuslon == False : 
            lon = lon + 'E'
    lat, lon = conv_lat_lon(lat,lon, text)
    if lat and lon :
        return lat, lon
    # conversion failed, return original
    if lat==None : lat = latorig
    if lon==None : lon = lonorig
    return lat, lon
        
    
#------------------------------------------------------------------------
#
# 
#
#------------------------------------------------------------------------
class PlaceCompletionOptions(Tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self,name,person_id=None):
        Tool.ToolOptions.__init__(self,name,person_id)
        self.set_new_options()

    def get_report_filters(self, person=None):
        """Set up the list of possible content filters.
            The options are so that argument person must exist. Not needed here
        """
        all = GenericPlaceFilter()
        all.set_name(_("All Places"))
        all.add_rule(rules.place.AllPlaces([]))
        nolatlon = GenericPlaceFilter()
        nolatlon.set_name(_("No Latitude/Longitude given"))
        nolatlon.add_rule(rules.place.HasNoLatOrLon([]))

        the_filters = [all,nolatlon]
        from gramps.gen.filters import CustomFilters
        the_filters.extend(CustomFilters.get_filters('Place'))
        return the_filters
        
    def set_new_options(self):
        # Options specific for this report
        self.options_dict = {
            'filternumber' : 0, 
            'countryfilter': '',
            'statefilter'  : '',
            'countyfilter'  : '',
            'cityfilter'  : '',
            'parishfilter'  : '',
            'centerlat'  : '',
            'centerlon'  : '',
            'rectwidth'  : '',
            'rectheight'  : '',
            'latlonfile'   : '',
            'latlonfind'   : '',
            'titleregex'   : '',
            'titleconstruct' : '',
            'titleconstruct_custom' : '',
            'latlonconv'   : '',
            'countryset': '',
            'stateset'  : '',
            'countyset'  : '',
            'cityset'  : '',
            'parishset'  : '',
            'zipset'  : '',
        }
        self.options_help = {
            'filternumber' : ("=int", "integer indicating which place filter to"
                                    "use",  "integer"), 
            'countryfilter': ("=str","string with wich to filter places on country",
                            "string"),
            'statefilter': ("=str","string with wich to filter places on state",
                            "string"),
            'countyfilter': ("=str","string with wich to filter places on county",
                            "string"),
            'cityfilter': ("=str","string with wich to filter places on city",
                            "string"),
            'parishfilter': ("=str","string with wich to filter places on parish",
                            "string"),
            'centerlat': ("=str","value in degrees denoting center latitude of a rectangle",
                            "string"),
            'centerlon': ("=str","value in degrees denoting center longitude of a rectangle",
                            "string"),
            'rectwidth': ("=str","value in degrees denoting width of a rectangle",
                            "string"),
            'rectheight': ("=str","value in degrees denoting height of a rectangle",
                            "string"),
            'latlonfile' : ("=filename",
        "Filename on which to run the regular expression",
                        "Filename"),
            'latlonfind' : ("=str",
        "Regular expression of how look up latitude/longitude",
                        "Regular expression"),
            'titleregex' : ("=str","Regular expresson with which to match title",
                            "Regular expression"),
            'titleconstruct' : ("=str","How to construct the tite",
        [ "%s\t%s" % (item[0],item[1]) for item in _options.titleconstruct ]),
            'titleconstruct_custom': ("=str","self defined format for titles",
                            "string"),
            'latlonconv' : ("=str","How to convert lat and lon",
        [ "%s\t%s" % (item[0],item[1]) for item in _options.latlonconv ]),
            'countryset': ("=str","string with country of the places",
                            "string"),
            'stateset': ("=str","string with state of the places",
                            "string"),
            'countyset': ("=str","string with county of the places",
                            "string"),
            'cityset': ("=str","string with wich city of the places",
                            "string"),
            'parishset': ("=str","string with parish of the places",
                            "string"),
            'zipset': ("=str","string with ZIP/postalcode of the places",
                            "string"),
        }
