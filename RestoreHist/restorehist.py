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
""" This module implements the Restore History functionality.
"""
import os
import json
from types import MethodType
from gramps.gen.config import config


orig_delete_pages = None


def clear_history(self):
    """
    Clear all history objects. Replaces DisplayState method.
    Reload history if it is valid for the db.
    """
    hist_list = list(self.history_lookup.values())
    if not hist_list:
        return
    for history in hist_list:
        history.clear()
    if not history.dbstate.is_open():
        return
    try:
        with open(os.path.join(os.path.dirname(__file__), "hist_save.ini"),
                  mode='r', encoding='utf-8') as _fp:
            hist = json.load(_fp)
    except:
        hist = None
    if not hist or hist['filename'] != history.dbstate.db.full_name:
        # set these once if not run before so user can unset if he wants
        config.set("behavior.autoload", True)
        config.set("preferences.use-last-view", True)
        return
    for history in hist_list:
        history.mru = hist[history.nav_type]
        if not history.mru:
            continue
        history.history = history.mru[:]
        history.index = len(history.mru) - 1
        newact = history.history[history.index]
        history.emit('mru-changed', (history.mru, ))
        history.emit('active-changed', (newact,))


def __delete_pages(self):
    """ save the history object pointers.  Replaces ViewManager method"""
    out = {'filename': self.dbstate.db.full_name}
    for history in self.uistate.history_lookup.values():
        out[history.nav_type] = history.mru[-6:]
    try:
        with open(os.path.join(os.path.dirname(__file__), "hist_save.ini"),
                  mode='w', encoding='utf-8') as _fp:
            _fp.write(json.dumps(out, indent=2))
    except:
        print("RestoreHist addon is not working correctly.")
    if orig_delete_pages:
        orig_delete_pages()


def load_on_reg(dbstate, uistate, plugin):
    """
    Runs when plugin is registered.
    """
    global orig_delete_pages
    if not uistate:
        # It is necessary to avoid load GUI elements when run under CLI mode.
        # So we just don't load it at all.
        return
    # Monkey patch my version of methods into the system
    try:
        orig_delete_pages = uistate.viewmanager._ViewManager__delete_pages
        setattr(uistate, 'clear_history', MethodType(clear_history, uistate))
        setattr(uistate.viewmanager, '_ViewManager__delete_pages',
                MethodType(__delete_pages, uistate.viewmanager))
    except:
        print("RestoreHist addon is not working correctly.")