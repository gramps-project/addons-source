#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2019 Matthias Kemmer
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
from gramps.gen.plug.menu import (FilterOption, MediaOption, PersonOption,
                                  BooleanOption)
from gramps.gen.db import DbTxn
import gramps.gen.plug.report.utils as ReportUtils
from gramps.gui.dialog import OkDialog
from gramps.gen.filters import GenericFilterFactory, rules
from gramps.gen.lib import MediaRef
from gramps.gen.errors import HandleError

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
class AvatarGeneratorOptions(MenuToolOptions):
    def __init__(self, name, person_id=None, dbstate=None):
        self.__db = dbstate.get_database()
        MenuToolOptions.__init__(self, name, person_id, dbstate)

    def add_menu_options(self, menu):
        """
        Add all menu options to the tool window.
        """
        # generate list for category menu option
        words = [_("male"), _("female"), _("unknown"),
                 _("Option"), _("single image mode")]
        itm1 = "{} 1: {}".format(words[3], words[4])
        itm2 = "{} 2: {}/{}/{}".format(words[3], words[0], words[1], words[2])
        category_names = [(0, itm1), (1, itm2)]

        # add all menu options
        self.__category = FilterOption(_("Category"), 0)
        text = _("Choose how many images you'd like to use.")
        self.__category.set_help(text)
        menu.add_option(_("Options"), "category",
                        self.__category)
        self.__category.set_items(category_names)
        self.__category.connect('value-changed', self.__update_options)

        self.__media1 = MediaOption(_("Unknown"))
        self.__media1.set_help(_("Image for people with unknown gender."))
        menu.add_option(_("Options"), "media1", self.__media1)

        self.__media2 = MediaOption(_("Male"))
        self.__media2.set_help(_("Image for males."))
        menu.add_option(_("Options"), "media2", self.__media2)

        self.__media3 = MediaOption(_("Female"))
        self.__media3.set_help(_("Image for females"))
        menu.add_option(_("Options"), "media3", self.__media3)

        self.__person_filter = FilterOption(_("Person Filter"), 0)
        self.__person_filter.set_help(_("Select filter to restrict people"))
        menu.add_option(_("Options"), "person_filter", self.__person_filter)
        self.__person_filter.connect('value-changed', self.__filter_changed)

        self.__pid = PersonOption(_("Center Person"))
        self.__pid.set_help(_("The center person for the filter"))
        menu.add_option(_("Options"), "pid", self.__pid)
        self.__pid.connect('value-changed', self.__update_filters)

        self.__remove = BooleanOption(_("Remove images from people"), False)
        txt = _("Remove selected image(s).")
        self.__remove.set_help(txt)
        menu.add_option(_("Options"), "remove", self.__remove)

    def __update_filters(self):
        """
        Update filter list based on the selected person.
        """
        gid = self.__pid.get_value()
        person = self.__db.get_person_from_gramps_id(gid)
        filter_list = ReportUtils.get_person_filters(person, False)
        self.__person_filter.set_filters(filter_list)

    def __filter_changed(self):
        """
        Handle filter change. If the filter is not specific to a person,
        disable the person option.
        """
        filter_value = self.__person_filter.get_value()
        if filter_value in [1, 2, 3, 4]:
            self.__pid.set_available(True)
        else:
            self.__pid.set_available(False)

    def __update_options(self):
        """
        Update the availability of media options in the menu depending on
        what the user selects in menu option"category".
        """
        self.__media2.set_available(False)
        self.__media3.set_available(False)
        if self.__category.get_value() == 1:
            self.__media2.set_available(True)
            self.__media3.set_available(True)


class AvatarGeneratorWindow(PluginWindows.ToolManagedWindowBatch):
    def get_title(self):
        return _("Avatar Generator")  # tool window title

    def initial_frame(self):
        return _("Options")  # tab title

    def run(self):
        """
        Main function running the Avatar Generator Tool.
        """
        self.__db = self.dbstate.get_database()
        self.__get_menu_options()

    def __get_menu_options(self):
        """
        General menu option processing.
        """
        menu = self.options.menu

        # moo = MenuOption object
        category_moo = menu.get_option_by_name('category')
        category_value = category_moo.get_value()

        remove_moo = menu.get_option_by_name('remove')
        remove = remove_moo.get_value()

        iter_people = self.dbstate.db.iter_person_handles()
        filter_options = menu.get_option_by_name('person_filter')
        person_filter = filter_options.get_filter()
        people = person_filter.apply(self.dbstate.db, iter_people)

        media_handles = self.__get_media_list(category_value)
        media_handles_ok = self.__check_media_list(media_handles)

        if media_handles_ok and remove:
            self.__remove_media_from_people(media_handles, people)
        elif media_handles_ok and category_value == 0 and not remove:
            self.__avatar_gen(media_handles, people, category_value)
        elif media_handles_ok and category_value == 1 and not remove:
            people_sorted = self.__people_sorted(people)
            self.__avatar_gen(media_handles, people_sorted, category_value)

    def __remove_media_from_people(self, person_media_handles, people):
        """
        Remove selected media from selected people when menu option "remove"
        was selected.
        """
        count_media = 0
        count_person = 0
        handle_error = 0
        with DbTxn(_("Avatar Generator"), self.db, batch=True) as self.trans:
            self.db.disable_signals()
            num_people = len(people)
            self.progress.set_pass(_('Remove avatar images...'),
                                   num_people)

            for person_handle in people:
                person = self.__db.get_person_from_handle(person_handle)
                media_removed = False
                for mediaRef_obj in person.get_media_list():
                    ref = mediaRef_obj.get_referenced_handles()
                    try:
                        media = self.__db.get_media_from_handle(ref[0][1])
                        media_handle = media.get_handle()
                        if media_handle in person_media_handles:
                            person.remove_media_references(media_handle)
                            self.db.commit_person(person, self.trans)
                            count_media += 1
                            media_removed = True
                    except HandleError:
                        handle_error += 1
                if media_removed:
                    count_person += 1
                self.progress.step()
        self.db.enable_signals()
        self.db.request_rebuild()

        if count_media == 0 and count_person == 0:
            OkDialog(_("INFO"), _("No media was removed."), parent=self.window)
        else:
            info_text = _("{} media references were removed from {} persons.")
            info_text = info_text.format(count_media, count_person)
            if handle_error > 0:
                info_text2 = _("\n{} HandleError occured, but were ignored.")
                info_text2 = info_text2.format(handle_error)
                info_text = info_text + info_text2
            OkDialog(_("INFO"), info_text, parent=self.window)

    def __apply_filter(self, people, filter_rule):
        """
        Apply a filter rule on a list of people. Return the filtered list of
        people handles.
        """
        FilterClass = GenericFilterFactory('Person')
        filter_obj = FilterClass()
        filter_obj.add_rule(filter_rule)
        filtered_people = filter_obj.apply(self.dbstate.db, people)
        return filtered_people

    def __people_sorted(self, people):
        """
        Sort people depending on their gender and return a sorted list of
        unknown, male and female person handles.
        """
        ismale = rules.person.IsMale([])
        isfemale = rules.person.IsFemale([])
        isunknown = rules.person.HasUnknownGender([])
        people_sorted = []

        males = self.__apply_filter(people, ismale)
        females = self.__apply_filter(people, isfemale)
        unknown = self.__apply_filter(people, isunknown)

        people_sorted.append(unknown)
        people_sorted.append(males)
        people_sorted.append(females)

        return people_sorted

    def __avatar_gen(self, media_handles, people, value):
        """
        Add the image(s) chosen in the menu options to the people.
        """
        counter = 0
        name_txt = _("Avatar Generator")

        if value == 0:  # Single image mode
            with DbTxn(name_txt, self.db, batch=True) as self.trans:
                self.db.disable_signals()
                num_people = len(people)
                self.progress.set_pass(_('Add avatar images...'), num_people)
                for person_handle in people:  # people = list of people handles
                    person = self.__db.get_person_from_handle(person_handle)
                    if person.get_media_list() == []:
                        mediaref = MediaRef()
                        mediaref.ref = media_handles[0]
                        person.add_media_reference(mediaref)
                        self.db.commit_person(person, self.trans)
                        counter += 1
                    self.progress.step()
            self.db.enable_signals()
            self.db.request_rebuild()

        elif value == 1:  # male/female/unknown
            with DbTxn(name_txt, self.db, batch=True) as self.trans:
                self.db.disable_signals()
                num_people = len(people[0]) + len(people[1]) + len(people[2])
                self.progress.set_pass(_('Add avatar images...'), num_people)
                # people = contains 3 lists here
                # each containing people handels of unknown, males or females
                for person_handle in people[0]:  # unknown people handles
                    person = self.__db.get_person_from_handle(person_handle)
                    if person.get_media_list() == []:
                        mediaref = MediaRef()
                        mediaref.ref = media_handles[0]
                        person.add_media_reference(mediaref)
                        self.db.commit_person(person, self.trans)
                        counter += 1
                    self.progress.step()
                for person_handle in people[1]:  # male people handles
                    person = self.__db.get_person_from_handle(person_handle)
                    if person.get_media_list() == []:
                        mediaref = MediaRef()
                        mediaref.ref = media_handles[1]
                        person.add_media_reference(mediaref)
                        self.db.commit_person(person, self.trans)
                        counter += 1
                    self.progress.step()
                for person_handle in people[2]:  # female people handles
                    person = self.__db.get_person_from_handle(person_handle)
                    if person.get_media_list() == []:
                        mediaref = MediaRef()
                        mediaref.ref = media_handles[2]
                        person.add_media_reference(mediaref)
                        self.db.commit_person(person, self.trans)
                        counter += 1
                    self.progress.step()
            self.db.enable_signals()
            self.db.request_rebuild()

        if counter > 0:
            info_text = _("{} avatar images were sucessfully added.")
            info_text2 = info_text.format(counter)
            OkDialog(_("INFO"), info_text2, parent=self.window)
        else:
            txt1 = _("There was no avatar image to add. ")
            txt2 = _("All persons already had one.")
            OkDialog(_("INFO"), (txt1 + txt2), parent=self.window)

    def __check_media_list(self, media_list):
        """
        Return 'True' if media list is valid and contains media handles only.
        """
        if False in media_list:
            OkDialog("INFO", "Select images first.", parent=self.window)
            return False  # Invalid, because user didn't selected a image
        else:
            return True  # valid list of handles

    def __get_media_list(self, value):
        """
        Media menu option processing. Returns a list of media handles.
        """
        menu = self.options.menu
        name = ['media1', 'media2', 'media3']
        media_list = []

        if value == 0:  # Option 1: single image
            menu_option = menu.get_option_by_name(name[0])
            media_handle = self.__get_media_handle(menu_option)
            media_list.append(media_handle)
            return media_list
        elif value == 1:  # Option 2: male/female/unknown
            for i in range(3):
                menu_option = menu.get_option_by_name(name[i])
                media_handle = self.__get_media_handle(menu_option)
                media_list.append(media_handle)
            return media_list

    def __get_media_handle(self, menu_option):
        """
        Return media handle from media menu option or 'False' if no image was
        selected.
        """
        gid = menu_option.get_value()
        if gid == "":
            return False
        else:
            media_obj = self.__db.get_media_from_gramps_id(gid)
            media_handle = media_obj.get_handle()
            return media_handle
