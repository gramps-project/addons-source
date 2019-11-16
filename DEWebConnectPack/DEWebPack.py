# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2011  Doug Blank <doug.blank@gmail.com>
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

# $Id$

from libwebconnect import *
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

# Format: [[nav_type, id, name, url_pattern], ...]

# http://gramps-project.org/wiki/index.php?title=Resources_and_related_sites#German_information_sites

WEBSITES = [
    ["Person", "Bielefeld Academic Search", _("Bielefeld Academic Search"), "http://www.base-search.net/Search/Results?lookfor=%(surname)s,+%(given)s&type=all&lem=0&lem=1&refid=dcbasde"],
    ["Person", "Geneanet", "Geneanet", "http://search.geneanet.org/result.php?lang=fr&name=%(surname)s"],
    ["Person", "FamilySearch", _("FamilySearch.org"), "https://familysearch.org/search/record/results?count=20&query=%%2Bgivenname%%3A%(given)s~ %%2Bsurname%%3A%(surname)s~ %%2Bbirth_year%%3A%(birth)s-%(birth)s~ %%2Bdeath_year%%3A%(death)s-%(death)s~"],
    ["Person", "Archive.org", "Archive.org", '''http://www.archive.org/search.php?query="%(surname)s,+%(given)s"'''],
    ["Person", "GeneaBook", "GeneaBook", "http://www.geneabook.org/genealogie/1/ouvrages.php?nom=%(surname)s&x=20&y=1"],
    ["Person", "Google Archives", _("Google Archives"), "http://news.google.de/archivesearch?q=%(surname)s"],
    ["Person", "DE-Google", _("DE Google"), '''http://www.google.de/#hl=de&q="%(surname)s,+%(given)s"'''],
    ["Person", "Open Library", _("Open Library"), "http://openlibrary.org/search?q=%(surname)s, %(given)s"],
    ["Person", "Namensverbreitungskarte", _("Surname map (1890-1996)"), "https://nvk.genealogy.net/map/1890:%(surname)s,1996:%(surname)s"],
    ["Person", "wiki-de.genealogy.net", _("GenWiki"), "http://wiki-de.genealogy.net/Spezial:Suche?search=%(surname)s"],
    ]

def load_on_reg(dbstate, uistate, pdata):
    # do things at time of load
    # now return functions that take:
    #     dbstate, uistate, nav_type, handle
    # and that returns a function that takes a widget
    return lambda nav_type: \
        make_search_functions(nav_type, WEBSITES)

