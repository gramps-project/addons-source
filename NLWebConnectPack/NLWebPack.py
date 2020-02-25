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
    ["Person", "OpenArchives", _("Open Archives"), "https://www.openarch.nl/search.php?name=%(surname)s+%(given)s"],
    ["Person", "GenealogyOnline", _("Genealogy Online"), "https://www.genealogieonline.nl/zoeken/index.php?q=%(surname)s&vn=%(given)s"],
    ["Person", "NationalArchives", _("National Archive"), "https://www.nationaalarchief.nl/onderzoeken/zoeken?searchTerm=%(surname)s+%(given)s"],
    ["Person", "Delpher", "Delpher", "https://www.delpher.nl/nl/platform/results?query=%(surname)s+PROX+%(given)s+&coll=platform"],
    ["Person", "WhoResearchesWho", _("Who (re)searches who?"), "https://www.stamboomforum.nl/wiezoektwie/zoeken.php?q=%(surname)s"],
    ["Person", "NL-FamilySearch", "FamilySearch NL", "https://www.familysearch.org/search/record/results?givenname=%(given)s&surname=%(surname)s&surname_exact=on&birth_year_from=%(birth)s&birth_year_to=%(birth)s&death_year_from=%(death)s&death_year_to=%(death)s&record_country=Netherlands"],
    ['Person', "NL-Google", "Google NL", "https://www.google.com/search?q=%(surname)s+%(given)s"],
    ]

def load_on_reg(dbstate, uistate, pdata):
    # do things at time of load
    # now return functions that take:
    #     dbstate, uistate, nav_type, handle
    # and that returns a function that takes a widget
    return lambda nav_type: \
        make_search_functions(nav_type, WEBSITES)
