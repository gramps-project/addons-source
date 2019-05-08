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
from gramps.gen.lib import (Place, PlaceName, PlaceType, PlaceRef,
                            PlaceHierType, Url, UrlType)
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
        root = self.__create_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(root)
        root.show_all()
        self.type_dic = dict()

    def __create_gui(self):
        """
        Create and display the GUI components of the gramplet.
        """
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_spacing(4)

        label = Gtk.Label(_('Enter GOV-id:'))
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

    def __get_places(self, _obj):
        gov_id = self.entry.get_text()
        to_do = [gov_id]
        try:
            preferred_lang = config.get('preferences.place-lang')
        except AttributeError:
            fmt = config.get('preferences.place-format')
            pf = _pd.get_formats()[fmt]
            preferred_lang = pf.language
        if len(preferred_lang) != 2:
            preferred_lang = glocale.lang
        visited = {}

        if not self.type_dic:
            self.__get_types()

        with DbTxn(_('Add GOV-id place %s') % gov_id,
                   self.dbstate.db) as trans:
            while to_do:
                gov_id = to_do.pop()
                place = self.dbstate.db.get_place_from_gramps_id(gov_id)
                if place is not None:
                    visited[gov_id] = (place, [])
                else:
                    place, ref_list = self.__get_place(gov_id, self.type_dic,
                                                       preferred_lang)
                    if place.get_name().get_value is not '':
                        self.dbstate.db.add_place(place, trans)
                        visited[gov_id] = (place, ref_list)
                        for ref, date in ref_list:
                            if (ref not in to_do) and (ref not in visited):
                                to_do.append(ref)

            for place, ref_list in visited.values():
                if len(ref_list) > 0:
                    for ref, date in ref_list:
                        handle = visited[ref][0].handle
                        place_ref = PlaceRef()
                        place_ref.ref = handle
                        place_ref.set_date_object(date)
                        place_ref.set_type(PlaceHierType.ADMIN)  # TODO deal with other hierarchies
                        place.add_placeref(place_ref)
                    self.dbstate.db.commit_place(place, trans)
        self.dbstate.db.save_place_types()

    def __get_types(self):
        groups = {
            1: _("Administrative"),
            2: _("Civil"),
            3: _("Religious"),
            4: _("Geographical"),
            5: _("Cultural"),
            6: _("Judicial"),
            8: _("Places"),
            9: _("Transportation"),
            10: _("Unpopulated Places"),
            13: _("Other"),
            26: _("Countries"),
            27: _("Regions"),
            28: _("Regions"),
            29: _("Regions"),
            30: _("Regions"),
            31: _("Places"),
            32: _("Places"),
        }
        self.groups_cnv = {}
        for grp_num, grp_name in groups.items():
            for grp, tup in PlaceType.GROUPMAP.items():
                if grp_name.lower() == tup[0].lower():
                    self.groups_cnv[grp_num] = grp
        self.type_groups = {}
        type_url = 'http://gov.genealogy.net/types.owl/'
        response = urlopen(type_url)
        data = response.read()
        dom = parseString(data)
        for group in dom.getElementsByTagName('owl:Class') :
            url_value = group.attributes['rdf:about'].value
            group_number = url_value.split('#')[1]
            g_num = self.groups_cnv.get(
                int(group_number.replace('group_', '')), 0)
            for element in dom.getElementsByTagNameNS("http://gov.genealogy."
                                                      "net/types.owl#",
                                                      group_number):
                self.__do_type(dom, element, g_num)
            for element in dom.getElementsByTagNameNS("http://gov.genealogy."
                                                      "net/ontology.owl#",
                                                      'Type'):
                self.__do_type(dom, element, g_num)

    def __do_type(self, dom, element, g_num):
        type_number = element.attributes['rdf:about'].value.split('#')[1]
        for pname in element.getElementsByTagName('rdfs:label'):
            type_lang = pname.attributes['xml:lang'].value
            type_text = pname.childNodes[0].data
            self.type_dic[type_number, type_lang] = type_text
        groups = g_num
        for res in element.getElementsByTagName('rdf:type'):
            gx_num = res.attributes['rdf:resource'].value.split('#')[1]
            if gx_num == 'Type' or 'group_' not in gx_num:
                continue
            groups += self.groups_cnv.get(int(gx_num.replace('group_', '')), 0)
        self.type_groups[int(type_number)] = groups

    def __get_place(self, gov_id, type_dic, preferred_lang):
        gov_url = 'http://gov.genealogy.net/semanticWeb/about/' + quote(gov_id)

        response = urlopen(gov_url)
        data = response.read()

        dom = parseString(data)
        top = dom.getElementsByTagName('gov:GovObject')

        place = Place()
        place.gramps_id = gov_id
        if not len(top) :
            return place, []

        types = []
        for element in top[0].getElementsByTagName('gov:hasName'):
            place_name = self.__get_hasname(element)
            place.add_name(place_name)
        for element in top[0].getElementsByTagName('gov:hasType'):
            place_type = self.__get_hastype(element, type_dic,
                                            preferred_lang)
            types.append(place_type)
        types.sort(key=lambda typ: typ.date.get_sort_value(), reverse=True)
        place.set_types(types)
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

        return place, ref_list

    def __get_hasname(self, element):
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

    def __get_hastype(self, element, type_dic, preferred_lang):
        place_type = PlaceType()
        ptype = element.getElementsByTagName('gov:PropertyType')
        if len(ptype):
            value = ptype[0].getElementsByTagName('gov:type')
            if len(value):
                type_url = value[0].attributes['rdf:resource'].value
                type_code = type_url.split('#')[1]
                for lang in (preferred_lang, 'de', 'en'):
                    t_nam = type_dic.get((type_code, lang), None)
                    if not t_nam:
                        continue
                    place_type.set((-int(type_code), t_nam,
                                   self.type_groups[int(type_code)]))
                    break
            date = self.__get_date_range(ptype[0])
            if date:
                place_type.set_date_object(date)
        return place_type

    def __get_position(self, element):
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
        url = Url()
        pobj = element.getElementsByTagName('gov:PropertyForObject')
        if len(pobj):
            value = pobj[0].getElementsByTagName('gov:value')
            if len(value):
                url.set_path(value[0].childNodes[0].data)
                url.set_type(UrlType.WEB_HOME)
        return url

    def __get_date_range(self, element):
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
