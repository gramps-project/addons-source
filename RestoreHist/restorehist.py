#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2018       Paul Culley <paulr2787_at_gmail.com>
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
"""
This module implements the Restore History functionality.
"""
import os
import json
from types import MethodType
from gramps.gen.config import config


def clear_history(self):
    """
    Clear all history objects. Replaces DisplayState method.
    Reload history if it is valid for the db.
    """
    history_list = list(self.history_lookup.values())
    if not history_list or not history_list[0].dbstate.is_open():
        return
    for history in history_list:
        history.clear()
    hist_save_ini = os.path.join(os.path.dirname(__file__), "hist_save.ini")
    if not os.path.isfile(hist_save_ini):
        # Set these once if not run before so user can unset if he wants
        config.set("behavior.autoload", True)
        config.set("preferences.use-last-view", True)
        return
    try:
        with open(hist_save_ini, mode="r", encoding="utf-8") as _fp:
            saved_history = json.load(_fp)
    except IOError as error_data:
        print(
            "Error reading hist_save.ini: {} {}".format(
                error_data.errno, error_data.strerror
            )
        )
        print("RestoreHist addon is not working correctly")
        return
    except json.JSONDecodeError as error_data:
        print("Error parsing hist_save.ini: {}".format(error_data.msg))
        print("RestoreHist addon is not working correctly")
        return
    if (
        "filename" not in saved_history
        or saved_history["filename"] != history_list[0].dbstate.db.get_dbid()
    ):
        return
    for history in history_list:
        if (
            history.nav_type not in saved_history
            or not saved_history[history.nav_type]
        ):
            continue
        history.mru = []
        for item in saved_history[history.nav_type]:
            if isinstance(item, list):
                history.mru.append(tuple(item))
            else:
                history.mru.append(item)
        history.history = history.mru[:]
        history.index = len(history.mru) - 1
        new_active_object = history.history[history.index]
        history.emit("mru-changed", (history.mru,))
        history.emit("active-changed", (new_active_object,))


def __delete_pages(self):
    """
    Save the history object pointers.  Replaces ViewManager method.
    """
    if self.dbstate.db.get_dbid():
        out = {"filename": self.dbstate.db.get_dbid()}
        for history in self.uistate.history_lookup.values():
            out[history.nav_type] = history.mru[-6:]
        try:
            with open(
                os.path.join(os.path.dirname(__file__), "hist_save.ini"),
                mode="w",
                encoding="utf-8",
            ) as _fp:
                _fp.write(json.dumps(out, indent=2))
        except:
            print("RestoreHist addon is not working correctly.")
    if ORIGINAL_DELETE_PAGES:
        ORIGINAL_DELETE_PAGES()


def load_on_reg(_dbstate, uistate, _plugin):
    """
    Runs when plugin is registered.
    """
    if not uistate or ("ORIGINAL_DELETE_PAGES" in globals()):
        # It is necessary to avoid load GUI elements when run under CLI mode.
        # So we just don't load it at all.
        return
    # Monkey patch my version of methods into the system
    global ORIGINAL_DELETE_PAGES
    ORIGINAL_DELETE_PAGES = None
    try:
        ORIGINAL_DELETE_PAGES = uistate.viewmanager._ViewManager__delete_pages
        setattr(uistate, "clear_history", MethodType(clear_history, uistate))
        setattr(
            uistate.viewmanager,
            "_ViewManager__delete_pages",
            MethodType(__delete_pages, uistate.viewmanager),
        )
    except:
        print("RestoreHist addon is not working correctly.")
