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

# $Id$

"Set Attribute Tool"

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
from PluginUtils import Tool, PluginWindows, MenuToolOptions
from gen.plug.menu import StringOption, FilterOption, PersonOption, \
    EnumeratedListOption
import gen.lib
try:
    from gen.display.name import displayer as name_displayer
except:
    from BasicUtils import name_displayer
import Errors
from ReportBase import ReportUtils

try:
    from TransUtils import get_addon_translator
    _ = get_addon_translator(__file__).ugettext
except:
    import gettext
    _ = gettext.gettext

#-------------------------------------------------
#
# Tool Classes
#
#-------------------------------------------------
class SetAttributeOptions(MenuToolOptions):
    """ Set Attribute options  """
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
        
        attribute_text = StringOption(_("Attribute"), "")
        attribute_value = StringOption(_("Value"), "")

        attribute_text.set_help(_("Attribute type to add or edit"))
        attribute_value.set_help(_("Attribute value to add or edit"))

        menu.add_option(category_name, "attribute_text", attribute_text)
        menu.add_option(category_name, "attribute_value", attribute_value)
        self.__attribute_text = attribute_text
        self.__attribute_value = attribute_value

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

class SetAttributeWindow(PluginWindows.ToolManagedWindowBatch):
    def get_title(self):
        return _("Set Attribute")

    def initial_frame(self):
        return _("Options")

    def run(self):
        self.trans = self.db.transaction_begin("",batch=True)

        self.add_results_frame(_("Results"))
        self.results_write(_("Processing...\n"))
        self.db.disable_signals()

        self.filter_option =  self.options.menu.get_option_by_name('filter')
        self.filter = self.filter_option.get_filter() # the actual filter

        # FIXME: currently uses old style for gramps31 compatible
        #    people = self.filter.apply(self.db,
        #                               self.db.iter_person_handles())
        people = self.filter.apply(self.db,
                                   self.db.get_person_handles(sort_handles=False))

        # FIXME: currently uses old style for gramps31 compatible
        # num_people = self.db.get_number_of_people()
        num_people = len(people)
        self.progress.set_pass(_('Setting attributes...'), 
                               num_people)
        count = 0
        attribute_text = self.options.handler.options_dict['attribute_text'] 
        attribute_value = self.options.handler.options_dict['attribute_value']
        specified_type = gen.lib.AttributeType()
        specified_type.set(attribute_text)
        self.results_write(_("Setting '%s' attributes to '%s'...\n\n" % 
                             (attribute_text, attribute_value)))
        for person_handle in people:
            count += 1
            self.progress.step()
            person = self.db.get_person_from_handle(person_handle)
            done = False
            for attr in person.get_attribute_list():
                if attr.get_type() == specified_type:
                    self.results_write("  %d) Changed" % count)
                    self.results_write_link(name_displayer.display(person),
                                            person, person_handle)
                    self.results_write(" from '%s'\n" % attr.get_value())
                    attr.set_value(attribute_value)
                    done = True
                    break
            if not done:
                attr = gen.lib.Attribute()
                attr.set_type(specified_type)
                attr.set_value(attribute_value)
                person.add_attribute(attr)
                # Update global attribute list:
                if attr.type.is_custom() and str(attr.type):
                    self.db.individual_attributes.update([str(attr.type)])
                self.results_write("  %d) Added attribute to" % count)
                self.results_write_link(name_displayer.display(person),
                                            person, person_handle)
                self.results_write("\n")
            self.db.commit_person(person, self.trans)
        self.db.transaction_commit(self.trans, _("Set Attribute"))
        self.db.enable_signals()
        self.db.request_rebuild()
        self.results_write(_("\nSet %d '%s' attributes to '%s'\n" % 
                             (count, attribute_text, attribute_value)))
        self.results_write(_("Done!\n"))

try:
    # Gramps 3.1 style:
    from gen.plug import PluginManager
    pmgr = PluginManager.get_instance()
    pmgr.register_tool(
        name = 'Set Atttribute Tool',
        category = Tool.TOOL_DBPROC,
        tool_class = SetAttributeWindow,
        options_class = SetAttributeOptions,
        modes = PluginManager.TOOL_MODE_GUI,
        translated_name = _("Set Attribute"),
        status = _("Beta"),
        author_name = "Douglas S. Blank",
        author_email = "doug.blank@gmail.com",
        description= _("Sets an attribute of a person to a given value."),
        )
except:
    pass
