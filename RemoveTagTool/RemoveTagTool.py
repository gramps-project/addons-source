#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2019-2020  Matthias Kemmer
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
"""Add/Remove a tag from groups of people, events, etc."""

# -------------------------------------------------
#
# GRAMPS modules
#
# -------------------------------------------------
from gramps.gui.plug import MenuToolOptions, PluginWindows
from gramps.gen.plug.menu import FilterOption, TextOption
from gramps.gen.db import DbTxn
from gramps.gui.dialog import OkDialog, WarningDialog
from gramps.gen.filters import CustomFilters, GenericFilterFactory, rules
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext


# ----------------------------------------------------------------------------
#
# Tool Option Class
#
# ----------------------------------------------------------------------------
class RemoveTagOptions(MenuToolOptions):
    """Class for creating menu options."""

    def __init__(self, name, person_id=None, dbstate=None):
        self.db = dbstate.get_database()
        MenuToolOptions.__init__(self, name, person_id, dbstate)

    def add_menu_options(self, menu):
        """Add the menu options for the tool."""
        if self.__is_db_empty():
            txt = [_("The Tool requires at least one tag to execute.")]
            self.empty = TextOption(_("ERROR"), txt)
            self.empty.set_available(False)
            menu.add_option(_("ERROR"), "empty", self.empty)
            return  # stop other menu option creation
        else:
            self.__general_options(menu)
            self.__filter_options(menu)

    def __enum_tag_list(self):
        """Return an enumerated tag name list."""
        tag_list = list(self.db.iter_tags())
        if tag_list:
            L = list(map(lambda x: x.get_name(), tag_list))
            return list(enumerate(L))

    def __is_db_empty(self):
        """Check if database has at least one tag."""
        try:
            next(self.db.iter_tag_handles())
        except StopIteration:
            # StopIteration is raised when the category has no objects
            return True  # Empty
        return False  # Not empty

    def __general_options(self, menu):
        """Menu Options for general option tab."""
        # Add or remove tags menu option
        self.add_remove = FilterOption(_("Add/Remove"), 0)
        self.add_remove.set_help(_("Add or remove tags from objects."))
        self.add_remove.set_items([(0, _("Add Tags")), (1, _("Remove Tags"))])
        menu.add_option(_("General options"), "add_remove", self.add_remove)

        # category menu option
        lst = ["People", "Families", "Events", "Places", "Sources",
               "Citations", "Repositories", "Media", "Notes"]
        category_list = list(enumerate(lst))
        self.tag_category = FilterOption(_("Category"), 0)
        self.tag_category.set_help(_("Choose a category."))
        menu.add_option(_("General options"), "category", self.tag_category)
        self.tag_category.set_items(category_list)
        self.tag_category.connect('value-changed', self.__update_options)

        # tag name list menu option
        tag_list = self.__enum_tag_list()
        self.tag_name = FilterOption("Choose Tag", 0)
        self.tag_name.set_help(_("Choose a tag to remove."))
        menu.add_option(_("General options"), "tag_name", self.tag_name)
        self.tag_name.set_items(tag_list)

    def __filter_options(self, menu):
        """Menu Options for filter option tab."""
        self.filter_dict = {}

        # get all filter rules, used for generic filters
        all_persons = rules.person.Everyone([])
        all_families = rules.family.AllFamilies([])
        all_events = rules.event.AllEvents([])
        all_places = rules.place.AllPlaces([])
        all_sources = rules.source.AllSources([])
        all_cits = rules.citation.AllCitations([])
        all_repos = rules.repository.AllRepos([])
        all_media = rules.media.AllMedia([])
        all_notes = rules.note.AllNotes([])

        # create a list used for menu filter option creation later
        lst = [(_("Person Filter"), 'Person', "Persons", all_persons),
               (_("Family Filter"), 'Family', "Families", all_families),
               (_("Event Filter"), 'Event', "Events", all_events),
               (_("Place Filter"), 'Place', "Places", all_places),
               (_("Source Filter"), 'Source', "Sources", all_sources),
               (_("Citation Filter"), 'Citation', "Citations", all_cits),
               (_("Repository Filter"), 'Repository', "Repositories",
                all_repos),
               (_("Media Filter"), 'Media', "Media", all_media),
               (_("Note Filter"), 'Note', "Notes", all_notes)]

        for entry in lst:
            # create a filter option for each category e.g. person, events
            # filter option is a combination of custom filters and
            # a generic filter for all objects of one category
            filter_name = FilterOption(entry[0], 0)
            menu.add_option(_("Filter options"),
                            entry[1].lower(),
                            filter_name)
            self.filter_dict[entry[1]] = filter_name

            # custom filter:
            filter_list = CustomFilters.get_filters(entry[1])

            # generic filter:
            GenericFilter = GenericFilterFactory(entry[1])
            all_filter = GenericFilter()
            all_filter.set_name(_("All %s" % (entry[2])))
            all_filter.add_rule(entry[3])

            # only add the generic filter if it isn't already in the menu
            all_filter_in_list = False
            for fltr in filter_list:
                if fltr.get_name() == all_filter.get_name():
                    all_filter_in_list = True
            if not all_filter_in_list:
                filter_list.insert(0, all_filter)

            # add the list of custom and generic filters
            # to the filter option
            self.filter_dict[entry[1]].set_filters(filter_list)

    def __update_options(self):
        """Turn availability on and off depending on user selection."""
        lst = ['Person', 'Family', 'Event', 'Place', 'Source', 'Citation',
               'Repository', 'Media', 'Note']
        for entry in lst:
            self.filter_dict[entry].set_available(False)
        value = self.tag_category.get_value()
        self.filter_dict[lst[value]].set_available(True)


# ----------------------------------------------------------------------------
#
# Tool Class
#
# ----------------------------------------------------------------------------
class RemoveTagWindow(PluginWindows.ToolManagedWindowBatch):
    """Remove Tag Tool."""

    def get_title(self):
        """Window title."""
        return _("Add/Remove Tag Tool")

    def initial_frame(self):
        """Category tab title."""
        return _("Options")

    def run(self):
        """Run function of Remove Tag Tool."""
        self.db = self.dbstate.get_database()
        if not self.__opt_by_name('add_remove'):
            # when the database is empty, prevent further tool processing
            # 'add_remove' menu option is not generated when db is empty
            txt = _("Unable to run the tool. Please check if your database "
                    "contains tags, filters and objects.")
            WarningDialog(_("WARNING"), txt, parent=self.window)
            return  # stop the tool
        self.remove = bool(self.__opt_by_name('add_remove').get_value())
        tag_info = self.__get_tag_info()

        tag_value = self.options.handler.options_dict['tag_name']
        for info in tag_info:
            if info[0] == tag_value:
                self.tag_handle = info[1]
                self.tag_name = info[2]

        lst = ['Person', 'Family', 'Event', 'Place', 'Source', 'Citation',
               'Repository', 'Media', 'Note']
        category_value = self.__opt_by_name('category').get_value()
        self.__menu_opt_handling(lst[category_value].lower())

    def __get_tag_info(self):
        """Return a list of tuples."""
        tag_list = list(self.db.iter_tags())
        L = list()
        counter = 0
        for Tag in tag_list:
            L.append((counter, Tag.get_handle(), Tag.get_name))
            counter += 1
        return L

    def __opt_by_name(self, opt_name):
        """Get an option by its name."""
        return self.options.menu.get_option_by_name(opt_name)

    def __menu_opt_handling(self, category):
        """General menu option handling."""
        iter_ = list(self.db.method('iter_%s_handles', category)())
        if iter_ == []:
            txt = _("No %s objects were found in database." % category)
            WarningDialog(_("WARNING"), txt, parent=self.window)
            return  # stop the tool
        filter_opt = self.__opt_by_name(category)
        filter_ = filter_opt.get_filter()
        objects = filter_.apply(self.dbstate.db, iter_)
        self.__remove_from(objects, category)

    def __remove_from(self, objects, category):
        """Remove the tag from objects of a selected category."""
        counter = [0, 0]
        num = len(objects)
        name = _("Add/Remove Tag Tool")
        with DbTxn(name, self.db, batch=True) as self.trans:
            self.db.disable_signals()
            self.progress.set_pass(_('Process tags...'), num)
            for handle in objects:
                Object = self.db.method("get_%s_from_handle", category)(handle)
                if self.remove and (self.tag_handle in Object.get_tag_list()):
                    Object.remove_tag(self.tag_handle)
                    self.db.method("commit_%s", category)(Object, self.trans)
                    counter[0] += 1
                elif not self.remove and (self.tag_handle
                                          not in Object.get_tag_list()):
                    Object.add_tag(self.tag_handle)
                    self.db.method("commit_%s", category)(Object, self.trans)
                    counter[1] += 1
                self.progress.step()
        self.db.enable_signals()
        self.db.request_rebuild()

        # Inform the user afterwards
        txt = (_("added"), str(counter[1]))
        if self.remove:
            txt = (_("removed"), str(counter[0]))
        text = _("Tag '{}' was {} to {} {} objects.\n")
        text_f = text.format(self.tag_name(), *txt, category)
        OkDialog(_("INFO"), text_f, parent=self.window)
