#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2007  Donald N. Allingham
# Copyright (C) 2007-2008  Brian G. Matherly
# Copyright (C) 2009       Gary Burton
# Copyright (C) 2010       Craig J. Anderson
# Copyright (C) 2010       Jakim Friant
# Copyright (C) 2011       Matt Keenan (matt.keenan@gmail.com)
# Copyright (C) 2011-2014  Tim G L Lyons
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

"""
Reports/Text Reports/Person Everything Report.
"""

#------------------------------------------------------------------------
#
# standard python modules
#
#------------------------------------------------------------------------
from __future__ import print_function
from gramps.gen.const import GRAMPS_LOCALE as glocale
import copy
import string

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
import os
import gramps
from gramps.gen.utils.string import conf_strings, gender
from gramps.gen.utils.file import media_path_full
from gramps.gen.plug.docgen import (IndexMark, FontStyle, ParagraphStyle,
                            FONT_SANS_SERIF, FONT_SERIF, 
                            INDEX_TYPE_TOC, PARA_ALIGN_CENTER,
                            LOCAL_HYPERLINK, LOCAL_TARGET)
from gramps.gen.plug.menu import (PersonOption, EnumeratedListOption)
from gramps.gen.plug.report import utils as ReportUtils
from gramps.gen.plug.report import Report
from gramps.gen.plug.report import MenuReportOptions
from gramps.gen.mime import get_description
from gramps.gen.datehandler import get_date, displayer
from gramps.gen.display.name import displayer as global_name_display
from gramps.gen.sort import Sort
from gramps.gen.utils.db import (get_birth_or_fallback, get_death_or_fallback)
from gramps.gen.utils.lds import TEMPLES

#------------------------------------------------------------------------
#
# PersonEverythingReport
#
#------------------------------------------------------------------------
# This has been derived in part from the Descendent Report, and in part from the
# ideas in the Test Data Generator
class PersonEverythingReport(Report):

    def __init__(self, database, options, user):
        """
        Create the PersonEverythingReport object that produces the report.
        
        The arguments are:

        database        - the GRAMPS database instance
        options         - instance of the Options class for this report
        user            - a gen.user.User() instance

        This report needs the following parameters (class variables)
        that come in the options class.
        
        pid           - The centre person about whom the report is to be
                        produced
        gen           - Maximum number of generations to include.
        name_format   - Preferred format to display names
        dups          - Whether to include duplicate descendant trees
        """

        Report.__init__(self, database, options, user)
        self._user = user

        menu = options.menu
        pid = menu.get_option_by_name('pid').get_value()
        self.center_person = database.get_person_from_gramps_id(pid)
        if (self.center_person == None) :
            raise ReportError(_("Person %s is not in the Database") % pid )
        
        sort = Sort(self.database)
        self.by_birthdate = sort.by_birthdate_key
    

        # Copy the global NameDisplay so that we don't change application
        # defaults
        self._name_display = copy.deepcopy(global_name_display)
        name_format = menu.get_option_by_name("name_format").get_value()
        if name_format != 0:
            self._name_display.set_default_format(name_format)

    def write_report(self):
        self.bibli = Bibliography(self.database, self.doc)
        self.print_citations = False
        
        level = 1
        
        # ------------------------------------------------------------------
        self.doc.start_paragraph("PE-Title")
        name = self._name_display.display(self.center_person)
        title = _("All information about %s") % name
        mark = IndexMark(title, INDEX_TYPE_TOC)
        self.doc.write_text(title, mark)
        self.doc.end_paragraph()
        self.print_person_summary(level, self.center_person)
        self.print_person_details(level, self.center_person)
        # ------------------------------------------------------------------
        self.doc.page_break()
        self.doc.start_paragraph("PE-Title")
        self.doc.write_text(_("Person Events"))
        self.doc.end_paragraph()
        self.print_events(level, self.center_person)
        # ------------------------------------------------------------------
        self.doc.page_break()
        self.doc.start_paragraph("PE-Title")
        self.doc.write_text(_("Families"))
        self.doc.end_paragraph()
        self.print_families(level, self.center_person)
        # ------------------------------------------------------------------
        self.doc.page_break()
        self.doc.start_paragraph("PE-Title")
        self.doc.write_text(_("Endnotes"))
        self.doc.end_paragraph()
        self.bibli.write_endnotes(self.print_header, self.print_object)
        # ------------------------------------------------------------------
        
    def print_person_summary(self, level, person):
        display_num = "%d." % level
        self.doc.start_paragraph("PE-Level%d" % min(level, 32))
        mark = ReportUtils.get_person_mark(self.database, person)
        self.doc.write_text(self._name_display.display(person), mark)
        self.doc.write_text(self.format_person_birth_and_death(person))
        self.doc.end_paragraph()
        return display_num
    
    def print_person_details(self, level, obj):
        self.print_header(level, "Person", obj.get_gramps_id(),
                          _("Gender"), gender[obj.get_gender()],
                          obj.get_privacy(), ref=obj)
        
        self.print_header(level, _("Primary name")+". ",
                          type_desc=_("Type"), 
                          obj_type=str(obj.get_primary_name().get_type()),
                          privacy=obj.get_primary_name().get_privacy(),
                          ref=obj.get_primary_name())
        self.print_object(level+1, obj.get_primary_name())
        for name in obj.get_alternate_names():
            self.print_header(level, _("Alternate name")+". ",
                              type_desc=_("Type"), 
                              obj_type=str(name.get_type()),
                              privacy=name.get_privacy(),
                              ref=name)
            self.print_object(level+1, name)
        
        self.print_object(1, self.center_person)

    def print_events(self, level, obj):
        for event_ref in obj.get_event_ref_list():
            event = self.database.get_event_from_handle(
                                            event_ref.get_reference_handle())
            text = ''
            if event.get_type() == gramps.gen.lib.EventType.BIRTH and \
                self.center_person.get_birth_ref() == event_ref:
                text = " This is the primary birth event."
            if event.get_type() == gramps.gen.lib.EventType.DEATH and \
                self.center_person.get_death_ref() == event_ref:
                text = " This is the primary death event."
            self.print_header(level, _("Event reference") + "." + text, 
                              type_desc=_("Role"),
                              obj_type=str(event_ref.get_role()))
            self.print_object(level+1, event_ref)

    def print_families(self, level, obj):
        for family_handle in obj.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)
            self.print_family_summary(level, family, _("Family"))
            for child_ref in family.get_child_ref_list():
                child_handle = child_ref.get_reference_handle()
                child = self.database.get_person_from_handle(child_handle)
                self.doc.start_paragraph("PE-Level%d" % min(level+1, 32))
                self.doc.start_bold()
                self.doc.write_text(_("Child") + " : ")
                self.doc.end_bold()
                self.doc.write_text("[" + child.get_gramps_id() + "] ")
                self.doc.write_text(self._name_display.display(child))

                self.doc.start_bold()
                self.doc.write_text(" " + _("Relationship to Father") + " : ")
                self.doc.end_bold()
                self.doc.write_text(str(child_ref.get_father_relation()))

                self.doc.start_bold()
                self.doc.write_text(" " + _("Relationship to Mother") + " : ")
                self.doc.end_bold()
                self.doc.write_text(str(child_ref.get_mother_relation()))
                self.bibli.cite_sources(child_ref)
                self.doc.end_paragraph()
            
                self.print_object(level+2, child_ref)
                
            self.print_object(level+1, family)
            self.print_events(level+1, family)
            
        for family_handle in obj.get_parent_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)
            self.print_family_summary(level, family, _("Parent Family"))
            self.doc.start_paragraph("PE-Level%d" % min(level+1, 32))
            self.doc.write_text("Details of any children and events etc. "
                                "would be in a similar report for the "
                                "father or mother.")
            self.doc.end_paragraph()

            self.print_object(level+1, family)
        
    def print_family_summary(self, level, family, family_type):
        self.print_header(level, family_type, family.get_gramps_id(),
                          _("Relationship"), 
                          str(family.get_relationship()),
                          family.get_privacy(),
                          ref=family)
        
        f_h = family.get_father_handle()
        if f_h:
            father = self.database.get_person_from_handle(f_h)
            self.doc.start_paragraph("PE-Level%d" % min(level+1, 32))
            self.doc.start_bold()
            self.doc.write_text(_("Father") + " : ")
            self.doc.end_bold()
            self.doc.write_text("[" + father.get_gramps_id() + "] ")
            self.doc.write_text(self._name_display.display(father))
            self.doc.end_paragraph()
        
        m_h = family.get_mother_handle()
        if m_h:
            mother = self.database.get_person_from_handle(m_h)
            self.doc.start_paragraph("PE-Level%d" % min(level+1, 32))
            self.doc.start_bold()
            self.doc.write_text(_("Mother") + " : ")
            self.doc.end_bold()
            self.doc.write_text("[" + mother.get_gramps_id() + "] ")
            self.doc.write_text(self._name_display.display(mother))
            self.doc.end_paragraph()
            
    def print_header(self, level, text, gid=None, type_desc='', obj_type='',
                     privacy=False, ref=""):
        self.doc.start_paragraph("PE-Level%d" % min(level, 32))
        self.doc.start_bold()
        self.doc.start_underline()
        self.doc.write_text(text)
        self.doc.stop_underline()
        self.doc.end_bold()
        if gid:
            self.doc.write_text(" [" + gid + "]")
        if type_desc:
            self.doc.start_bold()
            self.doc.write_text(" " + type_desc + " : ")
            self.doc.end_bold()
            self.doc.write_text(obj_type)
        if privacy:
            self.doc.write_text(" {" + _("Private") + "}")
        if ref:
            self.bibli.cite_sources(ref)
        self.doc.end_paragraph()
        

    def print_type(self, level, obj_type):
        self.doc.start_paragraph("PE-Level%d" % min(level, 32))
        self.doc.start_bold()
        self.doc.write_text(_("Type") + " : ")
        self.doc.end_bold()
        self.doc.write_text(str(obj_type))
        self.doc.end_paragraph()

    def print_object(self, level, o):

        if issubclass(o.__class__, gramps.gen.lib.address.Address):
            # Details of address are printed by the subclass conditions,
            # primarily by LocationBase, because address is a subclass of
            # LocationBase
            pass

        if issubclass(o.__class__, gramps.gen.lib.addressbase.AddressBase):
            for address in o.get_address_list():
                self.print_header(level, _("Address"), ref=address)
                self.print_object(level+1, address)

        if isinstance(o, gramps.gen.lib.Attribute):
            # The unique information about attributes (the type) is printed by
            # AttributeBase
            pass

        if issubclass(o.__class__, gramps.gen.lib.attrbase.AttributeBase):
            for attribute in o.get_attribute_list():
                self.print_header(level, _("Attribute")+". ",
                                  type_desc=str(attribute.get_type()),
                                  obj_type=attribute.get_value(),
                                  privacy=attribute.get_privacy(),
                                  ref=attribute)
                self.print_object(level+1, attribute)

        if isinstance(o, gramps.gen.lib.ChildRef):
            # The unique information about ChildRef (the father relation and
            # mother relation) is printed by the main write_report function
            pass

        if issubclass(o.__class__, gramps.gen.lib.citationbase.CitationBase):
            if self.print_citations:
                self.print_header(level, "CitationBase tbd")
    
                for citation_handle in o.get_citation_list():
                    citation = self.database.get_citation_from_handle(
                                                            citation_handle)
                    self.print_object(level+1, citation)

        if isinstance(o, gramps.gen.lib.Citation):
            # the unique information about Citation (the page) is printed by the
            # bibliography code. The other unique information, the confidence is
            # printed here
            if o.get_confidence_level() != gramps.gen.lib.Citation.CONF_NORMAL:
                self.doc.start_paragraph("PE-Level%d" % min(level, 32))
                self.doc.start_bold()
                self.doc.write_text(_("Confidence") + " : ")
                self.doc.end_bold()
                self.doc.write_text(conf_strings.get(o.get_confidence_level(),
                                                     _('Unknown')))
                self.doc.end_paragraph()
            
            if self.print_citations:
                source_handle = o.get_reference_handle()
                source = self.database.get_source_from_handle(source_handle)
                self.print_object(level+1, source)

        if issubclass(o.__class__, gramps.gen.lib.datebase.DateBase):
            if o.get_date_object() and not o.get_date_object().is_empty():
                self.doc.start_paragraph("PE-Level%d" % min(level, 32))
                self.doc.start_bold()
                self.doc.write_text(_("Date") + " : ")
                self.doc.end_bold()
                self.doc.write_text(displayer.display(o.get_date_object()))
                self.doc.end_paragraph()

        if isinstance(o, gramps.gen.lib.Event):
            # The event type is printed by the main write_report function
            self.doc.start_paragraph("PE-Level%d" % min(level, 32))
            self.doc.start_bold()
            self.doc.write_text(_("Description") + " : ")
            self.doc.end_bold()
            self.doc.write_text(str(o.get_description()))
            self.doc.end_paragraph()
                
        if issubclass(o.__class__, gramps.gen.lib.eventref.EventRef):
            # The unique information about EventRef (the EventRoleType) is
            # printed by the main write_report function
            event = self.database.get_event_from_handle(o.get_reference_handle())
            self.print_header(level, _("Event"), event.get_gramps_id(),
                              _("Event type"), str(event.get_type()),
                              event.get_privacy(),
                              ref=event)
            self.print_object(level+1, event)

        if isinstance(o, gramps.gen.lib.Family):
            # The unique information about Family (father, mother and children,
            # FamilyRelType and event references) are printed by the main
            # write_report function
            pass
            
        if isinstance(o, gramps.gen.lib.LdsOrd):
            # The Ordinance type is printed by LdsOrdBase
            self.doc.start_paragraph("PE-Level%d" % min(level, 32))
            self.doc.start_bold()
            self.doc.write_text(_("Temple and status") + " : ")
            self.doc.end_bold()
            self.doc.write_text(", ".join((TEMPLES.name(o.get_temple()),
                                           o.status2str()
                                   )))
            self.doc.end_paragraph()
            
            f_h = o.get_family_handle()
            if f_h:
                family = self.database.get_family_from_handle(f_h)
                self.print_family_summary(level+1, family, 
                                          _("LDS Ordinance family"))

        if issubclass(o.__class__, gramps.gen.lib.ldsordbase.LdsOrdBase):
            for ldsord in o.get_lds_ord_list():
                self.print_header(level, _("LDS "), 
                                  type_desc=_("Ordinance"), 
                                  obj_type=ldsord.type2str(),
                                  privacy=ldsord.get_privacy(),
                                  ref=ldsord)
                self.print_object(level+1, ldsord)

        if isinstance(o, gramps.gen.lib.Location):
            # The unique information about location (Parish) is printed by
            # Place. Location otherwise serves as a pointer to a LocationBase
            # object
            pass

        if issubclass(o.__class__, gramps.gen.lib.locationbase.LocationBase):
            self.doc.start_paragraph("PE-Level%d" % min(level, 32))
            self.doc.start_bold()
            self.doc.write_text(_("Street, City, County, State, Postal Code, "
                                  "Country, Phone number") + " : ")
            self.doc.end_bold()
            self.doc.write_text(", ".join((o.get_street(),
                                            o.get_city(),
                                            o.get_county(),
                                            o.get_state(),
                                            o.get_postal_code(),
                                            o.get_country(),
                                            o.get_phone())))
            self.doc.end_paragraph()

        if issubclass(o.__class__, gramps.gen.lib.mediabase.MediaBase):
            for mediaref in o.get_media_list():
                self.print_header(level, _("Media Reference"), ref=mediaref)
                self.print_object(level+1, mediaref)

        if isinstance(o, gramps.gen.lib.MediaObject):
            # thumb is not printed. The mime type is printed by MediaRef
            self.doc.start_paragraph("PE-Level%d" % min(level, 32))
            self.doc.start_bold()
            self.doc.write_text(_("Description and Path") + " : ")
            self.doc.end_bold()
            self.doc.write_text(o.get_description() + ", ")
            path = o.get_path()
            if path:
                mark = IndexMark("file://:" + 
                                 media_path_full(self.database, path), 
                                 LOCAL_HYPERLINK)
                self.doc.write_text(path, mark=mark)
            self.doc.end_paragraph()
            
            mime_type = o.get_mime_type()
            if mime_type and mime_type.startswith("image"):
                filename = media_path_full(self.database, o.get_path())
                if os.path.exists(filename):
                    self.doc.start_paragraph("PE-Level%d" % min(level, 32))
                    self.doc.add_media_object(filename, "single", 4.0, 4.0)
                    self.doc.end_paragraph()
                else:
                    self._user.warn(_("Could not add photo to page"),
                          "%s: %s" % (filename, _('File does not exist')))

        if isinstance(o, gramps.gen.lib.MediaRef):
            mediaobject_handle = o.get_reference_handle()
            mediaobject = self.database.get_object_from_handle(mediaobject_handle)
            
            if o.get_rectangle():
                self.doc.start_paragraph("PE-Level%d" % min(level, 32))
                self.doc.start_bold()
                self.doc.write_text(_("Referenced Region") + " : ")
                self.doc.end_bold()
                self.doc.write_text(", ".join((("%d" % i) for i in o.get_rectangle())))
                self.doc.end_paragraph()
                
                mime_type = mediaobject.get_mime_type()
                if mime_type and mime_type.startswith("image"):
                    filename = media_path_full(self.database,
                                               mediaobject.get_path())
                    if os.path.exists(filename):
                        self.doc.start_paragraph("PE-Level%d" % min(level, 32))
                        self.doc.add_media_object(filename, "single", 4.0, 4.0,
                                                  crop=o.get_rectangle()
                                                  )
                        self.doc.end_paragraph()

            desc = get_description(mediaobject.get_mime_type())
            if not desc:
                desc = _("unknown")
            self.print_header(level, _("Media Object"),
                              mediaobject.get_gramps_id(),
                              _("Mime type"), 
                              desc,
                              mediaobject.get_privacy(),
                              ref=mediaobject)
            self.print_object(level+1, mediaobject)

        if isinstance(o, gramps.gen.lib.Name):
            # group_as, sort_as and display_as are not printed. NameType is
            # printed by the main write_report function
            self.doc.start_paragraph("PE-Level%d" % min(level, 32))
            self.doc.start_bold()
            self.doc.write_text(_("Given name(s): Title, Given, Suffix, "
                                  "Call Name, Nick Name, Family Nick Name") +
                                  " : ")
            self.doc.end_bold()
            self.doc.write_text(", ".join((o.get_title(),
                                           o.get_first_name(),
                                           o.get_suffix(),
                                           o.get_call_name(),
                                           o.get_nick_name(),
                                           o.get_family_nick_name())))
            self.doc.end_paragraph()

        if isinstance(o, gramps.gen.lib.Note):
            # The NoteType is printed by NoteBase. Whether the note is flowed or
            # not is not printed, but affects the way the note appears
            self.doc.write_styled_note(o.get_styledtext(), 
                                       o.get_format(), 
                                       "PE-Level%d" % min(level, 32),
                                       contains_html = o.get_type()
                                        == gramps.gen.lib.notetype.NoteType.HTML_CODE
                                      )

        if issubclass(o.__class__, gramps.gen.lib.notebase.NoteBase):
            for n_h in o.get_note_list():
                note = self.database.get_note_from_handle(n_h)
                self.print_header(level, _("Note"), note.get_gramps_id(),
                                  _("Note type"), str(note.get_type()),
                                  note.get_privacy())
                self.print_object(level+1, note)
        
        if issubclass(o.__class__, gramps.gen.lib.Person):
            # This is printed by the main write-report function
            pass

        if isinstance(o, gramps.gen.lib.Place):
            # The title, name, type, code and lat/long are printed by PlaceBase
            for placeref in o.get_placeref_list():
                self.print_header(level, _("Parent Place"))
                self.print_object(level+1, placeref)
                
#            location = o.get_main_location()
#            if location.get_parish():
#                self.print_header(level, _("Main Location"), 
#                                  type_desc=_("Parish"), 
#                                  obj_type=location.get_parish())
#            else:
#                self.print_header(level, _("Main Location"))
#                
#            self.print_object(level+1, location)
#            
            for location in o.get_alternate_locations():
                if location.get_parish():
                    self.print_header(level, _("Alternate Location"), 
                                      type_desc=_("Parish"), 
                                      obj_type=location.get_parish())
                else:
                    self.print_header(level, _("Alternate Location"))
                self.print_object(level+1, location)

        if issubclass(o.__class__, gramps.gen.lib.placebase.PlaceBase) or \
            issubclass(o.__class__, gramps.gen.lib.placeref.PlaceRef):
            if issubclass(o.__class__, gramps.gen.lib.placebase.PlaceBase):
                place_handle = o.get_place_handle()
            else:
                place_handle = o.get_reference_handle()
            place = self.database.get_place_from_handle(place_handle)
            if place:
                self.print_header(level, _("Place"), place.get_gramps_id(),
                                  _("Place Title"), place.get_title(),
                                  privacy=place.get_privacy(),
                                  ref=place)
                self.doc.start_paragraph("PE-Level%d" % min(level+1, 32))
                self.doc.start_bold()
                self.doc.write_text(_("Name") + " : ")
                self.doc.end_bold()
                self.doc.write_text(place.get_name())
                self.doc.start_bold()
                self.doc.write_text(" " + _("Type") + " : ")
                self.doc.end_bold()
                self.doc.write_text(str(place.get_type()))
                self.doc.start_bold()
                self.doc.write_text(" " + _("Code") + " : ")
                self.doc.end_bold()
                self.doc.write_text(place.get_code())
                self.doc.end_paragraph()

                for name in place.get_alternative_names():
                    self.doc.start_paragraph("PE-Level%d" % min(level+1, 32))
                    self.doc.start_bold()
                    self.doc.write_text(_("Alternative Name") + " : ")
                    self.doc.end_bold()
                    self.doc.write_text(name)
                    self.doc.end_paragraph()

                if place.get_longitude() or place.get_latitude():
                    self.doc.start_paragraph("PE-Level%d" % min(level+1, 32))
                    self.doc.start_bold()
                    self.doc.write_text(_("Latitude, Longitude") + " : ")
                    self.doc.end_bold()
                    self.doc.write_text(", ".join((place.get_longitude(),
                                                   place.get_latitude())))
                    self.doc.end_paragraph()

                self.print_object(level+1, place)

        if issubclass(o.__class__, gramps.gen.lib.primaryobj.BasicPrimaryObject):
            # The Gramps ID is printed by the enclosing object
            pass


        if issubclass(o.__class__, gramps.gen.lib.privacybase.PrivacyBase):
            # The privacy is printed by the enclosing object
            pass
            
        if isinstance(o, gramps.gen.lib.RepoRef):
            # The media type is printed by source
            self.doc.start_paragraph("PE-Level%d" % min(level, 32))
            self.doc.start_bold()
            self.doc.write_text(_("Call number") + " : ")
            self.doc.end_bold()
            self.doc.write_text(o.get_call_number())
            self.doc.end_paragraph()

            repository_handle = o.get_reference_handle()
            repository = self.database.get_repository_from_handle(repository_handle)
            self.print_header(level, _("Repository"), repository.get_gramps_id(),
                              _("Repository type"), str(repository.get_type()),
                              privacy=repository.get_privacy())
            self.print_object(level+1, repository)

        if isinstance(o, gramps.gen.lib.Repository):
            # the repository type is printed by RepoRef
            pass

        if isinstance(o, gramps.gen.lib.Source):
            # The title, author, abbreviation and publication information are
            # printed by the bibliography code
#            data_map = o.get_data_map()
#            for key in data_map.keys():
#                self.doc.start_paragraph("PE-Level%d" % min(level, 32))
#                self.doc.start_bold()
#                self.doc.write_text(_("Data") + ". " + key + " : ")
#                self.doc.end_bold()
#                self.doc.write_text(data_map[key])
#                self.doc.end_paragraph()

            reporef_list = o.get_reporef_list()
            for reporef in reporef_list:
                self.print_header(level, _("Repository reference"),
                                  type_desc=_("Media type"),
                                  obj_type=str(reporef.get_media_type()),
                                  privacy=reporef.get_privacy())
                self.print_object(level+1, reporef)

        if isinstance(o, gramps.gen.lib.Surname):
            if o.get_origintype():
                self.print_header(level, _("Surname"),
                                  type_desc=_("Origin type"),
                                  obj_type=str(o.get_origintype()))
            else:
                self.print_header(level, _("Surname"),
                                  privacy=o.get_privacy())
            self.doc.start_paragraph("PE-Level%d" % min(level+1, 32))
            self.doc.start_bold()
            self.doc.write_text(_("Prefix, surname, connector") + " : ")
            self.doc.end_bold()
            self.doc.write_text(", ".join((o.get_prefix(), o.get_surname(),
                                           o.get_connector())))
            if o.get_primary():
                self.doc.write_text(" " + _("{This is the primary surname}"))
            self.doc.end_paragraph()
            
        if isinstance(o, gramps.gen.lib.surnamebase.SurnameBase):
            surname_list = o.get_surname_list()
            for surname in surname_list:
                self.print_object(level, surname)
                
        if issubclass(o.__class__, gramps.gen.lib.tagbase.TagBase):
            for tag_handle in o.get_tag_list():
                tag = self.database.get_tag_from_handle(tag_handle)
                self.doc.start_paragraph("PE-Level%d" % min(level, 32))
                self.doc.start_bold()
                self.doc.write_text(_("Tag name") + " : ")
                self.doc.end_bold()
                self.doc.write_text(tag.get_name())
                self.doc.end_paragraph()
                self.print_object(level+1, tag)
                
        if issubclass(o.__class__, gramps.gen.lib.Tag):
            # The tag name is printed by TagBase
            if o.get_color() != "#000000000000" or o.get_priority() != 0:
                self.doc.start_paragraph("PE-Level%d" % min(level, 32))
                self.doc.start_bold()
                self.doc.write_text(_("Tag colour and priority") + " : ")
                self.doc.end_bold()
                self.doc.write_text(o.get_color() + ", " + 
                                    "%d" % o.get_priority())
                self.doc.end_paragraph()
                
        if issubclass(o.__class__, gramps.gen.lib.urlbase.UrlBase):
            for url in o.get_url_list():
                self.print_header(level, _("URL"),
                                  type_desc=_("Type"),
                                  obj_type=str(url.get_type()),
                                  privacy=url.get_privacy())
                self.print_object(level+1, url)

        if isinstance(o, gramps.gen.lib.Url):
            self.doc.start_paragraph("PE-Level%d" % min(level, 32))
            self.doc.start_bold()
            self.doc.write_text(_("Description and Path") + " : ")
            self.doc.end_bold()
            self.doc.write_text(o.get_description() + ", ")
            path = o.get_path()
            if path:
                mark = IndexMark(path, LOCAL_HYPERLINK)
                self.doc.write_text(path, mark=mark)
            self.doc.end_paragraph()

        return o

    def __date_place(self, event):
        if event:
            date = get_date(event)
            place_handle = event.get_place_handle()
            if place_handle:
                place = self.database.get_place_from_handle(
                    place_handle).get_title()
                return("%(event_abbrev)s %(date)s - %(place)s" % {
                    'event_abbrev': event.type.get_abbreviation(),
                    'date' : date,
                    'place' : place,
                    })
            else:
                return("%(event_abbrev)s %(date)s" % {
                    'event_abbrev': event.type.get_abbreviation(),
                    'date' : date
                    })
        return ""

    def format_person_birth_and_death(self, person):
        text = self.__date_place(
                    get_birth_or_fallback(self.database, person)
                    )

        tmp = self.__date_place(get_death_or_fallback(self.database, person))
        if text and tmp:
            text += ", "
        text += tmp
        
        if text:
            text = " (" + text + ")"

        return text

class Bibliography:
    """
    This constructs endnotes in the Humanities style of the Chicago manual of
    style.
    
    The style of report is based on:
    http://www.deakin.edu.au/current-students/study-support/study-skills/handouts/oxford-docnote.php

    """
    def __init__(self, database, doc):
        self.citation_list = []
        self.database = database
        self.doc = doc
        self.cindex = 0
        
    def cite_sources(self, obj):
        """
        Cite any sources for the object and add them to the bibliography.
        
        @param bibliography: The bibliography to contain the citations.
        @type bibliography: L{Bibliography}
        @param obj: An object with source references.
        @type obj: L{gramps.gen.lib.CitationBase}
        """
        txt = ""
        slist = obj.get_citation_list()
        if slist:
            self.doc.start_superscript()
            first = 1
            for ref in slist:
                if not first:
                    txt += ', '
                    self.doc.write_text(", ")
                first = 0
                self.citation_list += [ref]
                self.cindex += 1
                text = "%d" % (self.cindex)
                mark = IndexMark("#endnote" + text, LOCAL_HYPERLINK)
                self.doc.write_text(text, mark=mark)
            self.doc.end_superscript()
        return txt
        
    def write_endnotes(self, print_header, print_object):
        """
        Write all the entries in the bibliography as endnotes.
        
        @param bibliography: The bibliography that contains the citations.
        @type bibliography: L{Bibliography}
        @param database: The database that the sources come from.
        @type database: DbBase
        @param doc: The document to write the endnotes into.
        @type doc: L{docgen.TextDoc}
        @param printnotes: Indicate if the notes attached to a source must be
                written too.
        @type printnotes: bool
        @param links: Indicate if URL links should be makde 'clickable'.
        @type links: bool
        """
        if len(self.citation_list) == 0:
            return
    
        already_printed = []
        source_dict = {}
        previous_source_handle = None
        
        cindex = 0
        for citation_handle in self.citation_list:
            cindex += 1
            citation = self.database.get_citation_from_handle(citation_handle)
            source_handle = citation.get_reference_handle()
            source = self.database.get_source_from_handle(source_handle)
            
            source_short_form = _format_source_text(source, short=True)
            
            op_cit = ""
            sub = ""
            sub_count = 0
            level = 2
            # Find whether the short form, possibly with letter suffix, has
            # already been output
            while source_short_form + sub in source_dict.keys():
                if source_dict[source_short_form+sub][0] == source_handle:
                    op_cit = source_handle
                    break
                sub = string.ascii_lowercase[sub_count]
                sub_count += 1
                if sub_count > len(string.ascii_lowercase):
                    break
            
            self.doc.start_paragraph('Endnotes-Source', "%d." % cindex)
            mark = IndexMark("endnote%d" % cindex, LOCAL_TARGET)
            self.doc.write_text("", mark=mark)
            citation_text = _format_citation_text(citation)

            if op_cit:
                # We have already output the details for this source
                if source_handle == previous_source_handle:
                    # ibid. (ibidem, meaning in the same place) relates to
                    # the same work, cited immediately before.
                    self.doc.write_text("ibid.")
                    if source_dict[source_short_form+sub][1] == citation_handle:
                        # (a) ibid can refer to the same page.
                        pass
                    else:
                        # (b) ibid can also refer to a different page.
                        self.doc.write_text(citation_text)
                else:
                    self.doc.write_text(source_short_form + 
                                        (" " if sub != "" else "") + 
                                        sub + ", ")
                    if source_dict[source_short_form+sub][1] == citation_handle:
                        # loc. cit. (loco citato, meaning in the place cited)
                        # refers to the same page of a work cited earlier
                        self.doc.write_text("loc.cit.")
                    else:
                        # op. cit. (opera citato, meaning in the work cited)
                        # refers to a different page of a work cited earlier
                        self.doc.write_text("op.cit.")
                        self.doc.write_text(citation_text)
                self.doc.end_paragraph()
            else:
                self.doc.write_text(_format_source_text(source,
                                                            short=False,
                                                            sub=sub))
                self.doc.write_text(citation_text)
                self.doc.end_paragraph()
                source_dict[source_short_form + sub] = (source_handle,
                                                        citation_handle)
                # We only need to print details of the source if they have not
                # been printed in the endnote
                if _source_has_details(source):
                    print_header(level, _("Source"), source.get_gramps_id(),
                                 privacy=source.get_privacy())
                    print_object(level+1, source)
                
            if citation_handle not in already_printed and \
                    _citation_has_details(citation):
                print_header(level, _("Citation"), citation.get_gramps_id(),
                             privacy=citation.get_privacy())
                print_object(level+1, citation)
                
            previous_source_handle = source_handle
            already_printed += [source_handle, citation_handle]

def _source_has_details(source):
    return source.get_note_list() or source.get_media_list() or \
           source.get_reporef_list() #or source.get_data_map()

def _citation_has_details(citation):
    return citation.get_media_list() or \
           citation.get_confidence_level() != gramps.gen.lib.Citation.CONF_NORMAL or \
           (citation.get_date_object() is not None and
                        not citation.get_date_object().is_empty())

def _format_source_text(source, short=False, sub=""):
    if not source:
        return ""

    src_txt = ""
    
    if source.get_author():
        src_txt += source.get_author()
    if short and src_txt != "":
        return src_txt
    
    if source.get_title():
        if src_txt:
            src_txt += ", "
        src_txt += '"%s"' % source.get_title()
    if short and src_txt != "":
        return src_txt
        
    if source.get_abbreviation():
        # short title used for sorting, filing, and retrieving source records
        src_txt += "(%s)" % source.get_abbreviation()
        
    if source.get_publication_info():
        if src_txt:
            src_txt += ", "
        src_txt += source.get_publication_info()
    if short and src_txt != "":
        return src_txt
        
    if short:
        # and we haven't already exited
        return _("No source information found")
    
    # If we got here then we must have been asked for a long form
    src_txt += " " + sub
    src_txt +=" [" + source.get_gramps_id() + "]" 
    if source.get_privacy():
        src_txt += " {" + _("Private") + "}"
    
    return src_txt

def _format_citation_text(ref):
    if not ref:
        return ""
    
    ref_txt = ", "
    
    if ref.get_page() != "":
        ref_txt += ref.get_page() + " "
        
    ref_txt += "[" + ref.get_gramps_id() + "]"
    
    if ref.get_privacy():
        ref_txt += " {" + _("Private") + "}"
   
    return ref_txt

#------------------------------------------------------------------------
#
# PersonEverthingOptions
#
#------------------------------------------------------------------------
class PersonEverthingOptions(MenuReportOptions):

    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, dbase):
        MenuReportOptions.__init__(self, name, dbase)
        
    def add_menu_options(self, menu):
        category_name = _("Report Options")
        
        pid = PersonOption(_("Center Person"))
        pid.set_help(_("The center person for the report"))
        menu.add_option(category_name, "pid", pid)
        
        # We must figure out the value of the first option before we can
        # create the EnumeratedListOption
        fmt_list = global_name_display.get_name_format()
        name_format = EnumeratedListOption(_("Name format"), 0)
        name_format.add_item(0, _("Default"))
        for num, name, fmt_str, act in fmt_list:
            name_format.add_item(num, name)
        name_format.set_help(_("Select the format to display names"))
        menu.add_option(category_name, "name_format", name_format)

    def make_default_style(self, default_style):
        """Make the default output style for the Person Everything Report."""
        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=12, bold=1)
        para = ParagraphStyle()
        para.set_header_level(1)
        para.set_bottom_border(1)
        para.set_top_margin(ReportUtils.pt2cm(3))
        para.set_bottom_margin(ReportUtils.pt2cm(3))
        para.set_font(font)
        para.set_alignment(PARA_ALIGN_CENTER)
        para.set_description(_("The style used for the title of the page."))
        default_style.add_paragraph_style("PE-Title", para)

        font = FontStyle()
        font.set(face=FONT_SERIF, size=10)
        for i in range(1, 33):
            para = ParagraphStyle()
            para.set_font(font)
            para.set_top_margin(ReportUtils.pt2cm(font.get_size()*0.125))
            para.set_bottom_margin(ReportUtils.pt2cm(font.get_size()*0.125))
            para.set_left_margin(min(10.0, float(i-1.0)))
            para.set_description(_("The style used for the "
                                "level %d display.") % i)
            default_style.add_paragraph_style("PE-Level%d" % min(i, 32), para)
            
        add_endnote_styles(default_style)

def add_endnote_styles(style_sheet):
    """
    Add paragraph styles to a style sheet to be used for displaying endnotes.
    
    @param style_sheet: Style sheet
    @type style_sheet: L{docgen.StyleSheet}
    """

    font = FontStyle()
    font.set(face=FONT_SERIF, size=10)
    para = ParagraphStyle()
    para.set_font(font)
    para.set(first_indent=-0.75, lmargin=1.00)
    para.set_top_margin(ReportUtils.pt2cm(font.get_size()*0.125))
    para.set_bottom_margin(ReportUtils.pt2cm(font.get_size()*0.125))
    para.set_description(_('The basic style used for the endnotes source display.'))
    style_sheet.add_paragraph_style("Endnotes-Source", para)
