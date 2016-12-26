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
GetGOV Gramplet.
"""

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
from urllib.request import urlopen
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
TYPES = {"1": "Amt",
"2": "Amtsbezirk",
"3": "Magistrates' Court",
"4": "Bauerschaft",
"5": "Bezirk",
"6": "Bistum",
"7": "federal state",
"8": "castle",
"9": "deanery",
"10": "Departement",
"11": "diocese",
"12": "Dompfarrei",
"13": "Filiale",
"14": "Flecken",
"15": "field name",
"16": "free state",
"17": "building",
"18": "municipality",
"19": "Gerichtsbezirk",
"20": "Grafschaft",
"21": "manor (building)",
"22": "dominion",
"23": "duchy",
"24": "Farm",
"25": "canton",
"26": "church",
"27": "Kirchenkreis",
"28": "Kirchenprovinz",
"29": "parish",
"30": "monastery (building)",
"31": "kingdom",
"32": "county (generic)",
"33": "Kurfürstentum",
"34": "Land",
"35": "Landeskirche",
"36": "rural county (rural)",
"37": "Oberamt",
"38": "oblast",
"39": "Ort",
"40": "Ortsteil",
"41": "Pfarr-Rektorat",
"42": "Pfarrei",
"43": "Pfarrkuratie",
"44": "Pfarrverband",
"45": "province",
"46": "administrative district",
"47": "historical region",
"48": "Samtgemeinde",
"49": "Sprengel",
"50": "country",
"51": "town",
"52": "Stadtbezirk",
"53": "urban county (city)",
"54": "Stadtteil",
"55": "village",
"56": "republic",
"57": "Amt",
"58": "union republic",
"59": "voivodship",
"60": "principality",
"61": "grand duchy",
"62": "margravate",
"63": "Rayon",
"64": "Vorwerk",
"65": "Pfarrdorf",
"66": "Kirchdorf",
"67": "solitude",
"68": "Hauptort",
"69": "hamlet",
"70": "bailiwick",
"71": "Staatenbund",
"72": "people's republic",
"73": "Landdrostei",
"74": "deprecated",
"75": "Güterdistrikt",
"76": "Adeliges Gut",
"77": "Reichskreis",
"78": "Amt (administrative division)",
"79": "hundred",
"80": "Landschaft",
"81": "Kloster",
"82": "Domkapitel",
"83": "Hanseatic city",
"84": "Kirchspielvogtei",
"85": "Landgemeinde",
"86": "Teilprovinz",
"87": "mill",
"88": "Judet",
"89": "cemetery",
"90": "abandoned place",
"91": "Bistumsregion",
"92": "Kirchengemeinde",
"93": "Reichsstadt",
"94": "Verwaltungsgemeinschaft",
"95": "county-level city",
"96": "archbishopric",
"97": "Bürgermeisterei",
"98": "veraltet",
"99": "captaincy",
"100": "Kreishauptmannschaft",
"101": "Kreisdirektion",
"102": "forester's house",
"103": "civil registry",
"104": "veraltet",
"105": "Landgericht",
"107": "island",
"108": "Gutsbezirk",
"109": "Forstgutsbezirk",
"110": "district office",
"111": "Schloss",
"112": "Gespanschaft",
"113": "comitatus",
"114": "Vest",
"115": "girininkija",
"116": "Oberförsterei",
"117": "Unterförsterei",
"118": "train station",
"119": "Haltestelle",
"120": "settlement",
"121": "colony",
"122": "Verbandsgemeinde",
"124": "Abbey",
"125": "imperial abbey",
"126": "Syssel",
"127": "Verwaltungsverband",
"128": "Landgrafschaft",
"129": "settlement",
"130": "state",
"131": "Weichbild",
"133": "Region",
"134": "arrondissement",
"135": "canton",
"136": "commune",
"137": "Region",
"138": "Oberlandratsbezirk",
"139": "Einschicht",
"140": "Einheitsgemeinde",
"142": "Reichsgau",
"143": "kommune",
"144": "Ortschaft",
"145": "Markt",
"146": "Bezirkshauptmannschaft/Politischer Bezirk",
"147": "veraltet",
"148": "Erfüllende Gemeinde",
"149": "Landratsamt",
"150": "Stadt",
"151": "Oberlandesgericht",
"152": "Landbürgermeisterei",
"153": "Kommissariat",
"154": "Honschaft",
"155": "Region",
"156": "Gemeindebezirk",
"157": "Guberniya",
"158": "Gemeindeteil",
"159": "Khutor",
"160": "Sowjetrepublik",
"161": "Verwaltungsbezirk",
"162": "Stadt- und Landgemeinde",
"163": "Ortsgemeinde",
"164": "Ortsbezirk",
"165": "Gnotschaft",
"166": "ruins",
"167": "mandate territory",
"168": "Provinz",
"169": "Gemeinde",
"170": "Distrikt",
"171": "Stadthauptmannschaft",
"172": "Katastralgemeinde",
"173": "Райхскомісаріат",
"174": "Генеральбецірк",
"175": "Kreisgebiet",
"176": "protectorate",
"177": "Reichsritterschaft",
"178": "Ritterkanton",
"179": "Ritterkreis",
"180": "Marktgemeinde",
"181": "Rotte",
"182": "Erzstift",
"183": "Hochstift",
"184": "Kammerschreiberei",
"185": "Klosteramt",
"186": "Rentkammer",
"187": "zu überprüfen",
"188": "Ritterorden",
"189": "Großpriorat",
"190": "Ballei",
"191": "Kommende",
"192": "zone of occupation",
"193": "Alm",
"194": "Distrikts-Amt",
"195": "veraltet",
"196": "veraltet",
"197": "veraltet",
"198": "veraltet (früher: Bundesverwaltungsgericht)",
"199": "veraltet (früher: Landesverwaltungsgericht)",
"200": "veraltet (früher: Verwaltungsgericht)",
"201": "Landeskommissarbezirk",
"202": "Amtsgerichtsbezirk",
"203": "Domanialamt",
"204": "Ritterschaftliches Amt",
"205": "selsoviet",
"206": "Regionalkirchenamt",
"207": "Oberamtsbezirk",
"210": "Kirchenbund",
"211": "Landgebiet",
"212": "Landherrenschaft",
"213": "gorsoviet",
"214": "realm",
"215": "Reichshälfte",
"216": "Landesteil",
"217": "Direktionsbezirk",
"218": "Stadt",
"219": "Expositur",
"221": "Fylke",
"222": "Kreis",
"223": "Landgericht",
"224": "Pfleggericht",
"225": "Rentamt",
"226": "Obmannschaft",
"227": "Kirchspiellandgemeinde",
"228": "Gerichtsamt",
"229": "Häusergruppe",
"230": "scattered settlement",
"231": "Höfe",
"232": "Randort",
"233": "Flecken",
"234": "borough",
"235": "unitary authority",
"236": "Häuser",
"237": "селищна рада",
"238": "селище міського типу",
"239": "Verwaltungsamt",
"240": "uyezd",
"241": "Volost",
"242": "Katasteramt",
"243": "Propstei",
"244": "Nebenkirche",
"245": "chapel",
"246": "Gromada",
"247": "Ortsteil",
"248": "Schulzenamt",
"249": "unbenutzt (4)",
"250": "unbenutzt (5)",
"251": "autonome Gemeinschaft",
"252": "local government",
"253": "unbenutzt (6)",
"254": "Окръг",
"255": "Stadtgut",
"256": "Landesbezirk",
"257": "Landgemeinde PL",
"258": "Stadtgemeinde"}

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

    def __create_gui(self):
        """
        Create and display the GUI components of the gramplet.
        """
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_spacing(4)

        label = Gtk.Label(_('Enter GOV id:'))
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
        gov_id = self.entry.get_text()
        to_do = [gov_id]
        visited = {}

        with DbTxn(_('Add GOV place %s') % gov_id, self.dbstate.db) as trans:
            while to_do:
                gov_id = to_do.pop()
                place = self.dbstate.db.get_place_from_gramps_id(gov_id)
                if place is not None:
                    visited[gov_id] = (place, [])
                else:
                    place, ref_list = self.__get_place(gov_id)
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
                        place.add_placeref(place_ref)
                    self.dbstate.db.commit_place(place, trans)

    def __get_place(self, gov_id):
        gov_url = 'http://gov.genealogy.net/semanticWeb/about/' + gov_id

        response = urlopen(gov_url)
        data = response.read()

        dom = parseString(data)
        top = dom.getElementsByTagName('gov:GovObject')

        place = Place()
        place.gramps_id = gov_id

        count = 0
        for element in top[0].getElementsByTagName('gov:hasName'):
            count += 1
            place_name = self.__get_hasname(element)
            if count == 1:
                place.set_name(place_name)
            else:
                place.add_alternative_name(place_name)
#       If there is a single name (no alternates) and lang is not blank or preference language,
#        then add a fake alternate name with preferences language as language. This makes Titles work better.
        curr_lang = config.get('preferences.place-lang')
        if count == 1 and len(curr_lang) == 2 :

            if place_name.get_language() != None and place_name.get_language() != curr_lang :
                curr_lang_place_name = self.__get_hasname(element)
                curr_lang_place_name.set_language(curr_lang)
                place.add_alternative_name(curr_lang_place_name)
#
        for element in top[0].getElementsByTagName('gov:hasType'):
            place_type = self.__get_hastype(element)
            place.set_type(place_type)
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
                name.set_language(ISO_CODE_LOOKUP.get(language[0].childNodes[0].data))
#                name.set_language(language[0].childNodes[0].data)
            date = self.__get_date_range(pname[0])
            name.set_date_object(date)
        return name

    def __get_hastype(self, element):
        place_type = PlaceType()
        ptype = element.getElementsByTagName('gov:PropertyType')
        if len(ptype):
            value = ptype[0].getElementsByTagName('gov:type')
            if len(value):
                type_url = value[0].attributes['rdf:resource'].value
                type_code = type_url.split('#')[1]
                place_type.set_from_xml_str(TYPES.get(type_code, 'Unknown'))
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
            date_str = 'from %s to %s' % (begin_str, end_str)
        elif begin_str:
            date_str = 'after %s' % begin_str
        elif end_str:
            date_str = 'before %s' % end_str
        else:
            date_str = ''

        return parser.parse(date_str) if date_str else None
