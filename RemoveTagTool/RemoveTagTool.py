#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2007  Donald N. Allingham
# Copyright (C) 2008  Brian Matherly
# Copyright (C) 2019  Matthias Kemmer
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

# -------------------------------------------------
#
# GRAMPS modules
#
# -------------------------------------------------
from gramps.gui.plug import MenuToolOptions, PluginWindows
from gramps.gen.plug.menu import StringOption, FilterOption, PersonOption
from gramps.gen.db import DbTxn
import gramps.gen.plug.report.utils as ReportUtils
from gramps.gui.dialog import OkDialog

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# -------------------------------------------------
#
# Tool Classes
#
# -------------------------------------------------
class RemoveTagOptions(MenuToolOptions):
    """
    Remove tag options
    """
    def __init__(self, name, person_id=None, dbstate=None):
        self.__db = dbstate.get_database()
        MenuToolOptions.__init__(self, name, person_id, dbstate)

    def add_menu_options(self, menu):
        """
        Add the menu options for the Remove Tag Tool
        """
        category_name = _("Options")

        self.__filter = FilterOption(_("Person Filter"), 0)
        self.__filter.set_help(_("Select filter to restrict people"))
        menu.add_option(category_name, "filter", self.__filter)
        self.__filter.connect('value-changed', self.__filter_changed)

        self.__pid = PersonOption(_("Filter Person"))
        self.__pid.set_help(_("The center person for the filter"))
        menu.add_option(category_name, "pid", self.__pid)
        self.__pid.connect('value-changed', self.__update_filters)

        tag_name = StringOption(_("Tag Name"), "")
        tag_name.set_help(_("Tag name to remove from the people"))
        menu.add_option(category_name, "tag_name", tag_name)
        self.__tag_name = tag_name

        self.__update_filters()

    def __update_filters(self):
        """
        Update the filter list based on the selected person
        """
        gid = self.__pid.get_value()
        person = self.__db.get_person_from_gramps_id(gid)
        filter_list = ReportUtils.get_person_filters(person, False)
        self.__filter.set_filters(filter_list)

    def __filter_changed(self):
        """
        Handle filter change. If the filter is not specific to a person,
        disable the person option
        """
        filter_value = self.__filter.get_value()
        if filter_value in [1, 2, 3, 4]:
            # Filters 0, 2, 3, 4 and 5 rely on the center person
            self.__pid.set_available(True)
        else:
            # The rest don't
            self.__pid.set_available(False)


class RemoveTagWindow(PluginWindows.ToolManagedWindowBatch):
    def get_title(self):
        return _("Remove Tag Tool")  # Window title

    def initial_frame(self):
        return _("Options")  # Tab title

    def run(self):
        """
        Main function running the Remove Tag Tool
        """
        tag_name = self.options.handler.options_dict['tag_name']
        tag_name_exists = self.__tagNameExists(tag_name)
        if tag_name_exists[0]:
            tag_handle = tag_name_exists[1]
            self.__removeTag(tag_handle)

    def __tagNameExists(self, tag_name):
        """
        Check if the entered tag name exists in the family tree.
        """
        db = self.dbstate.db
        tag_dict = {}
        tagList = db.iter_tags()
        for Tag in tagList:
            serialized = Tag.serialize()
            tag_handle = serialized[0]
            name = serialized[1]
            tag_dict[name] = tag_handle
        if tag_name in tag_dict:
            return_tag_handle = str(tag_dict[tag_name])
            return (True, return_tag_handle)
        else:
            text = _("No tag with name '{}' was found in this family tree.\n")
            text_f = text.format(str(tag_name))
            OkDialog("ERROR", text_f, parent=self.window)
            return (False, None)

    def __removeTag(self, tag_handle):
        counter = 0
        iter_people = self.dbstate.db.iter_person_handles()
        self.filter_option = self.options.menu.get_option_by_name('filter')
        self.filter = self.filter_option.get_filter()
        people = self.filter.apply(self.dbstate.db, iter_people)

        with DbTxn(_("Remove Tag Tool"), self.db, batch=True) as self.trans:
            self.db.disable_signals()
            num_people = len(people)
            self.progress.set_pass(_('Removing tags...'),
                                   num_people)
            for person_handle in people:
                person = self.dbstate.db.get_person_from_handle(person_handle)
                if tag_handle in person.get_tag_list():
                    person.remove_tag(tag_handle)
                    self.db.commit_person(person, self.trans)
                    counter += 1
        self.db.enable_signals()
        self.db.request_rebuild()

        text = _("Tag removed from {} people.\n")
        text_f = text.format(str(counter))
        OkDialog("INFO", text_f, parent=self.window)
