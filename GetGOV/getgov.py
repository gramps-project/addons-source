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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""
GetGOV Gramplet.
"""

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
from urllib.request import urlopen, quote, URLError
from xml.dom.minidom import parseString
import socket
import re
import os
import json

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
from gramps.gen.lib import (Place, PlaceName, PlaceType, PlaceRef,
                            PlaceGroupType as P_G, PlaceHierType as P_H,
                            Url, UrlType)
from gramps.gen.datehandler import parser
from gramps.gen.config import config
from gramps.gen.display.place import displayer as _pd
from gramps.gen.utils.id import create_id
from gramps.gui.dialog import ErrorDialog

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

ISO_CODE_LOOKUP = {
    "aar": "aa",
    "abk": "ab",
    "afr": "af",
    "aka": "ak",
    "alb": "sq",
    "amh": "am",
    "ara": "ar",
    "arg": "an",
    "arm": "hy",
    "asm": "as",
    "ava": "av",
    "ave": "ae",
    "aym": "ay",
    "aze": "az",
    "bak": "ba",
    "bam": "bm",
    "baq": "eu",
    "bel": "be",
    "ben": "bn",
    "bih": "bh",
    "bis": "bi",
    "bod": "bo",
    "bos": "bs",
    "bre": "br",
    "bul": "bg",
    "bur": "my",
    "cat": "ca",
    "ces": "cs",
    "cha": "ch",
    "che": "ce",
    "chi": "zh",
    "chu": "cu",
    "chv": "cv",
    "cor": "kw",
    "cos": "co",
    "cre": "cr",
    "cym": "cy",
    "cze": "cs",
    "dan": "da",
    "deu": "de",
    "div": "dv",
    "dut": "nl",
    "dzo": "dz",
    "ell": "el",
    "eng": "en",
    "epo": "eo",
    "est": "et",
    "eus": "eu",
    "ewe": "ee",
    "fao": "fo",
    "fas": "fa",
    "fij": "fj",
    "fin": "fi",
    "fra": "fr",
    "fre": "fr",
    "fry": "fy",
    "ful": "ff",
    "geo": "ka",
    "ger": "de",
    "gla": "gd",
    "gle": "ga",
    "glg": "gl",
    "glv": "gv",
    "gre": "el",
    "grn": "gn",
    "guj": "gu",
    "hat": "ht",
    "hau": "ha",
    "heb": "he",
    "her": "hz",
    "hin": "hi",
    "hmo": "ho",
    "hrv": "hr",
    "hun": "hu",
    "hye": "hy",
    "ibo": "ig",
    "ice": "is",
    "ido": "io",
    "iii": "ii",
    "iku": "iu",
    "ile": "ie",
    "ina": "ia",
    "ind": "id",
    "ipk": "ik",
    "isl": "is",
    "ita": "it",
    "jav": "jv",
    "jpn": "ja",
    "kal": "kl",
    "kan": "kn",
    "kas": "ks",
    "kat": "ka",
    "kau": "kr",
    "kaz": "kk",
    "khm": "km",
    "kik": "ki",
    "kin": "rw",
    "kir": "ky",
    "kom": "kv",
    "kon": "kg",
    "kor": "ko",
    "kua": "kj",
    "kur": "ku",
    "lao": "lo",
    "lat": "la",
    "lav": "lv",
    "lim": "li",
    "lin": "ln",
    "lit": "lt",
    "ltz": "lb",
    "lub": "lu",
    "lug": "lg",
    "mac": "mk",
    "mah": "mh",
    "mal": "ml",
    "mao": "mi",
    "mar": "mr",
    "may": "ms",
    "mkd": "mk",
    "mlg": "mg",
    "mlt": "mt",
    "mon": "mn",
    "mri": "mi",
    "msa": "ms",
    "mya": "my",
    "nau": "na",
    "nav": "nv",
    "nbl": "nr",
    "nde": "nd",
    "ndo": "ng",
    "nep": "ne",
    "nld": "nl",
    "nno": "nn",
    "nob": "nb",
    "nor": "no",
    "nya": "ny",
    "oci": "oc",
    "oji": "oj",
    "ori": "or",
    "orm": "om",
    "oss": "os",
    "pan": "pa",
    "per": "fa",
    "pli": "pi",
    "pol": "pl",
    "por": "pt",
    "pus": "ps",
    "que": "qu",
    "roh": "rm",
    "ron": "ro",
    "rum": "ro",
    "run": "rn",
    "rus": "ru",
    "sag": "sg",
    "san": "sa",
    "sin": "si",
    "slk": "sk",
    "slo": "sk",
    "slv": "sl",
    "sme": "se",
    "smo": "sm",
    "sna": "sn",
    "snd": "sd",
    "som": "so",
    "sot": "st",
    "spa": "es",
    "sqi": "sq",
    "srd": "sc",
    "srp": "sr",
    "ssw": "ss",
    "sun": "su",
    "swa": "sw",
    "swe": "sv",
    "tah": "ty",
    "tam": "ta",
    "tat": "tt",
    "tel": "te",
    "tgk": "tg",
    "tgl": "tl",
    "tha": "th",
    "tib": "bo",
    "tir": "ti",
    "ton": "to",
    "tsn": "tn",
    "tso": "ts",
    "tuk": "tk",
    "tur": "tr",
    "twi": "tw",
    "uig": "ug",
    "ukr": "uk",
    "urd": "ur",
    "uzb": "uz",
    "ven": "ve",
    "vie": "vi",
    "vol": "vo",
    "wel": "cy",
    "wln": "wa",
    "wol": "wo",
    "xho": "xh",
    "yid": "yi",
    "yor": "yo",
    "zha": "za",
    "zho": "zh",
    "zul": "zu"}


COU = "#FFFF00000000"
REG = "#0000FFFFFFFF"
PLA = "#0000FFFF0000"
OTH = "#800080008000"
types_file = os.path.join(os.path.dirname(__file__), "gov_types.json")


#------------------------------------------------------------------------
#
# GetGOV class
#
#------------------------------------------------------------------------
class GetGOV(Gramplet):
    """
    Gramplet to get places from the GOV database.
    """
    def init(self):
        """
        Initialise the gramplet.
        """
        self.place_view = None
        root = self.__create_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(root)
        root.show_all()
        self.update_btn.set_sensitive(False)
        self.types_scanned = False  # if we need to scan for types in db
        self.visited = {}      # key: place handle, data: True for touched, or
        #                      # list of [(date, hierarchy)] tuples

    type_dic = {}     # key: str type num, data: name

    def __create_gui(self):
        """
        Create and display the GUI components of the gramplet.
        """
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_spacing(4)

        label = Gtk.Label(label=_('Enter GOV-id:'))
        label.set_halign(Gtk.Align.START)

        self.entry = Gtk.Entry()

        button_box = Gtk.ButtonBox()
        button_box.set_layout(Gtk.ButtonBoxStyle.START)

        get = Gtk.Button(label=_('Get Place'))
        get.connect("clicked", self.__get_places)
        button_box.add(get)

        self.update_btn = Gtk.Button(label=_('Update'))
        self.update_btn.connect("clicked", self.__update_places)
        button_box.add(self.update_btn)

        vbox.pack_start(label, False, True, 0)
        vbox.pack_start(self.entry, False, True, 0)
        vbox.pack_start(button_box, False, True, 0)

        return vbox

    def db_changed(self):
        if self.dbstate.is_open():
            self.connect(self.dbstate.db, 'place-update', self.update)
            self.connect_signal('Place', self.update)
        else:
            self.update_btn.set_sensitive(False)
            self.types_scanned = False

    def main(self):
        if not self.place_view:
            _vm = self.uistate.viewmanager
            self.place_view = _vm.pages[_vm.page_lookup[(
                _vm.navigator.active_cat, _vm.navigator.active_view)]]
            self.place_view.selection.connect('changed', self.row_changed)
            self.row_changed()
        if not self.types_scanned and self.type_dic:
            # scan db to see if any of the Gov_xx are in use
            got_new = got_any = False
            count = 0
            for place in self.dbstate.db.iter_places():
                if count % 100 == 0:
                    yield True
                for typ in place.get_types():
                    if typ.pt_id.startswith("Gov_"):
                        got_any = True
                        tup = self.type_dic[typ.pt_id[4:]]
                        if tup[2]:
                            continue
                        tup[2] = True
                        got_new = True
            if not got_any:
                # clear down the type usage data
                for data in self.type_dic.values():
                    data[2] = False
                got_new = True
            if got_new:
                # save changes
                with open(types_file, 'w', encoding='utf-8') as f_p:
                    json.dump((self.type_dic), f_p,
                              ensure_ascii=False, indent=2)
                load_on_reg(None, None, None, getfile=False)
                self.dbstate.db.emit("custom-type-changed")

    _gramps_id = re.compile(r' *[^\d]{0,3}(\d+){3,9}[^\d]{0,3}')

    def row_changed(self, *_selection):
        """
        from the Place view
        """
        selected_ids = self.place_view.selected_handles()
        if not selected_ids:
            return
        place = self.dbstate.db.get_place_from_handle(selected_ids[0])
        # See if this is a normal Gramps ID (if not, GOV ID)
        if not (self._gramps_id.match(place.gramps_id) or
                place.gramps_id.startswith("GEO")):
            self.update_btn.set_sensitive(True)
        else:
            self.update_btn.set_sensitive(False)

    def __update_places(self, _obj):
        """
        This is called when the update button is clicked.
        The selected places are updated from GOV
        """
        try:
            self.preferred_lang = config.get('preferences.place-lang')
        except AttributeError:
            fmt = config.get('preferences.place-format')
            pf = _pd.get_formats()[fmt]
            self.preferred_lang = pf.language
        if len(self.preferred_lang) != 2:
            self.preferred_lang = glocale.lang[0:2]

        if not self.type_dic:
            # if first run, get all the place types information from GOV
            if not self.__get_types():
                self.type_dic = {}
                return

        selected_ids = self.place_view.selected_handles()
        for hndl in selected_ids:
            place = self.dbstate.db.get_place_from_handle(hndl)
            # See if this is a normal Gramps ID (if not, GOV ID)
            if(self._gramps_id.match(place.gramps_id) or
               place.gramps_id.startswith("GEO")):
                continue
            self.__update_place(place)

    def __update_place(self, place):
        """
        Update a single place from GOV data.  Note: this will actually call
        itself recursivly if an enclosing place seems out of date.  It will
        also call __add_place if an enclosing place is entirely missing.

        Returns: [(date, hierarchy)] list of tuples
        """
        ret = self.visited.get(place.handle)
        if ret is True:  # we have been here before and have a loop
            print("Error: Place enclosure Loop in GOV data!")
            return None
        elif ret is not None:  # we have added or validated this place
            return place.handle, ret

        # get place data from GOV
        resp = self.__get_place(place.gramps_id)
        if not resp:
            return None
        u_place, ref_list, hiers = resp
        # this is tracked to detect possible loops
        self.visited[place.handle] = True
        # We replace the place enclosures from the found GOV data
        place.set_placeref_list([])
        for ref, date in ref_list:
            resp = self.__add_place(ref)
            if resp is None:
                return None
            handle, hiers = resp

            place_ref = PlaceRef()
            place_ref.ref = handle
            place_ref.set_date_object(date)
            for hdate, hier in hiers:
                if hdate.is_empty() or date.match_exact(hdate):
                    hierarchy = hier
                    break
            else:
                hierarchy = P_H(P_H.ADMIN)
            place_ref.set_type(hierarchy)
            place.add_placeref(place_ref)
        # we replace the current types from the found GOV types
        place.set_types(u_place.get_types())
        # we replace the current names from the found GOV names
        place.set_names(u_place.get_names())
        # we replace the current urls from the found GOV urls
        place.set_url_list(u_place.get_url_list())
        with DbTxn(_('Update GOV-id place %s') % place.gramps_id,
                   self.dbstate.db) as self.trans:
            self.dbstate.db.add_place(place, self.trans)
        self.visited[place.handle] = hiers
        return hiers

    def __get_places(self, _obj):
        """
        Main routine called when entering a GOV ID.  This looks up the place,
        adds it to db, and adds any enclosing places not already present.
        """
        gov_id = self.entry.get_text()
        try:
            self.preferred_lang = config.get('preferences.place-lang')
        except AttributeError:
            fmt = config.get('preferences.place-format')
            pf = _pd.get_formats()[fmt]
            self.preferred_lang = pf.language
        if len(self.preferred_lang) != 2:
            self.preferred_lang = glocale.lang[0:2]

        if not self.type_dic:
            # if first run, get all the place types information from GOV
            if not self.__get_types():
                self.type_dic = {}
                return
        self.__add_place(gov_id)

    def __add_place(self, gov_id):
        """
        This looks up and then adds a single place.  During enclosure
        processing, the method may get called recursivly to add missing
        enclosing places.  Or, if the enclosing place exists, but doesn't
        have valid GOV place Types, the __update_place method might get called.

        returns place handle, [(date, hierarchy)] list of tuples
        """
        place = self.dbstate.db.get_place_from_gramps_id(gov_id)
        if place is not None:
            ret = self.visited.get(place.handle)
            if ret is True:  # we have been here before and have a loop
                print("Error: Place enclosure Loop in GOV data!")
                return None
            elif ret is not None:  # we have added or validated this place
                return place.handle, ret

            # need to figure out hierarchy from the place type
            hiers = []
            try:
                for ptype in place.get_types():
                    type_date = ptype.get_date_object()
                    gtype = ptype.pt_id.split("Gov_")[1]
                    hierarchy = self.groups[self.type_dic[gtype][1]][1]
                    hiers.append((type_date, hierarchy))
            except (IndexError, ValueError):
                    # GOV placetype not found, need to perform an update
                    hiers = self.__update_place(place)
                    if hiers is None:
                        hiers = []
        else:
            resp = self.__get_place(gov_id)
            if not resp:
                return None
            place, ref_list, hiers = resp
            # this is tracked to detect possible loops
            self.visited[place.handle] = True
            for ref, date in ref_list:
                resp = self.__add_place(ref)
                if resp is None:
                    return None
                handle, hiers = resp

                place_ref = PlaceRef()
                place_ref.ref = handle
                place_ref.set_date_object(date)
                for hdate, hier in hiers:
                    if(hdate.is_empty() or date is None or
                       date.match_exact(hdate)):
                        hierarchy = hier
                        break
                else:
                    hierarchy = P_H(P_H.ADMIN)
                place_ref.set_type(hierarchy)
                place.add_placeref(place_ref)
            with DbTxn(_('Add GOV-id place %s') % gov_id,
                       self.dbstate.db) as self.trans:
                self.dbstate.db.add_place(place, self.trans)
        self.visited[place.handle] = hiers
        return place.handle, hiers

    groups = {
        # key is GOV group, data is tuple(group, hierarchy, priority)
        1: (P_G(P_G.REGION), P_H(P_H.ADMIN), 7, REG),     # Administrative
        2: (P_G(_("Civil")), P_H(_("Civil")), 13, OTH),
        3: (P_G(P_G.REGION), P_H(P_H.RELI), 12, REG),     # Religious
        4: (P_G(P_G.REGION), P_H(P_H.GEOG), 10, REG),     # Geographical
        5: (P_G(P_G.REGION), P_H(P_H.CULT), 14, REG),     # Cultural
        6: (P_G(P_G.REGION), P_H(P_H.JUDI), 15, REG),     # Judicial
        8: (P_G(P_G.PLACE), P_H(P_H.ADMIN), 8, PLA),      # Places
        9: (P_G(P_G.REGION), P_H(_("Transportation")), 11, REG),
        10: (P_G(P_G.UNPOP), P_H(P_H.ADMIN), 9, PLA),    # Unpopulated Places
        13: (P_G(P_G.NONE), P_H(P_H.ADMIN), 16, OTH),    # Other
        26: (P_G(P_G.COUNTRY), P_H(P_H.ADMIN), 0, COU),  # ADM0 Countries
        27: (P_G(P_G.REGION), P_H(P_H.ADMIN), 1, REG),   # ADM1 States
        28: (P_G(P_G.REGION), P_H(P_H.ADMIN), 2, REG),   # ADM2 Counties
        29: (P_G(P_G.REGION), P_H(P_H.ADMIN), 3, REG),   # ADM3
        30: (P_G(P_G.REGION), P_H(P_H.ADMIN), 4, REG),   # ADM4
        31: (P_G(P_G.PLACE), P_H(P_H.ADMIN), 5, PLA),    # ADM5 Cities, etc.
        32: (P_G(P_G.PLACE), P_H(P_H.ADMIN), 6, PLA),    # ADM6
    }

    def __get_types(self):
        """
        Get the types tables from GOV.  We collect type names (for each
        available language), and the GOV group, which is translated to
        PlaceGroupType, as well as the hierarchy the type belongs to.

        This collects all the types.
        """
        type_url = 'http://gov.genealogy.net/types.owl/'
        dom = self.get_gov_data(type_url)
        if not dom:
            return False
        for group in dom.getElementsByTagName('owl:Class') :
            url_value = group.attributes['rdf:about'].value
            group_number = url_value.split('#')[1]
            g_num = int(group_number.replace('group_', ''))
            for element in dom.getElementsByTagNameNS("http://gov.genealogy."
                                                      "net/types.owl#",
                                                      group_number):
                self.__do_type(dom, element, g_num)
            for element in dom.getElementsByTagNameNS("http://gov.genealogy."
                                                      "net/ontology.owl#",
                                                      'Type'):
                self.__do_type(dom, element, g_num)
        with open(types_file, 'w', encoding='utf-8') as f_p:
            json.dump((self.type_dic), f_p,
                      ensure_ascii=False, indent=2)
        load_on_reg(None, None, None, getfile=False)
        self.dbstate.db.emit("custom-type-changed")
        return True

    def get_gov_data(self, url):
        """
        Get GOV data from web with error checking
        """
        try:
            with urlopen(url, timeout=20) as response:
                data = response.read()
        except URLError as err:
            try:
                txt = err.read().decode('utf-8')
            except Exception:
                txt = ''
            ErrorDialog(_('Problem getting data from web'),
                        msg2=str(err) + '\n' + txt,
                        parent=self.uistate.window)
            return None
        except socket.timeout:
            ErrorDialog(_('Problem getting data from web'),
                        msg2=_('Web request Timeout, you can try again...'),
                        parent=self.uistate.window)
            return None

        dom = parseString(data)
        status = dom.getElementsByTagName('rdf:RDF')
        if not status:
            ErrorDialog(_('Problem getting data from GOV'),
                        parent=self.uistate.window)
            return None
        return dom

    def __do_type(self, _dom, element, g_num):
        """
        Get the individual type datas from GOV.  We collect type names (for
        each available language), and the GOV group, which is translated to
        PlaceGroupType, as well as the hierarchy the type belongs to.
        """
        type_number = element.attributes['rdf:about'].value.split('#')[1]
        langs = {}  # key:lang, data:name
        for pname in element.getElementsByTagName('rdfs:label'):
            type_lang = pname.attributes['xml:lang'].value
            type_text = pname.childNodes[0].data
            langs[type_lang] = type_text[:1].upper() + type_text[1:]
        groups = [g_num]
        for res in element.getElementsByTagName('rdf:type'):
            gx_num = res.attributes['rdf:resource'].value.split('#')[1]
            if gx_num == 'Type' or 'group_' not in gx_num:
                continue
            groups.append(int(gx_num.replace('group_', '')))
        # we may have several groups, need to prioritize best group
        group = 13  # original value for 'other'
        prior = 20  # low priority
        for grp in groups:
            tup = self.groups.get(grp)
            if not tup:
                tup = self.groups[13]
            if tup[2] < prior:
                prior = tup[2]
                group = grp
        self.type_dic[type_number] = list(langs, group, False)

    def __get_place(self, gov_id):
        """
        Get data on an individual place.
        """
        gov_url = 'http://gov.genealogy.net/semanticWeb/about/' + quote(gov_id)

        dom = self.get_gov_data(gov_url)
        if not dom:
            return None
        top = dom.getElementsByTagName('gov:GovObject')

        place = Place()
        place.handle = create_id()

        place.gramps_id = gov_id
        place.group = None
        if not len(top) :
            return place, [], P_H(P_H.ADMIN)

        types = []
        for element in top[0].getElementsByTagName('gov:hasName'):
            place_name = self.__get_hasname(element)
            place.add_name(place_name)
        for element in top[0].getElementsByTagName('gov:hasType'):
            place_type, group_tup = self.__get_hastype(element)
            types.append((place_type, group_tup))
        types.sort(key=lambda typ: typ[0].date.get_sort_value(), reverse=True)
        hiers = []
        for typ in types:
            place.add_type(typ[0])
            hiers.append((typ[0].date, typ[1][1]))
        place.group = types[0][1][0]
        for element in top[0].getElementsByTagName('gov:position'):
            latitude, longitude = self.__get_position(element)
            place.set_latitude(latitude)
            place.set_longitude(longitude)
        ref_list = []
        for element in top[0].getElementsByTagName('gov:isPartOf'):
            ref, date = self.__get_ispartof(element)
            ref_list.append((ref, date))
        for element in top[0].getElementsByTagName('gov:hasURL'):
            url = self.__get_hasurl(element)
            place.add_url(url)

        return place, ref_list, hiers

    def __get_hasname(self, element):
        """
        Get one name data for a place
        """
        name = PlaceName()
        pname = element.getElementsByTagName('gov:PropertyName')
        if len(pname):
            value = pname[0].getElementsByTagName('gov:value')
            if len(value):
                name.set_value(value[0].childNodes[0].data)
            language = pname[0].getElementsByTagName('gov:language')
            if len(language):
                name.set_language(
                    ISO_CODE_LOOKUP.get(language[0].childNodes[0].data))
            date = self.__get_date_range(pname[0])
            name.set_date_object(date)
        return name

    def __get_hastype(self, element):
        """
        get one type data for place
        """
        place_type = PlaceType()
        ptype = element.getElementsByTagName('gov:PropertyType')
        gnum = 8  # default to generic place if nothing found
        if not len(ptype):
            return place_type, self.groups[gnum]
        value = ptype[0].getElementsByTagName('gov:type')
        if len(value):
            type_url = value[0].attributes['rdf:resource'].value
            type_num = type_url.split('#')[1]
            tup = self.type_dic.get(type_num, None)
            pt_id = "Gov_%s" % type_num
            gnum = tup[1]
            if not tup:
                # TODO Types list out of date?
                place_type.set((pt_id, _("Unknown") + ":%s" % type_num))
            else:
                for lang in (self.preferred_lang, 'de', 'en'):
                    t_nam = tup[0].get(lang, None)
                    if not t_nam:
                        continue
                    place_type.set((pt_id, t_nam))
                    break
                if not tup[2]:  # do we have in db?
                    # if not, then flag as used and update the DATAMAP so
                    # Place Type selector sees it.
                    tup[2] = True
                    nam, nat, _ctr, col, grp, tra = PlaceType.DATAMAP[pt_id]
                    PlaceType.DATAMAP[pt_id] = (nam, nat, "GOV", col, grp, tra)
        date = self.__get_date_range(ptype[0])
        if date:
            place_type.set_date_object(date)
        return place_type, self.groups[gnum]

    def __get_position(self, element):
        """
        Get position data for place
        """
        latitude = ''
        longitude = ''
        point = element.getElementsByTagName('wgs84:Point')
        if len(point):
            lat = element.getElementsByTagName('wgs84:lat')
            if len(lat):
                latitude = lat[0].childNodes[0].data
            lon = element.getElementsByTagName('wgs84:lon')
            if len(lon):
                longitude = lon[0].childNodes[0].data
        return (latitude, longitude)

    def __get_ispartof(self, element):
        """
        Get one enclosure data for a place
        """
        ref_url = None
        relation = element.getElementsByTagName('gov:Relation')
        if len(relation):
            ref = relation[0].getElementsByTagName('gov:ref')
            if len(ref):
                ref_url = ref[0].attributes['rdf:resource'].value
        if ref_url:
            ref = ref_url.split('/')[3]
        else:
            ref = None
        date = self.__get_date_range(element)
        return (ref, date)

    def __get_hasurl(self, element):
        """
        Get one URL associated with a place
        """
        url = Url()
        pobj = element.getElementsByTagName('gov:PropertyForObject')
        if len(pobj):
            value = pobj[0].getElementsByTagName('gov:value')
            if len(value):
                url.set_path(value[0].childNodes[0].data)
                url.set_type(UrlType.WEB_HOME)
        return url

    def __get_date_range(self, element):
        """
        Get date data for a place name or type
        """
        begin_str = None
        begin = element.getElementsByTagName('gov:timeBegin')
        if len(begin):
            begin_str = begin[0].childNodes[0].data
        end_str = None
        end = element.getElementsByTagName('gov:timeEnd')
        if len(end):
            end_str = end[0].childNodes[0].data

        if begin_str and end_str:
            date_str = _('from %s to %s') % (begin_str, end_str)
        elif begin_str:
            date_str = _('after %s') % begin_str
        elif end_str:
            date_str = _('before %s') % end_str
        else:
            date_str = ''

        return parser.parse(date_str) if date_str else None


def load_on_reg(_dbstate, _uistate, _plugin, getfile=True):
    """
    Runs when plugin is registered.
    """
    if getfile:
        types_file = os.path.join(os.path.dirname(__file__), "gov_types.json")
        try:
            with open(types_file, encoding="utf-8") as f_p:
                GetGOV.type_dic = json.load(f_p)
            if len(GetGOV.type_dic) < 250:
                GetGOV.type_dic = {}
                return
        except Exception:
            GetGOV.type_dic = {}
            return
    # The data map (dict) contains a tuple with pt_id as key and data as tuple;
    #   translatable name
    #   native name
    #   color (used for map markers, I suggest picking by probable group)
    #   probable group (used for legacy XML import and preloading Group in
    #                   place editor)
    #   gettext method (or None if standard method)
    for gnum, data in GetGOV.type_dic.items():
        pt_id = "Gov_" + gnum
        for lang in (glocale.lang[0:2], 'de', 'en'):
            name = data[0].get(lang, None)
            if not name:
                continue
            break
        groups = GetGOV.groups[data[1]]
        tup = (name, "GOV:" + gnum, groups[3], groups[0], translate_func)
        PlaceType.register_placetype(pt_id, tup, "GOV" if data[2] else "")
    PlaceType.update_name_map()


def translate_func(ptype, locale=glocale, pt_id=None):
    """
    This function provides translations for the locally defined place types.
    It is called by the place type display code for the GUI and reports.

    The locale parameter is an instance of a GrampsLocale.  This is used to
    determine the language for tranlations. (locale.lang)  It is also used
    as a backup translation if no local po/mo file is present.

    :param ptype: the placetype translatable string
    :type ptype: str
    :param locale: the backup locale
    :type locale: GrampsLocale instance
    :param pt_id: the placetype pt_id ("Gov_50" or similar)
    :type pt_id: str
    :returns: display string of the place type
    :rtype: str
    """
    gtype = pt_id.split("Gov_")[1]
    typ_inf = GetGOV.type_dic.get(gtype)
    if not typ_inf:
        return _(ptype)
    name = typ_inf[0].get(locale.lang)
    if not name:
        return _(ptype)
    return name
