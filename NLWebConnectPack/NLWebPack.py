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

WEBSITES = [
    ["Person", "Archieven", ("Archieven NL"), "https://www.archieven.nl/nl/zoeken?mivast=0&miadt=0&mizig=310&miview=tbl&milang=nl&micols=1&mip3=%(surname)s&mip1=%(given)s"],
    ["Person", "OpenArchives", _("Open Archives"), "https://www.openarch.nl/search.php?name=%(surname)s"],
    ["Person", "GenealogyOnline", _("Genealogy Online"), "https://www.genealogieonline.nl/zoeken/index.php?q=%(surname)s&vn=%(given)s"],
    ["Person", "NationalArchives", _("National Archive"), "https://www.nationaalarchief.nl/onderzoeken/zoeken?searchTerm=%(surname)s+%(given)s"],
    ["Person", "Delpher", "Delpher", "https://www.delpher.nl/nl/platform/results?query=%(surname)s+PROX+%(given)s+&coll=platform"],
    ["Person", "WhoResearchesWho", _("Who (re)searches who?"), "https://www.stamboomforum.nl/wiezoektwie/zoeken.php?q=%(surname)s"],
    ["Person", "NL-FamilySearch", "FamilySearch NL", "https://www.familysearch.org/search/record/results?givenname=%(given)s&surname=%(surname)s&surname_exact=on&birth_year_from=%(birth)s&birth_year_to=%(birth)s&death_year_from=%(death)s&death_year_to=%(death)s&record_country=Netherlands"],
    ['Person', "NL-Google", "Google NL", "https://www.google.com/search?q=%(surname)s+%(given)s"],
    ['Person', "NL-GeneaNet", "GeneaNet NL", "https://nl.geneanet.org/fonds/individus/?go=1&nom=%(surname)s&prenom=%(given)s"],
    ['Person', "Stamboomzoeker.nl", "Stamboomzoeker.nl", "https://www.stamboomzoeker.nl/?a=search&fn=%(given)s&sn=%(surname)s&m=1&bd1=0&bd2=2020&bp=&t=1&submit=Zoeken"],
    ['Person', "GenDex", "GenDex", "http://gendexnetwork.org/index.php"],
    ['Person', "WieWasWie", "WieWasWie", "https://www.wiewaswie.nl/nl/zoeken/"],
    ['Person', "Mensenlinq", "Mensenlinq", "https://mensenlinq.nl/overlijdensberichten/?passed_at_from=&passed_at_until=&lastname=%(surname)s&firstname=%(given)s&filtered=true"],
    ['Person', "GENi", "GENi", "https://www.geni.com/search?names=%(given)s+%(surname)s"],
    ['Person', "NL-Find-A-Grave", "Find A Grave NL", "https://nl.findagrave.com/memorial/search?firstname=%(given)s&middlename=&lastname=%(surname)s"],
    ['Person', "Hilversum-GenWiki", "Hilversum-GenWiki NL", "http://www.hilversum.genwiki.net/search.php?myfirstname=%(given)s&mylastname=%(surname)s&mypersonid=&idqualify=equals"],
    ['Person', "CBG", "CBG", "https://cbg.nl/#q=%(given)s %(surname)s"],
    ['Person', "AlleFriezen", "AlleFriezen", "https://allefriezen.nl/zoeken/persons?ss={\"q\":\"%(given)s %(surname)s\"}"],
    ]

def load_on_reg(dbstate, uistate, pdata):
    # do things at time of load
    # now return functions that take:
    #     dbstate, uistate, nav_type, handle
    # and that returns a function that takes a widget
    return lambda nav_type: \
        make_search_functions(nav_type, WEBSITES)
