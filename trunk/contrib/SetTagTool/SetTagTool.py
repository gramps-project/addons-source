#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2007  Donald N. Allingham
# Copyright (C) 2008  Brian Matherly
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

"Set Tag Tool"

#-------------------------------------------------
#
# python modules
#
#-------------------------------------------------
import time

#-------------------------------------------------
#
# GRAMPS modules
#
#-------------------------------------------------
from gramps.gui.plug.tool import Tool
from gramps.gui.plug import MenuToolOptions, PluginWindows
from gramps.gen.plug.menu import StringOption, FilterOption, PersonOption, \
    EnumeratedListOption
import gramps.gen.lib
from gramps.gen.db import DbTxn
from gramps.gen.display.name import displayer as name_displayer
import gramps.gen.plug.report.utils as ReportUtils

try:
    from gramps.gen.utils.trans import get_addon_translator
    _ = get_addon_translator(__file__).ugettext
except:
    import gettext
    _ = gettext.gettext

#-------------------------------------------------
#
# Tool Classes
#
#-------------------------------------------------
class SetTagOptions(MenuToolOptions):
    """ Set Tag options  """
    def __init__(self, name, person_id=None, dbstate=None):
        self.__db = dbstate.get_database()
        MenuToolOptions.__init__(self, name, person_id, dbstate)
    
    def add_menu_options(self, menu):
        
        """ Add the options """
        category_name = _("Options")
        
        self.__filter = FilterOption(_("Person Filter"), 0)
        self.__filter.set_help(_("Select filter to restrict people"))
        menu.add_option(category_name, "filter", self.__filter)
        self.__filter.connect('value-changed', self.__filter_changed)
        
        self.__pid = PersonOption(_("Filter Person"))
        self.__pid.set_help(_("The center person for the filter"))
        menu.add_option(category_name, "pid", self.__pid)
        self.__pid.connect('value-changed', self.__update_filters)
        
        tag_value = StringOption(_("Tag"), "")

        tag_value.set_help(_("Tag value to add or edit"))

        menu.add_option(category_name, "tag_value", tag_value)
        self.__tag_value = tag_value

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

class SetTagWindow(PluginWindows.ToolManagedWindowBatch):
    def get_title(self):
        return _("Set Tag")

    def initial_frame(self):
        return _("Options")

    def run(self):
        with DbTxn(_("Set Tag"), self.db, batch=True) as self.trans:

            self.add_results_frame(_("Results"))
            self.results_write(_("Processing...\n"))
            self.db.disable_signals()

            self.filter_option =  self.options.menu.get_option_by_name('filter')
            self.filter = self.filter_option.get_filter() # the actual filter

            people = self.filter.apply(self.db,
                                       self.db.get_person_handles(sort_handles=False))

            num_people = len(people)
            self.progress.set_pass(_('Setting tags...'), 
                                   num_people)
            count = 0
            tag_value = self.options.handler.options_dict['tag_value']
            self.results_write(_("Setting tags to '%s'...\n\n" % tag_value))
            tag = self.db.get_tag_from_name(tag_value)
            for person_handle in people:
                count += 1
                self.progress.step()
                person = self.db.get_person_from_handle(person_handle)
                if person and person.get_tag_list() != tag:
                    self.results_write("  %d) Changed" % count)
                    self.results_write_link(name_displayer.display(person),
                                            person, person_handle)
                    self.results_write(" from '%s'\n" % person.get_tag_list())
                    #gramps.gen.lib.tag.set_name(tag_value)
                    person.add_tag(tag)
                    self.db.commit_person(person, self.trans)
                    count += 1
            self.db.enable_signals()
            self.db.request_rebuild()
            self.results_write(_("\nSet %d tags to '%s'\n" % (count, tag_value)))
            self.results_write(_("Done!\n"))
