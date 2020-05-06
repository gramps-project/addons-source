# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010  Doug Blank <doug.blank@gmail.com>
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

# $Id: $

from libwebconnect import *
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

# Format: [[nav_type, id, name, url_pattern], ...]

# You can use this values in 'url_patterns':
#   %(given)s
#   %(surname)s
#   %(middle)s
#   %(birth)s
#   %(death)s

WEBSITES = [
    ["Person", "Obd-memorial", _("OBD \"Memorial\""), "https://obd-memorial.ru/html/search.htm?f=%(surname)s&n=%(given)s&s=&y=%(birth)s&r="],
    ["Person", "Pamyat-Naroda", _("People memory"), "https://pamyat-naroda.ru/heroes/?adv_search=y&last_name=%(surname)s&first_name=%(given)s&middle_name=%(middle)s&date_birth=%(birth)s&group=all&types=pamyat_commander:nagrady_nagrad_doc:nagrady_uchet_kartoteka:nagrady_ubilein_kartoteka:pamyat_voenkomat:potery_vpp:pamyat_zsp_parts:kld_upk:kld_vmf:potery_doneseniya_o_poteryah:potery_gospitali:potery_utochenie_poter:potery_spiski_zahoroneniy:potery_voennoplen:potery_iskluchenie_iz_spiskov&page=1"],
    ["Person", "Pobediteli", _("Winners"), "https://www.pobediteli.ru/veteran-search/index.html?charset=utf-8&flag=&region=&district=&mode=lastname&q=%(surname)s+%(given)s"],
    ["Person", "Prozhito", _("Lived"), "https://prozhito.org/persons?keyword=\"%(surname)s+%(given)s\""],
    ["Person", "OpenList", _("Open list"), "https://ru.openlist.wiki/Служебная:OlSearch?olsearch-name=%(surname)s+%(given)s&olsearch-birth_min=%(birth)s&olsearch-birth_max=%(birth)s&olsearch-death_min=%(death)s&olsearch-death_max=%(death)s&olsearch-birthplace=&olsearch-liveplace=&olsearch-nationality=&olsearch-social=&olsearch-profession=&olsearch-deathplace=&olsearch-burialplace=&olsearch-body=&olsearch-categories=&olsearch-arrest_min=&olsearch-arrest_max=&olsearch-indictment=&olsearch-conviction_min=&olsearch-conviction_max=&olsearch-conviction-org=&olsearch-sentence=&olsearch-detentionplace=&olsearch-release_min=&olsearch-release_max=&olsearch-execution_min=&olsearch-execution_max=&olsearch-archive-case-number=&olsearch-run=1&olsearch-advform=1#OlSearch-results-caption"],
    ["Person", "WaitForMe", _("Wait for me"), "https://poisk.vid.ru/?lname=%(surname)s&fname=%(given)s&id_let=&p=10&view=18&age_1=1&age_2=99&searched=НАЙТИ"],
    ["Person", "VGD", _("All Russia Family Tree (forum)"), "https://vgd.ru/search/index.php?q=%(surname)s&x=0&y=0&tu=0"],
    ["Person", "YandexPeople", _("Yandex people"), "https://yandex.by/people/search?text=%(surname)s+%(given)s&ps_age=%(birth)s"],
    ["Person", "ok.ru", _("OK"), "https://ok.ru/search/profiles/%(surname)s %(given)s %(birth)s"],
    ]

def load_on_reg(dbstate, uistate, pdata):
    # do things at time of load
    # now return functions that take:
    #     dbstate, uistate, nav_type, handle
    # and that returns a function that takes a widget
    return lambda nav_type: \
        make_search_functions(nav_type, WEBSITES)

