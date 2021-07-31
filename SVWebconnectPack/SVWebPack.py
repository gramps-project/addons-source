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
    ["Person", "Finn en grav", _("Find A Grave"), "http://www.findagrave.com/cgi-bin/fg.cgi?page=gsr&GSfn=%(given)s&GSmn=%(middle)s&GSln=%(surname)s&GSby=%(birth)s&GSbyrel=in&GSdy=%(death)s&GSdyrel=in&GScntry=0&GSst=0&GSgrid=&df=all&GSob=b"],
    ["Person", "FamilySearch", _("FamilySearch.org")+"  (Fritt konto för inloggning)", "https://familysearch.org/search/record/results?count=20&query=%%2Bgivenname%%3A%(given)s~ %%2Bsurname%%3A%(surname)s~ %%2Bbirth_year%%3A%(birth)s-%(birth)s~ %%2Bdeath_year%%3A%(death)s-%(death)s~"], #Fritt konto krävs
    ["Person", "SV Google", _("SV Google"), '''http://www.google.com/search?&q="%(surname)s,+%(given)s"'''],
    ["Person", "Geneanet", "Geneanet", "http://search.geneanet.org/result.php?lang=sv&name=%(surname)s"],
    ["Person", "Wikipedia", "Wikipedia", "https://sv.wikipedia.org/w/index.php?search=%(given)s+%(surname)s"],
    ["Person", "FamilySearch Släktträd", _("FamilySearch.org Tree")+"  (Fritt konto för inloggning)", "https://www.familysearch.org/tree/find/name?search=1&birth=%%7C%(birth)s-%(birth)s%%7C0&death=%%7C%(death)s-%(death)s%%7C0&self=%(given)s%%20%(middle)s%%7C%(surname)s%%7C0%%7C1"], #Fritt konto krävs
    ["Person", "WikiTree", "WikiTree", "https://wikitree.sdms.si/function/WTWebProfileSearch/Profiles.htm?&Query=%(given)s+%(surname)s+B%(birth)s+D%(death)s&MaxProfiles=500&SortOrder=Default&PageSize=10"],
    ["Person", "Riksarkivet Personsök", _("National archives personsearch"), "https://sok.riksarkivet.se/person?Namn=%(given)s+%(surname)s&Ort=&Fodelsear=&AvanceradSok=True&PageSize=100"],
    ["Person", "Riksarkivet Frisök", _("National archives free search"), "https://sok.riksarkivet.se/fritext?Sokord=%(given)s+%(surname)s&f=True&EndastDigitaliserat=false&AvanceradSok=True&PageSize=100"],
    ["Person", "Arkiv Digital bouppteckningar", _("Arkiv Digital estate records"), "https://www.arkivdigital.se/registers?county_id=0&first_name=%(given)s&last_name=%(surname)s&location=&parish=&inventory_date=&type=bouppteckningar"],
    ["Person", "Ancestry Sök", _("Ancestry Search"), "https://www.ancestry.se/search/?name=%(given)s_%(surname)s"],
    ]

def load_on_reg(dbstate, uistate, pdata):
    # do things at time of load
    # now return functions that take:
    #     dbstate, uistate, nav_type, handle
    # and that returns a function that takes a widget
    return lambda nav_type: \
        make_search_functions(nav_type, WEBSITES)
