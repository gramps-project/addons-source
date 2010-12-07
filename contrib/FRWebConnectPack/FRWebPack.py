# -*- coding: UTF-8 -*-
#
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

# Format: [[nav_type, id, name, url_pattern], ...]

# http://www.gramps-project.org/wiki/index.php?title=Resource_and_related_sites#French_resources
#
# http://www.bigenet.org/index.php ?
# http://www.cybergenealogie.fr/cailgeo/us/screch.php

WEBSITES = [
    ["Person", u"Ministère de la culture", _("French cultural ministry"), "http://www.culture.fr/genealogie/?action_type=search&lang=fr&search_nom=%(surname)s&search_prenom=%(given)s"],
    ["Person", "Geneabank", _("Genealogical bank"), "http://searchgbk.geneanet.org/result.php3?name=%(surname)s&place=%(place_title)s&start=&end=&source=gbk*"],
    #["Person", u"Centre Départemental d'Histoire des Familles (CDHF)", _("Historical Families Center Departement (CDHF)"), "http://www.cdhf.net/fr/index.php?t=bases&d=bases%2Fmoteurpat&c=moteurpat&f=selection&p=&order=&order2=&motcle=&patronyme=%(surname)s"],
    ["Person", "Fichier Origine", _("OrigineFile (Quebec)"), "http://www.fichierorigine.com/recherche.php?nom=%(surname)s"],
    ["Person", "Geneanet", "Geneanet", "http://search.geneanet.org/result.php?lang=fr&name=%(surname)s"],
    ["Person", "Geneanet-Favrejhas", "Geneanet, Favrejhas", "http://gw1.geneanet.org/index.php3?b=favrejhas&m=NG&n=%(surname)s&t=N&x=0&y=0"],
    ["Person", "Roglo", "Roglo", "http://roglo.eu/roglo?m=NG&n=%(given)s+%(surname)s&t=PN"],
    ["Person", "FamilySearch-Beta", _("FamilySearch.org Beta"), "http://beta.familysearch.org/s/search/index/record-search#searchType=records&filtered=false&fed=true&collectionId=&advanced=false&givenName=%(given)s&surname=%(surname)s&birthYear=%(birth)s&birthLocation=&deathYear=%(death)s&deathLocation="],
    ["Person", "CAILGEO", _("Cyber genealogy"), "http://www.cybergenealogie.fr/cailgeo/fr/cail01n.php?nomr=%(surname)s"],
    ["Person", "Gallica", "Gallica", '''http://gallica.bnf.fr/Search?ArianeWireIndex=index&p=1&lang=FR&q="%(surname)s,+%(given)s"'''],
    ["Person", "Archive.org", "Archive.org", '''http://www.archive.org/search.php?query="%(surname)s,+%(given)s"'''],
    ["Person", "GeneaBook", "GeneaBook", "http://www.geneabook.org/genealogie/1/ouvrages.php?nom=%(surname)s&x=20&y=1"],
    ["Person", "FR-Google", _("FR Google"), '''http://www.google.fr/#hl=fr&q="%(surname)s,+%(given)s"'''],
    #["Place", "Geneanet", "Geneanet", "http://search.geneanet.org/result.php?lang=fr&place=%(city)s"],
    #["Place", u"Centre Départemental d'Histoire des Familles (CDHF)", _("Historical Families Center Departement (CDHF)"), "http://www.cdhf.net/fr/index.php?t=villages&d=villages&c=villages&f=results&p=&page=&lieu2=%(city)s"],
    #["Place", "Fichier Origine", _("OrigineFile (Quebec)"), "http://www.fichierorigine.com/recherche.php?commune=%(city)s&pays=%(country)s"],
    #["Place", "Gallica", "Gallica", "http://gallica.bnf.fr/Search?ArianeWireIndex=index&p=1&lang=FR&q=%(city)s"],
    #["Place", "Archive.org", "Archive.org", "http://www.archive.org/search.php?query=%(city)s"],
    #["Source", "Gallica", "Gallica", "http://gallica.bnf.fr/Search?ArianeWireIndex=index&p=1&lang=FR&q=%(source_title)s"],
    #["Source", "Archive.org", "Archive.org", "http://www.archive.org/search.php?query=%(source_title)s"],
    #["Source", "Google books", _("Google books"), "http://www.google.fr/search?tbs=bks%3A1&q=%(source_title)s"],
    ]

def load_on_reg(dbstate, uistate, pdata):
    # do things at time of load
    # now return functions that take:
    #     dbstate, uistate, nav_type, handle
    # and that returns a function that takes a widget
    return lambda nav_type: \
        make_search_functions(nav_type, WEBSITES)

