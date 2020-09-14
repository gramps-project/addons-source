#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2019    Matthias Kemmer
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
"""A tool to find and replace event descriptions."""

import re

# ----------------------------------------------------------------------------
#
# GRAMPS modules
#
# ----------------------------------------------------------------------------
from gramps.gui.plug import MenuToolOptions, PluginWindows
from gramps.gen.plug.menu import FilterOption, StringOption, BooleanOption
from gramps.gen.filters import CustomFilters, GenericFilterFactory, rules
from gramps.gui.dialog import OkDialog
from gramps.gen.db import DbTxn
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# ----------------------------------------------------------------------------
#
# Tool Class
#
# ----------------------------------------------------------------------------
class EventDescriptionEditor(PluginWindows.ToolManagedWindowBatch):
    """Handles the Event Description Editor Tool processing."""

    def get_title(self):
        """Tool window title."""
        return _("Event Description Editor")

    def run(self):
        """Run the tool."""
        db = self.dbstate.get_database()
        menu = self.options.menu
        opt = self.options.options_dict

        sub_str = opt["find"]
        replace_str = opt["replace"]
        keep_old = opt["keep_old"]
        regex = opt["regex"]
        txt = _("Event Description Editor")

        iter_events = db.iter_event_handles()
        index = opt["events"]
        filter_ = menu.filter_list[index]
        events = filter_.apply(db, iter_events)

        with DbTxn(txt, db, batch=True) as self.trans:
            db.disable_signals()
            num = len(events)
            counter = 0
            self.progress.set_pass(_('Search substring...'), num)

            for handle in events:
                Event = db.get_event_from_handle(handle)
                event_desc = Event.get_description()
                if sub_str == "":
                    break
                elif not regex and sub_str in event_desc and not keep_old:
                    Event.set_description(replace_str)
                    counter += 1
                elif not regex and sub_str in event_desc and keep_old:
                    new_str = event_desc.replace(sub_str, replace_str)
                    Event.set_description(new_str)
                    counter += 1
                elif regex and re.search(sub_str, event_desc) and not keep_old:
                    Event.set_description(replace_str)
                    counter += 1
                elif regex and re.search(sub_str, event_desc) and keep_old:
                    for string in re.findall(sub_str, event_desc):
                        if string != "":
                            new_str = event_desc.replace(string, replace_str)
                            Event.set_description(new_str)
                            counter += 1

                db.commit_event(Event, self.trans)
                self.progress.step()

            db.enable_signals()
            db.request_rebuild()

            OkDialog(_("INFO"),
                     _("%s event descriptions of %s events were changed."
                       % (str(counter), str(num))),
                     parent=self.window)


# ----------------------------------------------------------------------------
#
# Option Class
#
# ----------------------------------------------------------------------------
class EventDescriptionEditorOptions(MenuToolOptions):
    """Option class for event description editor."""

    def __init__(self, name, person_id=None, dbstate=None):
        MenuToolOptions.__init__(self, name, person_id, dbstate)

    def add_menu_options(self, menu):
        """Menu options."""
        menu.filter_list = CustomFilters.get_filters("Event")
        all_filter = GenericFilterFactory("Event")()
        all_filter.set_name(_("All Events"))
        all_filter.add_rule(rules.event.AllEvents([]))
        all_filter_in_list = False
        for fltr in menu.filter_list:
            if fltr.get_name() == all_filter.get_name():
                all_filter_in_list = True
        if not all_filter_in_list:
            menu.filter_list.insert(0, all_filter)

        events = FilterOption(_("Events"), 0)
        menu.add_option(_("Option"), "events", events)
        events.set_filters(menu.filter_list)

        find = StringOption(_("Find"), "")
        menu.add_option(_("Option"), "find", find)

        replace = StringOption(_("Replace"), "")
        menu.add_option(_("Option"), "replace", replace)

        keep_old = BooleanOption(_("Replace substring only"), False)
        keep_old.set_help(_("If True only the substring will be replaced, "
                            "otherwise the whole description will be deleted "
                            "and replaced by the new one."))
        menu.add_option(_("Option"), "keep_old", keep_old)

        regex = BooleanOption(_("Allow regex"), False)
        regex.set_help(_("Allow regular expressions."))
        menu.add_option(_("Option"), "regex", regex)
