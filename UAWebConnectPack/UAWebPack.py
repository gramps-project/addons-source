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
    # --- Forums ---
    ["Person", "ukrgenealogy.com.ua", _("Forum: ukrgenealogy.com.ua"), "https://ukrgenealogy.com.ua/search.php?keywords=%(surname)s+%(given)s"],
    ["Person", "genoua.name", _("Forum: genoua.name"), "http://forum.genoua.name/search.php?action=search&keywords=%(surname)s+%(given)s&search=Знайти"],

    # --- Encyclopedias ---
    ["Person", "esu.com.ua", _("Encyclopedia: esu.com.ua"), "https://esu.com.ua/search?s=%(surname)s+%(given)s"],
    ["Person", "uk.wikipedia.org", _("Wikipedia: uk.wikipedia.org"), "https://uk.wikipedia.org/w/index.php?fulltext=1&search=%(surname)s+%(given)s&title=Спеціальна:Пошук&ns0=1"],

    # --- Repressions ---
    ["Person", "reabit.org.ua", _("Repressed DB: reabit.org.ua"), "https://www.reabit.org.ua/nbr/?st=4&region=&ss=&logic=or&f1_type=begins&f1_str=%(surname)s&f2_type=begins&f2_str=%(given)s&f3_type=begins&f3_str=&f4_from=&f4_till=&f7[]=all&f14[]=all"],

    # --- Genealogy ---
    ["Person", "familysearch.org", _("Genealogy DB: familysearch.org"), "https://www.familysearch.org/search/all-collections/results?q.surname=%(surname)s&q.givenName=%(given)s"],
    ["Person", "myheritage.com.ua", _("Genealogy DB: myheritage.com.ua"), "https://www.myheritage.com.ua/research?formId=master&formMode=1&useTranslation=1&exactSearch=&p=1&action=query&view_mode=card&qname=Name+fn.%(given)s+fnmo.1+ln.%(surname)s+lnmsrs.false"],

    ["Person", "pra.in.ua", _("Genealogy DB: pra.in.ua"), "https://pra.in.ua/en/search/filter?lastname=%(surname)s&firstname=%(given)s&year_from=&year_to=&settlement_name="],

    # --- Maps ---
    ["Person", "ridni.org", _("Map: Ridni.org"), "https://ridni.org/karta/%(surname)s"],

    # --- Search ---
    ["Person", "google.com.ua", _("Search: google.com.ua"), "http://www.google.com.ua/search?q=%(surname)s,+%(given)s"],
    ["Person", "roots.in.ua", _("Search: roots.in.ua"), "https://roots.in.ua/advanced-search?page=1&last_name_search_type=should&last_name=%(surname)s&first_name=%(given)s&base_type=[all]"],
    ]

def load_on_reg(dbstate, uistate, pdata):
    # do things at time of load
    # now return functions that take:
    #     dbstate, uistate, nav_type, handle
    # and that returns a function that takes a widget
    return lambda nav_type: \
        make_search_functions(nav_type, WEBSITES)