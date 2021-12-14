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
    ["Person", "Find-A-Grave", _("Find A Grave"), "http://www.findagrave.com/cgi-bin/fg.cgi?page=gsr&GSfn=%(given)s&GSmn=%(middle)s&GSln=%(surname)s&GSby=%(birth)s&GSbyrel=in&GSdy=%(death)s&GSdyrel=in&GScntry=0&GSst=0&GSgrid=&df=all&GSob=b"],
    ["Person", "FamilySearch", _("FamilySearch.org")+"  (Account Login; free)", "https://www.familysearch.org/search/record/results?q.birthLikeDate.from=%(birth)s&q.birthLikeDate.to=%(birth)s&q.deathLikeDate.from=%(death)s&q.deathLikeDate.to=%(death)s&q.givenName=%(given)s+%(middle)s&q.surname=%(surname)s"], #Free Account Needed
    ["Person", "US-Google", _("US Google"), '''http://www.google.com/search?q="%(given)s+%(middle)s+%(surname)s+%(birth)s+%(death)s"'''],
    ["Person", "newspapers.nla.gov.au", "Australia / Newspaper Family Notices", "http://trove.nla.gov.au/newspaper/result?q=%(given)s+%(surname)s&exactPhrase=&anyWords=&notWords=&requestHandler=&dateFrom=&dateTo=&l-advcategory=Family+Notices&sortby="], # Australian
    ["Person", "Geneanet", "Geneanet", "http://search.geneanet.org/result.php?lang=en&name=%(surname)s"],
    #["Person", "Geneanet-Favrejhas", "Geneanet, Favrejhas", "http://gw1.geneanet.org/index.php3?b=favrejhas&m=NG&n=%(surname)s&t=N&x=0&y=0"], # French
    ["Person", "Roglo", "Roglo", "http://roglo.eu/roglo?m=NG&n=%(given)s+%(surname)s&t=PN"],
    ["Person", "FindMyPast", "FindMyPast  (Account Login; free)", "https://www.findmypast.com/search/results?firstname=%(given)s&firstname_variants=true&lastname=%(surname)s&eventyear=%(birth)s&eventyear_offset=2&yearofdeath=%(death)s&yearofdeath_offset=2&sid=999"], #Free Account Needed
    ["Person", "Hathi Trust Digital Library", _("Hathi Trust Digital Library"), "http://babel.hathitrust.org/cgi/ls?q1=%(surname)s+%(given)s+&lmt=ft&a=srchls"],
    ["Person", "Open Library", _("Open Library"), "http://openlibrary.org/search?q=%(surname)s, %(given)s"],
    ["Person", "Legacy Obits", "Legacy.com", "https://www.legacy.com/search?countryId=366899&countryUrl=united-states-of-america&dateRange=All&firstName=%(given)s&lastName=%(surname)s"],
    ["Person", "Archive.org", "Archive.org", '''http://www.archive.org/search.php?query="%(given)s+%(surname)s+%(birth)s+"-"+%(death)s"'''],
    ["Person", "Wikipedia", "Wikipedia", "https://en.wikipedia.org/w/index.php?search=%(given)s+%(surname)s"],
    ["Person", "FamilySearch-Tree", _("FamilySearch.org")+" - Family Trees  (Account Login; free)", "https://www.familysearch.org/tree/find/name?search=1&birth=%%7C%(birth)s-%(birth)s%%7C0&death=%%7C%(death)s-%(death)s%%7C0&self=%(given)s%%20%(middle)s%%7C%(surname)s%%7C0%%7C1"], #Free Account Needed
    ["Person", "WeRelate", "WeRelate", "https://www.werelate.org/wiki/Special:Search?sort=score&ns=Person&a=&st=&g=%(given)s+%(middle)s&s=%(surname)s&p=&bd=%(birth)s&br=1&bp=&dd=%(death)s&dr=1&rows=20&ecp=c"],
    ["Person", "WikiTree", "WikiTree", "https://wikitree.sdms.si/function/WTWebProfileSearch/Profiles.htm?&Query=%(given)s+%(surname)s+B%(birth)s+D%(death)s&MaxProfiles=500&SortOrder=Default&PageSize=10"],
    ]

def load_on_reg(dbstate, uistate, pdata):
    # do things at time of load
    # now return functions that take:
    #     dbstate, uistate, nav_type, handle
    # and that returns a function that takes a widget
    return lambda nav_type: \
        make_search_functions(nav_type, WEBSITES)
