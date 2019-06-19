#
# Gramps - a GTK+/GNOME based genealogy program
#
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

# -------------------------------------------------
#
# GRAMPS modules
#
# -------------------------------------------------
from gramps.gui.plug import MenuToolOptions, PluginWindows
from gramps.gen.plug.menu import FilterOption, PersonOption, FamilyOption
from gramps.gen.db import DbTxn
import gramps.gen.plug.report.utils as ReportUtils
from gramps.gui.dialog import OkDialog
from gramps.gen.filters import CustomFilters
from gramps.gen.filters import GenericFilterFactory, rules
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# ----------------------------------------------------------------------------
#
# Option Class
#
# ----------------------------------------------------------------------------
class RemoveTagOptions(MenuToolOptions):
    """
    Class for creating 'Remove Tag Tool' menu options.

    The options are needed for processing tag removal in
    :class RemoveTagWindow:.
    """
    def __init__(self, name, person_id=None, dbstate=None):
        self.__db = dbstate.get_database()
        MenuToolOptions.__init__(self, name, person_id, dbstate)

    def get_enum_tag_name_list(self):
        """
        Get an enumerated tag name list.

        :rtype: list
        """
        tag_list = self.__db.iter_tags()
        L = list(map(lambda x: x.get_name(), tag_list))
        return list(enumerate(L))

    def add_menu_options(self, menu):
        """
        Add the menu options for the Remove Tag Tool.
        """
        self.__add_tag_category_options(menu)
        self.__add_person_options(menu)
        self.__add_family_options(menu)

        self.filter_dict = {}
        lst = [("events", _("Event Filter"), "event_filter", 'Event',
                _("All Events"), _("Option 2")),
               ("places", _("Place Filter"), "place_filter", 'Place',
                _("All Places"), _("Option 2")),
               ("sources", _("Source Filter"), "scource_filter", 'Source',
                _("All Places"), _("Option 2")),
               ("citations", _("Citation Filter"), "cit_filter", 'Citation',
                _("All Places"), _("Option 2")),
               ("repositories", _("Repository Filter"), "repo_filter",
                'Repository', _("All Places"), _("Option 2")),
               ("media", _("Media Filter"), "media_filter", 'Media',
                _("All Places"), _("Option 2")),
               ("notes", _("Note Filter"), "note_filter", 'Note',
                _("All Places"), _("Option 2"))]

        for entry in lst:
            filter_name = FilterOption(entry[1], 0)
            filter_name.set_help(_("Select filter to restrict {}"
                                   .format(entry[0])))
            menu.add_option(entry[5], entry[2], filter_name)
            self.filter_dict[entry[3]] = filter_name

            filter_list = CustomFilters.get_filters(entry[3])
            GenericFilter = GenericFilterFactory(entry[3])
            all_filter = GenericFilter()
            all_filter.set_name(entry[4])
            all_filter.add_rule(rules.event.AllEvents([]))
            all_filter_in_list = False
            for fltr in filter_list:
                if fltr.get_name() == all_filter.get_name():
                    all_filter_in_list = True
            if not all_filter_in_list:
                filter_list.insert(0, all_filter)
            self.filter_dict[entry[3]].set_filters(filter_list)

    def __add_tag_category_options(self, menu):
        """
        Menu Options for general category tab.

        Users select from which category they'd like to remove a tag.
        The chosen category also restricts the tag removal to this category
        e.g. remove tag 'ToDo' from filtered persons, but not from places,
        events, etc.
        """
        lst = ["People", "Families", "Events", "Places", "Sources",
               "Citations", "Repositories", "Media", "Notes"]
        category_list = list(enumerate(lst))

        self.__tag_category = FilterOption(_("Category"), 0)
        self.__tag_category.set_help(_("Choose a category."))
        menu.add_option(_("Option 1"), "category",
                        self.__tag_category)
        self.__tag_category.set_items(category_list)
        self.__tag_category.connect('value-changed', self.__update_options)

        tag_list = self.get_enum_tag_name_list()
        self.__tag_name = FilterOption("Remove Tag", 0)
        self.__tag_name.set_help(_("Choose a tag to remove."))
        menu.add_option(_("Option 1"), "tag_name", self.__tag_name)
        self.__tag_name.set_items(tag_list)

    def __update_options(self):
        """
        Turn availability on depending on user selection.
        """
        self.__disable_all_options()
        value = self.__tag_category.get_value()

        if value == 0:
            self.__person_filter.set_available(True)
            self.__filter_changed()
        elif value == 1:
            self.__family_filter.set_available(True)
            self.__family_filter_changed()
        elif value == 2:
            self.filter_dict['Event'].set_available(True)
        elif value == 3:
            self.filter_dict['Place'].set_available(True)
        elif value == 4:
            self.filter_dict['Source'].set_available(True)
        elif value == 5:
            self.filter_dict['Citation'].set_available(True)
        elif value == 6:
            self.filter_dict['Repository'].set_available(True)
        elif value == 7:
            self.filter_dict['Media'].set_available(True)
        elif value == 8:
            self.filter_dict['Note'].set_available(True)

    def __disable_all_options(self):
        """
        Turn all options off, except options 'category' and 'tag_name'
        """
        self.__person_filter.set_available(False)
        self.__pid.set_available(False)
        self.__family_filter.set_available(False)
        self.__fid.set_available(False)
        for entry in ['Event', 'Place', 'Source', 'Citation', 'Repository',
                      'Media', 'Note']:
            self.filter_dict[entry].set_available(False)

    def __add_person_options(self, menu):
        """
        Menu Options for person category.

        Menu Option 'pers_filter' is used to choose a generic or custom person
        filter. Menu Option 'pid' selects the center person, which is needed
        for some person filters.

        :param menu: a menu object where options can be added
        :type menu: :class Menu: object
        """
        self.__person_filter = FilterOption(_("Person Filter"), 0)
        self.__person_filter.set_help(_("Select filter to restrict people"))
        menu.add_option(_("Option 1"), "pers_filter", self.__person_filter)
        self.__person_filter.connect('value-changed', self.__filter_changed)

        self.__pid = PersonOption(_("Center Person"))
        self.__pid.set_help(_("The center person for the filter"))
        menu.add_option(_("Option 1"), "pid", self.__pid)
        self.__pid.connect('value-changed', self.__update_filters)

        self.__update_filters()

    def __update_filters(self):
        """
        Update the filter list based on the selected person.
        """
        gid = self.__pid.get_value()
        person = self.__db.get_person_from_gramps_id(gid)
        filter_list = ReportUtils.get_person_filters(person, False)
        self.__person_filter.set_filters(filter_list)

    def __filter_changed(self):
        """
        Handle person filter change.

        If the filter is not specific to a person, disable the person option.
        """
        filter_value = self.__person_filter.get_value()
        (self.__pid.set_available(True) if (filter_value in [1, 2, 3, 4])
         else self.__pid.set_available(False))

    def __add_family_options(self, menu):
        """
        Menu Options for family category.

        Menu Option 'family_filter' is used to choose a generic or custom
        family filter. Menu Option 'fid' selects the center family, which is
        needed for some filters.

        :param menu: a menu object where options can be added
        :type menu: :class Menu: object
        """
        self.__family_filter = FilterOption(_("Family Filter"), 0)
        self.__family_filter.set_help(_("Select filter to restrict families"))
        menu.add_option(_("Option 1"), "family_filter",
                        self.__family_filter)
        self.__family_filter.connect('value-changed',
                                     self.__family_filter_changed)

        self.__fid = FamilyOption(_("Center Family"))
        self.__fid.set_help(_("The center person for the filter"))
        menu.add_option(_("Option 1"), "fid", self.__fid)
        self.__fid.connect('value-changed', self.__update_family_filters)

        self.__update_family_filters()

    def __update_family_filters(self):
        """
        Update the filter list based on the selected family.
        """
        gid = self.__fid.get_value()
        family = self.__db.get_family_from_gramps_id(gid)
        filter_list = ReportUtils.get_family_filters(self.__db, family, False)
        self.__family_filter.set_filters(filter_list)

    def __family_filter_changed(self):
        """
        Handle family filter change.

        If the filter is not specific to a family, disable the family option.
        """
        filter_value = self.__family_filter.get_value()
        (self.__fid.set_available(True) if (filter_value in [1, 2]) else
         self.__fid.set_available(False))


# ----------------------------------------------------------------------------
#
# Tool Class
#
# ----------------------------------------------------------------------------
class RemoveTagWindow(PluginWindows.ToolManagedWindowBatch):
    def get_title(self):
        """
        Window title.
        """
        return _("Remove Tag Tool")

    def initial_frame(self):
        """
        Category tab title.
        """
        return _("Options")

    def run(self):
        """
        Main function running the Remove Tag Tool.
        """
        self.__db = self.dbstate.get_database()
        self.__tag_info = self.__get_tag_info()
        self.__get_menu_options()

    def __get_tag_info(self):
        """
        Return a list of tuples

        :rtype: list
        :example tuple: (counter, tag_handle, tag_name)
        """
        tag_list = self.__db.iter_tags()
        L = []
        counter = 0
        for Tag in tag_list:
            L.append((counter, Tag.get_handle(), Tag.get_name))
            counter += 1
        return L

    def __get_menu_options(self):
        """
        A function selecting which category is processed.

        The category_value is selected by the user in the
        menu options for general category. This function is the interating
        through the items of that category, aplying the selected filter
        from the menu options. Finally the tag_handle is removed from all
        those items of the category, but not from the other categories.
        """
        tag_category = self.__opt_by_name('category')
        category_value = tag_category.get_value()
        tag_value = self.options.handler.options_dict['tag_name']
        for info in self.__tag_info:
            if info[0] == tag_value:
                self.tag_handle = info[1]
                self.tag_name = info[2]

        if category_value == 0:
            self.menu_opt_handling("person", 'pers_filter')
        elif category_value == 1:
            self.menu_opt_handling("family", 'family_filter')
        elif category_value == 2:
            self.menu_opt_handling("event", 'event_filter')
        elif category_value == 3:
            self.menu_opt_handling("place", 'place_filter')
        elif category_value == 4:
            self.menu_opt_handling("source", 'source_filter')
        elif category_value == 5:
            self.menu_opt_handling("citation", 'cit_filter')
        elif category_value == 6:
            self.menu_opt_handling("repository", 'repo_filter')
        elif category_value == 7:
            self.menu_opt_handling("media", 'media_filter')
        elif category_value == 8:
            self.menu_opt_handling("note", 'note_filter')

    def __opt_by_name(self, opt_name):
        """
        Get an option by its name.

        :param opt_name: the name of the option
        :type opt_name: string
        :returns: option of this option name
        :rtype: :class FilterOption: object
        """
        return self.options.menu.get_option_by_name(opt_name)

    def menu_opt_handling(self, category, option_name):
        """
        General menu option handling

        :param category: name of the category
        :type category: string
        :param option_name: name of the menu option
        :type option_name: string
        """
        iter_ = eval("self.dbstate.db.iter_{}_handles()".format(category))
        filter_opt = self.__opt_by_name(option_name)
        filter_ = filter_opt.get_filter()
        objects = filter_.apply(self.dbstate.db, iter_)
        self.__remove_from(objects, category)

    def __remove_from(self, objects, category):
        """
        Remove the tag from objects of a selected category

        :param objects: object handles of a selected category
        :type objects: list
        :param category: name of a selected category
        :type category: string
        """
        db = self.dbstate.db
        counter = 0
        with DbTxn(_("Remove Tag Tool"), self.db, batch=True) as self.trans:
            self.db.disable_signals()
            num = len(objects)
            self.progress.set_pass(_('Removing tags...'), num)
            for handle in objects:
                Object = eval("db.get_{}_from_handle(handle)".format(category))
                if self.tag_handle in Object.get_tag_list():
                    Object.remove_tag(self.tag_handle)
                    eval("self.db.commit_{}(Object, self.trans)"
                         .format(category))
                    counter += 1
                    self.progress.step()
        self.db.enable_signals()
        self.db.request_rebuild()

        text = _("Tag '{}' removed from {} {}.\n")
        text_f = text.format(self.tag_name(), str(counter), category)
        OkDialog("INFO", text_f, parent=self.window)
