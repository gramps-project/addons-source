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
#---------------------------------------------------------------
#
# Gramps modules
#
#---------------------------------------------------------------
from GrampsDisplay import url
from TransUtils import get_addon_translator
_ = get_addon_translator(__file__).ugettext
from config import config as configman

#---------------------------------------------------------------
#
# Local config and functions
#
#---------------------------------------------------------------
config = configman.register_manager("WebConnects", "WebConnects.ini")
# "leave alone", "separate", or "remove":
config.register("behavior.middle-name", "remove") 
config.load()
config.save()

def escape(text):
    """
    Turn spaces into + symbols.
    """
    text = str(text).replace(" ", "+")
    return text

def make_callback(key, name):
    """
    Decorator for web connect callbacks. Adds the key and name for the
    menu operations. key is a no-space unique id, and name is a
    translated name for the menu.
    """
    def decorator(func):
        func.key = key
        func.name = name
        return func
    return decorator

def make_person_dict(dbstate, handle):
    """
    Create a dictionary to hold values for replacing in URLs.
    """
    results = {
        "surname": "", 
        "given": "",
        "middle": "",
        "birth": "",
        "death": "",
        }
    person = dbstate.db.get_person_from_handle(handle)
    if person:
        results["surname"] = person.get_primary_name().get_surname()
        results["given"] = person.get_primary_name().get_first_name()
        if " " in results["given"]:
            if config.get("behavior.middle-name") == "remove":
                results["given"], junk = \
                    results["given"].split(" ", 1)
            elif config.get("behavior.middle-name") == "separate":
                results["given"], results["middle"] = \
                    results["given"].split(" ", 1)
            elif config.get("behavior.middle-name") == "leave alone":
                pass
            else:
                raise AttributeError("invalid middle-name setting: %s" % 
                                     config.get("behavior.middle-name"))
        ref = person.get_birth_ref()
        if ref:
            event = dbstate.db.get_event_from_handle(ref.ref)
            if event:
                results["birth"] = event.get_date_object().get_year()
        ref = person.get_death_ref()
        if ref:
            event = dbstate.db.get_event_from_handle(ref.ref)
            if event:
                results["death"] = event.get_date_object().get_year()
        # clean up results
        for key in results:
            results[key] = escape(results[key])
    return results
