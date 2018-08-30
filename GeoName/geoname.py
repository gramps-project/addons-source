#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2015      Nick Hall
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
GeoName Gramplet.
"""

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
from urllib.request import urlopen, quote
from xml.dom.minidom import parseString

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
from gramps.gen.plug import Gramplet
from gramps.gen.db import DbTxn
from gramps.gen.lib import Place, PlaceName, PlaceType, PlaceRef, Url, UrlType
from gramps.gen.datehandler import parser
from gramps.gen.config import config
from gramps.gen.display.place import displayer as _pd

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

GeoNames_Account = "garygriffin"

#------------------------------------------------------------------------
#
# GeoName class
#
#------------------------------------------------------------------------
class GeoName(Gramplet):
    """
    Gramplet to get places from the GeoNames database.
    """
    def init(self):
        """
        Initialise the gramplet.
        """
        root = self.__create_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(root)
        root.show_all()

    def __create_gui(self):
        """
        Create and display the GUI components of the gramplet.
        """
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_spacing(4)

        label = Gtk.Label(_('Enter either GeoName ID (number) or the populated place in the format: city, US-state code or city, country code such as, Cleveland, OH or Paris, FR'))
        label.set_halign(Gtk.Align.START)

        self.entry = Gtk.Entry()

        button_box = Gtk.ButtonBox()
        button_box.set_layout(Gtk.ButtonBoxStyle.START)

        get = Gtk.Button(label=_('Get Place'))
        get.connect("clicked", self.__get_places)
        button_box.add(get)

        vbox.pack_start(label, False, True, 0)
        vbox.pack_start(self.entry, False, True, 0)
        vbox.pack_start(button_box, False, True, 0)

        return vbox

    def main(self):
        """
        Called to update the display.
        """
        pass

    def __get_places(self, obj):
        geoNames_id = self.entry.get_text()
        fmt = config.get('preferences.place-format')
        pf = _pd.get_formats()[fmt]
        preferred_lang = pf.language
        if len(preferred_lang) != 2:
            preferred_lang = 'en'
#
# Get GeoName ID for the entered populated place. 
# First check if the input is a number (GeoName ID). If it is, use it. If not, then the input is the entity name
#     Search assuming 2-letter code is a state/province ID. 
#     If that fails, then assume it is a country code
#
        if geoNames_id.isnumeric():
            geoNames_Hierachy_url = 'http://api.geonames.org/hierarchy?username='+ GeoNames_Account + '&geonameId=' + geoNames_id
        else:
            words = geoNames_id.split(',')
            if len(words) < 2: return
            geoNames_Search_url = 'http://api.geonames.org/search?username=' + GeoNames_Account + '&featureClass=P&adminCode1=' + quote(words[1]) + '&name_equals=' + quote(words[0])
            response = urlopen(geoNames_Search_url)
            data = response.read()
            dom = parseString(data)
            top = dom.getElementsByTagName('geonames')
        
            value = top[0].getElementsByTagName('totalResultsCount')
            if len(value):
                found_requests = value[0].childNodes[0].data
                if found_requests == '0':
                    geoNames_Search_url = 'http://api.geonames.org/search?username=' + GeoNames_Account + '&featureClass=P&country=' + quote(words[1]) + '&name_equals=' + quote(words[0])
                    response=urlopen(geoNames_Search_url)
                    data = response.read()
                    dom = parseString(data)
                    top = dom.getElementsByTagName('geonames')

                    value = top[0].getElementsByTagName('totalResultsCount')
                    if len(value):
                        found_requests = value[0].childNodes[0].data
                        if found_requests == '0':
                            return []
            top = dom.getElementsByTagName('geoname')
            value = top[0].getElementsByTagName('geonameId')
            geoNames_Hierachy_url = 'http://api.geonames.org/hierarchy?username='+ GeoNames_Account + '&geonameId=' + value[0].childNodes[0].data
        response = urlopen(geoNames_Hierachy_url)
        data = response.read()
        dom = parseString(data)
        top = dom.getElementsByTagName('geonames')
        visited = {}
#
# now parse Hierarchy
#
        with DbTxn(_('Add GeoNames-id place %s') % geoNames_id, self.dbstate.db) as trans:
            parentID = None
            for element in top[0].getElementsByTagName('geoname'):
                value = element.getElementsByTagName('fcl')
                feature_code = value[0].childNodes[0].data
                if feature_code == 'L' : continue
                value = element.getElementsByTagName('geonameId')
                geoname_entity_id = "Geo" + value[0].childNodes[0].data

                place = self.dbstate.db.get_place_from_gramps_id(geoname_entity_id)
                if place is not None:
                    visited[geoname_entity_id] = (place, [])
                else:
                    place, ref_list = self.__get_place(geoname_entity_id, parentID, preferred_lang)
                    if place.get_name().get_value is not '':
                        self.dbstate.db.add_place(place, trans)
                        visited[geoname_entity_id] = (place, ref_list)
                parentID = geoname_entity_id
            for place, ref_list in visited.values():
                if len(ref_list) > 0:
                    for ref, date in ref_list:
                        handle = visited[ref][0].handle
                        place_ref = PlaceRef()
                        place_ref.ref = handle
                        place_ref.set_date_object(date)
                        place.add_placeref(place_ref)
                    self.dbstate.db.commit_place(place, trans)
#
#
#
    def __get_place(self,entity_id, parent, preferred_lang):
#
#  Get the detail data for the GeoName entity and extract all properties. This includes Lat/Lon, FeatureCode, PostalCode, and AlternateNames
#
        geoNames_Get_url = 'http://api.geonames.org/get?username=' + GeoNames_Account + '&geonameId=' + entity_id[3:]
        response = urlopen(geoNames_Get_url)
        data = response.read()
        dom = parseString(data)
        element = dom.getElementsByTagName('geoname')
        
        place = Place()
        curr_lang = "en"
        place.gramps_id = entity_id
        value = element[0].getElementsByTagName('name')
        place_name = PlaceName()
        place_name.set_value(value[0].childNodes[0].data)
        place_name.set_language(curr_lang)
        place.name = place_name
        value = element[0].getElementsByTagName('lat')
        place.set_latitude(str(value[0].childNodes[0].data))
        value = element[0].getElementsByTagName('lng')
        place.set_longitude(str(value[0].childNodes[0].data))
        value = element[0].getElementsByTagName('fcl')
        feature_code = value[0].childNodes[0].data

        value = element[0].getElementsByTagName('toponymName')
        geoname_fcode = value[0].childNodes[0].data
        allowed_languages = ["en","fr","de","pl","ru","da","es","fi","sw","no",preferred_lang]
#
# Try to deduce PlaceType:  
#   If populated place, set as City. Long description could over-ride
#   Parse long description, looking for keyword (Region, County, ...)
#   Top-level must be a country. 
#   Children of USA are States. 
#   Children of Canada are Provinces.
#
        level = -1
        if feature_code == 'P' : level = 4
        for tup in PlaceType._DATAMAP :
            if tup[2] in geoname_fcode: level = tup[0]
        US_code = "Geo6252001"
        CA_code = "Geo6251999"
        if parent is None : level = 1
        if parent == US_code : level = 2
        if parent == CA_code : level = 8

        place.set_type(PlaceType(level))
        for pname in element[0].getElementsByTagName('alternateName'):
            if pname.getAttribute("lang"):
                pattr = pname.getAttribute("lang")
                if(pattr == "post"):
                    place.set_code(place.get_code() + " " + pname.childNodes[0].data)
                elif pattr in allowed_languages :
                    new_place = PlaceName()
                    new_place.set_language(pattr)
                    new_place.set_value(pname.childNodes[0].data)
                    if (preferred_lang == pattr) and (preferred_lang != curr_lang) :
                        curr_lang = preferred_lang
                        place.add_alternative_name(place.get_name())
                        place.set_name(new_place)
                    else:
                        place.add_alternative_name(new_place)
            else:
                new_place = PlaceName()
                new_place.set_value(pname.childNodes[0].data)
                new_place.set_language("en")
                place.add_alternative_name(new_place)
        ref_list = []
        if parent is not None:
            ref_list.append((parent,None))
        return place, ref_list

