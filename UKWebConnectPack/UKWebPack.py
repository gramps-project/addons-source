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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
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
    ['Person', "UK-Google", _("UK Google"), '''http://www.google.co.uk/#hl=en&q="%(surname)s,+%(given)s"'''],
    ["Person", "Userdb-rootsweb", _("British, UK, and Ireland"), "http://userdb.rootsweb.ancestry.com/uki/cgi-bin/uki.cgi?surname=%(surname)s&fname=%(given)s"],
    ["Person", "FamilySearch", _("FamilySearch.org"), "https://www.familysearch.org/s/search/index/record-search#searchType=records&filtered=false&fed=true&collectionId=&advanced=false&givenName=%(given)s&surname=%(surname)s&birthYear=%(birth)s&birthLocation=&deathYear=%(death)s&deathLocation="],
    ["Person", "Geneanet", "Geneanet", "http://search.geneanet.org/result.php?lang=en&name=%(surname)s"],
    ["Person", "National Archives", _("National Archives"), "http://www.nationalarchives.gov.uk/documentsonline/search-results-summary.asp?searchType=powersearch&query=first_name%%3D%(surname)s|last_name%%3D%(given)s&catID=10,12,11,6,14,13,15,16,18,20,19,21,22,25,29,23,24,27,1,32,28,34,7,33,31,36,37,40,45,42,43,49,9,3,4,2,17,30,38,39,41,44,46,47,48&mediaArray=*&pageNumber=1&queryType=1"],
    ["Person", "Hathi Trust Digital Library", _("Hathi Trust Digital Library"), "http://babel.hathitrust.org/cgi/ls?q1=%(surname)s+%(given)s+&lmt=ft&a=srchls"],
    ["Person", "Open Library", _("Open Library"), "http://openlibrary.org/search?q=%(surname)s, %(given)s"],
    ]

def load_on_reg(dbstate, uistate, pdata):
    # do things at time of load
    # now return functions that take:
    #     dbstate, uistate, nav_type, handle
    # and that returns a function that takes a widget
    return lambda nav_type: \
        make_search_functions(nav_type, WEBSITES)

