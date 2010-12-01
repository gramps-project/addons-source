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
# http://www.bigenet.org/index.php
# http://www.geneabank.org/frenind.php3
# http://www.culture.fr/fr/sections/collections/genealogie
# http://www.cdhf.net/fr/index.php?t=bases&d=bases/moteurpat&c=moteurpat&f=selection
# https://beta.familysearch.org/
# http://www.geneanet.org/
#
# Quebec (Canada)
# http://www.fichierorigine.com/
WEBSITES = [
    ["Person", "Geneanet-Favrejhas", "Geneanet, Favrejhas", "http://gw1.geneanet.org/index.php3?b=favrejhas&m=NG&n=%(surname)s&t=N&x=0&y=0"],
    ["Person", "Roglo", "Roglo", "http://roglo.eu/roglo?m=NG&n=%(given)s+%(surname)s&t=PN"],
    ]

def load_on_reg(dbstate, uistate, pdata):
    # do things at time of load
    # now return functions that take:
    #     dbstate, uistate, nav_type, handle
    # and that returns a function that takes a widget
    return lambda nav_type: \
        make_search_functions(nav_type, WEBSITES)

