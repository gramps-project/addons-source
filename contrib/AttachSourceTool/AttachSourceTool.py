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

"Attach Source Tool"

#------------------------------------------------------------------------
#
# python modules
#
#------------------------------------------------------------------------
import time

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gui.plug.tool import Tool
from gramps.gui.plug import MenuToolOptions, PluginWindows
from gramps.gen.plug.menu import StringOption, FilterOption, PersonOption, \
    EnumeratedListOption
import gramps.gen.lib
from gramps.gen.db import DbTxn
import gramps.gen.plug.report.utils as ReportUtils
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.get_addon_translator(__file__).gettext

#------------------------------------------------------------------------
#
# Tool Classes
#
#------------------------------------------------------------------------
class AttachSourceOptions(MenuToolOptions):
    """ Attach Source options  """
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
        
        self.__update_filters()

        source_type = EnumeratedListOption(_("Source type"), 0)
        source_type.add_item(0, _("New source"))
        source_type.add_item(1, _("Existing source"))
        source_type.set_help(_("Select the type of source to attach"))
        menu.add_option(category_name, "source_type", source_type)
        source_type.connect('value-changed', self.__update_source_type)
        self.__source_type = source_type

        source_text = StringOption(_("New Source Title"), "")
        source_text.set_help(_("Text of source to attach"))
        menu.add_option(category_name, "source_text", source_text)
        self.__source_text = source_text

        source_id = StringOption(_("Existing Source ID"), "")
        source_id.set_help(_("ID of source to attach"))
        menu.add_option(category_name, "source_id", source_id)
        self.__source_id = source_id

        self.__update_source_type()

    def __update_source_type(self):
        """
        Update the options based on the selected source type
        """
        sid = self.__source_type.get_value()
        if sid == 0:
            self.__source_text.set_available(True)
            self.__source_id.set_available(False)
        else:
            self.__source_text.set_available(False)
            self.__source_id.set_available(True)

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

class AttachSourceWindow(PluginWindows.ToolManagedWindowBatch):
    def get_title(self):
        return _("Attach Source")

    def initial_frame(self):
        return _("Options")

    def run(self):
        self.skeys = {}
        source_type = self.options.handler.options_dict['source_type'] 
        # 0 - new, 1 - lookup
        if source_type == 0:
            source_text = self.options.handler.options_dict['source_text']
        else:
            source_id = self.options.handler.options_dict['source_id']
            source = self.db.get_source_from_gramps_id(source_id)
            if source is None:
                # FIXME: show an error message
                return

        with DbTxn(_("Attach Source"), self.db, batch=True) as self.trans:
            self.add_results_frame(_("Results"))
            self.results_write(_("Processing...\n"))
            self.db.disable_signals()
            if source_type == 0:
                source = self.create_source(source_text)
    
            self.filter_option =  self.options.menu.get_option_by_name('filter')
            self.filter = self.filter_option.get_filter() # the actual filter
    
            # FIXME: use old style for gramps31 compatible
            #    people = self.filter.apply(self.db,
            #                               self.db.iter_person_handles())
            people = self.filter.apply(self.db,
                                 self.db.get_person_handles(sort_handles=False))
    
            # FIXME: use old style for gramps31 compatible
            # num_people = self.db.get_number_of_people()
            num_people = len(people)
            self.results_write(_("Attaching sources...\n"))
            self.progress.set_pass(_('Attaching sources...'), 
                                   num_people)
            count = 1
            for person_handle in people:
                self.progress.step()
                person = self.db.get_person_from_handle(person_handle)
                
                citation = gramps.gen.lib.Citation()
                citation.set_reference_handle(source.handle)
                self.db.add_citation(citation, self.trans)
                self.db.commit_citation(citation, self.trans)
                person.add_citation(citation.handle)
                self.db.commit_person(person, self.trans)

                self.results_write("  %d) " % count)
                self.results_write_link(name_displayer.display(person),
                                        person, person_handle)
                self.results_write("\n")
                count += 1

        self.db.enable_signals()
        self.db.request_rebuild()
        self.results_write(_("Done!\n"))

    def create_source(self, source_text):
        source = None
        if source_text in self.skeys:
            source = self.db.get_source_from_handle(self.skeys[source_text])
        else:
            source = gramps.gen.lib.Source()
            source.set_title(source_text)
            self.db.add_source(source,self.trans)
            self.db.commit_source(source,self.trans)
            self.skeys[source_text] = source.handle
        self.db.add_source(source, self.trans)
        return source

        self.db.add_event(event, self.trans)
        return event

