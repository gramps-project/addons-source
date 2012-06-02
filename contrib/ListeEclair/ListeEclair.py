#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2008,2011  Gary Burton
# Copyright (C) 2010       Jakim Friant
# Copyright (C) 2011       Heinz Brinker
# Copyright (C) 2012       Eric Doutreleau
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


"""ListeEclair Report"""

#------------------------------------------------------------------------
#
# gramps modules
#
#------------------------------------------------------------------------
from gen.plug.menu import FilterOption, PlaceListOption, EnumeratedListOption, \
                          BooleanOption
from gen.plug.report import Report
from gui.plug.report import MenuReportOptions
from gen.plug.docgen import (IndexMark, FontStyle, ParagraphStyle, TableStyle,
                            TableCellStyle, FONT_SANS_SERIF, FONT_SERIF, 
                            INDEX_TYPE_TOC, PARA_ALIGN_CENTER)
from gen.proxy import PrivateProxyDb, LivingProxyDb
import gen.datehandler
import Sort
from gen.display.name import displayer as _nd
from gui.utils import ProgressMeter
from collections import defaultdict
import logging

from TransUtils import get_addon_translator
_ = get_addon_translator(__file__).ugettext

class ListeEclairReport(Report):
    def __init__(self, database, options_class):

        Report.__init__(self, database, options_class)

        menu = options_class.menu
        places = menu.get_option_by_name('places').get_value()
        self.reporttype  = menu.get_option_by_name('reporttype').get_value()
        self.incpriv = menu.get_option_by_name('incpriv').get_value()
        #self.incliving = menu.get_option_by_name('incliving').get_value()

        if self.incpriv:
            self.database = database
        else:
            self.database = PrivateProxyDb(database)

        #self.database = LivingProxyDb(database, LivingProxyDb.MODE_EXCLUDE_ALL)

        filter_option = menu.get_option_by_name('filter')
        self.filter = filter_option.get_filter()
        self.sort = Sort.Sort(self.database)

        if self.filter.get_name() != '':
            # Use the selected filter to provide a list of place handles
            plist = self.database.iter_place_handles()
            self.place_handles = self.filter.apply(self.database, plist)
        else:
            # Use the place handles selected without a filter
            self.place_handles = self.__get_place_handles(places)

        self.place_handles.sort(key=self.sort.by_place_title_key)

    def write_report(self):
        """
        The routine the actually creates the report. At this point, the document
        is opened and ready for writing.
        """

        # Create progress meter bar
        self.progress = ProgressMeter(_("Liste Eclair"), '')

        # Write the title line. Set in INDEX marker so that this section will be
        # identified as a major category if this is included in a Book report.

        title = _("Liste Eclair")
        mark = IndexMark(title, INDEX_TYPE_TOC, 1)        
        self.doc.start_paragraph("Eclair-ReportTitle")
        self.doc.write_text(title, mark)
        self.doc.end_paragraph()
        self.__write_all_places()

        # Close the progress meter
        self.progress.close()

    def __write_all_places(self):
        """
        This procedure writes out each of the selected places.
        """
        place_nbr = 1
        self.doc.start_paragraph("Eclair-Report")
        self.progress.set_pass(_("Generating report"), len(self.place_handles))
	self.result=[]
        for handle in self.place_handles:
            city = self.__write_place(handle, place_nbr)
            self.__write_referenced_events(handle, city)
            place_nbr += 1
            # increment progress bar
            self.progress.step()
	self.result.sort()
	for msg in self.result:
        	self.doc.write_text("%s\n" % msg)
	self.doc.end_paragraph()

    def __write_place(self, handle, place_nbr):
        """
        This procedure writes out the details of a single place
        """
        place = self.database.get_place_from_handle(handle)
        location = place.get_main_location()

        city = location.get_city()
	return city

    def __write_referenced_events(self, handle , city):
        """
        This procedure writes out each of the events related to the place
        """
        event_handles = [event_handle for (object_type, event_handle) in
                         self.database.find_backlink_handles(handle)]
        event_handles.sort(self.sort.by_date)

	self.debut = defaultdict(lambda: defaultdict(dict))
	self.fin = defaultdict(lambda: defaultdict(dict))
        for evt_handle in event_handles:
            event = self.database.get_event_from_handle(evt_handle)
            if event:
		date = event.get_date_object()
		if date:
			year = int(date.get_year())
		else:
			next()
                person_list = []
                ref_handles = [x for x in
                               self.database.find_backlink_handles(evt_handle)]
                for (ref_type, ref_handle) in ref_handles:
                    if ref_type == 'Person':
                        person_list.append(ref_handle)
                    else:
                        family = self.database.get_family_from_handle(ref_handle)
                        father = family.get_father_handle()
                        if father:
                            person_list.append(father)
                        mother = family.get_mother_handle()
                        if mother:
                            person_list.append(mother)

                people = ""
                person_list = list(set(person_list))
                for p_handle in person_list:
                    person = self.database.get_person_from_handle(p_handle)
                    if person:
                        people = person.get_primary_name().get_surname()
			if not self.debut[city][people]:
				self.debut[city][people] = year
				self.fin[city][people] = year
			if self.debut[city][people] > year:
				self.debut[city][people] = year
			if self.fin[city][people] < year:
				self.fin[city][people] = year
                event_details = [year, people]
	keylist = self.debut.keys()
	keylist.sort()
	for city in keylist:
		for people in sorted(self.debut[city].keys()):
			if self.reporttype == "ListeEclair":
				if self.debut[city][people] == 0:
					msg = city + ":" + people
				else:
					msg = city + ":" + people + ":" + str(self.debut[city][people]) + ":" + str(self.fin[city][people])
			else:
				msg = people + ":" + city 
			if msg:
				self.result.append(str(msg))


    def __get_place_handles(self, places):
        """
        This procedure converts a string of place GIDs to a list of handles
        """
        place_handles = [] 
        for place_gid in places.split():
            place = self.database.get_place_from_gramps_id(place_gid)
            if place is not None:
                #place can be None if option is gid of other fam tree
                place_handles.append(place.get_handle())

        return place_handles
    
#------------------------------------------------------------------------
#
# ListeEclairOptions
#
#------------------------------------------------------------------------
class ListeEclairOptions(MenuReportOptions):

    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, dbase):
        MenuReportOptions.__init__(self, name, dbase)
        
    def add_menu_options(self, menu):
        """
        Add options to the menu for the place report.
        """
        category_name = _("Report Options")

        # Reload filters to pick any new ones
        CustomFilters = None
        from gen.filters import CustomFilters, GenericFilter

        opt = FilterOption(_("Select using filter"), 0)
        opt.set_help(_("Select places using a filter"))
        filter_list = []
        filter_list.append(GenericFilter())
        filter_list.extend(CustomFilters.get_filters('Place'))
        opt.set_filters(filter_list)
        menu.add_option(category_name, "filter", opt)

        places = PlaceListOption(_("Select places individually"))
        places.set_help(_("List of places to report on"))
        menu.add_option(category_name, "places", places)

        reporttype = EnumeratedListOption(_("Type de Liste"), "ListeType")
        reporttype.set_items([
                ("ListeEclair",   _("Tiny Tafel")),
                ("cousingenweb",   _("cousingenweb"))])
        reporttype.set_help(_("Type de liste"))
        menu.add_option(category_name, "reporttype", reporttype)

        incpriv = BooleanOption(_("Include private data"), True)
        incpriv.set_help(_("Whether to include private data"))
        menu.add_option(category_name, "incpriv", incpriv)

        #incliving = BooleanOption(_("Include living persons"), True)
        #incliving.set_help(_("Whether to include living persons"))
        #menu.add_option(category_name, "incliving", incliving)

    def make_default_style(self, default_style):

        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=16, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_header_level(1)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for the liste eclair.'))
        default_style.add_paragraph_style("Eclair-Report", para)

        """
        Define the style used for the place title
        """
        font = FontStyle()
        font.set(face=FONT_SERIF, size=12, italic=0, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set(first_indent=-1.5, lmargin=1.5)
        para.set_top_margin(0.75)
        para.set_bottom_margin(0.25)        
        para.set_description(_('The style used for place title.'))
        default_style.add_paragraph_style("Eclair-ReportTitle", para)
