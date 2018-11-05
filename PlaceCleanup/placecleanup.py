# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2018      Paul Culley
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
#
# Place Cleanup Gramplet.
#
# pylint: disable=attribute-defined-outside-init
#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
from urllib.request import urlopen, URLError, quote
from xml.dom.minidom import parseString
import os
import sys
import ctypes
import locale
import socket

#------------------------------------------------------------------------
#
# GTK modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------
from gramps.gen.merge.mergeplacequery import MergePlaceQuery
from gramps.gui.dialog import ErrorDialog, WarningDialog
from gramps.gen.plug import Gramplet
from gramps.gen.db import DbTxn
from gramps.gen.lib import Citation
from gramps.gen.lib import Place, PlaceName, PlaceType, PlaceRef, Url, UrlType
from gramps.gen.lib import Note, NoteType, Repository, RepositoryType, RepoRef
from gramps.gen.lib import StyledText, StyledTextTag, StyledTextTagType
from gramps.gen.lib import Source, SourceMediaType
from gramps.gen.datehandler import get_date
from gramps.gen.config import config
from gramps.gen.constfunc import win
from gramps.gui.display import display_url
from gramps.gui.autocomp import StandardCustomSelector
from gramps.gen.display.place import displayer as _pd
from gramps.gen.utils.location import located_in


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
# Constants
#
#------------------------------------------------------------------------
WIKI_PAGE = ('https://gramps-project.org/wiki/index.php/'
             'Addon:PlaceCleanupGramplet')
PREFS_WIKI = ('https://gramps-project.org/wiki/index.php/'
              'Addon:PlaceCleanupGramplet#Preferences')
#-------------------------------------------------------------------------
#
# configuration
#
#-------------------------------------------------------------------------

GRAMPLET_CONFIG_NAME = "place_cleanup_gramplet"
CONFIG = config.register_manager(GRAMPLET_CONFIG_NAME)
CONFIG.register("preferences.geo_userid", '')
CONFIG.register("preferences.web_links", True)
CONFIG.register("preferences.add_cit", True)
CONFIG.register("preferences.keep_enclosure", True)
CONFIG.register("preferences.keep_lang", "en fr de pl ru da es fi sw no")
CONFIG.load()


#------------------------------------------------------------------------
#
# PlaceCleanup class
#
#------------------------------------------------------------------------
class PlaceCleanup(Gramplet):
    """
    Gramplet to cleanup places.
    Can Look for place that needs attention, or work on current place.
    Can search your own places, and merge current with another
    Can search GeoNames data on web and load data to a place.
    Data includes, Lat/Lon, enclosed by, type, postal code, and alternate
    names.
    """
    def init(self):
        """
        Initialise the gramplet.
        """
        self.keepweb = CONFIG.get("preferences.web_links")
        self.addcitation = CONFIG.get("preferences.add_cit")
        self.geonames_id = CONFIG.get("preferences.geo_userid")
        self.keep_enclosure = CONFIG.get("preferences.keep_enclosure")
        allowed_languages = CONFIG.get("preferences.keep_lang")
        self.allowed_languages = allowed_languages.split()
        self.incomp_hndl = ''  # a last used handle for incomplete places
        self.matches_warn = True  # Display the 'too many matches' warning?
        root = self.__create_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(root)
        root.show_all()

    def __create_gui(self):
        """
        Create and display the GUI components of the gramplet.
        """
        self.top = Gtk.Builder()  # IGNORE:W0201
        # Found out that Glade does not support translations for plugins, so
        # have to do it manually.
        base = os.path.dirname(__file__)
        glade_file = base + os.sep + "placecleanup.glade"
        # This is needed to make gtk.Builder work by specifying the
        # translations directory in a separate 'domain'
        try:
            localedomain = "addon"
            localepath = base + os.sep + "locale"
            if hasattr(locale, 'bindtextdomain'):
                libintl = locale
            elif win():  # apparently wants strings in bytes
                localedomain = localedomain.encode('utf-8')
                localepath = localepath.encode('utf-8')
                libintl = ctypes.cdll.LoadLibrary('libintl-8.dll')
            else:  # mac, No way for author to test this
                libintl = ctypes.cdll.LoadLibrary('libintl.dylib')

            libintl.bindtextdomain(localedomain, localepath)
            libintl.textdomain(localedomain)
            libintl.bind_textdomain_codeset(localedomain, "UTF-8")
            # and finally, tell Gtk Builder to use that domain
            self.top.set_translation_domain("addon")
        except (OSError, AttributeError):
            # Will leave it in English
            print("Localization of PlaceCleanup failed!")

        self.top.add_from_file(glade_file)
        # the results screen items
        self.results_win = self.top.get_object("results")
        self.alt_store = self.top.get_object("alt_names_liststore")
        self.alt_selection = self.top.get_object("alt_names_selection")
        self.res_lbl = self.top.get_object("res_label")
        self.find_but = self.top.get_object("find_but")
        self.top.connect_signals({
            # for results screen
            "on_res_ok_clicked"      : self.on_res_ok_clicked,
            "on_res_cancel_clicked"  : self.on_res_cancel_clicked,
            "on_keep_clicked"        : self.on_keep_clicked,
            "on_prim_clicked"        : self.on_prim_clicked,
            "on_disc_clicked"        : self.on_disc_clicked,
            "on_alt_row_activated"   : self.on_alt_row_activated,
            "on_latloncheck"         : self.on_latloncheck,
            "on_postalcheck"         : self.on_postalcheck,
            "on_typecheck"           : self.on_typecheck,
            "on_idcheck"             : self.on_idcheck,
            # Preferences screen item
            "on_pref_help_clicked"   : self.on_pref_help_clicked,
            # main screen items
            "on_find_clicked"        : self.on_find_clicked,
            "on_prefs_clicked"       : self.on_prefs_clicked,
            "on_select_clicked"      : self.on_select_clicked,
            "on_edit_clicked"        : self.on_edit_clicked,
            "on_next_clicked"        : self.on_next_clicked,
            "on_res_row_activated"   : self.on_select_clicked,
            "on_res_sel_changed"     : self.on_res_sel_changed,
            "on_title_entry_changed" : self.on_title_entry_changed,
            "on_help_clicked"        : self.on_help_clicked})
        # main screen items
        self.res_store = self.top.get_object("res_names_liststore")
        self.res_selection = self.top.get_object("res_selection")
        self.mainwin = self.top.get_object("main")
        return self.mainwin

    # ======================================================
    # gramplet event handlers
    # ======================================================
    def on_help_clicked(self, dummy):
        ''' Button: Display the relevant portion of GRAMPS manual'''
        display_url(WIKI_PAGE)

    def on_res_sel_changed(self, res_sel):
        """ Selecting a row in the results list """
        self.top.get_object("select_but").set_sensitive(
            res_sel.get_selected())

    def on_title_entry_changed(self, dummy):
        ''' Occurs during edits of the Title box on the main screen.
        we use this to reset the GeoNames search row, as the user may be
        trying another search term.'''
        self.reset_main()

    def on_save(self, *args, **kwargs):
        CONFIG.set("preferences.geo_userid", self.geonames_id)
        CONFIG.set("preferences.web_links", self.keepweb)
        CONFIG.set("preferences.add_cit", self.addcitation)
        CONFIG.set("preferences.keep_enclosure", self.keep_enclosure)
        CONFIG.set("preferences.keep_lang", ' '.join(self.allowed_languages))
        CONFIG.save()

    def db_changed(self):
        self.dbstate.db.connect('place-update', self.update)
        self.main()
        if not self.dbstate.db.readonly:
            self.connect_signal('Place', self.update)

    def main(self):
        self.reset_main()
        if self.gui.get_child().get_child() == self.results_win:
            self.gui.get_child().remove(self.results_win)
            self.gui.get_child().add(self.mainwin)
        active_handle = self.get_active('Place')
        self.top.get_object("edit_but").set_sensitive(False)
        self.top.get_object("find_but").set_sensitive(False)
        self.top.get_object("title_entry").set_sensitive(False)
        if active_handle:
            self.place = self.dbstate.db.get_place_from_handle(active_handle)
            self.mainwin.hide()
            if self.place:
                self.set_has_data(True)
                title = _pd.display(self.dbstate.db, self.place)
                item = self.top.get_object("title_entry")
                item.set_text(title)
                self.top.get_object("edit_but").set_sensitive(True)
                self.top.get_object("find_but").set_sensitive(True)
                self.top.get_object("title_entry").set_sensitive(True)
            else:
                self.set_has_data(False)
            self.mainwin.show()
        else:
            self.set_has_data(False)

    def reset_main(self):
        """ Reset the main Gui to default clear """
        self.res_store.clear()
        self.res_lbl.set_text(_('No\nMatches'))
        self.find_but.set_label(_("Find"))
        self.start_row = 0
        self.geo_stage = False
        self.top.get_object("select_but").set_sensitive(False)

    def on_find_clicked(self, dummy):
        """ find a matching place.  First try in the db, then try in the
        GeoNames. """
        self.res_store.clear()
        self.top.get_object("select_but").set_sensitive(False)
        if self.geo_stage:
            self.search_geo()
        else:
            self.geo_stage = True
            item = self.top.get_object("title_entry")
            title = item.get_text()
            self.places = self.lookup_places_by_name(title)
            for index, place in enumerate(self.places):
                # make sure the place found isn't self, or a place
                # enclosed by the working place
                if place.handle != self.place.handle and not located_in(
                        self.dbstate.db, place.handle, self.place.handle):
                    title = _pd.display(self.dbstate.db, place)
                    self.res_store.append(row=(index, title,
                                               str(place.place_type)))
            if len(self.res_store) > 0:
                self.res_lbl.set_text(_('%s\nLocal\nMatches') %
                                      len(self.res_store))
                self.find_but.set_label(_("Find GeoNames"))
            else:
                self.search_geo()

    def search_geo(self):
        """ find a matching place in the geonames, if possible """
        self.res_store.clear()
        if not self.geonames_id:
            ErrorDialog(_('Need to set GeoNames ID'),
                        msg2=_('Use the Help button for more information'),
                        parent=self.uistate.window)
            return
        # lets get a preferred language
        fmt = config.get('preferences.place-format')
        placef = _pd.get_formats()[fmt]
        self.lang = placef.language
        if len(self.lang) != 2:
            self.lang = 'en'
        if self.lang not in self.allowed_languages:
            self.allowed_languages.append(self.lang)
        # now lets search for a place in GeoNames
        item = self.top.get_object("title_entry")
        title = quote(item.get_text().lower().replace('co.', 'county'))
        adm = self.top.get_object('adm_check').get_active()
        ppl = self.top.get_object('ppl_check').get_active()
        spot = self.top.get_object('spot_check').get_active()
        geo_url = (
            'http://api.geonames.org/search?q=%s'
            '&maxRows=10&style=SHORT&lang=en&isNameRequired=True'
            '%s%s%s&username=%s&startRow=%s' %
            (title,
             '&featureClass=A' if adm else '',
             '&featureClass=P' if ppl else '',
             '&featureClass=S' if spot else '',
             self.geonames_id, self.start_row))
        dom = self.get_geo_data(geo_url)
        if not dom:
            return

        g_names = dom.getElementsByTagName('geoname')
        if not g_names:
            WarningDialog(_('No matches were found'),
                          msg2=_('Try changing the Title, or use the "Edit"'
                                 ' button to finish this level of the place'
                                 ' manually.'),
                          parent=self.uistate.window)
            return
        # let's check the total results; if too many, warn user and set up for
        # another pass through the search.
        value = dom.getElementsByTagName('totalResultsCount')
        if value:
            totalresults = int(value[0].childNodes[0].data)
            self.res_lbl.set_text(_("%s\nGeoNames\nMatches") % totalresults)
            if totalresults > 10:
                self.start_row += 10
                if self.matches_warn:
                    self.matches_warn = False
                    WarningDialog(
                        _('%s matches were found') % totalresults,
                        msg2=_('Only 10 matches are shown.\n'
                               'To see additional results, press the'
                               ' search button again.\n'
                               'Or try changing the Title with'
                               ' more detail, such as a country.'),
                        parent=self.uistate.window)
        index = 0
        self.places = []
        for g_name in g_names:
            # got a match, now get its hierarchy for display.
            value = g_name.getElementsByTagName('geonameId')
            geoid = value[0].childNodes[0].data
            value = g_name.getElementsByTagName('fcl')
            fcl = value[0].childNodes[0].data
            value = g_name.getElementsByTagName('fcode')
            _type = fcl + ':' + value[0].childNodes[0].data
            geo_url = ('http://api.geonames.org/hierarchy?geonameId=%s'
                       '&lang=%s&username=%s' %
                       (geoid, self.lang, self.geonames_id))
            hier = self.get_geo_data(geo_url)
            if not hier:
                return
            h_names = hier.getElementsByTagName('geoname')
            h_name_list = []
            h_geoid_list = []
            for h_name in h_names:
                value = h_name.getElementsByTagName('fcl')
                fcl = value[0].childNodes[0].data
                if fcl not in 'APS':
                    # We don't care about Earth or continent (yet)
                    continue
                value = h_name.getElementsByTagName('name')
                h_name_list.append(value[0].childNodes[0].data)
                value = h_name.getElementsByTagName('geonameId')
                h_geoid_list.append('GEO' + value[0].childNodes[0].data)
            # make sure that this place isn't already enclosed by our place.
            bad = self.place.gramps_id in h_geoid_list[:-1]
            # assemble a title for the result
            h_name_list.reverse()
            h_geoid_list.reverse()
            if bad:
                title = ('<span strikethrough="true" strikethrough_color='
                         '"red">' + _(', ').join(h_name_list) + '</span>')
            else:
                title = _(', ').join(h_name_list)
            row = (index, title, _type)
            self.res_store.append(row=row)
            self.places.append(('GEO' + geoid, title, h_geoid_list,
                                h_name_list, bad))
            index += 1
            while Gtk.events_pending():
                Gtk.main_iteration()

    def get_geo_data(self, geo_url):
        """ Get GeoNames data from web with error checking """
        print(geo_url)
        try:
            with urlopen(geo_url, timeout=20) as response:
                data = response.read()
        except URLError as err:
            try:
                txt = err.read().decode('utf-8')
            except:
                txt = ''
            ErrorDialog(_('Problem getting data from web'),
                        msg2=str(err) +'\n' + txt,
                        parent=self.uistate.window)
            return None
        except socket.timeout:
            ErrorDialog(_('Problem getting data from web'),
                        msg2=_('Web request Timeout, you can try again...'),
                        parent=self.uistate.window)
            return None

        dom = parseString(data)
        status = dom.getElementsByTagName('status')
        if status:
            err = status[0].getAttribute("message")
            ErrorDialog(_('Problem getting data from GeoNames'),
                        msg2=err,
                        parent=self.uistate.window)
            return None
        return dom

    def on_next_clicked(self, dummy):
        """ find a incomplete place in the db, if possible """
        self.reset_main()
        place = self.find_an_incomplete_place()
        if place:
            self.set_active('Place', place.handle)

    def on_select_clicked(self, *dummy):
        """ If the selected place is mergable, merge it, otherwise Open
        completion screen """
        model, _iter = self.res_selection.get_selected()
        if not _iter:
            return
        (index, ) = model.get(_iter, 0)
        place = self.places[index]
        if not isinstance(place, Place):
            # we have a geoname_id
            if place[4]:
                return
            # check if we might already have it in db
            t_place = self.dbstate.db.get_place_from_gramps_id(place[0])
            if not t_place or t_place.handle == self.place.handle:
                # need to process the GeoNames ID for result
                self.gui.get_child().remove(self.mainwin)
                self.gui.get_child().add(self.results_win)
                if not self.geoparse(*place):
                    return
                self.res_gui()
                return
            else:
                # turns out we already have this place, under different name!
                place = t_place
        # we have a Gramps Place, need to merge
        if place.handle == self.place.handle:
            # found self, nothing to do.
            return
        if(located_in(self.dbstate.db, place.handle, self.place.handle) or
           located_in(self.dbstate.db, self.place.handle, place.handle)):
            # attempting to create a place loop, not good!
            ErrorDialog(_('Place cycle detected'),
                        msg2=_("One of the places you are merging encloses "
                               "the other!\n"
                               "Please choose another place."),
                        parent=self.uistate.window)
            return
        # lets clean up the place name
        self.place.name.value = self.place.name.value.split(',')[0].strip()
        place_merge = MergePlaceQuery(self.dbstate, place, self.place)
        place_merge.execute()
        # after merge we should select merged result
        self.set_active('Place', place.handle)

    adm_table = {
        # note the True/False in the following indicates the certainty that the
        # entry is correct.  If it is only sometimes correct, and the name
        # might have a different type embedded in it, then use False.
        'US': {'ADM1': (PlaceType.STATE, True),
               'ADM2': (PlaceType.COUNTY, False),
               'ADM3': (PlaceType.TOWN, False)},
        'CA': {'ADM1': (PlaceType.PROVINCE, True),
               'ADM2': (PlaceType.REGION, False)},
        'GB': {'ADM1': (PlaceType.COUNTRY, True),
               'ADM2': (PlaceType.REGION, True),
               'ADM3': (PlaceType.COUNTY, False),
               'ADM4': (PlaceType.BOROUGH, False)},
        'FR': {'ADM1': (PlaceType.REGION, True),
               'ADM2': (PlaceType.DEPARTMENT, True)},
        'DE': {'ADM1': (PlaceType.STATE, True),
               'ADM2': (PlaceType.COUNTY, False),
               'ADM3': ('Amt', False)}}

    def geoparse(self, geoid, title, h_geoid_list, h_name_list, *dummy):
        """ get data for place and parse out g_name dom structure into the
        NewPlace structure """
        geo_url = ('http://api.geonames.org/get?geonameId=%s&style=FULL'
                   '&username=%s' % (geoid.replace('GEO', ''),
                                     self.geonames_id))
        dom = self.get_geo_data(geo_url)
        if not dom:
            return False

        g_name = dom.getElementsByTagName('geoname')[0]
        self.newplace = NewPlace(title)
        self.newplace.geoid = geoid
        self.newplace.gramps_id = geoid
        value = g_name.getElementsByTagName('lat')
        self.newplace.lat = str(value[0].childNodes[0].data)
        value = g_name.getElementsByTagName('lng')
        self.newplace.long = str(value[0].childNodes[0].data)
        value = g_name.getElementsByTagName('toponymName')
        topname = value[0].childNodes[0].data
        new_place = PlaceName()
        new_place.set_value(topname)
        new_place.set_language("")
        # make sure we have the topname in the names list and default to
        # primary
        self.newplace.add_name(new_place)
        self.newplace.name = new_place
        # lets parse the alternative names
        alt_names = g_name.getElementsByTagName('alternateName')
        for a_name in alt_names:
            pattr = a_name.getAttribute("lang")
            value = a_name.childNodes[0].data
            if pattr == "post":
                if self.newplace.code:
                    self.newplace.code += " " + value
                else:
                    self.newplace.code = value
            elif pattr == "link":
                url = Url()
                url.set_path(value)
                url.set_description(value)
                url.set_type(UrlType(UrlType.WEB_HOME))
                self.newplace.links.append(url)
            elif pattr not in ['iata', 'iaco', 'faac', 'wkdt', 'unlc']:
                new_place = PlaceName()
                new_place.set_language(pattr)
                new_place.set_value(value)
                self.newplace.add_name(new_place)
            if a_name.hasAttribute('isPreferredName') and (
                    pattr and pattr == self.lang):
                # if not preferred lang, we use topo name, otherwise
                # preferred name for lang
                self.newplace.name = new_place
        # Try to deduce PlaceType:
        #   If populated place, set as City. Long description could over-ride
        #   Parse long description, looking for keyword (Region, County, ...)
        #   Top-level must be a country.
        #   Children of USA are States.
        #   Children of Canada are Provinces.
        #
        value = g_name.getElementsByTagName('fcl')
        fcl = value[0].childNodes[0].data
        value = g_name.getElementsByTagName('fcode')
        fcode = value[0].childNodes[0].data
        value = g_name.getElementsByTagName('countryCode')
        countrycode = value[0].childNodes[0].data
        self.newplace.place_type = PlaceType(PlaceType.UNKNOWN)
        ptype = PlaceType()
        # scan thorough names looking for name portion that matches a Placetype
        for name in self.newplace.names:
            for tname in name.value.split(' '):
                ptype.set_from_xml_str(tname.capitalize())
                if ptype != PlaceType.CUSTOM:
                    self.newplace.place_type = ptype
                    break
                # see if it is a translated PlaceType
                ptype.set(tname.capitalize())
                if ptype != PlaceType.CUSTOM:
                    self.newplace.place_type = ptype
                    break
                # see if it is an already added custom type
                cust_types = self.dbstate.db.get_place_types()
                if tname.capitalize() in cust_types:
                    self.newplace.place_type = ptype
                    break
            else:
                # Continue if the inner loop wasn't broken.
                continue
            # Inner loop was broken, break the outer.
            break
        if fcl == 'P':
            self.newplace.place_type = PlaceType(PlaceType.CITY)
        elif fcode == 'PRSH':
            self.newplace.place_type = PlaceType(PlaceType.PARISH)
        elif 'PCL' in fcode:
            self.newplace.place_type = PlaceType(PlaceType.COUNTRY)
        elif 'ADM' in fcode:
            if countrycode in self.adm_table:
                _ptype = self.adm_table[countrycode].get(fcode[:4])
                if _ptype and (_ptype[1] or
                               self.newplace.place_type.is_default()):
                    self.newplace.place_type = PlaceType(_ptype[0])
        # save a parent for enclosing
        if len(h_geoid_list) > 1:
            # we have a parent
            self.newplace.parent_names = h_name_list[1:]
            self.newplace.parent_ids = h_geoid_list[1:]
        return True

    def on_edit_clicked(self, dummy):
        """User wants to jump directly to the results view to finish off
        the place, possibly because a place was not found"""
#         if ',' in self.place.name.value:
#             name = self.place.name.value
#         else:
        name = self.place.name.value
        self.newplace = NewPlace(name)
        names = name.split(',')
        names = [name.strip() for name in names]
        self.newplace.name = PlaceName()
        self.newplace.name.value = names[0]
        self.newplace.gramps_id = self.place.gramps_id
        self.newplace.lat = self.place.lat
        self.newplace.long = self.place.long
        self.newplace.code = self.place.code
        if self.place.place_type == PlaceType.UNKNOWN:
            self.newplace.place_type = PlaceType(PlaceType.UNKNOWN)
            if any(i.isdigit() for i in self.newplace.name.value):
                self.newplace.place_type = PlaceType(PlaceType.STREET)
            ptype = PlaceType()
            for tname in self.newplace.name.value.split(' '):
                # see if it is an English PlaceType
                ptype.set_from_xml_str(tname.capitalize())
                if ptype != PlaceType.CUSTOM:
                    self.newplace.place_type = ptype
                    break
                # see if it is a translated PlaceType
                ptype.set(tname.capitalize())
                if ptype != PlaceType.CUSTOM:
                    self.newplace.place_type = ptype
                    break
                # see if it is an already added custom type
                cust_types = self.dbstate.db.get_place_types()
                if tname.capitalize() in cust_types:
                    self.newplace.place_type = ptype
        else:
            self.newplace.place_type = self.place.place_type
        self.newplace.add_name(self.newplace.name)
        self.newplace.add_name(self.place.name)
        self.newplace.add_names(self.place.alt_names)
        if self.place.placeref_list:
            # If we already have an enclosing place, use it.
            parent = self.dbstate.db.get_place_from_handle(
                self.place.placeref_list[0].ref)
            self.newplace.parent_ids = [parent.gramps_id]
        elif len(names) > 1:
            # we have an enclosing place, according to the name string
            self.newplace.parent_names = names[1:]
        self.gui.get_child().remove(self.mainwin)
        self.gui.get_child().add(self.results_win)
        self.res_gui()

# Results view

    def res_gui(self):
        """ Fill in the results display with values from new place."""
        self.alt_store.clear()
        # Setup sort on 'Inc" column so Primary is a top with checks next
        self.alt_store.set_sort_func(0, inc_sort, None)
        self.alt_store.set_sort_column_id(0, 0)
        # Merge old name and alt names into new set
        self.newplace.add_name(self.place.name)
        self.newplace.add_names(self.place.alt_names)
        # Fill in ohter fields
        self.top.get_object('res_title').set_text(self.newplace.title)
        self.top.get_object('primary').set_text(self.newplace.name.value)
        self.on_idcheck()
        self.on_latloncheck()
        self.on_postalcheck()
        self.on_typecheck()
        # Fill in names list
        for index, name in enumerate(self.newplace.names):
            if self.newplace.name == name:
                inc = 'P'
            elif name.lang in self.allowed_languages or (
                    name.lang == 'abbr' or name.lang == 'en' or not name.lang):
                inc = '\u2714'  # Check mark
            else:
                inc = ''
            row = (inc, name.value, name.lang, get_date(name), index)
            self.alt_store.append(row=row)

# Results dialog items

    def on_res_ok_clicked(self, dummy):
        """ Accept changes displayed and commit to place.
        Also find or create a new enclosing place from parent. """
        # do the names
        namelist = []
        for row in self.alt_store:
            if row[0] == 'P':
                self.place.name = self.newplace.names[row[4]]
            elif row[0] == '\u2714':
                namelist.append(self.newplace.names[row[4]])
        self.place.alt_names = namelist
        # Lat/lon/ID/code/type
        self.place.lat = self.top.get_object('latitude').get_text()
        self.place.long = self.top.get_object('longitude').get_text()
        self.place.gramps_id = self.top.get_object('grampsid').get_text()
        self.place.code = self.top.get_object('postal').get_text()
        self.place.place_type.set(self.type_combo.get_values())
        # Add in URLs if wanted
        if self.keepweb:
            for url in self.newplace.links:
                self.place.add_url(url)
        # Enclose in the next level place
        next_place = False
        parent = None
        if not self.keep_enclosure or not self.place.placeref_list:
            if self.newplace.parent_ids:
                # we might have a parent with geo id 'GEO12345'
                parent = self.dbstate.db.get_place_from_gramps_id(
                    self.newplace.parent_ids[0])
            if not parent and self.newplace.parent_names:
                # make one, will have to be examined/cleaned later
                parent = Place()
                parent.title = ', '.join(self.newplace.parent_names)
                name = PlaceName()
                name.value = parent.title
                parent.name = name
                parent.gramps_id = self.newplace.parent_ids[0]
                with DbTxn(_("Add Place (%s)") % parent.title,
                           self.dbstate.db) as trans:
                    self.dbstate.db.add_place(parent, trans)
                    next_place = True
            if parent:
                if located_in(self.dbstate.db, parent.handle,
                              self.place.handle):
                    # attempting to create a place loop, not good!
                    ErrorDialog(_('Place cycle detected'),
                                msg2=_("The place you chose is enclosed in the"
                                       " place you are workin on!\n"
                                       "Please cancel and choose another "
                                       "place."),
                                parent=self.uistate.window)
                    return
                # check to see if we already have the enclosing place
                already_there = False
                for pref in self.place.placeref_list:
                    if parent.handle == pref.ref:
                        already_there = True
                        break
                if not already_there:
                    placeref = PlaceRef()
                    placeref.set_reference_handle(parent.handle)
                    self.place.set_placeref_list([placeref])
        # Add in Citation/Source if wanted
        if self.addcitation and self.newplace.geoid:
            src_hndl = self.find_or_make_source()
            cit = Citation()
            cit.set_reference_handle(src_hndl)
            cit.set_page("GeoNames ID: %s" %
                         self.newplace.geoid.replace('GEO', ''))
            with DbTxn(_("Add Citation (%s)") % "GeoNames",
                       self.dbstate.db) as trans:
                self.dbstate.db.add_citation(cit, trans)
            self.place.add_citation(cit.handle)
        # We're finally ready to commit the updated place
        with DbTxn(_("Edit Place (%s)") % self.place.title,
                   self.dbstate.db) as trans:
            self.dbstate.db.commit_place(self.place, trans)
        # Jump to enclosing place to clean it if necessary
        if next_place:
            self.set_active('Place', parent.handle)
            self.place = parent
            # if geoparse fails, leave us at main view
            if self.newplace.parent_ids and \
                self.geoparse(self.newplace.parent_ids[0],
                              _(", ").join(self.newplace.parent_names),
                              self.newplace.parent_ids,
                              self.newplace.parent_names):
                # geoparse worked, lets put up the results view
                self.gui.get_child().remove(self.mainwin)
                self.gui.get_child().add(self.results_win)
                self.res_gui()
                return
        self.reset_main()
        if self.gui.get_child().get_child() == self.results_win:
            self.gui.get_child().remove(self.results_win)
            self.gui.get_child().add(self.mainwin)

    def on_res_cancel_clicked(self, dummy):
        """ Cancel operations on this place. """
        self.gui.get_child().remove(self.results_win)
        self.gui.get_child().add(self.mainwin)

    def on_keep_clicked(self, dummy):
        """ Keep button clicked.  Mark selected names rows to keep. """
        model, rows = self.alt_selection.get_selected_rows()
        for row in rows:
            if model[row][0] == 'P':
                continue
            model[row][0] = '\u2714'

    def on_prim_clicked(self, dummy):
        """ Primary button clicked.  Mark first row in selection as Primary
        name, any previous primary as keep """
        model, rows = self.alt_selection.get_selected_rows()
        # Clear prior primary
        for row in model:
            if row[0] == 'P':
                row[0] = '\u2714'
        # mark new one.
        self.top.get_object('primary').set_text(model[rows[0]][1])
        model[rows[0]][0] = 'P'

    def on_disc_clicked(self, dummy):
        """ Discard button clicked.  Unmark selected rows. """
        model, rows = self.alt_selection.get_selected_rows()
        for row in rows:
            if model[row][0] == 'P':
                continue
            model[row][0] = ''

    def on_alt_row_activated(self, *dummy):
        """ Toggle keep status for selected row.  Seems this only works for
        last selected row."""
        model, rows = self.alt_selection.get_selected_rows()
        for row in rows:
            if model[row][0] == 'P':
                continue
            if model[row][0] == '':
                model[row][0] = '\u2714'
            else:
                model[row][0] = ''

    def on_latloncheck(self, *dummy):
        """ Check toggled; if active, load lat/lon from original place, else
        use lat/lon from gazetteer """
        obj = self.top.get_object("latloncheck")
        if not dummy:
            # inititlization
            obj.set_sensitive(True)
            obj.set_active(False)
        place = self.newplace
        if self.place.lat and self.place.long:
            if obj.get_active():
                place = self.place
        else:
            obj.set_sensitive(False)
        self.top.get_object('latitude').set_text(place.lat)
        self.top.get_object('longitude').set_text(place.long)

    def on_postalcheck(self, *dummy):
        """ Check toggled; if active, load postal from original place, else
        use postal from gazetteer """
        obj = self.top.get_object("postalcheck")
        if not dummy:
            # inititlization
            obj.set_sensitive(True)
            obj.set_active(False)
        place = self.newplace
        if self.place.code:
            if obj.get_active():
                place = self.place
            obj.set_sensitive(True)
        else:
            obj.set_sensitive(False)
        self.top.get_object('postal').set_text(place.code)

    def on_typecheck(self, *dummy):
        """ Check toggled; if active, load type from original place, else
        use type from gazetteer """
        obj = self.top.get_object("typecheck")
        combo = self.top.get_object('place_type')
        additional = sorted(self.dbstate.db.get_place_types(),
                            key=lambda s: s.lower())
        self.type_combo = StandardCustomSelector(PlaceType().get_map(), combo,
                                                 PlaceType.CUSTOM,
                                                 PlaceType.UNKNOWN,
                                                 additional)
        if not dummy:
            # inititlization
            obj.set_sensitive(True)
            obj.set_active(False)
        place = self.newplace
        if(self.place.place_type and
           self.place.place_type != PlaceType.UNKNOWN):
            if obj.get_active():
                place = self.place
        else:
            obj.set_sensitive(False)
        self.type_combo.set_values((int(place.place_type),
                                    str(place.place_type)))

    def on_idcheck(self, *dummy):
        """ Check toggled; if active, load gramps_id from original place, else
        use geonamesid from gazetteer """
        obj = self.top.get_object("idcheck")
        if not dummy:
            # inititlization
            obj.set_sensitive(True)
            obj.set_active(False)
        place = self.newplace
        if self.place.gramps_id:
            if obj.get_active():
                place = self.place
        else:
            obj.set_sensitive(False)
        self.top.get_object('grampsid').set_text(place.gramps_id)

    def find_or_make_source(self):
        """ Find or create a source.
        returns handle to source."""
        for hndl in self.dbstate.db.get_source_handles():
            if self.dbstate.db.get_raw_source_data(hndl)[2] == 'GeoNames':
                return hndl
        # No source found, lets add one with associated repo and note
        repo = Repository()
        repo.set_name("www.geonames.org")
        rtype = RepositoryType(RepositoryType.WEBSITE)
        repo.set_type(rtype)
        url = Url()
        url.set_path('http://www.geonames.org/')
        url.set_description(_('GeoNames web site'))
        url.set_type(UrlType(UrlType.WEB_HOME))
        repo.add_url(url)
        url = Url()
        url.set_path('marc@geonames.org')
        url.set_description(_('GeoNames author'))
        url.set_type(UrlType(UrlType.EMAIL))
        repo.add_url(url)

        note_txt = StyledText(_(
            'GeoNames was founded by Marc Wick. You can reach him at '))
        note_txt += StyledText('marc@geonames.org' + '\n')
        note_txt += StyledText(_(
            'GeoNames is a project of Unxos GmbH, Weingartenstrasse 8,'
            ' 8708 Männedorf, Switzerland.\nThis work is licensed under a '))
        note_txt += linkst(
            _('Creative Commons Attribution 3.0 License'),
            'https://creativecommons.org/licenses/by/3.0/legalcode')

        new_note = Note()
        new_note.set_styledtext(note_txt)
        new_note.set_type(NoteType.REPO)
        src = Source()
        src.title = 'GeoNames'
        src.author = 'Marc Wick'
        repo_ref = RepoRef()
        mtype = SourceMediaType(SourceMediaType.ELECTRONIC)
        repo_ref.set_media_type(mtype)
        with DbTxn(_("Add Souce/Repo/Note (%s)") % "GeoNames",
                   self.dbstate.db) as trans:

            self.dbstate.db.add_note(new_note, trans)
            repo.add_note(new_note.get_handle())
            self.dbstate.db.add_repository(repo, trans)
            repo_ref.set_reference_handle(repo.handle)
            src.add_repo_reference(repo_ref)
            self.dbstate.db.add_source(src, trans)
        return src.handle

# Preferences dialog items

    def on_prefs_clicked(self, dummy):
        """ Button: display preference dialog """
        top = self.top.get_object("pref_dialog")
        top.set_transient_for(self.uistate.window)
        parent_modal = self.uistate.window.get_modal()
        if parent_modal:
            self.uistate.window.set_modal(False)
        keepweb = self.top.get_object("keepweb")
        keepweb.set_active(self.keepweb)
        addcit = self.top.get_object("addcitation")
        addcit.set_active(self.addcitation)
        # for some reason you can only set the radiobutton to True
        self.top.get_object(
            "enc_radio_but_keep" if self.keep_enclosure
            else "enc_radio_but_repl").set_active(True)
        geoid = self.top.get_object("geonames_id_entry")
        geoid.set_text(self.geonames_id)
        keepalt = self.top.get_object("keep_alt_entry")
        keepalt.set_text(' '.join(self.allowed_languages))
        top.show()
        top.run()
        if self.uistate.window and parent_modal:
            self.uistate.window.set_modal(True)
        self.geonames_id = geoid.get_text()
        self.addcitation = addcit.get_active()
        self.keepweb = keepweb.get_active()
        self.keep_enclosure = self.top.get_object(
            "enc_radio_but_keep").get_active()
        self.allowed_languages = keepalt.get_text().split()
        top.hide()

    def on_pref_help_clicked(self, dummy):
        ''' Button: Display the relevant portion of GRAMPS manual'''
        display_url(PREFS_WIKI)

    def lookup_places_by_name(self, search_name):
        """ In local db.  Only completed places are matched.
        We may want to try some better matching algorithms, possibly
        something from difflib"""
        search_name = search_name.lower().split(',')
        places = []
        for place in self.dbstate.db.iter_places():
            if (place.get_type() != PlaceType.UNKNOWN and
                (place.get_type() == PlaceType.COUNTRY or
                 (place.get_type() != PlaceType.COUNTRY and
                  place.get_placeref_list()))):
                # valid place, get all its names
                for name in place.get_all_names():
                    if name.get_value().lower() == search_name[0]:
                        places.append(place)
                        break
        return places

    def find_an_incomplete_place(self):
        """ in our db.  Will return with a place (and active set to place)
        or None if no incomplete places, in which case active will be the same.
        Will also find unused places, and offer to delete."""
        p_hndls = self.dbstate.db.get_place_handles()
        if not p_hndls:
            return None  # in case there aren't any
        # keep handles in an order to avoid inconsistant
        # results when db returns them in different orders.
        p_hndls.sort()
        # try to find the handle after the previously scanned handle in the
        # list.
        found = False
        for indx, hndl in enumerate(p_hndls):
            if hndl > self.incomp_hndl:
                found = True
                break
        if not found:
            indx = 0
        # now, starting from previous place, look for incomplete place
        start = indx
        while True:
            hndl = p_hndls[indx]
            place_data = self.dbstate.db.get_raw_place_data(hndl)
            p_type = place_data[8][0]  # place_type
            refs = list(self.dbstate.db.find_backlink_handles(hndl))
            if(p_type == PlaceType.UNKNOWN or
               not refs or
               p_type != PlaceType.COUNTRY and
               not place_data[5]):  # placeref_list
                # need to get view to this place...
                self.set_active("Place", hndl)
                self.incomp_hndl = hndl
                if not refs:
                    WarningDialog(
                        _('This Place is not used!'),
                        msg2=_('You should delete it, or, if it contains '
                               'useful notes or other data, use the Find to '
                               'merge it into a valid place.'),
                        parent=self.uistate.window)
                return self.dbstate.db.get_place_from_handle(hndl)
            indx += 1
            if indx == len(p_hndls):
                indx = 0
            if indx == start:
                break
        return None


class NewPlace():
    """ structure to store data about a found place"""
    def __init__(self, title):
        self.title = title
        self.gramps_id = ''
        self.lat = ''
        self.long = ''
        self.code = ''
        self.place_type = None
        self.names = []  # all names, including alternate, acts like a set
        self.name = PlaceName()
        self.links = []
        self.geoid = ''
        self.parent_ids = []   # list of gramps_ids in hierarchical order
        self.parent_names = [] # list of names in hierarchical order

    def add_name(self, name):
        """ Add a name to names list without repeats """
        if ',' in name.value:
            name.value = name.value.split(',')[0]
            return
        if name not in self.names:
            self.names.append(name)

    def add_names(self, names):
        """ Add names to names list without repeats """
        for name in names:
            self.add_name(name)

#------------------------------------------------------------------------
#
# Functions
#
#------------------------------------------------------------------------


def linkst(text, url):
    """ Return text as link styled text
    """
    tags = [StyledTextTag(StyledTextTagType.LINK, url, [(0, len(text))])]
    return StyledText(text, tags)


def inc_sort(model, row1, row2, user_data):
    value1 = model.get_value(row1, 0)
    value2 = model.get_value(row2, 0)
    if value1 == value2:
        return 0
    if value1 == 'P':
        return -1
    if value2 == 'P':
        return 1
    if value2 > value1:
        return 1
    else:
        return -1

# if found a matching place in our db, merge
# if not, lookup on web, present list of candidates
# start with simple search
#   extend each result with heirarchy query
# Web button, if pressed again, more answers.

# Alternative name Lang field:
#   unlc:Un/locodes
#   post:for postal codes
#   iata,icao,faac: for airport codes
#   fr_1793:French Revolution names
#   abbr:abbreviation
#   link: to a website (mostly to wikipedia)
#   wkdt: for the wikidata id
#   otherwise 2/3 char ISO639 lang code
#   empty: just an alternative name
# Alternative name other fields:
#   isPreferredName="true"
#   isShortName="true"
#   isColloquial="true"
#   isHistoric="true"
