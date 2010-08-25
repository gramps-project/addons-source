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

"""
The WebConnect API works as follows:

1) load_on_reg is set True in the gpr.py file, category is set to
   "WebConnect" and type is GENERAL.

2) load_on_reg is a function that takes dbstate, uistate, and
   plugindata. It returns a generate function (#3).

3) The generate function takes a nav_type (eg, 'Person') and
   returns a list of search-constructor functions (#4). 

4) Each search constructor function takes a dbstate, uistate,
   nav_type, and handle, and returns a callback (#5). A search
   constructor function must have .key and .name properties. Below,
   these are attached through a decorator.

5) A callback takes a gtk widget (usually the popup menu) and performs
   the search operation, usually running url() to open a browser.

Read the following code from bottom to top.
"""

from libwebconnect import *

@make_callback("UK-Google", _("UK Google"))
def google(dbstate, uistate, nav_type, handle):
    """
    Construct the search function, and return it as a callback
    """
    results = make_person_dict(dbstate, handle)
            
    def callback(widget):
        url('''http://www.google.co.uk/#hl=en&q="%(surname)s,+%(given)s"''' 
            % results, uistate)
    return callback

def generate_search_functions(nav_type):
    """
    Generate the search functions based on the nav_type, which is one
    of 'Person', 'Family', etc.
    """
    # Returned functions need to have key and name properties.
    if nav_type == 'Person':
        return [google]
    else:
        return []

def load_on_reg(dbstate, uistate, pdata):
    # do things at time of load
    # now return functions that take:
    #     dbstate, uistate, nav_type, handle
    # and that returns a function that takes a widget
    return generate_search_functions

