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
from gramps.gen.utils.trans import get_addon_translator
_ = get_addon_translator(__file__).gettext

# Format: [[nav_type, id, name, url_pattern], ...]

WEBSITES = [
    ["Person", "Find-A-Grave", _("Find A Grave"), "http://www.findagrave.com/cgi-bin/fg.cgi?page=gsr&GSfn=%(given)s&GSmn=%(middle)s&GSln=%(surname)s&GSby=%(birth)s&GSbyrel=in&GSdy=%(death)s&GSdyrel=in&GScntry=0&GSst=0&GSgrid=&df=all&GSob=b"],
    ["Person", "FamilySearch", _("FamilySearch.org"), 
     "https://www.familysearch.org/search/records/index#count=20&query=%%2Bgivenname%%3A%(given)s~%%20%%2Bsurname%%3A%(surname)s~"],
    ["Person", "US-Google", _("US Google"), '''http://www.google.com/#hl=en&q="%(surname)s,+%(given)s"'''],
    ["Person", "GenCircles", "GenCircle", "http://www.gencircles.com/globaltree/gosearch?f=%(surname)s&l=%(given)s&by=%(birth)s&ba=0&bp=&fa=&dy=%(death)s&da=0&mo=&dp=&sp=&t=Marriage&oy=&oa=0&op=&g.x=6&g.y=12"],
    ["Person", "german-immigrants.com", _("German Immigrants"), "http://www.german-immigrants.com/tng/search.php?mylastname=%(surname)s&myfirstname=%(given)s&mybool=AND&offset=0&search=Search"],
    ["Person", "Worldconnect-Rootsweb", "WorldConnect", "http://worldconnect.rootsweb.ancestry.com/cgi-bin/igm.cgi?surname=%(surname)s&given=%(given)s"], 
    ["Person", "SSDI-Rootsweb", "Social Security Death Index", "http://ssdi.rootsweb.ancestry.com/cgi-bin/newssdi?sn=%(surname)s&fn=%(given)s&nt=exact"], 
    ["Person", "CaliforniaDeathIndex", "California Death Index", "http://vitals.rootsweb.ancestry.com/ca/death/search.cgi?surname=%(surname)s&given=%(given)s"],
    ["Person", "SiteSearch", _("Free Rootsweb Site Search"), '''http://sitesearch.rootsweb.ancestry.com/cgi-bin/search?words="%(surname)s+%(given)s"'''], 
    ["Person", "newspapers.nla.gov.au", "Australia / Newspaper Family Notices", "http://newspapers.nla.gov.au/ndp/del/search?searchTerm=%(given)s+%(surname)s&exactPhrase=&anyWords=&notWords=&textSearchScope=full&fromdd=&frommm=&fromyyyy=&todd=&tomm=&toyyyy=&facet=category%%3AFamily+Notices&facet=&sortBy="], # Australian
    ["Person", "Geneanet", "Geneanet", "http://search.geneanet.org/result.php?lang=en&name=%(surname)s"],
    ["Person", "Geneanet-Favrejhas", "Geneanet, Favrejhas", "http://gw1.geneanet.org/index.php3?b=favrejhas&m=NG&n=%(surname)s&t=N&x=0&y=0"], # French
    ["Person", "Roglo", "Roglo", "http://roglo.eu/roglo?m=NG&n=%(given)s+%(surname)s&t=PN"],
    ["Person", "Pow-mia", "US POW/MIA", "http://userdb.rootsweb.ancestry.com/pow_mia/cgi-bin/pow_mia.cgi?surname=%(surname)s&fname=%(given)s"],
    ["Person", "Disnorge", "DIS-Norge", "http://www.disnorge.no/gravminner/global1.php?ordalle=%(given)s+%(surname)s"], # Norway
    ["Person", "Mocavo", _("Mocavo"), '''http://www.mocavo.com/search?q="%(surname)s,+%(given)s"'''],
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

