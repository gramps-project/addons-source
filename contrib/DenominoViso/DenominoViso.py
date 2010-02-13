#
# DenominoViso - a plugin for GRAMPS, the GTK+/GNOME based genealogy program,
#                that creates an Ancestor Chart Map.
#
# Copyright (C) 2007-2009 Michiel D. Nauta
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

# version 2.0

# The basic idea of this plugin is very simple: create an ancestry map in SVG
# supply each rectangle with an event handler and the data of a person packed
# in a JavaScript object. The head section of the document should contain
# the necessary functions to unpack the JavaScript object and represent
# it as HTML.

# TODO
# use ReportUtils.get_address_str() in Gramps2.4.5
# add keyboard navigation.
# Add method to allow user to see data as GEDCOM/Gramps-xml.
# Add option to prefer baptism above birth
# Apply privacy on people still alive.
# Hourglass-mode
# Add repositories


# CONTENT
# _cnsts
# polar2cart
# hex2int_color
# DenominoViso
#  __init__
#  get_event_attribute_types
#  write_report
#  walk_the_tree_depth_asc
#  walk_the_tree_depth_desc
#  walk_the_tree_asc
#  walk_the_tree_desc
#  sort_family_list
#  sort_child_list
#  fan_segment
#  growthspiral_segment
#  matree_segment
#  pytree_segment
#  get_birth_confidence
#  relationship_line
#  generation2coord
#  add_personal_data
#  mouse_event_handler
#  pack_person_img
#  pack_person_url
#  pack_birth_death_data
#  unpack_birth_death_data
#  pack_event_data
#  sort_event_ref_list
#  get_event_description
#  event_is_birth
#  event_is_death
#  event_is_wanted
#  get_death_estimate
#  unpack_event_data
#  pack_attribute_data
#  unpack_attribute_data
#  pack_address_data
#  unpack_address_data
#  pack_note_data
#  unpack_note_data
#  pack_source_data
#  unpack_source_data
#  get_family_event_refs
#  get_death_ref_or_fallback
#  event_role2names
#  marriage_event2spouse_name
#  marriage_event2parent_names
#  witnesses2JS
#  event_source2JS
#  event_roles2JS
#  event_attributes2JS
#  photo2JS
#  get_copied_photo_name
#  img_attr_check
#  relpathA2B
#  privacy_filter
#  escbacka
#  start_page
#  get_css_style
#  get_javascript_functions
#  end_page
#  get_html_search_options
#  write_old_browser_output
# DenominoVisoOptions
#  __init__
#  set_new_options
#  add_user_options
#  array2table
#  img_toggled
#  dash_toggled
#  on_dash_length_edited
#  on_inter_dash_length_edited
#  on_conf_color_edited
#  parse_user_options
# DenominoVisoDialog
#  __init__
#  setup_style_frame
# etc.
#-------------------------------------------------------------------------
#
# python modules
#
#-------------------------------------------------------------------------
import os
import shutil
import re
from urllib import quote,splittype
from xml.sax.saxutils import quoteattr
from math import sin,cos,exp,sqrt,e,pi

#-------------------------------------------------------------------------
#
# gtk
#
#-------------------------------------------------------------------------
import gobject
import gtk

#-------------------------------------------------------------------------
#
# GRAMPS modules
#
#-------------------------------------------------------------------------
import Sort
from ReportBase import Report, ReportUtils, MenuReportOptions, CATEGORY_WEB
#from ReportBase._CommandLineReport import CommandLineReport
import Errors
from QuestionDialog import ErrorDialog, WarningDialog
from ReportBase._FileEntry import FileEntry
from gen.plug.menu import NumberOption, BooleanOption, TextOption, PersonOption, EnumeratedListOption, ColorOption, DestinationOption, StringOption
from gen.display.name import displayer as name_displayer
from gen.display.date import displayer as _dd
import AutoComp
from gen.lib import EventType, EventRoleType, ChildRefType, AttributeType
from Utils import confidence
from gen.plug.menu import Option as PlugOption
from gen.proxy import PrivateProxyDb
from TransUtils import get_addon_translator

#-------------------------------------------------------------------------
#
# constants
#
#-------------------------------------------------------------------------
_ = get_addon_translator(__file__).ugettext
ext_confidence = confidence.copy()
ext_confidence[len(confidence)] = _('No Source')

class _cnsts:
    ANCESTOR = 0
    DESCENDANT = 1
    REGULAR = 0
    FAN = 1
    GROWTHSPIRAL = 2
    MATREE = 3
    PYTREE = 4
    ONCLICK = 0
    ONMOUSEOVER = 1
    RIGHT2LEFT = 0
    LEFT2RIGHT = 1
    TOP2BOTTOM = 2
    BOTTOM2TOP = 3
    BIRTH_REL_COLUMN = 0
    USE_DASH_COLUMN = 1
    DASH_LENGTH_COLUMN = 2
    INTER_DASH_LENGTH_COLUMN = 3
    CONFIDENCE_COLUMN = 0
    COLOR_COLUMN = 1

    mouse_events = [
        (ONCLICK, "onclick"),
        (ONMOUSEOVER, "onmouseover")
    ]

    chart_mode = [
        (ANCESTOR, _('Ancestor')),
        (DESCENDANT,_('Descendant'))
    ]

    chart_type = [
        (REGULAR, _('Regular')),
        (FAN, _('Fan')),
        (GROWTHSPIRAL, _('Growth Spiral')),
        (MATREE, _('Mandelbrot Tree')),
        (PYTREE, _('Pythagoras Tree'))
    ]

    time_direction = [
        (RIGHT2LEFT, _('right to left')),
        (LEFT2RIGHT, _('left to right')),
        (TOP2BOTTOM, _('top to bottom')),
        (BOTTOM2TOP, _('bottom to top'))
    ]

def polar2cart(r,phi):
    x = r*cos(phi)
    y = r*sin(phi)
    return x,y

def hex2int_color(x):
    """Return the decimal representation of a given hex color string.
    x: #e112ff a color in hex notation"""
    return ",".join([str(int(x[i+1:i+3],16)) for i in [0,2,4]])

def list_of_strings2list_of_lists(data_obj):
    # If the option (DNMdash_child_rel or DNMconf_color) is read from the
    # report_options.xml it is a list of strings, while if it comes from
    # the widget or the default it is a list of lists.
    if type(data_obj[0]) == type([]):
        return data_obj
    else:
        rv = []
        for i in data_obj:
            if i[0] != '[' or i[-1] != ']':
                raise TypeError('invalid list-option value')
            rv.append(eval(i))
        return rv

class DenominoVisoReport(Report):
    def __init__(self, database, options_class):
        Report.__init__(self, database, options_class)
        self.options = {}
        menu = options_class.menu
        self.database = database
        for name in menu.get_all_option_names():
            self.options[name] = menu.get_option_by_name(name).get_value()
        self.options['DNMexl_private'] = not self.options['DNMuse_privacy']
        self.start_person = database.get_person_from_gramps_id(self.options['DNMpid'])
        self.rect_xdist = 100.0
        self.rect_width = self.options['DNMrect_width']*self.rect_xdist
        if self.options['DNMrect_height'] >= self.options['DNMrect_ydist']:
            self.options['DNMrect_height'] = 0.9*self.options['DNMrect_ydist']
        self.rect_height = self.options['DNMrect_height']*self.rect_xdist
        self.rect_ydist = self.options['DNMrect_ydist']*self.rect_xdist
        self.advance = 1.0
        self.target_path = self.options['DNMfilename']
        self.open_subwindow = self.options['DNMtree_width'] > 90
        self.copyright = '\n'.join(self.options['DNMcopyright'])
        # split megawidget options
        # IncAttributeOption into DNMinc_attributes en DNMinc_att_list
        (self.options['DNMinc_attributes'], self.options['DNMinc_att_list']) =\
            self.options['DNMinc_attributes_m'].split(', ',1)
        self.options['DNMinc_attributes'] = self.options['DNMinc_attributes'] == 'True'
        # CopyImgOption into DNMcopy_img and DNMcopy_dir
        (self.options['DNMcopy_img'], self.options['DNMcopy_dir']) = \
            self.options['DNMcopy_img_m'].split(', ',1)
        self.options['DNMcopy_img'] = self.options['DNMcopy_img'] == 'True'
        # ImageIncludeAttrOption into DNMinexclude_img, DNMimg_attr4inex, DNMimg_attr_val4inex
        (self.options['DNMinexclude_img'], self.options['DNMimg_attr4inex'],
            self.options['DNMimg_attr_val4inex']) = self.options['DNMimg_attr_m'].split(', ',2)
        self.options['DNMinexclude_img'] = int(self.options['DNMinexclude_img'])
        # HtmlWrapperOption into DNMold_browser_output and DNMfilename4old_browser
        # MouseHandlerOption
        # LineStyleOption
        # ConfidenceColorOption
        (self.options['DNMold_browser_output'], self.options['DNMfilename4old_browser']) = \
            self.options['DNMold_browser_output_m'].split(', ',1)
        self.options['DNMold_browser_output'] = self.options['DNMold_browser_output'] == 'True'
	
        self.options['DNMdash_child_rel'] = list_of_strings2list_of_lists(\
                self.options['DNMdash_child_rel'])
        self.options['DNMconf_color'] = list_of_strings2list_of_lists(\
                self.options['DNMconf_color'])
        self.event_format = '\n'.join(self.options['DNMevent_format'])
        placeholders = re.findall('<.+?>',self.event_format)
        placeholders = set(placeholders)
        placeholders -= set(['<' + _('type') + '>', \
                             '<' + _('role') + '>', \
                             '<' + _('date') + '>', \
                             '<' + _('place') + '>', \
                             '<' + _('description') + '>', \
                             '<' + _('witnesses') + '>', \
                             '<' + _('source') + '>'])
        placeholders = map(lambda(x): x.strip('<>'),placeholders)
        placeholders = set(placeholders)
        #roles = RelLib.EventRoleType().get_standard_names()
        roles = EventRoleType().get_standard_names()
        roles.extend(self.database.get_event_roles())
        roles = set(roles)
        self.event_format_roles = placeholders & roles
        placeholders -= self.event_format_roles
        # perhaps remove Family,Custom,Unknown from self.event_format_roles?
        attributes = AttributeType().get_standard_names()
        #attributes = RelLib.AttributeType().get_standard_names()
        attributes.extend(self.get_event_attribute_types())
        attributes = set(attributes)
        self.event_format_attributes = placeholders & attributes
        # if the user wants to see the source of events, she will probably
        # also want to see the source of attributes.
        self.options_inc_attr_source = ('<' + _('source') + '>') in \
                self.event_format
        self.options_inc_addr_source = self.options_inc_attr_source
        source_ref_formats = [i for i in enumerate(self.options['DNMevent_format']) \
                if ('<' + _('source') + '>') in i[1]]
        if len(source_ref_formats) > 0:
            # add the character on the line before the <source> line
            # if it is a punctuation mark such a newline, comma, semi-colon.
            self.source_ref_format = '\n' + source_ref_formats[0][1]
            if source_ref_formats[0][0] > 0:
                try:
                    end_char_line_before = self.options['DNMevent_format'][source_ref_formats[0][0]-1][-1]
                    # assume end_char_line_b is printable then this = [:punct:]
                    if (not end_char_line_before.isalnum() and not \
                            end_char_line_before.isspace() and \
                            end_char_line_before != '>'):
                        add_char = end_char_line_before
                    else:
                        add_char = ''
                except IndexError:
                    add_char = '\n'
                self.source_ref_format = add_char + self.source_ref_format
        else:
            self.source_ref_format = ''
        self.source_format = '\n'.join(self.options['DNMsource_format'])
        # if any conf_color deviates from the default, use colors
        self.colorcode_confidence = len([i[_cnsts.COLOR_COLUMN] for i in \
                self.options['DNMconf_color'] if i[_cnsts.COLOR_COLUMN] != \
                self.options['DNMconf_color'][-1][_cnsts.COLOR_COLUMN]]) > 0
        self.person_srcs = []
        self.person_imgs = set([]) # makes images being shown only once.
        self.person_img_srcs = []
        self.copied_imgs = {}
        self.search_subjects = {}
        self.sort = Sort.Sort(self.database)

    def get_event_attribute_types(self):
        """There should be a function GrampsDb/_GrampsDbBase that does this!"""
        rv = set()
        for handle in self.database.get_event_handles():
            event= self.database.get_event_from_handle(handle)
            if event:
                for attr in event.get_attribute_list():
                    if attr.type.is_custom() and str(attr.type):
                        rv.add(str(attr.get_type()))
        return rv

    def write_report(self):
        if self.options['DNMold_browser_output']:
            self.write_old_browser_output()
        try:
            f = open(self.target_path,'w')
        except IOError,msg:
            ErrorDialog(_('Failure writing %s') % self.target_path,msg)
            return
        startup = {}
        startup[_cnsts.FAN] = ((0,-pi,pi), (0,0,2*pi), (0,pi/2,5*pi/2), \
                (0,-pi/2,3*pi/2))
        startup[_cnsts.GROWTHSPIRAL] = ((10,50,-pi/2), (10,50,pi/2), \
                (10,50,pi), (10,50,0))
        startup[_cnsts.MATREE] = ((0,-50,0,50), (0,50,0,-50), (-50,0,50,0), \
                (50,0,-50,0))
        startup[_cnsts.PYTREE] = ((0,50,0,-50), (0,-50,0,50), (50,0,-50,0), \
                (-50,0,50,0))
        self.start_page(f)
        if self.options['DNMchart_type'] == _cnsts.REGULAR:
            if self.options['DNMchart_mode'] == _cnsts.DESCENDANT:
                self.walk_the_tree_depth_desc(f,self.start_person.get_handle(),0)
            else:
                self.walk_the_tree_depth_asc(f,self.start_person.get_handle(),0)
        else:
            if self.options['DNMchart_mode'] == _cnsts.DESCENDANT:
                self.walk_the_tree_desc(f,self.start_person.get_handle(),0,\
                        startup[self.options['DNMchart_type']][self.options['DNMtime_dir']])
            else:
                self.walk_the_tree_asc(f,self.start_person.get_handle(),0,\
                        startup[self.options['DNMchart_type']][self.options['DNMtime_dir']])
        self.end_page(f)
        f.close()

    # I need four tree-walking routines: for ascestor/descendant mode and for
    # depth-first or not. So they are all quite similar but not similar enough
    # to merge them.
    def walk_the_tree_depth_asc(self,f,person_handle,generation):
        """Traverse the ancestor tree depth first and call the necessary
        functions to write the data to file.

        Arguments:
        f               Fileobject for output.
        person_handle   Database handle of the present person.
        generation      Integer indicating the generation of person (x-coord).

        It takes one step in the recursive traversal, returning the new \
        cross-coordinate."""

        if not person_handle:
            return
        if self.options['DNMtime_dir'] >= _cnsts.TOP2BOTTOM:
            advance_incr = self.rect_xdist
        else:
            advance_incr = self.rect_ydist
        cross_coord = self.advance # coord perpendicular to generation-coord.
        person = self.database.get_person_from_handle(person_handle)
        family_handle = person.get_main_parents_family_handle()
        birth_confidence = ""
        if self.colorcode_confidence:
            birth_confidence = self.get_birth_confidence(person)
        if family_handle and \
                generation < (self.options['DNMmax_generations'] - 1):
            family = self.database.get_family_from_handle(family_handle)
            relationList = [(ref.get_mother_relation(),ref.get_father_relation())\
                    for ref in family.get_child_ref_list() if \
                    ('Person',person_handle) in ref.get_referenced_handles()]
            if len(relationList) > 0:
                (mrel,frel) = relationList[0]
            else:
                raise Errors.DatabaseError("Can't find person " + 
                    person.get_gramps_id()+" in family "+family.get_gramps_id())
            father_coord = self.walk_the_tree_depth_asc(f,family.get_father_handle(),\
                    generation+1)
            self.advance += advance_incr
            mother_coord = self.walk_the_tree_depth_asc(f,family.get_mother_handle(),\
                    generation+1)
            if father_coord and mother_coord:
                cross_coord = (father_coord + mother_coord)/2.0
                self.relationship_line(f,generation,cross_coord, \
                        father_coord,frel,birth_confidence)
                self.relationship_line(f,generation,cross_coord, \
                        mother_coord,mrel,birth_confidence)
            elif father_coord:
                cross_coord = father_coord + advance_incr/2.0
                self.relationship_line(f,generation,cross_coord, \
                        father_coord,frel,birth_confidence)
            elif mother_coord:
                cross_coord = mother_coord - advance_incr/2.0
                self.relationship_line(f,generation,cross_coord, \
                        mother_coord,mrel,birth_confidence)
        self.add_personal_data(f,person,generation,(cross_coord,))
        return cross_coord

    # should add birth_confidence
    def walk_the_tree_depth_desc(self,f,person_handle,generation,parent_in_middle=False):
        """Traverse the tree in a depth first manner getting the children of
            person person_handle."""
        if not person_handle:
            return
        cross_coord = self.advance
        cross_coord_child = []
        prel = []
        person = self.database.get_person_from_handle(person_handle)
        family_handle_list = person.get_family_handle_list()
        family_handle_list.sort(self.sort_family_list)
        for family_handle in family_handle_list:
            if family_handle and generation > (-self.options['DNMmax_generations'] + 1):
                family = self.database.get_family_from_handle(family_handle)
                person_is_mother = family.get_mother_handle() == person_handle
                child_ref_list = family.get_child_ref_list()
                if len(child_ref_list) > 0:
                    child_ref_list.sort(self.sort_child_list)
                    for child_ref in child_ref_list:
                        if child_ref:
                            if person_is_mother:
                                prel.append(child_ref.get_mother_relation())
                            else:
                                prel.append(child_ref.get_father_relation())
                            cross_coord_child.append(self.walk_the_tree_depth_desc(f,child_ref.ref,generation-1))
        if len(cross_coord_child) > 0:
            if len(cross_coord_child) > 1 and parent_in_middle:
                cross_coord = (cross_coord_child[0] + cross_coord_child[-1])/2.0
            else:
                cross_coord = cross_coord_child[0]
            for xy,rel in zip(cross_coord_child,prel):
                self.relationship_line(f,generation,cross_coord,xy,rel,0)
        self.add_personal_data(f,person,generation,(cross_coord,))
        if self.options['DNMtime_dir'] < _cnsts.TOP2BOTTOM:
            self.advance += self.rect_ydist
        else:
            self.advance += self.rect_xdist
        return cross_coord

    def walk_the_tree_asc(self,f,person_handle,generation,attachment_segment):
        """Tree walker that draws the node first before going to the parents."""
        if not person_handle:
            return
        person = self.database.get_person_from_handle(person_handle)
        family_handle = person.get_main_parents_family_handle()
        if family_handle and generation < (self.options['DNMmax_generations']-1):
            family = self.database.get_family_from_handle(family_handle)
            nr_attachees = 2
            attach_points = self.add_personal_data(f,person,generation,\
                    attachment_segment,nr_attachees)
            self.walk_the_tree_asc(f,family.get_father_handle(),generation+1,\
                    attach_points[0])
            self.walk_the_tree_asc(f,family.get_mother_handle(),generation+1,\
                    attach_points[1])
        else:
            self.add_personal_data(f,person,generation,attachment_segment)
        return

    def walk_the_tree_desc(self,f,person_handle,generation,attachment_segment):
        """Tree walker that draws the node first before going to the kids."""
        if not person_handle:
            return
        nr_attachees = 0
        child_refs = []
        person = self.database.get_person_from_handle(person_handle)
        family_handles = person.get_family_handle_list()
        family_handles.sort(self.sort_family_list)
        for family_handle in family_handles:
            if family_handle and generation > (-self.options['DNMmax_generations']+1):
                family = self.database.get_family_from_handle(family_handle)
                child_ref_list = family.get_child_ref_list()
                nr_attachees += len(child_ref_list)
                child_ref_list.sort(self.sort_child_list)
                child_refs.extend(child_ref_list)
        if nr_attachees == 0:
            self.add_personal_data(f,person,generation,attachment_segment)
        else:
            attach_points = self.add_personal_data(f,person,generation,\
                    attachment_segment,nr_attachees)
        for i,ref in enumerate(child_refs):
            self.walk_the_tree_desc(f,ref.ref,generation-1,attach_points[i])
        return

    def sort_family_list(self,a_id,b_id):
        """Function called by a sort to order the families according to
            marriage date."""
        if not (a_id and b_id):
            return 0
        a = self.database.get_family_from_handle(a_id)
        b = self.database.get_family_from_handle(b_id)
        if not (a and b):
            return 0
        a_event_ref_list = a.get_event_ref_list()
        b_event_ref_list = b.get_event_ref_list()
        a_marriage = None
        b_marriage = None
        for ref in a_event_ref_list:
            event = self.database.get_event_from_handle(ref.ref)
            if event.get_type() == EventType.MARRIAGE:
                a_marriage = event
                break
        for ref in b_event_ref_list:
            event = self.database.get_event_from_handle(ref.ref)
            if event.get_type() == EventType.MARRIAGE:
                b_marriage = event
                break
        if not (a_marriage and b_marriage):
            return 0
        return cmp(a_marriage.get_date_object(),b_marriage.get_date_object())

    def sort_child_list(self,a_id,b_id):
        """Function called by a sort to order the children according to birth
            date."""
        if not (a_id.ref and b_id.ref):
            return 0
        a = self.database.get_person_from_handle(a_id.ref)
        b = self.database.get_person_from_handle(b_id.ref)
        if not (a and b):
            return 0
        a_birth_ref = a.get_birth_ref()
        b_birth_ref = b.get_birth_ref()
        if not (a_birth_ref and  b_birth_ref):
            return 0
        a_birth = self.database.get_event_from_handle(a_birth_ref.ref)
        b_birth = self.database.get_event_from_handle(b_birth_ref.ref)
        if not (a_birth and b_birth):
            return 0
        return cmp(a_birth.get_date_object(),b_birth.get_date_object())
    
    def fan_segment(self,nr_ret_attach_points,att_rad,att_phi1,att_phi2):
        """Return the svg-pathstring to draw a fan-segment which is to be
            attached to a circle with radius att_rad from angle att_ph1 to
            att_phi2. Also return the attachment parameters for the next
            parent/child segments."""
        delta_r = 100
        rel_att = [] # attachment segments for relatives
        if att_rad == 0:
            path_str = "M-100,0A100,100 0 1,1 -100,1"
            outer_rad = delta_r
        else:
            x1,y1 = polar2cart(att_rad,att_phi1)
            x2,y2 = polar2cart(att_rad,att_phi2)
            outer_rad = att_rad + delta_r
            x3,y3 = polar2cart(outer_rad,att_phi2)
            x4,y4 = polar2cart(outer_rad,att_phi1)
            path_str = "M%d,%dA%d,%d 0 0,1 %d,%dL%d,%dA%d,%d 0 0,0 %d,%dZ" % \
                (x1,y1,att_rad,att_rad,x2,y2,x3,y3,outer_rad,outer_rad,x4,y4)
        if nr_ret_attach_points > 0:
            delta_phi = (att_phi2-att_phi1)/nr_ret_attach_points
            for i in range(0,nr_ret_attach_points):
                rel_att.append((outer_rad,att_phi1+i*delta_phi,\
                        att_phi1+(i+1)*delta_phi))
        return (path_str,rel_att)

    def growthspiral_segment(self,nr_attach_points,att_rad1,att_rad2,att_phi):
        # r = r0*exp(0.69*phi)
        rel_att = []
        angular_step = 1.0
        x1,y1 = polar2cart(att_rad1,att_phi)
        r1 = att_rad1*exp(0.69*angular_step)
        x2,y2 = polar2cart(r1,att_phi+angular_step)
        r2 = att_rad2*exp(0.69*angular_step)
        x3,y3 = polar2cart(r2,att_phi+angular_step)
        x4,y4 = polar2cart(att_rad2,att_phi)
        path_str = "M%d,%dL%d,%dL%d,%dL%d,%dZ" % (x1,y1,x2,y2,x3,y3,x4,y4)
        if nr_attach_points > 0:
            delta_r = (r2-r1)/nr_attach_points
            for i in range(nr_attach_points-1,-1,-1):
                rel_att.append((r1+i*delta_r,r1+(i+1)*delta_r,att_phi+angular_step))
        return (path_str,rel_att)
 
    def matree_segment(self,x1,y1,x2,y2):
        """Mandelbrot tree segment, make a drawing to understand what's below"""
        twig_length = 5 # self.twig_length
        shrink = 1.47 # theoretically this number should be larger
        rel_att = []
        if y1 == y2:
            width = abs(x2-x1)
            height = twig_length*width
            if x1 < x2:                                   # |-|
                x = x1                                    #
                y = y1 - height                           # | |
                rel_att.append((x,y+width/shrink,x,y))    # | |
                rel_att.append((x2,y,x2,y+width/shrink))  # |-|
            else:                                                      # |-|
                x = x2                                                 # | |
                y = y2                                                 # | |
                rel_att.append((x1,y+height-width/shrink,x1,y+height)) #
                rel_att.append((x,y+height,x,y+height-width/shrink))   # |-|
        else:
            height = abs(y2-y1)
            width = twig_length*height
            if y1 < y2:    # ----- -
                x = x1     # |     |
                y = y1     # ----- -
                rel_att.append((x+width-height/shrink,y,x+width,y))
                rel_att.append((x+width,y2,x+width-height/shrink,y2))
            else:                # - -----
                x = x2 - width   # |     |
                y = y2           # - -----
                rel_att.append((x1-width+height/shrink,y1,x1-width,y1))
                rel_att.append((x2-width,y2,x2-width+height/shrink,y2))
        path_str = 'rect x="%d" y="%d" width="%d" height="%d"' % \
                (x,y,width,height)
        return (path_str,rel_att)

    def pytree_segment(self,x1,y1,x2,y2):
        """Pythagoras tree segment"""
        twig_length = 4 # self.twig_length?
        shrink = 0.68 # value between 0.5 and 1
        rel_att = []
        x3 = x2 + twig_length*(y1-y2)
        y3 = y2 + twig_length*(x2-x1)
        x5 = x1 + twig_length*(y1-y2)
        y5 = y1 + twig_length*(x2-x1)
        x4 = (x3+x5)/2 + sqrt(shrink**2-0.25)*(y5-y3)
        y4 = (y3+y5)/2 + sqrt(shrink**2-0.25)*(x3-x5)
        path_str = 'M%d,%dL%d,%dL%d,%dL%d,%dL%d,%dZ' % \
                (x1,y1,x2,y2,x3,y3,x4,y4,x5,y5)
        rel_att.append((x4,y4,x3,y3))
        rel_att.append((x5,y5,x4,y4))
        return (path_str,rel_att)

    def get_birth_confidence(self,person):
        """Return the numerical confidence level of the source of the
            birth-event or an empty string"""
        rv = ""
        birth = ReportUtils.get_birth_or_fallback(self.database,person)
        if birth:
            source_list = birth.get_source_references()
            if len(source_list) > 0:
                rv = source_list[0].get_confidence_level()
        return rv

    def relationship_line(self,f,generation,y_person,y_relative,rel,birth_conf):
        """Write the SVG to create a line connecting a parent and child.

            f           Fileobject for output.
            generation  integer for the generation of the child.
            y_person     y_coordinate of the person.
            y_relative    y_coordinate of the relavive.
            rel         object of type ChildRelType indicating kind of
                        parent-child relationship
            birth_conf  integer indicating confidence in relationship.

            If the rel is one that is drawn with dashes or if the confidence
            is of a color that deviates from the default, the line is assigned
            to specific classes.
            It is not enough to set the color of every birth_conf but one
            needs to actually remove the class assignment because it might
            otherwise leak how the user thinks about certain sources."""

        cls = ""
        if self.options['DNMchart_mode'] == _cnsts.DESCENDANT:
            mode = -1
        else:
            mode = 1
        if birth_conf != "":
            if self.options['DNMconf_color'][birth_conf][_cnsts.COLOR_COLUMN] \
                    != self.options['DNMconf_color'][-1][_cnsts.COLOR_COLUMN]:
                cls += ext_confidence[birth_conf].replace(' ','')
        if rel.xml_str() in [i[_cnsts.BIRTH_REL_COLUMN] for i in \
                self.options['DNMdash_child_rel'] if i[_cnsts.USE_DASH_COLUMN]]:
            cls += ' ' + rel.xml_str().replace(' ','')
        if self.options['DNMtime_dir'] < _cnsts.TOP2BOTTOM:
            x1 = self.generation2coord(generation)
            y1 = y_person
            x2 = self.generation2coord(generation + mode*1)
            y2 = y_relative
            if (self.options['DNMchart_mode'] == _cnsts.ANCESTOR and \
                    self.options['DNMtime_dir'] == _cnsts.RIGHT2LEFT) or \
                    (self.options['DNMchart_mode'] == _cnsts.DESCENDANT and \
                    self.options['DNMtime_dir'] == _cnsts.LEFT2RIGHT) :
                f.write('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" class="%s"/>\n' \
                    % (x1+self.rect_width/2,y1,x2-self.rect_width/2,y2,cls.strip()))
            else:
                f.write('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" class="%s"/>\n' \
                    % (x1-self.rect_width/2,y1,x2+self.rect_width/2,y2,cls.strip()))
        else: # time_dir >= TOP2BOTTOM
            x1 = y_person
            y1 = self.generation2coord(generation)
            x2 = y_relative
            y2 = self.generation2coord(generation + mode*1)
            if (self.options['DNMchart_mode'] == _cnsts.ANCESTOR and \
                    self.options['DNMtime_dir'] == _cnsts.TOP2BOTTOM) or \
                    (self.options['DNMchart_mode'] == _cnsts.DESCENDANT and \
                    self.options['DNMtime_dir'] == _cnsts.BOTTOM2TOP):
                f.write('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" class="%s"/>\n' \
                    % (x1,y1-self.rect_height/2,x2,y2+self.rect_height/2,cls.strip()))
            else:
                f.write('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" class="%s" />\n' \
                    % (x1,y1+self.rect_height/2,x2,y2-self.rect_height/2,cls.strip()))
        return

    def generation2coord(self,generation):
        if self.options['DNMtime_dir'] == _cnsts.RIGHT2LEFT:
            return generation*self.rect_xdist
        elif self.options['DNMtime_dir'] == _cnsts.LEFT2RIGHT:
            return -generation*self.rect_xdist
        elif self.options['DNMtime_dir'] == _cnsts.TOP2BOTTOM:
            return -generation*self.rect_ydist
        elif self.options['DNMtime_dir'] == _cnsts.BOTTOM2TOP:
            return generation*self.rect_ydist
        else:
            ErrorDialog(_('Unknown time direction'),self.options['DNMtime_dir'])
        return

    def add_personal_data(self,f,person,generation,attachment_segment, \
        nr_ret_attachment_points=2):
        """
        Write the data on the specified person to file.

        Arguments:
        f           Fileobject for output.
        person      The person to write the data about.
        generation  Measure of the x-coordinate of the person.
        attachment  List of coordinates to which the svg-shape is to be glued.
        nr_ret_attachment_points Number of attachment points the svg-shape should offer for relatives.

        In practice this means an svg-shape is created with an onmouse
        event handler that has a JavaScript object as argument packed with
        the persons details."""

        child_att = []
        self.person_srcs = []
        self.person_imgs.clear()
        self.person_img_srcs = []
        person_name = self.escbacka(_nd.display(person))
        person_txt = "{person_name:'" + person_name + "'" 
        self.search_subjects['Name'] = 'person_name'
        person_img = self.pack_person_img(person)
        if person_img:
            person_txt += ',' + person_img
        person_url = self.pack_person_url(person)
        if person_url:
            person_txt += ',' + person_url
        event_data = self.pack_event_data(person)
        if event_data:
            person_txt += "," + event_data
        attribute_data = self.pack_attribute_data(person)
        if attribute_data:
            person_txt += "," + attribute_data
        address_data = self.pack_address_data(person)
        if address_data:
            person_txt += "," + address_data
        note_data = self.pack_note_data(person)
        if note_data:
            person_txt += "," + note_data
        source_data = self.pack_source_data(person)
        if source_data:
            person_txt += "," + source_data

        if len(self.person_img_srcs) > 0:
            person_txt += "," + "img_sources:['" + \
                    "','".join(map(self.escbacka,self.person_img_srcs)) + "']"

        person_txt = "activate(this," + person_txt + "})"
        person_name = "setStatusbar('" + person_name + "')"
        person_txt = quoteattr(person_txt)
        person_name = quoteattr(person_name)
        person_gender = ['female','male','unknown'][int(person.get_gender())]

        if self.options['DNMchart_type'] == _cnsts.FAN:
            path_str,child_att = self.fan_segment(nr_ret_attachment_points, \
                    *attachment_segment)
            f.write("""<path d="%s" class="%s" %s/>\n""" % (path_str, \
                    person_gender, self.mouse_event_handler(person_txt, \
                    person_name)))
        elif self.options['DNMchart_type'] == _cnsts.GROWTHSPIRAL:
            path_str,child_att = self.growthspiral_segment(\
                    nr_ret_attachment_points,*attachment_segment)
            f.write("""<path d="%s" class="%s" %s/>\n""" % (path_str, \
                    person_gender, self.mouse_event_handler(person_txt, \
                    person_name)))
        elif self.options['DNMchart_type'] == _cnsts.MATREE:
            path_str,child_att = self.matree_segment(*attachment_segment)
            f.write("""<%s class="%s" %s/>\n""" % (path_str, person_gender, \
                    self.mouse_event_handler(person_txt, person_name)))
        elif self.options['DNMchart_type'] == _cnsts.PYTREE:
            path_str,child_att = self.pytree_segment(*attachment_segment)
            f.write("""<path d="%s" class="%s" %s/>\n""" % (path_str, \
                    person_gender, self.mouse_event_handler(person_txt, \
                    person_name)))
        else:
            if self.options['DNMtime_dir'] < _cnsts.TOP2BOTTOM:
                f.write("""<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f"
                        class="%s" %s/>\n""" % \
                    (self.generation2coord(generation)-self.rect_width/2.0, attachment_segment[0]-self.rect_height/2.0,\
                        self.rect_width, self.rect_height, person_gender, \
                        self.mouse_event_handler(person_txt,person_name)))
            else:
                f.write("""<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f"
                        class="%s" %s/>\n""" % \
                    (attachment_segment[0]-self.rect_width/2.0,self.generation2coord(generation)-self.rect_height/2.0,self.rect_width, self.rect_height, person_gender, self.mouse_event_handler(person_txt,person_name)))
        return child_att

    def mouse_event_handler(self,person_txt,person_name):
        if self.options['DNMclick_over'] == _cnsts.ONCLICK:
            return "onclick=%s onmouseover=%s" % (person_txt,person_name)
        else:
            return "onmouseover=%s" % person_txt

    def pack_person_img(self,person):
        """Return a string that will be part of the JavaScript object
            describing the main/portret photo of a person, e.g.:
            person_img:{img_path:'...'}"""
        rv = ""
        if self.options['DNMinc_img']:
            plist = filter(self.privacy_filter,person.get_media_list())
            if (len(plist) > 0):
                media_object = self.database.get_object_from_handle(\
                        plist[0].get_reference_handle())
                pJS = self.photo2JS(media_object)
                if pJS:
                    rv += "person_img:" + pJS 
        return rv

    def pack_person_url(self,person):
        """Return a string that will be part of the JavaScript object
            describing the main URL of a person, e.g.:
            url:{url_path:'...',url_desc:'...'}"""
        # Is there any need to support more than 1 uri?
        rv = ""
        if self.options['DNMinc_url']:
            ulist = filter(self.privacy_filter,person.get_url_list())
            if len(ulist) > 0:
                (type,path) = splittype(ulist[0].get_path())
                if not path: return rv
                if type:
                    rv += "url:{url_path:'" + type + ":" + quote(path) + "'"
                else:
                    rv += "url:{url_path:'http://" + quote(path) + "'"
                if self.options['DNMinc_url_desc']:
                    rv += ",url_desc:'" + \
                            self.escbacka(ulist[0].get_description()) + "'"
                    self.search_subjects['URL description'] = "url_desc"
        if rv:
            rv += "}"
        return rv

	# pack_birth_death_data was moved into pack_event_data, this is just a
	# modification of what pack_event_data returns.
    def pack_birth_death_data(self,type,event_str):
        """Return a string that will be part of the JavaScript object
            describing a birth or death event, e.g.:
            birth:{event_type:'...',birth_date:'...',birth_place:'...',
            event_witnesses:['...',...],event_img:{...}}
            Date and place are treated specially to allow searching on them.
            event_str also can contain description, the unpack routine does
            nothing with this; event_role should not occur because it is Primary"""
        # I set here the search_subjects. I should actually remove
        # search_subjects event_date and event_place if there are no such
        # events, but I leave it in, gets too complicated.
        rv = ''
        if event_str:
            tmp = event_str.replace(',event_date', ','+type+'_date')
            if tmp != event_str:
                self.search_subjects[type.capitalize() + ' Date'] = type+'_date'
            rv = tmp.replace(',event_place', ','+type+'_place')
            if rv != tmp:
                self.search_subjects[type.capitalize()+' Place'] = type+'_place'
            rv = type + ':{' + rv[1:] + '}'
        return rv

    def unpack_birth_death_data(self,bir_dea):
        """Return a string that is a JavaScript function suitable to unpack
            the birth or death data packed into the person-JS-object."""
        JSfunction = """
function %(bd)s2html(person,containerDL) {
    if (person.%(bd)s != undefined) {
        var eventDT = document.createElement('dt');
        eventDT.appendChild(document.createTextNode(person.%(bd)s.event_type + ":"));
        containerDL.appendChild(eventDT);
        var eventDD = document.createElement('dd');
        if (person.%(bd)s.event_imgs != undefined) {
            var imgDIV = document.createElement('div');
            imgDIV.setAttribute('class','imgTable');
            var imgTABLE = document.createElement('table');
            var imgTR = document.createElement('tr');
            for (var j=0; j<person.%(bd)s.event_imgs.length; j++) {
                 var imgTD = document.createElement('td');
                 imgTD.appendChild(photo2html(person.%(bd)s.event_imgs[j]));
                 imgTR.appendChild(imgTD);
            }
            imgTABLE.appendChild(imgTR);
            imgDIV.appendChild(imgTABLE);
            eventDD.appendChild(imgDIV);
        }
        var event_str = "%(event_format)s"
        event_str = replaceSubstring(event_str,"<%(date)s>",
                    person.%(bd)s.%(bd)s_date);
        event_str = replaceSubstring(event_str,"<%(place)s>",
                    person.%(bd)s.%(bd)s_place);
        event_str = replaceSubstring(event_str,"<%(role)s>","");
        event_str = replaceSubstring(event_str,"<%(type)s>","");
        event_str = replaceSubstring(event_str,"<%(description)s>","");
        event_str = replaceSubstring(event_str,"<%(witnesses)s>",
            witness_array2string_array(person.%(bd)s.event_witnesses));
        if ('event_source' in person.%(bd)s) {
            event_str = replaceSubstring(event_str,"<%(source)s>",
                    person.%(bd)s.event_source.source_page);
            if ('source_conf' in person.%(bd)s.event_source) {
                var src_cls = '<%(source)s ' + person.%(bd)s.event_source.source_conf + ">";
                event_str = event_str.replace('<%(source)s>',src_cls);
            }
        } else {
            event_str = replaceSubstring(event_str,"<%(source)s>","");
        }
        """ % {'bd':bir_dea, \
            'event_format':self.event_format.replace('\n','\\n').replace('"','\\"'),
            'date':_('date'), 'place':_('place'), 'role':_('role'), \
            'type':_('type'), 'description':_('description'), \
            'witnesses':_('witnesses'), 'source':_('source')}
        for i in self.event_format_roles:
            JSfunction += 'event_str = replaceSubstring(event_str,"<%s>",person.%s.event_%s);' % (i,bir_dea,i.replace(' ','_'))
        for i in self.event_format_attributes:
            JSfunction += 'event_str = replaceSubstring(event_str,"<%s>",person.%s.event_%s);' % (i,bir_dea,i.replace(' ','_'))
        JSfunction += """
        event_str2html(event_str,eventDD);
        containerDL.appendChild(eventDD);
    }
    return;
}
    """
        return JSfunction

    def pack_event_data(self,person):
        """Return a string that will be part of the JavaScript object
            describing all events of a person, e.g.:
            events:[{event_type:'...',event_date:'...',event_place:'...',
            event_desc:'...',event_witnesses:[...],event_img:{...}},...]
            Also returns the string needed for birth/death events by calling
            pack_birth_death_data."""
        # Events are related to person being alive. Some events indicate the
        # person is still alive (e.g. witness), others should be suppressed
        # when the person is dead (e.g. death-spouse).
        rv = ""
        if not self.options['DNMall_events']:
            event_ref_list = person.get_primary_event_ref_list()
        else:
            event_ref_list = person.get_event_ref_list()[0:]
        birth_str = death_str = ''
        birth_ref = person.get_birth_ref()
        death_ref = person.get_death_ref()
        family_event_refs = self.get_family_event_refs(person)
        event_ref_list.extend(family_event_refs.keys())
        event_ref_list.sort(self.sort_event_ref_list)
        try:
            death_estimate = self.database.get_event_from_handle(death_ref.ref).get_date_object()
        except:
            death_estimate = self.get_death_estimate(event_ref_list,family_event_refs)
        for event_ref in event_ref_list:
            event_str = ''
            event = self.database.get_event_from_handle(event_ref.ref)
            if self.options['DNMexl_private'] and \
                (event_ref.get_privacy() or event.get_privacy()):
                continue
            relative = event_ref in family_event_refs.keys()
            if relative and family_event_refs[event_ref]:
                type = family_event_refs[event_ref]
            else:
                type = event.get_type()
            role = event_ref.get_role()
            date = event.get_date_object()
            if not self.event_is_wanted(type,role,relative,birth_ref,death_ref,\
                    date,death_estimate):
                continue

            event_str += ",event_type:'" + self.escbacka(_(str(type))) + "'"
            self.search_subjects['Event Type'] = 'event_type'
            if ('<' + _('role') + '>') in self.event_format and \
                    role != EventRoleType.PRIMARY \
                and role != EventRoleType.FAMILY:
                event_str += ",event_role:'" + self.escbacka(_(str(role))) + "'"
                # add self.search_subject?           
            if ('<' + _('date') + '>') in self.event_format:
                if date:
                    event_str += ",event_date:'" + self.escbacka(_dd.display(date))+"'"
                    if self.options['DNMinc_events']:
                        self.search_subjects['Event Date'] = 'event_date'

            if ('<' + _('place') + '>') in self.event_format:
                place_handle = event.get_place_handle()
                if place_handle:
                    place_name = self.database.get_place_from_handle(\
                            place_handle).get_title()
                    event_str += ",event_place:'" +self.escbacka(place_name)+"'"
                    if self.options['DNMinc_events']:
                        self.search_subjects['Event Place'] = 'event_place'

            if ('<' + _('description') + '>') in self.event_format:
                desc = self.get_event_description(type,role,relative,event_ref,event,family_event_refs,person)
                if desc:
                    event_str += ",event_desc:'" + self.escbacka(desc) + "'"
                    if self.options['DNMinc_events']:
                        self.search_subjects['Event Description'] = 'event_desc'

            if ('<' + _('witnesses') + '>') in self.event_format:
                wJS = self.witnesses2JS(event)
                if wJS:
                    event_str += ",event_witnesses:" + wJS

            if ('<' + _('source') + '>') in self.event_format:
                sJS = self.event_source2JS(event)
                if sJS:
                    event_str += ",event_source:" + sJS

#            if self.options['DNMinc_img']:
#                plist = event.get_media_list()
#                if len(plist) > 0:
#                    media_object = self.database.get_object_from_handle(\
#                            plist[0].get_reference_handle())
#                    pJS = self.photo2JS(media_object)
#                    if pJS:
#                        event_str += ",event" + pJS
            if self.options['DNMinc_img']:
                plist = event.get_media_list()
                psJS = ''
                # use maximum nr of images
                for photo in plist:
                    media_object = self.database.get_object_from_handle(\
                            photo.get_reference_handle())
                    pJS = self.photo2JS(media_object)
                    if pJS:
                        psJS += pJS + ','
                if psJS:
                    event_str += ",event_imgs:[" + psJS[0:-1] + ']'

            # add those persons with a role in the event_format:
            erJS = self.event_roles2JS(event)
            if erJS:
                event_str += erJS

            # add those event attributes that occur in the event_format:
            eaJS = self.event_attributes2JS(event)
            if eaJS:
                event_str += eaJS

            if self.event_is_birth(type,role,relative,birth_ref):
                birth_str = self.pack_birth_death_data('birth',event_str)
                continue
            if self.event_is_death(type,role,relative,death_ref):
                death_str = self.pack_birth_death_data('death',event_str)
                continue
            if event_str:
                rv += '{' + event_str[1:] + '},'
            # end of loop over event_references

        if rv:
            rv = 'events:[' + rv[0:-1] + ']'
        if death_str:
            rv = death_str + ',' + rv
        if birth_str:
            rv = birth_str + ',' + rv
        rv = rv.rstrip(',')
        return rv

    def sort_event_ref_list(self,a_id,b_id):
        if not (a_id and b_id):
            return 0
        a = self.database.get_event_from_handle(a_id.ref)
        b = self.database.get_event_from_handle(b_id.ref)
        if not (a and b):
            return 0
        return cmp(a.get_date_object(),b.get_date_object())

    def get_event_description(self,type,role,relative,event_ref,event,family_event_refs,person):
        desc = ''
        if relative and family_event_refs[event_ref] and \
                role == EventRoleType.PRIMARY:
            desc = ", ".join(self.event_role2names(event,EventRoleType.PRIMARY))
        elif type in [EventType.BAPTISM,EventType.CHRISTEN] and \
                role == EventRoleType.WITNESS:
            desc = ", ".join(self.event_role2names(event,EventRoleType.PRIMARY))
        elif type in [EventType.MARRIAGE,EventType.MARR_BANNS] and \
                role == EventRoleType.FAMILY:
            desc = self.marriage_event2spouse_name(event_ref,person)
        elif type in [EventType.MARRIAGE,EventType.MARR_BANNS] and \
                role == EventRoleType.WITNESS:
            joiner = ' ' + _('and') + ' '
            desc = joiner.join(self.marriage_event2parent_names(event_ref))
        else:
            desc = event.get_description()
        return desc

    def event_is_birth(self,type,role,relative,birth_ref):
        if relative or role != EventRoleType.PRIMARY:
            return False
        if birth_ref:
            if type == EventType.BIRTH:
                return True
            else:
                return False
        else:
            if type in [EventType.BAPTISM,EventType.CHRISTEN]:
                return True
            else:
                return False

    def event_is_death(self,type,role,relative,death_ref):
        if relative or role != EventRoleType.PRIMARY:
            return False
        if death_ref:
            if type == EventType.DEATH:
                return True
            else:
                return False
        else:
            if type in [EventType.BURIAL,EventType.CREMATION]:
                return True
            else:
                return False

    def event_is_wanted(self,type,role,relative,birth_ref,death_ref, \
            date,death_estimate):
        type_str = str(type)
        if relative and date and death_estimate and date > death_estimate and \
            (('Death' in type_str) or ('Burial' in type_str) or ('Cremation' in type_str)):
            return False
        if self.options['DNMinc_events']:
            return True
        return self.event_is_birth(type,role,relative,birth_ref) or \
                self.event_is_death(type,role,relative,death_ref)

    def get_death_estimate(self,event_ref_list,family_event_refs):
        r_event_ref_list = event_ref_list[0:]
        r_event_ref_list.reverse()
        for event_ref in r_event_ref_list:
            event = self.database.get_event_from_handle(event_ref.ref)
            type = event.get_type()
            role = event_ref.get_role()
            relative = event_ref in family_event_refs.keys()
            if relative:
                type = family_event_refs[event_ref]
                if type and (('Birth' in type) or ('Baptism' in type) or \
                    ('Christening' in type)):
                    return event.get_date_object()
            else:
                if (type in [EventType.BURIAL,EventType.CREMATION] and \
                        role == EventRoleType.PRIMARY) or \
                    role == EventRoleType.WITNESS or \
                    type in [EventType.MARRIAGE,EventType.MARR_BANNS]: 
                    return event.get_date_object()
        return None
                    

    def unpack_event_data(self):
        """Return a string that is a JavaScript function suitable to unpack
            the event data packed into the person-JS-object."""
        JSfunction = """
        function events2html(person,containerDIV) {
            if (person.events != undefined) {
                var eventsUL = document.createElement('ul');
                for (i=0; i< person.events.length; i++) {
                    var eventLI = document.createElement('li');
                    if (person.events[i].event_imgs != undefined) {
                        var imgDIV = document.createElement('div');
                        imgDIV.setAttribute('class','imgTable');
                        var imgTABLE = document.createElement('table');
                        var imgTR = document.createElement('tr');
                        for (var j=0; j<person.events[i].event_imgs.length; j++) {
                            var imgTD = document.createElement('td');
                            imgTD.appendChild(photo2html(person.events[i].event_imgs[j]));
                            imgTR.appendChild(imgTD);
                        }
                        imgTABLE.appendChild(imgTR);
                        imgDIV.appendChild(imgTABLE);
                        eventLI.appendChild(imgDIV);
                    }
                    var event_str = "%(event_format)s"
                    event_str = replaceSubstring(event_str,"<%(date)s>",
                                person.events[i].event_date);
                    event_str = replaceSubstring(event_str,"<%(role)s>",
                                person.events[i].event_role);
                    event_str = replaceSubstring(event_str,"<%(type)s>",
                                person.events[i].event_type)
                    event_str = replaceSubstring(event_str,"<%(description)s>",
                                person.events[i].event_desc);
                    event_str = replaceSubstring(event_str,"<%(place)s>",
                                person.events[i].event_place);
                    event_str = replaceSubstring(event_str,"<%(witnesses)s>",
                                witness_array2string_array(person.events[i].event_witnesses));
                    if ('event_source' in person.events[i]) {
                        event_str = replaceSubstring(event_str,"<%(source)s>",
                                person.events[i].event_source.source_page);
                        if ('source_conf' in person.events[i].event_source) {
                            var src_cls = '<%(source)s ' + person.events[i].event_source.source_conf + '>';
                            event_str = event_str.replace('<%(source)s>',src_cls);
                        }
                    } else {
                        event_str = replaceSubstring(event_str,"<%(source)s>","");
                    }
        """ % {'event_format':self.event_format.replace('\n','\\n').replace('"','\\"'),
            'date':_('date'), 'role':_('role'), 'type':_('type'), \
            'description':_('description'), 'place':_('place'), \
            'witnesses':_('witnesses'), 'source':_('source')}
        for i in self.event_format_roles:
            JSfunction += """
                    event_str = replaceSubstring(event_str,"<%s>",
                                person.events[i].event_%s);""" % (i,i.replace(' ','_'))
        for i in self.event_format_attributes:
            JSfunction += """
                    event_str = replaceSubstring(event_str,"<%s>",
                                person.events[i].event_%s);""" % (i,i.replace(' ','_'))
        JSfunction += """
                    event_str2html(event_str,eventLI)
                    eventsUL.appendChild(eventLI);
                }
                var subtitle = document.createElement('h3');
                subtitle.appendChild(document.createTextNode('%s:'));
                containerDIV.appendChild(subtitle);
                containerDIV.appendChild(eventsUL);
            }
            return;
        }
        """ % self.escbacka(_('Events'))
        return JSfunction

    def pack_attribute_data(self,person):
        """Return a string that will be part of the JavaScript object
        describing all attributes of a person, e.g.:
        attributes:[{attr_type:'...',attr_val:'...'},...]"""
        rv = ""
        inc_atts = []
        if not self.options['DNMinc_attributes']: return rv
        if self.options['DNMinc_att_list'] != '':
            inc_atts = [i.strip() for i in self.options['DNMinc_att_list'].split(',')]
        attributes = person.get_attribute_list()
        attributes.sort(lambda a,b: cmp(a.get_type(),b.get_type()))
        for attribute in attributes:
            if self.options['DNMexl_private'] and attribute.get_privacy():
                continue
            attr_type = attribute.get_type()
            attr_val  = attribute.get_value()
            if not attr_type or (inc_atts and attr_type not in inc_atts):
                continue
            rv += "{attr_type:'" + self.escbacka(str(attr_type)) + "'"
            self.search_subjects['Attribute Type'] = 'attr_type'
            if attr_val:
                rv += ",attr_val:'" + self.escbacka(attr_val) + "'"
                self.search_subjects['Attribute Value'] = 'attr_val'
            if self.options_inc_attr_source:
                sJS = self.event_source2JS(attribute)
                if sJS:
                    rv += ",attr_source:" + sJS
            rv += "},"
        if rv:
            rv = "attributes:[" + rv[:-1] + "]"
        return rv

    def unpack_attribute_data(self):
        """Return a string that is a JavaScript function suitable to unpack
            the attribute data packed into the person_JS-object."""
        JSfunction = """
        function attributes2html(person,containerDIV) {
            if (person.attributes != undefined) {
                var attributesDL = document.createElement('dl');
                for (i=0; i< person.attributes.length; i++) {
                    var attributeDT = document.createElement('dt');
                    if (person.attributes[i].attr_type != undefined) {
                        attributeDT.appendChild(document.createTextNode(person.attributes[i].attr_type));
                    }
                    attributesDL.appendChild(attributeDT);
                    var attributeDD = document.createElement('dd');
                    var attr_str = "%(source_format)s";
                    if (person.attributes[i].attr_val != undefined) {
                        var attr_str = person.attributes[i].attr_val + attr_str;
                    }
                    if ('attr_source' in person.attributes[i]) {
                        attr_str = replaceSubstring(attr_str,"<%(source)s>",
                            person.attributes[i].attr_source.source_page);
                        if ('source_conf' in person.attributes[i].attr_source) {
                            var src_cls = '<%(source)s ' + person.attributes[i].attr_source.source_conf + '>';
                            attr_str = attr_str.replace('<%(source)s>',src_cls);
                        }
                    } else {
                        attr_str = replaceSubstring(attr_str,"<%(source)s>","");
                    }
                    event_str2html(attr_str,attributeDD);
                    attributesDL.appendChild(attributeDD);
                }
                var subtitle = document.createElement('h3');
                subtitle.appendChild(document.createTextNode('%(sectitle)s:'));
                containerDIV.appendChild(subtitle);
                containerDIV.appendChild(attributesDL);
            }
            return;
        }
        """
        return JSfunction % {'source_format':self.source_ref_format.replace('\n','\\n').replace('"','\\"'),\
            'sectitle':_("Attributes"), \
            'source':_('source')}

    def pack_address_data(self,person):
        """Return a string that will be part of the JavaScript object
            describing all addresses of a person, e.g.:
            addresses:[{address_date:'...',address_str:'...'},...]"""
        rv = ""
        if not self.options['DNMinc_addresses']: return rv
        addresses = person.get_address_list()
        addresses.sort(lambda a,b: cmp(a.get_date_object(),b.get_date_object()))
        for address in addresses:
            if self.options['DNMexl_private'] and address.get_privacy():
                continue
            address_data = address.get_text_data_list()
            address_data.insert(0,address.get_street())
            address_date = address.get_date_object()
            address_str = self.options['DNMaddress_separator'].join(\
                    filter(lambda(x): x!='',address_data))
            if not address_str: continue
            rv += "{"
            if address_date:
                rv += "address_date:'" + self.escbacka(_dd.display(address_date)) + "',"
                self.search_subjects['Address Date'] = 'address_date'
            rv += "address_str:'" + self.escbacka(address_str) + "'"
            self.search_subjects['Address'] = 'address_str'
            if self.options_inc_addr_source:
                sJS = self.event_source2JS(address)
                if sJS:
                    rv += ",addr_source:" + sJS
            rv += "},"
        if rv:
            rv = "addresses:[" + rv[:-1] + "]"
        return rv 

    def unpack_address_data(self):
        """Return a string that is a JavaScript function suitable to unpack
            the address data packed into the person-JS-object."""
        JSfunction = """
        function addresses2html(person,containerDIV) {
            if (person.addresses != undefined) {
                var addressesDL = document.createElement('dl');
                for (i=0; i< person.addresses.length; i++) {
                    var addressDT = document.createElement('dt');
                    if (person.addresses[i].address_date != undefined) {
                        addressDT.appendChild(document.createTextNode(person.addresses[i].address_date))
                    }
                    addressesDL.appendChild(addressDT);
                    var addressDD = document.createElement('dd');
                    var addr_str = "%(source_format)s";
                    if (person.addresses[i].address_str != undefined) {
                        addr_str = person.addresses[i].address_str + addr_str
                    }
                    if ('addr_source' in person.addresses[i]) {
                        addr_str = replaceSubstring(addr_str,"<%(source)s>",
                            person.addresses[i].addr_source.source_page);
                        if ('source_conf' in person.addresses[i].addr_source) {
                            var src_cls = '<%(source)s ' + person.addresses[i].addr_source.source_conf + '>';
                            addr_str = addr_str.replace('<%(source)s>',src_cls);
                        }
                    } else {
                        addr_str = replaceSubstring(addr_str,"<%(source)s>","");
                    }
                    event_str2html(addr_str,addressDD);
                    addressesDL.appendChild(addressDD);
                }
                var subtitle = document.createElement('h3');
                subtitle.appendChild(document.createTextNode('%(sectitle)s:'));
                containerDIV.appendChild(subtitle);
                containerDIV.appendChild(addressesDL);
            }
            return;
        }
        """
        return JSfunction % {'source_format':self.source_ref_format.replace('\n','\\n').replace('"','\\"'),\
            'sectitle':self.escbacka(_('Addresses')), \
            'source':_('source')}

    def pack_note_data(self,person):
        """Return a string that will be part of the JavaScript object
            describing the note, e.g.:
            notes:{note_text:'...',note_format:true}"""
        rv = ""
        note = None
        if not self.options['DNMinc_notes']: return rv
        # use person.get_note_list() QUICK FIX
        note_handles = person.get_note_list()
        if len(note_handles) > 0:
            note = self.database.get_note_from_handle(note_handles[0])
            note_format = note.get_format()
            note = self.escbacka(note.get())
        #note = self.escbacka(person.get_note())
        #note_format = person.get_note_format()
        if note:
            #if note_format:
                # without this the xhtml file contains a newline while I need \n
            # python 2.5 had a change in xml/sax/saxutils so that \n is escaped
            # to &#10;. Firefox can't cope with this, so apply \n->\\n now also
            # for unformatted notes, ugly.
            note = note.replace("\n","\\n")
            rv += "notes:{note_text:'" + note + "',note_format:"\
                    + str(note_format).lower() + "}"
            self.search_subjects['Note'] = 'note_text'
        return rv

    def unpack_note_data(self):
        """Return a string that is a JavaScript function suitable to unpack
            the note data packed into the person-JS-object."""
        JSfunction = """
        function notes2html(person,containerDIV) {
            if (person.notes != undefined) {
                if (person.notes.note_format) {
                    var notesP = document.createElement('pre');
                } else {
                    var notesP = document.createElement('p');
                }
                notesP.appendChild(document.createTextNode(person.notes.note_text));
                subtitle = document.createElement('h3');
                subtitle.appendChild(document.createTextNode('%s:'));
                containerDIV.appendChild(subtitle);
                containerDIV.appendChild(notesP);
            }
            return;
        }
        """
        return JSfunction % self.escbacka(_('Notes'))

    def pack_source_data(self,person):
        """Return a string that will be part of the JavaScript object
            describing all sources, e.g.:
            sources:[{source_title:'...'},...]"""
        rv = ""
        source_handle_list = []
        if len(self.person_srcs) > 0:
            source_handle_list.extend(self.person_srcs)
        if self.options['DNMinc_sources']:
            source_ref_list = filter(self.privacy_filter,person.get_source_references())
            source_handle_list.extend([i.get_reference_handle() for i in source_ref_list])
        # Do not sort: the sources referenced in events are already ordered!
        if len(source_handle_list) > 0:
            for i,handle in enumerate(source_handle_list):
                st = '' #source text
                source = self.database.get_source_from_handle(handle)
                if self.options['DNMexl_private'] and source.get_privacy():
                    continue
                title = source.get_title()
                if title:
                    st += ",source_title:'" + self.escbacka(title) + "'"
                    self.search_subjects['Source Title'] = 'source_title'
                if '<volume>' in self.source_format and i >= len(self.person_srcs):
                    page = source_ref_list[i].get_page()
                    if page:
                        st += ",source_page:'" + self.escbacka(page) + "'"
                if '<author>' in self.source_format:
                    author = source.get_author()
                    if author:
                        st += ",source_author:'" + self.escbacka(author) + "'"
                        self.search_subjects['Source Author'] = 'source_author'
                if '<publication_info>' in self.source_format:
                    pub_info = source.get_publication_info()
                    if pub_info:
                        st += ",source_pub_info:'" + self.escbacka(pub_info) + "'"
                        self.search_subjects['Source Publication Information'] = 'source_pub_info'
                if '<abbreviation>' in self.source_format:
                    abbr = source.get_abbreviation()
                    if abbr:
                        st += ",source_abbr:'" + self.escbacka(abbr) + "'"
                        self.search_subjects['Source Abbreviation'] = 'source_abbr'
                if st:
                    rv += "{" + st[1:] + "},"
        if rv:
            rv = "sources:[" + rv[:-1] + "]"
        return rv

    def unpack_source_data(self):
        """Return a string that is a JavaScript function suitable to unpack
            the source data packed into the person-JS-object."""
        JSfunction = """
        function sources2html(person,containerDIV) {
            if (person.sources != undefined) {
                var sourcesOL = document.createElement('ol');
                for (i=0; i< person.sources.length; i++) {
                    var sourceLI = document.createElement('li');
                    var source_str = "%(source_format)s"
                    source_str = replaceSubstring(source_str,"<%(title)s>",
                                 person.sources[i].source_title);
                    source_str = replaceSubstring(source_str,"<%(volume)s>",
                                 person.sources[i].source_page);
                    source_str = replaceSubstring(source_str,"<%(author)s>",
                                 person.sources[i].source_author);
                    source_str = replaceSubstring(source_str,"<%(publication_info)s>",
                                person.sources[i].source_pub_info);
                    source_str = replaceSubstring(source_str,"<%(abbreviation)s>",
                                 person.sources[i].source_abbr);
                    event_str2html(source_str,sourceLI);
                    sourcesOL.appendChild(sourceLI);
                }
                subtitle = document.createElement('h3');
                subtitle.appendChild(document.createTextNode('%(sectitle)s:'));
                containerDIV.appendChild(subtitle);
                containerDIV.appendChild(sourcesOL);
            }
            return;
        }
        """
        return JSfunction % {'source_format':self.source_format.replace('\n','\\n').replace('"','\\'), \
            'sectitle':self.escbacka(_('Sources')), \
            'title':_('title'), 'volume':_('volume'), 'author':_('author'), \
            'publication_info':_('publication_info'), \
            'abbreviation':_('abbreviation')}

    def get_family_event_refs(self,person):
        """Return events for person person that are stored in the families to
            which this person belongs. A hash is returned where the key is
            the event_reference and the value a textual description of the
            event."""
        ret_hash = {}
        for family_handle in person.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)
            ret_hash.update(ret_hash.fromkeys(family.get_event_ref_list()))
            if self.options['DNMinc_child_birth'] or self.options['DNMinc_death_relative']:
                for ref in family.get_child_ref_list():
                    if ref.ref:
                        child = self.database.get_person_from_handle(ref.ref)
                        birth_ref = child.get_birth_ref()
                        if self.options['DNMinc_child_birth']:
                            if birth_ref:
                                ret_hash[birth_ref] = 'Birth Child'
                            else:
                                for er in child.get_primary_event_ref_list():
                                    e = self.database.get_event_from_handle(er.ref)
                                    if e.get_type() == EventType.BAPTISM:
                                        ret_hash[er] = 'Baptism Child'
                                        break
                                    elif e.get_type() == EventType.CHRISTEN:
                                        ret_hash[er] = 'Christening Child'
                                        break
                        death_ref = self.get_death_ref_or_fallback(child,'Child')
                        if self.options['DNMinc_death_relative'] and death_ref:
                            ret_hash[death_ref[0]] = death_ref[1]
            if self.options['DNMinc_death_relative']:
                spouse_handle = ReportUtils.find_spouse(person,family)
                if spouse_handle:
                    spouse = self.database.get_person_from_handle(spouse_handle)
                    death_ref = self.get_death_ref_or_fallback(spouse,'Spouse')
                    if death_ref:
                        ret_hash[death_ref[0]] = death_ref[1]
        if self.options['DNMinc_death_relative']:
            for family_handle in person.get_parent_family_handle_list():
                family = self.database.get_family_from_handle(family_handle)
                parent_handle = family.get_father_handle()
                if parent_handle:
                    parent = self.database.get_person_from_handle(parent_handle)
                    death_ref = self.get_death_ref_or_fallback(parent,'Father')
                    if death_ref:
                        ret_hash[death_ref[0]] = death_ref[1]
                parent_handle = family.get_mother_handle()
                if parent_handle:
                    parent = self.database.get_person_from_handle(parent_handle)
                    death_ref = self.get_death_ref_or_fallback(parent,'Mother')
                    if death_ref:
                        ret_hash[death_ref[0]] = death_ref[1]
        return ret_hash

    def get_death_ref_or_fallback(self, person, person_type):
        death_ref = person.get_death_ref()
        if death_ref:
            return (death_ref,'Death ' + person_type)
        else:
            for er in person.get_primary_event_ref_list():
                e = self.database.get_event_from_handle(er.ref)
                if e.get_type() == EventType.BURIAL:
                    return (er,'Burial ' + person_type)
                elif e.get_type() == EventType.CREMATION:
                    return (er,'Cremation ' + person_type)
        return

    def event_role2names(self,event,role=EventRoleType.PRIMARY,output_notes=False):
        """Return the names of those persons that have role role with event event, possibly with the role-notes"""
        ret_names = []
        ret_notes = []
        event_handle = event.get_handle()
        if event_handle:
            for l in self.database.find_backlink_handles(event_handle,['Person']):
                person = self.database.get_person_from_handle(l[1])
                for ref in person.get_event_ref_list():
                    event2 = self.database.get_event_from_handle(ref.ref)
                    if event.are_equal(event2) and ref.get_role() == role:
                        ret_names.append(_nd.display(person))
                        if output_notes:
                            #use ref.get_note_list() QUICK FIX
                            note_handles = ref.get_note_list()
                            if len(note_handles) > 0:
                                note = self.database.get_note_from_handle(note_handles[0])
                                ret_notes.append(self.escbacka(note.get()))
                            else:
                                ret_notes.append('')
                            #ret_notes.append(ref.get_note())
                        break
        if output_notes:
            return (ret_names,ret_notes)
        else:
            return ret_names

    def marriage_event2spouse_name(self,event_ref,person):
        """Return the name of the spouse"""
        # Could use ReportUtils.find_spouse()
        rv = ""
        if event_ref.ref:
            for l in self.database.find_backlink_handles(event_ref.ref,['Family']):
                family = self.database.get_family_from_handle(l[1])
                person_handle = person.get_handle()
                father_handle = family.get_father_handle()
                mother_handle = family.get_mother_handle()
                if father_handle and mother_handle:
                    if person_handle == father_handle:
                        rv = _nd.display(self.database.get_person_from_handle(mother_handle))
                    else:
                        rv = _nd.display(self.database.get_person_from_handle(father_handle))
                break
        return rv
                    
        
    def marriage_event2parent_names(self,event_ref):
        """Return a tuple with the names of the husband and wife of a marriage
            event."""
        father = None
        mother = None
        if event_ref.ref:
            for l in self.database.find_backlink_handles(event_ref.ref,['Family']):
                family = self.database.get_family_from_handle(l[1])
                father_handle = family.get_father_handle()
                if father_handle:
                    father = _nd.display(self.database.get_person_from_handle(\
                            father_handle))
                mother_handle = family.get_mother_handle()
                if mother_handle:
                    mother = _nd.display(self.database.get_person_from_handle(\
                            mother_handle))
                break
        return (father,mother)

    def witnesses2JS(self,event):
        """Return the JavaScript that describes a list of witnesses, e.g.:
            [{witness_name:'...',witness_note:'...'},...]"""
        rv = ""
        if self.options['DNMinc_witness_note']:
            (witness_array,notes_array) = \
                    self.event_role2names(event,EventRoleType.WITNESS,True)
        else:
            witness_array = self.event_role2names(event,EventRoleType.WITNESS)
            notes_array = len(witness_array)*['']
        if len(witness_array) > 0:
            def tmpfunc(x,y):
                if y[1]:
                    return x + "{witness_name:'" + self.escbacka(y[0]) + \
                            "',witness_note:'" + self.escbacka(y[1]) + "'},"
                else:
                    return x + "{witness_name:'" + self.escbacka(y[0]) + "'},"
            rv += reduce(tmpfunc,zip(witness_array,notes_array),'')
        # witnesses from Gramps 2.0.11 were dumped in notes with notation:
        # Witness name:...
        # Witness comment:...
        check_comment = False
        # use get_note_list() QUICK FIX
        lines = []
        note_handles = event.get_note_list()
        if len(note_handles) > 0:
            note = self.database.get_note_from_handle(note_handles[0])
            lines = note.get().split("\n")
        #lines = event.get_note().split("\n")
        for line_nr,line in enumerate(lines):
            if line[0:13] == 'Witness name:':
                rv += "{witness_name:'" + self.escbacka(line[14:]) + "'"
                if self.options['DNMinc_witness_note'] and line_nr+1 < len(lines)\
                        and lines[line_nr+1][0:16] == 'Witness comment:':
                    rv += ",witness_note:'" + self.escbacka(lines[line_nr+1][17:]) + "'"
                rv += "},"
        if rv:
            rv = "[" + rv[:-1] + "]"
            self.search_subjects['Witness Name'] = 'witness_name'
            if 'witness_note' in rv:
                self.search_subjects['Witness Note'] = 'witness_note'
        return rv

    def event_source2JS(self,event):
        """Return the JavaScript that describes a source reference, e.g.:
            {source_page:'...',source_conf:'...'}
            event can be more general than just events: attributes/addresses."""
        rv = ''
        source_page = ''
        source_refs = filter(self.privacy_filter,event.get_source_references())
        if len(source_refs) > 0:
            source_page = source_refs[0].get_page()
            source_handle = source_refs[0].get_reference_handle()
            if source_handle and not (self.options['DNMexl_private'] and \
                    self.database.get_source_from_handle(source_handle).get_privacy()):
                if source_page:
                    source_page +=  ' ' + _('of') + ' '
                if source_handle in self.person_srcs:
                    source_nr = self.person_srcs.index(source_handle)
                else:
                    source_nr = len(self.person_srcs)
                    self.person_srcs.append(source_handle)
                source_page += '[' + str(source_nr + 1) + ']'
            if source_page:
                rv += "source_page:'" + self.escbacka(source_page) + "'"
                conf_level = source_refs[0].get_confidence_level()
                if self.options['DNMconf_color'][conf_level][_cnsts.COLOR_COLUMN] \
                        != self.options['DNMconf_color'][-1][_cnsts.COLOR_COLUMN]:
                    rv += ",source_conf:'" + ext_confidence[conf_level].replace(' ','') + "'"
            if rv:
                rv = '{' + rv + '}'
        return rv

    def event_roles2JS(self,event):
        """Return the JavaScript that describes the event_roles, e.g.:
        ,event_Clergy:'...',event_Bride:'...',...
        mind the first comma!"""
        rv = ""
        for role_str in self.event_format_roles:
            names = self.event_role2names(event,role_str)
            if len(names)>0:
                rv += ',event_' + role_str.replace(' ','_') + ":'" + \
                        self.escbacka(", ".join(names)) + "'"
                self.search_subjects['Event ' + role_str] = \
                    'event_' + role_str.replace(' ','_')
        return rv

    def event_attributes2JS(self,event):
        """Return the JavaScript that describes the event_attributes, e.g.:
            ,event_Church:'...',event_National_Origin:'...',...
            mind the first comma!"""
        rv = ""
        event_attributes = event.get_attribute_list()
        for attr_type in self.event_format_attributes:
            attr_vals = [i.get_value() for i in event_attributes \
                if i.get_type() == attr_type]
            if len(attr_vals) > 0:
                rv += ",event_" + attr_type.replace(' ','_') + ":'" + \
                        self.escbacka(attr_vals[0]) + "'"
                self.search_subjects['Event ' + attr_type] = \
                        'event_' + attr_type.replace(' ','_')
        return rv

    def photo2JS(self,media_object):
        """Return the JavaScript that describes a photo e.g.:
            {img_path:'...',img_ref:'...'}

        There can be considerable trouble with the copyright on images, so I
        needed a way to exclude images; I use an attribute for that.
        Images should only be included once per person and images should only
        be copied once if images should be gathered in a separate directory.
        Some images need more than a simple reference to their source, this
        can be stored in a special image attribute.
        """
        rv = ""
        mime_type = media_object.get_mime_type()
        if not mime_type.startswith("image/"):
            return rv
        media_path = media_object.get_path()
        if self.options['DNMexl_private'] and media_object.get_privacy():
            return rv
        if self.options['DNMimg_attr4inex'].strip() != '':
            attr_list = filter(self.img_attr_check,media_object.get_attribute_list())
            if (self.options['DNMinexclude_img'] and len(attr_list) > 0) or \
                (not self.options['DNMinexclude_img'] and len(attr_list) <=0): \
                return rv
        if self.options['DNMcopy_img']:
            if not os.path.isdir(self.options['DNMcopy_dir']):
                os.makedirs(self.options['DNMcopy_dir'])
            if self.copied_imgs.has_key(media_path):
                media_path = self.copied_imgs[media_path]
            else:
                dest = self.get_copied_photo_name(media_object,media_path)
                shutil.copyfile(media_path,dest)
                self.copied_imgs[media_path] = self.relpathA2B(self.target_path,dest)
                media_path = self.copied_imgs[media_path]
        if media_path not in self.person_imgs:
            rv = "{img_path:'" + self.escbacka(media_path) + "'"
            self.person_imgs.add(media_path)
            if self.options['DNMimg_src_ref_str'].strip() != "":
                source_refs = [x.get_value() \
                    for x in media_object.get_attribute_list() \
                    if x.get_type() == self.options['DNMimg_src_ref_str']]
                if len(source_refs) > 0:
                    source_ref_str = ", ".join(source_refs)
                    try:
                        source_idx = self.person_img_srcs.index(source_ref_str) + 1
                    except ValueError:
                        self.person_img_srcs.append(source_ref_str)
                        source_idx = len(self.person_img_srcs)
                    return rv + ",img_ref:'" + str(source_idx) + "'}"
            if self.options['DNMinc_img_src_ref']:
                media_source_list = media_object.get_source_references()
                source_refs = ""
                for ref in media_source_list:
                    handle = ref.get_reference_handle()
                    source = self.database.get_source_from_handle(handle)
                    # what happens where get_title is empty
                    try:
                        source_idx = self.person_img_srcs.index(source.get_title()) + 1
                    except ValueError:
                        self.person_img_srcs.append(source.get_title())
                        source_idx = len(self.person_img_srcs)
                    source_refs += "," + str(source_idx)
                if source_refs:
                    rv += ",img_ref:'" + source_refs[1:] + "'"
            rv += "}"
        return rv

    def get_copied_photo_name(self,photo,media_path):
        """Return the filepath that the copied photo should use."""
        ext = os.path.splitext(media_path)[1]
        if self.options['DNMuse_sequential_photoname']:
            dest = os.path.join(self.options['DNMcopy_dir'],"P"+"%04d" % len(self.copied_imgs) + ext)
        else:
            id = photo.get_gramps_id()
            # id might not be unique
            dest = os.path.join(self.options['DNMcopy_dir'],id + ext)
            rel_path = self.relpathA2B(self.target_path,dest)
            already = self.copied_imgs.values()
            if rel_path in already:
                same_ids = filter(lambda x: x.startswith(rel_path[0:-len(ext)]), already)
                id += '_%d' % len(same_ids)
                dest = os.path.join(self.options['DNMcopy_dir'],id + ext)
        return dest

    def img_attr_check(self,attribute):
        """Filter function, returns true when image attribute is of right type
            and value.

            Arguments:
            attribute    Attribute of the image you want to check

            DNMimg_attr_val4inex contains the value of the image
            attribute as set by the user in the dialog. If it is empty then
            only the attribute-types are to match to return true."""
        if self.options['DNMimg_attr_val4inex'] != '':
            return attribute.get_type() == self.options['DNMimg_attr4inex'] \
                and attribute.get_value() == self.options['DNMimg_attr_val4inex']
        else:
            return attribute.get_type() == self.options['DNMimg_attr4inex']

    def relpathA2B(self,A,B):
        """Return a relative pathname to get from file A to B"""
        retval = ''
        A = os.path.abspath(A)
        B = os.path.abspath(B)
        cp = os.path.split(os.path.commonprefix([A,B]))[0]
        if cp == '':
            raise NameError('Unable to construct a relative path from ' + \
                A + ' to ' + B)
        a = os.path.dirname(A)
        while a != cp:
            retval += "../"
            a = os.path.dirname(a)
        rv = os.path.basename(B)
        b = os.path.dirname(B)
        while b != cp:
            rv = os.path.basename(b) + '/' + rv
            b = os.path.dirname(b)
        return retval + rv

    def privacy_filter(self,obj):
        """Return false if the data is private and it should be excluded, used
            in filters of lists."""
        return not (self.options['DNMexl_private'] and obj.get_privacy())

    def escbacka(self,strng):
        """Escape any backslash and apostroph sign in strng"""
        return strng.replace("\\","\\\\").replace("'",r"\'")

    def start_page(self,f):
        """Write the start of the webpage to file"""
        if self.options['DNMchart_type'] == _cnsts.REGULAR:
            viewBox_width = self.options['DNMmax_generations']*self.rect_xdist
            viewBox_height = 3*viewBox_width # 3 is just a guess, see end_page.
            viewBox = "0 0 %d %d" % (viewBox_width,viewBox_height)
        elif self.options['DNMchart_type'] == _cnsts.FAN:
            viewBox = " ".join([str(100*self.options['DNMmax_generations']*i) \
                    for i in [-1,-1,2,2]])
        elif self.options['DNMchart_type'] == _cnsts.GROWTHSPIRAL:
            x_max,x_min,y_max,y_min = (100,-100,100,-100)
            offset = (-pi/2,pi/2,pi,0)[self.options['DNMtime_dir']]
            for i in range(1,self.options['DNMmax_generations']):
                x,y = polar2cart(50*exp(0.69*i),i+offset)
                x_max,y_max = max(x_max,x),max(y_max,y)
                x_min,y_min = min(x_min,x),min(y_min,y)
            viewBox = "%d %d %d %d" % (x_min,y_min,x_max-x_min,y_max-y_min)
        elif self.options['DNMchart_type'] == _cnsts.MATREE:
            viewBox = ("-10 -750 1020 1500","-1020 -750 1020 1500", \
                    "-750 -1010 1500 1020","-750 -10 1500 1020")[self.options['DNMtime_dir']]
        elif self.options['DNMchart_type'] == _cnsts.PYTREE:
            # the following formulas are empirical
            height = 4*100/(1-0.68)
            width = 0.68**2*4*100*(1/(1-0.68) + 1.2)
            viewBox = "%d %d %d %d" % ((0,-width,height,2*width),(-height,-width,height,2*width),(-width,-height,2*width,height),(-width,0,2*width,height))[self.options['DNMtime_dir']]
        else:
            ErrorDialog(_("the chart type runs out of bounds"),self.options['DNMchart_type'])

        strng = """<?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
                "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
            <html:html xmlns:html="http://www.w3.org/1999/xhtml"
                    xmlns="http://www.w3.org/2000/svg"
                    xml:lang="nl">
            <html:head>
            <html:meta http-equiv="Content-Type" content="application/xhtml+xml; charset=UTF-8"/>
            <html:title>%s</html:title>
            <html:style>
        """ % self.options['DNMtitle']
        strng += self.get_css_style()
        strng += """</html:style>
            <html:script type="text/javascript">
            <![CDATA["""
        strng += self.get_javascript_functions()
        strng += self.unpack_birth_death_data("birth")
        strng += self.unpack_birth_death_data("death")
        strng += self.unpack_event_data()
        strng += self.unpack_attribute_data()
        strng += self.unpack_address_data()
        strng += self.unpack_note_data()
        strng += self.unpack_source_data()
        onunload = ''
        if self.open_subwindow:
            onunload = ' onunload="cleanUp()"'
        strng += """]]>
            </html:script>
            </html:head>
            <html:body%s>
            <html:div id="infoField"></html:div>
            <html:form id="searchForm" action="">
            <html:label>%s:
            <html:input id="searchString" type="text" onkeyup="searchStrInSubj()"/>
            </html:label>
            <html:label>%s:
            <html:select id="searchSubject" onchange="searchStrInSubj()">
            </html:select>
            </html:label>
            </html:form>
            <html:p><html:br/></html:p> <!-- To accomodate the search form. -->
            <svg id="AncestorChart" width="%d%%" height="%dpx"
                viewBox="%s" preserveAspectRatio="xMinYMin" onclick="start_halo(evt)">
        """ % (onunload,_('Search'),_('in'),self.options['DNMtree_width'],self.options['DNMheight'],viewBox)
        if self.options['DNMchart_type'] == _cnsts.PYTREE:
            viewb = [int(i) for i in viewBox.split()]
            strng += """<rect id="sky" x="%d" y="%d" width="100%%" height="%d" />
                <rect id="landscape" x="%d" y="-500" width="100%%" height="%d" />\
                """ % (viewb[0],viewb[1],-500-viewb[1],viewb[0],viewb[3])
        f.write(strng)
        return

    def get_css_style(self):
        """Return a string with all style settings for the webpage."""
        style_str = """
            div#infoField {position: fixed;
                   height:   auto;
                   top:      3%%;
                   right:    0;
                   bottom:   5%%;
                   left:     %(w)d%%;
                   overflow: auto;}
            form#searchForm {position: fixed;}
            input.valid {background: rgb(191,255,191);}
            input.invalid {background: rgb(255,191,191);}
            pre#copyright {position: fixed;
                    bottom: 0;}
            line {stroke-width: 5px;}
            rect {fill: black;}
            path {stroke: white; stroke-width: 1;}
            .male {fill: rgb(%(malc)s);}
            .female {fill: rgb(%(femc)s);}
            rect.activated {stroke: black;
                   fill:   rgb(%(ac)s) ! important;}
            rect.searched {stroke: black;
                   fill:   rgb(%(fc)s);}
            path.activated {stroke: black;
                   fill:   rgb(%(ac)s) ! important;}
            path.searched {stroke: black;
                   fill:   rgb(%(fc)s);}
            h3 {clear: left;}
            dt {clear: right;}
            li {clear: right;}
            div.imgTable {position: relative;
                    float: right;
                    max-width: 70%%;}
            object:before {content: attr(imgref);
                color: black;
                font-size: smaller;}
            object { width: 100%%;
                    max-height: 5em;
                    margin: 1px;
                    border-style: none;}
            object.portret {float: left;
                    max-width: 25%%;
                    max-height: 10em;}
            img:before {content: attr(imgref);
                color: black;
                font-size: smaller;}
            img { width: 100%%;
                    max-height: 5em;
                    margin: 1px;
                    border-style: none;}
            img.portret {float: left;
                    max-width: 25%%;
                    max-height: 10em;}
            """ % {'w':self.options['DNMtree_width'], \
                   'ac':hex2int_color(self.options['DNMactivated_color']),
                   'fc':hex2int_color(self.options['DNMfound_color']),
                   'malc':hex2int_color(self.options['DNMmale_color']),
                   'femc':hex2int_color(self.options['DNMfemale_color'])}
        for row in self.options['DNMdash_child_rel']:
            if row[_cnsts.USE_DASH_COLUMN]:
                style_str += "line.%s {stroke-dasharray: %d,%d;}\n" % \
                        (row[_cnsts.BIRTH_REL_COLUMN].replace(' ',''),\
                        row[_cnsts.DASH_LENGTH_COLUMN],\
                        row[_cnsts.INTER_DASH_LENGTH_COLUMN])
        for row in self.options['DNMconf_color'][0:-1]:
            style_str += "line.%(clName)s {stroke: %(clColor)s;}\nspan.%(clName)s {color: %(clColor)s;}\n" % \
                    {'clName':ext_confidence[row[_cnsts.CONFIDENCE_COLUMN]].replace(' ',''),\
                    'clColor':row[_cnsts.COLOR_COLUMN]}
        style_str += '\nline {stroke:' + self.options['DNMconf_color'][-1][_cnsts.COLOR_COLUMN] + ';}'
        if self.options['DNMchart_type'] == _cnsts.PYTREE:
            style_str += """\nrect#sky {fill: lightblue; cursor: url(./woodpecker_flight.png),pointer;}
                rect#landscape {fill:green; cursor: url(./woodpecker_flight.png),pointer;}
                path {cursor: url(./woodpecker_seated.png),pointer;}"""
        style_str += '\n' + '\n'.join(self.options['DNMfree_style'])
        return style_str

    def get_javascript_functions(self):
        """Return a string which is basically a collection of JavaScript
             functions."""
        if self.options['DNMchart_type'] == _cnsts.REGULAR or \
            self.options['DNMchart_type'] == _cnsts.MATREE :
            shape = 'rect'
        else:
            shape = 'path'
        strng = """
        var infoWindow
        function activate(aRect,person) {
            var class = ""
            class = aRect.getAttribute('class');
            if (! class || class.indexOf('activated') == -1) {
                aRect.setAttribute('class',class + ' activated');
            }
            var infoField = getInfoField(person);
            infoField.scrollTop = 0;
            addText(person,infoField);
            var rects = document.getElementsByTagName('%(shp)s');
            for (var i=0; i<rects.length; i++) {
                class = rects[i].getAttribute('class');
                if (/activated/.test(class) && rects[i] != aRect) {
                    rects[i].setAttribute('class',class.replace(/activated/g,''));
                }
            }
        }
        function addText(person,infoField) {
            //var infoField = document.getElementById('infoField');
            removeText(infoField);
            var nameF = document.createElement('h2');
            if (person.url != undefined && person.url.url_path != undefined) {
                var a = document.createElement('a');
                a.setAttribute('href',person.url.url_path);
                a.setAttribute('target','_blank');
                if (person.url.url_desc != undefined) {
                    a.setAttribute('title',person.url.url_desc);
                }
                a.appendChild(document.createTextNode(person.person_name));
                nameF.appendChild(a);
            } else {
                nameF.appendChild(document.createTextNode(person.person_name));
            }
            infoField.appendChild(nameF);
            if (person.person_img != undefined) {
                infoField.appendChild(photo2html(person.person_img,'portret'))
            }

            var vitalDL = document.createElement('dl');
            birth2html(person,vitalDL);
            death2html(person,vitalDL);
            infoField.appendChild(vitalDL);
            events2html(person,infoField);
            attributes2html(person,infoField);
            addresses2html(person,infoField);
            notes2html(person,infoField);
            sources2html(person,infoField);
            img_sources2html(person,infoField);
            setStatusbar(person.person_name)
        }
        function setStatusbar(str) {
            // There is a configuration option in Firefox that can disable this.
            window.defaultStatus=str;
        }
        function removeText(infoField) {
            //var infoField = document.getElementById('infoField');
            while (infoField.hasChildNodes()) {
                infoField.removeChild(infoField.firstChild);
            }
        }
        function photo2html(photo) {
            var a = document.createElement('a');
            //var img = document.createElement('img');
            var img = document.createElement('object');
            //img.setAttribute('src',photo.img_path);
            img.setAttribute('data',photo.img_path);
            if (arguments.length > 1) {
                img.setAttribute('class',arguments[1]);
            }
            a.setAttribute('href',photo.img_path);
            if (photo.img_ref != undefined) {
                img.setAttribute('imgref',photo.img_ref);
            }
            a.appendChild(img);
            return a
        }
        function img_sources2html(person,containerDIV) {
            if (person.img_sources != undefined) {
                var sourcesOL = document.createElement('ol');
                for (var i=0; i < person.img_sources.length; i++) {
                    var sourceLI = document.createElement('li');
                    sourceLI.appendChild(document.createTextNode(person.img_sources[i]));
                    sourcesOL.appendChild(sourceLI);
                }
                var subtitle = document.createElement('h3');
                subtitle.appendChild(document.createTextNode('Image Sources:'));
                containerDIV.appendChild(subtitle);
                containerDIV.appendChild(sourcesOL);
            }
            return;
        }
        function replaceSubstring(mainStr,subsStr,replText) {
            //mainStr is a multiline string
            //subStr is the substring that must be replaced.
            // replText is a string or an array of strings.
            var delete_start;
            if ((replText) &&
                ((delete_start = mainStr.indexOf(subsStr)) >=0)) {
                if (typeof(replText) != 'string') {
                    replText = replText.join(", ");
                }
                var newline_index = mainStr.substr(0,delete_start).lastIndexOf('\\n');
                return mainStr.substr(0,newline_index+1) + subsStr + mainStr.substring(newline_index+1,delete_start) + replText + mainStr.substring(delete_start+subsStr.length,mainStr.length)
            } else {
                //remove whole line
                var re = new RegExp("^.*?" + subsStr + ".*?(?:\\n|$)","m")
                return mainStr.replace(re,"")
            }
        }
        function event_str2html(event_str,containerEL) {
            var empty_line = false;
            event_pieces = event_str.split(/\\n/);
            for (j=0; j<event_pieces.length; j++) {
                var end_class_index = event_pieces[j].indexOf('>');
                if (event_pieces[j] == '') {
                    empty_line = true;
                    continue;
                }
                if (empty_line) {
                    containerEL.appendChild(document.createElement('br'));
                    empty_line = false;
                }
                if (event_pieces[j].charAt(0) == '<' && end_class_index != -1) {
                    var cls = event_pieces[j].substr(1,end_class_index-1);
                    var span = document.createElement('span');
                    span.setAttribute('class',cls);
                    span.appendChild(document.createTextNode(event_pieces[j].substr(end_class_index+1) + ' '));
                    containerEL.appendChild(span);
                } else {
                    containerEL.appendChild(document.createTextNode(event_pieces[j] + ' '));
                }
            }
            return
        }
        function witness_array2string_array(witnesses) {
            // The input of replaceSubstring() needs to be an array of string.
            // This function converts the array of witness objects to an
            // array of strings.
            if (witnesses == undefined) { return witnesses; }
            var ret_ar = [];
            for (var i=0; i<witnesses.length; i++) {
                ret_ar[i] = witnesses[i].witness_name
                if (witnesses[i].witness_note != undefined) {
                    ret_ar[i] += " (" + witnesses[i].witness_note + ")";
                }
            }
            return ret_ar;
        }
        function searchStrInSubj() {
            var inp = document.getElementById('searchString');
            var strng = inp.value;
            var sel = document.getElementById('searchSubject');
            var subj = sel.options[sel.selectedIndex].value;
            var resultFound = search(strng,subj);
            if (resultFound) {
                inp.setAttribute('class','valid');
            } else {
                if (strng != '') {
                    inp.setAttribute('class','invalid');
                } else {
                    inp.setAttribute('class','');
                }
            }
            return true;
        }
        function search(strg,subj) {
            //make sure subj is unique so no name: and event_name:!
            // There is trouble with witnesses because it is an array
            // ..._witnesses:['... in stead of ..._date:'...
            var eureka = false;
            strng = strg.replace(/\\\\/g,"\\\\\\\\").replace(/'/g,"\\\\'")
            var rects = document.getElementsByTagName('%(shp)s');
            RectangleLoop: for (var i=0; i<rects.length; i++) {
                var found = false;
                var class = "";
                if (rects[i].hasAttribute('class')) {
                    class = rects[i].getAttribute('class');
                    found = (class.indexOf('searched') != -1);
                }
                var personObj = rects[i].getAttribute('%(maction)s');
                //var personObj = rects[i].getAttribute('onmouseover');
                var startIndex = personObj.indexOf(subj);
                if (startIndex == -1 && found) {
                    rects[i].setAttribute('class',class.replace(/searched/g,''));
                }
                while (startIndex != -1) {
                    startIndex += subj.length;
                    var endIndex = personObj.indexOf("'",startIndex);
                    while (personObj.charAt(endIndex-1) == '\\\\') {
                        endIndex = personObj.indexOf("'",endIndex+1);
                    }
                    subjVal = personObj.substring(startIndex,endIndex);
                    if (strng == strng.toLowerCase()) { 
                        if (strng != "" && subjVal.toLowerCase().indexOf(strng) != -1) {
                            if (! found) {
                                rects[i].setAttribute('class',class + " searched");
                            }
                            eureka = true;
                            continue RectangleLoop;
                        }
                    } else {
                        if (subjVal.indexOf(strng) != -1) {
                            if (! found) {
                                rects[i].setAttribute('class',class + " searched");
                            }
                            eureka = true;
                            continue RectangleLoop;
                        }
                    }
                    startIndex = personObj.indexOf(subj,endIndex+1);
                }
                if (found) {
                    rects[i].setAttribute('class',class.replace(/searched/g,''));
                }
            }
            return eureka;
        }
        function start_halo(evt) {
            const ring_width_px = 3
            const r_min_px = 10
		    if (evt.detail != 2) { return; }
            var persons = document.getElementsByTagName('%(shp)s')
            for (var i=0; i<persons.length; i++) {
                if (persons[i].hasAttribute('class') && persons[i].getAttribute('class').indexOf('activated') != -1) {
                    if (persons[i].hasAttribute('x')) {
                        var x = persons[i].getAttribute('x')
                        var y = persons[i].getAttribute('y')
                    } else {
                        /^M(-?\d+),(-?\d+)/.exec(persons[i].getAttribute('d'))
                        var x = RegExp.$1
                        var y = RegExp.$2
                    }
				    var halo = document.getElementById('halo')
                    halo.setAttribute('fill','none')
                    halo.setAttribute('cx',x);
                    halo.setAttribute('cy',y);
                    var svg = document.getElementById('AncestorChart')
                    var ctm = svg.getScreenCTM()
                    x_click = (evt.clientX-ctm.e)/ctm.a
                    y_click = (evt.clientY-ctm.f)/ctm.a
                    var radius = Math.sqrt(Math.pow(x_click-x,2) + Math.pow(y_click-y,2))
                    halo.setAttribute('r',radius);
                    halo.setAttribute('stroke','rgb(%(ac)s)')
                    halo.setAttribute('stroke-width',ring_width_px/ctm.a)
                    var r_min = r_min_px/ctm.a
                    window.setTimeout(self.halo,100,x,y,radius,r_min);
				    break;
                }
            } 
        }
        function halo(cx,cy,r,r_min) {
            var h = document.getElementById('halo');
            if (r > r_min) {
                h.setAttribute('r',0.85*r);
                window.setTimeout(self.halo,100,cx,cy,0.85*r,r_min);
            } else {
                h.setAttribute('stroke','none')
                h.setAttribute('r',1);
                h.setAttribute('cx',1);
                h.setAttribute('cy',1);
            }
        }
        function cleanUp() {
            if (infoWindow != undefined && ! infoWindow.closed) {
                infoWindow.close();
            }
        }""" % {'shp':shape, 'maction':_cnsts.mouse_events[self.options["DNMclick_over"]][1], \
            'ac':hex2int_color(self.options['DNMactivated_color'])}

        if not self.open_subwindow:
            strng += """
                function getInfoField(person) {
                    return document.getElementById('infoField');
                }"""
        else:
            strng += """
            function getInfoField(person) {
            // Trouble in that Firefox and Opera behave differently.
            // Firefox is OK with a window.URL of "" while Opera complains
            // about a missing root of the xml-document.
            // Opera is OK with about:blank while Firefox seems to use some
            // onload handler to whipe the content clean after (sic) the data to
            // be displayed is shown. 
            // Why isn't the title set and fails focus in Firefox?
            if (infoWindow == undefined || infoWindow.closed) {
                infoWindow = window.open("about:blank","","dependent=yes,titlebar=yes,scrollbars=yes,width=500");
            }
            var doc = infoWindow.document;
            doc.open('text/html','replace'); // clear what is in the window
            doc.close();
            var heads = doc.getElementsByTagName('head');
            if (heads.length > 0) {
                var headEl = heads[0];
            } else {
                var htmlEl = doc.getElementsByTagName('html')[0];
                var headEl = htmlEl.appendChild(doc.createElement('head'));
            }
            var style = document.getElementsByTagName('style')[0];
            headEl.appendChild(style.cloneNode(true));
            var titles = doc.getElementsByTagName('title');
            if (titles.length > 0) {
                var titleEl = titles[0];
            } else {
                var titleEl = headEl.appendChild(doc.createElement('title'));
            }
            while (titleEl.hasChildNodes()) {
                titleEl.removeChild(titleEl.firstChild);
            }
            titleEl.appendChild(doc.createTextNode(person.person_name))
            infoWindow.focus()
            var bodies = doc.getElementsByTagName('body');
            return bodies[0];
            }""" 
        return strng

    def end_page(self,f):
        """Close the webpage, that is: write the closing tag for svg, add
        information that is only now available and close the html-tag."""
        strng = """
            <circle id="halo" cx="1" cy="1" r="1" stroke="none" fill="none"/>
            </svg>
            <html:p><html:br/></html:p><!--To accomodate the copyright string.-->
            <html:pre id="copyright">%s</html:pre>
            """ % self.copyright
        if self.options['DNMchart_type'] == _cnsts.REGULAR:
            if self.options['DNMtime_dir'] < _cnsts.TOP2BOTTOM:
                width = self.options['DNMmax_generations']*self.rect_xdist
                height = self.advance + 0.5*self.rect_height
                if (self.options['DNMchart_mode'] == _cnsts.ANCESTOR and \
                    self.options['DNMtime_dir'] == _cnsts.RIGHT2LEFT) or \
                    (self.options['DNMchart_mode'] == _cnsts.DESCENDANT and \
                    self.options['DNMtime_dir'] == _cnsts.LEFT2RIGHT):
                    viewBox = "%d %d %d %d" % (-self.rect_width/2, -self.rect_height/2, width, height + self.rect_height/2)
                else:
                    viewBox = "%d %d %d %d" % (-width + self.rect_width/2, - self.rect_height/2, width, height + self.rect_height/2)
            else:
                width = self.advance
                height = self.options['DNMmax_generations']*self.rect_ydist
                if (self.options['DNMchart_mode'] == _cnsts.ANCESTOR and \
                    self.options['DNMtime_dir'] == _cnsts.TOP2BOTTOM) or \
                    (self.options['DNMchart_mode'] == _cnsts.DESCENDANT and
                    self.options['DNMtime_dir'] == _cnsts.BOTTOM2TOP):
                    viewBox = "%d %d %d %d" % (-self.rect_width/2,-height,width + self.rect_width,height)
                else:
                    viewBox = "%d %d %d %d" % (-self.rect_width/2,-self.rect_height/2,width + self.rect_width, height)
            strng += """
            <html:script>
                var svg_el = document.getElementById('AncestorChart');
                svg_el.setAttribute('viewBox',"%s");
            </html:script>
            """ % viewBox
        strng += self.get_html_search_options()
        strng += """</html:body></html:html>"""
        f.write(strng)
        return

    def get_html_search_options(self):
        """The generated webpage contains a search-form, this function 
        returns a string of html-JS to fill the select-element with options.

        Since the available options are only known after the svg was created,
        JS must be used to fill the select-element."""
        options = ''
        if len(filter(lambda x: x[-4:]=='Date',self.search_subjects.keys())) > 1:
            self.search_subjects['Date'] = '_date'
        if len(filter(lambda x: x[-5:]=='Place',self.search_subjects.keys())) > 1:
            self.search_subjects['Place'] = '_place'
        options = """<html:script>
            var search_subject_sel = document.getElementById('searchSubject');
        """
        for subj in sorted(self.search_subjects.keys()):
            options += "var opt = document.createElement('option');\n"
            if subj == 'Name':
                options += "opt.setAttribute('selected','selected');\n"
            localised_subj = _(subj)
            # special localisation for Event <role> and Event <attribute>
            if localised_subj == subj and subj[0:6] == 'Event ':
                localised_subj = _('Event') + subj[5:]
            options += """opt.setAttribute('value',"%s");
                opt.appendChild(document.createTextNode('%s'));
                search_subject_sel.appendChild(opt);
                """ % (self.search_subjects[subj]+":'",self.escbacka(localised_subj))
        options += "</html:script>"
        return options

    # I would like to include the DOCTYPE but then it gets hard to have the
    # object fill the whole content of the browser. Don't understand why.
    def write_old_browser_output(self):
        strng ="""<html>
            <head>
            <title>%s</title>
            <meta http-equiv="Content Type" content="text/html; charset=UTF-8" />
            </head>
            <body>
            <object data="%s" type="application/xhtml+xml" width="100%%" height="100%%">
            <!-- <object data="NavWebPage.html" type="text/html"> -->
            Your browser is incapable of representing this document. Get a good
            browser, for example <a href="http://www.mozilla.com">Firefox</a> or
            <a href="http://www.opera.com">Opera</a>, they are for "free".
            <!-- </object> -->
            </object>
            </body>
            </html>
        """ % (self.options['DNMtitle'],self.relpathA2B(\
                self.options['DNMfilename4old_browser'], self.target_path))
        try:
            f = open(self.options['DNMfilename4old_browser'],'w')
        except IOError,msg:
            ErrorDialog(_('Failure writing %s') % self.options['DNMfilename4old_browser'],msg)
            return
        f.write(strng)
        f.close()
        return

    # Functions for Pythagoras tree. Not used yet
    def nrAncestors(self,person_handle):
        """Return a hash with for each person in the list of ancestors of person
            the number of ancestors of that person."""
        if not person_handle:
            return
        rv = {}
        rv[person_handle] = 0
        person = self.database.get_person_from_handle(person_handle)
        family_handle = person.get_main_parents_family_handle()
        if family_handle:
            family = self.database.get_family_from_handle(family_handle)
            father_anc = self.nrAncestors(family.get_father_handle())
            if father_anc:
                rv.update(father_anc)
                rv[person_handle] += len(father_anc) + 1
            mother_anc = self.nrAncestors(family.get_mother_handle())
            if mother_anc:
                rv.update(mother_anc)
                rv[person_handle] += len(mother_anc) + 1
        return rv

#-------------------------------------------------------------------------
#
#
#
#-------------------------------------------------------------------------
class DenominoVisoOptions(MenuReportOptions):
    def __init__(self, name, dbase):
        self.db = dbase
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):
        category_name = _("DenominoViso Options")

        des = DestinationOption(_("Destination"),
            os.path.join(os.getcwd(),"DenominoViso.xhtml"))
        des.set_help(_("The destination file for the xhtml-content."))
        menu.add_option(category_name, "DNMfilename", des)

        pid = PersonOption(_("Central Person"))
        pid.set_help(_("The central person for the tree"))
        menu.add_option(category_name, "DNMpid", pid)

        title = StringOption(_("Title of the webpage"),'')
        title.set_help(_("Any string you wish."))
        menu.add_option(category_name, "DNMtitle", title)

        chart_mode = EnumeratedListOption("Display mode",_cnsts.ANCESTOR)
        chart_mode.set_help(_("Either plot ancestor or descendants graph."))
        for mode in _cnsts.chart_mode:
            chart_mode.add_item(mode[0],mode[1])
        menu.add_option(category_name, "DNMchart_mode", chart_mode)

        chart_type = EnumeratedListOption(_("Display type"),_cnsts.REGULAR)
        chart_type.set_help(_("The type of graph to create."))
        for type in _cnsts.chart_type:
            chart_type.add_item(type[0],type[1])
        menu.add_option(category_name, "DNMchart_type", chart_type)

        time_dir = EnumeratedListOption(_("Direction of time"),_cnsts.RIGHT2LEFT)
        time_dir.set_help(_("Direction in which time increases."))
        for dir in _cnsts.time_direction:
            time_dir.add_item(dir[0],dir[1])
        menu.add_option(category_name, "DNMtime_dir", time_dir)

        max_gen = NumberOption(_("Generations"), 10, 1, 100)
        max_gen.set_help(_("The number of generations to include in the tree"))
        menu.add_option(category_name, "DNMmax_generations", max_gen)

        tree_width = NumberOption(_("Max chart width (%)"), 50, 10, 100)
        tree_width.set_help(_("Width of the tree as fraction of the browser window"))
        menu.add_option(category_name, "DNMtree_width", tree_width)

        tree_height = NumberOption(_("Max chart height (px)"), 1000.0, 100.0,20000.0)
        tree_height.set_help(_("Height of the tree in pixels."))
        menu.add_option(category_name, "DNMheight", tree_height)

        copyright = TextOption(_("Closing remarks"),["Copyright ....",])
        copyright.set_help(_("List of strings, free text added at the bottom, for example for a copyright notice."))
        menu.add_option(category_name, "DNMcopyright", copyright)

        category_name = _("Include Options")

        # strange meaning true and false
        priv = BooleanOption(_("Include private records"), True)
        priv .set_help(_("Wheater to leave out private data."))
        menu.add_option(category_name, "DNMuse_privacy", priv)

        inc_events = MyBooleanOption(_("Include Events"), True)
        #inc_events = BooleanOption(_("Include Events"), True)
        inc_events.set_help(_("Wheather to include a person's events."))
        menu.add_option(category_name, "DNMinc_events", inc_events)

        #inc_all_events = BooleanOption(_("Include All Events"), True)
        #inc_all_events.set_help(_("Whether to include all events or only those where person is of role 'Primary'."))
        inc_all_events = CliOption(True)
        menu.add_option(category_name, "DNMall_events", inc_all_events)

        inc_childbirth = BooleanOption(_("Include birth children"), True)
        inc_childbirth.set_help(_("Whether to include the birth of children in the list of events."))
        menu.add_option(category_name, "DNMinc_child_birth", inc_childbirth)

        inc_deathrelatives = BooleanOption(_("Include death relatives"), False)
        inc_deathrelatives.set_help(_("Whether to include the death of relatives during the lifetime of person."))
        menu.add_option(category_name, "DNMinc_death_relative", inc_deathrelatives)

        inc_witnessnote = BooleanOption(_("Include witness note"), False)
        inc_witnessnote.set_help(_("Whether to include the note belonging to a witness (if the event_format contains <witnesses>)"))
        menu.add_option(category_name, "DNMinc_witness_note", inc_witnessnote)

        #inc_attributes = BooleanOption(_("Include Attributes"), False)
        inc_attributes = IncAttributeOption(_("Include Attributes"), "True,")
        inc_attributes.set_help(_("Whether to include a person's attributes"))
        menu.add_option(category_name, "DNMinc_attributes_m", inc_attributes)

        inc_addresses = BooleanOption(_("Include Addresses"), False)
        inc_addresses.set_help(_("Whether to include a person's addresses."))
        menu.add_option(category_name, "DNMinc_addresses", inc_addresses)

        inc_notes = BooleanOption(_("Include Note"), False)
        inc_notes.set_help(_("Whether to include a person's note."))
        menu.add_option(category_name, "DNMinc_notes", inc_notes)

        self.__inc_url = BooleanOption(_("Include URL"), False)
        self.__inc_url.set_help(_("Whether to include a person's internet address."))
        menu.add_option(category_name, "DNMinc_url", self.__inc_url)

        self.__inc_url_desc = BooleanOption(_("Include URL description"), False)
        self.__inc_url_desc.set_help(_("Whether to include the description of the first URL"))
        menu.add_option(category_name, "DNMinc_url_desc", self.__inc_url_desc)
        self.__inc_url.connect('value-changed',
            lambda : self.__inc_url_desc.set_available(self.__inc_url.get_value()))

        inc_sources = BooleanOption(_("Include Sources"), False)
        inc_sources.set_help(_("Whether to include a person's sources."))
        menu.add_option(category_name, "DNMinc_sources", inc_sources)

        category_name = _("Image Options")

        inc_img = BooleanOption(_("Include Photos/Images from Gallery"), False)
        inc_img.set_help(_("Whether to include images"))
        menu.add_option(category_name, "DNMinc_img", inc_img)

        copy_img = CopyImgOption(_("Copy Image"), "False, " + os.getcwd())
        copy_img.set_help(_("Copy the images to a designated directory."))
        menu.add_option(category_name, "DNMcopy_img_m", copy_img)

        seq_img_name = CliOption(0)
        menu.add_option(category_name, "DNMuse_sequential_photoname", seq_img_name)

        image_selection = ImageIncludeAttrOption(_("Images with Attribute"),"0, , ")
        image_selection.set_help(_("Determine images with which attributes to in/exclude"))
        menu.add_option(category_name, "DNMimg_attr_m", image_selection)

        inc_img_src_ref = BooleanOption(_("Include Image source references"), False)
        inc_img_src_ref.set_help(_("Whether to include references for images"))
        menu.add_option(category_name, "DNMinc_img_src_ref", inc_img_src_ref)

        img_src_ref_str = EnumeratedListOption(_("Source reference attribute"),'Publishable')
        img_src_ref_str.set_help(_("Image attribute that should be used as source reference"))
        for attr in self.db.get_media_attribute_types():
            img_src_ref_str.add_item(attr,attr)
        #img_src_ref_str.add_item("Publishable","Publishable")
        menu.add_option(category_name, "DNMimg_src_ref_str", img_src_ref_str)

        category_name = _("Style Options")

        activated_color = ColorOption(_("Color of active person:"),"#ffff00")
        activated_color.set_help(_("RGB-color of geometric shape of the activated person."))
        menu.add_option(category_name, "DNMactivated_color", activated_color)

        found_color = ColorOption(_("Color of found persons:"),"#ff0000")
        found_color.set_help(_("RGB-color of geometric shape of the persons found."))
        menu.add_option(category_name, "DNMfound_color", found_color)

        male_color = ColorOption(_("Color of male persons:"),"#000066")
        male_color.set_help(_("RGB-color of geometric shape of the male persons."))
        menu.add_option(category_name, "DNMmale_color", male_color)

        female_color = ColorOption(_("Colour of female persons:"),"#660000")
        female_color.set_help(_("RGB-color of geometric shape of the female persons."))
        menu.add_option(category_name, "DNMfemale_color", female_color)

        rect_width = NumberOption(_("Width of rectangle (hrd):"), 0.66, 0.1, 1.0, 0.01)
        rect_width.set_help(_(""))
        menu.add_option(category_name, "DNMrect_width", rect_width)

        rect_height = NumberOption(_("Height of rectangle (hrd):"), 0.16, 0.1, 20.0, 0.01)
        rect_height.set_help(_(""))
        menu.add_option(category_name, "DNMrect_height", rect_height)

        rect_ydist = NumberOption(_("Vertical distance of rectangles (hrd):"), 0.19, 0.1, 20.0, 0.01)
        rect_ydist.set_help(_(""))
        menu.add_option(category_name, "DNMrect_ydist", rect_ydist)

        free_style = TextOption(_("Extra style settings:"),("span.witnesses" + " {font-size: smaller;}","span.bron {font-size: smaller;}"))
        free_style.set_help(_(""))
        menu.add_option(category_name, "DNMfree_style", free_style)

        category_name = _("Advanced Options")

        html_wrapper = HtmlWrapperOption(_("Old browser friendly output"),"False, ")
        html_wrapper.set_help(_("Whether to create an ordinary html-file that includes the xhtml-file so that deprecated browsers can be presented with content they can swallow."))
        menu.add_option(category_name, "DNMold_browser_output_m", html_wrapper)

        mouse_handler = MouseHandlerOption(_("Mouse event handler"), \
            _cnsts.ONCLICK)
        mouse_handler.set_help(_("Mouse handler used to interact with visitor of webpage."))
        menu.add_option(category_name, "DNMclick_over", mouse_handler)

        child_ref_types = ChildRefType().get_standard_xml() #nakijken
        line_style = LineStyleOption(_("Birth relationship linestyle"), \
            [str([i, False, 10L, 10L]) for i in child_ref_types])
        line_style.set_help(_("List of lists where each sublist is a list with information about the dash pattern of lines connecting children to parents."))
        #menu.add_option(category_name, "DNMline_style", line_style)
        menu.add_option(category_name, "DNMdash_child_rel", line_style)

        ext_confidence_keys = ext_confidence.keys()
        ext_confidence_keys.sort()
        confidence_color = ConfidenceColorOption(_("Source confidence color"),\
            [str([i, '#000000']) for i in ext_confidence_keys])
        confidence_color.set_help(_("List os lists where each sublist is a list with information on the color to use for a certain confidence level."))
        menu.add_option(category_name, 'DNMconf_color', confidence_color)

        event_format = TextOption(_("Event format"),["<" + _('date') + ">",
            "<" + _('role') + "> " + _('at'),
            "<" + _('type') + ">:",
            "<" + _('description') + ">",
            "in <" + _('place') + ">"])
        event_format.set_help(_("List os strings with placeholders for events. Known placeholders: <type>, <role>, <date>, <place>, <description>, <witnesses>, <source> and any <attribute-value>."))
        menu.add_option(category_name, "DNMevent_format", event_format)

        source_format = TextOption(_("Source format"),["<" + _('title') + ">",])
        source_format.set_help(_("List of strings with placeholders for sources. Known placeholders: <title>, <volume>, <author>, <publication_info> and <abbreviation>."))
        menu.add_option(category_name, "DNMsource_format", source_format)

        address_sep = CliOption(', ')
        menu.add_option(category_name, "DNMaddress_separator", address_sep)

#-------------------------------------------------------------------------
# Own option
#-------------------------------------------------------------------------
class MyBooleanOption(PlugOption):
    def __init__(self, label, value):
        PlugOption.__init__(self, label, value)

class MyGuiBooleanOption(gtk.CheckButton):
    def __init__(self, option, dbstate, uistate, track):
        self.__option = option
        gtk.CheckButton.__init__(self, "")
        self.set_active(self.__option.get_value())
        self.connect('toggled', self.__value_changed)
        # FIXME:
        #tooltip.set_tip(self, self.__option.get_help())
        self.__option.connect('avail-changed', self.__update_avail)
        self.__update_avail()

    def __value_changed(self, obj):
        self.__option.set_value(self.get_active())

    def __update_avail(self):
        avail = self.__option.get_available()
        self.set_sensitive(avail)


class CliOption(PlugOption):
    """Option without a corresponding widget, only for cli"""
    def __init__(self, value):
        PlugOption.__init__(self, '', value)

class GuiCliOption(gtk.HBox):
    def __init__(self, option, dbstate, uistate, track):
        pass

class IncAttributeOption(PlugOption):
    """Option to ask for the inclusion of attributes."""
    def __init__(self, label, value):
        """value: comma seperated string of attributes preceded by True/False"""
        PlugOption.__init__(self, label, value)

class GuiIncAttributeOption(gtk.HBox):
    """Megawidget consisting of a checkbutton, label and entry box to
        ask if and which attributes should be included in the output"""
    def __init__(self, option, dbstate, uistate, track):
        gtk.HBox.__init__(self)
        self.__option = option
        value_str = self.__option.get_value()
        (attr_inc, attr_list) = value_str.split(',',1)
        attr_list = attr_list.strip()
        self.cb_w = gtk.CheckButton("")
        self.cb_w.connect('toggled', self.__value_changed)
        self.l_w = gtk.Label(_('restricted to:'))
        self.l_w.set_sensitive(False)
        self.e_w = gtk.Entry()
        self.e_w.set_text(attr_list)
        self.e_w.connect('changed', self.__value_changed)
        self.e_w.set_sensitive(False)
        self.cb_w.set_active(attr_inc == 'True')
        self.pack_start(self.cb_w, False)
        self.pack_end(self.e_w, False)
        self.pack_end(self.l_w, False)
        # FIXME
        #tooltip.set_tip(self, self.__option.get_help())

    def __value_changed(self, obj):
        attr_inc = self.cb_w.get_active()
        self.l_w.set_sensitive(attr_inc)
        self.e_w.set_sensitive(attr_inc)
        self.__option.set_value(str(attr_inc) + ", " + self.e_w.get_text())

class CopyImgOption(PlugOption):
    """Option to ask if images should be copied to a separate directory"""
    def __init__(self, label, value):
        """value: directory name preceded by True/False"""
        PlugOption.__init__(self, label, value)

#class GuiCopyImgOption_new(GuiOptionalFileEntry):
#    def __init__(self, option, dbstate, uistate, track, tooltip):
#        GuiOptionalFileEntry(self, option, dbstate, uistate, track, tooltip)
#        self.l_w.set_label(_("to directory:"))
#        self.fe_w.title = _("Save images in ...")

class GuiCopyImgOption(gtk.HBox):
    """Megawidget consisting of a checkbutton, label and FileEntry widget to
        ask if images should be copied to a separate directory"""
    def __init__(self, option, dbstate, uistate, track):
        gtk.HBox.__init__(self)
        self.__option = option
        value_str = self.__option.get_value()
        (copy_img, copy_dir) = value_str.split(', ',1)
        self.cb_w = gtk.CheckButton("")
        self.cb_w.connect('toggled', self.__value_changed)
        self.l_w = gtk.Label(_('to directory:'))
        self.l_w.set_sensitive(False)
        self.fe_w = FileEntry(copy_dir, _('Save images in ...'))
        self.fe_w.set_directory_entry(True)
        self.fe_w.entry.connect('changed', self.__value_changed)
        #self.fe_w.connect('changed', self.__value_changed)
        # Update ReportBase/_FileEntry.py so that signal changed is OK
        self.fe_w.set_sensitive(False)
        self.cb_w.set_active(copy_img == 'True')
        self.pack_start(self.cb_w, False)
        self.pack_end(self.fe_w, False)
        self.pack_end(self.l_w, False)
        # FIXME:
        #tooltip.set_tip(self, self.__option.get_help())

    def __value_changed(self, obj):
        copy_img = self.cb_w.get_active()
        self.l_w.set_sensitive(copy_img)
        self.fe_w.set_sensitive(copy_img)
        self.__option.set_value(str(copy_img) + ", " + unicode(self.fe_w.get_full_path(0)))

class ImageIncludeAttrOption(PlugOption):
    """Option allowing attributes on images to determine their inclusion in
        the output."""
    def __init__(self, label, value):
        """value: attribute name, attribute value, include/exclude"""
        PlugOption.__init__(self, label, value)

class GuiImageIncludeAttrOption(gtk.HBox):
    """Megawidget consisting of attribute selection, label, attribute value
        entry, label and include/exclude selection to ask which images with
        with which attributes should be included/excluded."""
    def __init__(self, option, dbstate, uistate, track):
        gtk.HBox.__init__(self)
        self.__option = option
        value_str = self.__option.get_value()
        (incl, attr, attr_value) = value_str.split(', ',2)
        incl = int(incl)
        self.cbe_w = gtk.ComboBoxEntry()
        image_attributes = dbstate.db.get_media_attribute_types()
        image_attributes.insert(0,' ')
        AutoComp.fill_combo(self.cbe_w, image_attributes)
        try:
            idx = image_attributes.index(attr)
            self.cbe_w.set_active(idx)
        except ValueError:
            pass
        self.cbe_w.connect('changed',self.__value_changed)
        self.l1_w = gtk.Label(_("equal to"))
        self.e_w = gtk.Entry()
        self.e_w.set_text(attr_value)
        self.e_w.connect('changed',self.__value_changed)
        self.l2_w = gtk.Label(_("should be"))
        self.cb2_w = gtk.combo_box_new_text()
        self.cb2_w.append_text('Included')
        self.cb2_w.append_text('Excluded')
        self.cb2_w.set_active(incl)
        self.cb2_w.connect('changed',self.__value_changed)
        self.pack_start(self.cbe_w, False)
        self.pack_start(self.l1_w, False)
        self.pack_start(self.e_w, False)
        self.pack_start(self.l2_w, False)
        self.pack_start(self.cb2_w, False)

    def __value_changed(self, obj):
        new_val = str(int(self.cb2_w.get_active())) + ", " + self.cbe_w.get_active_text() + ", " + str(self.e_w.get_text())
        self.__option.set_value(new_val)

# ImageSouceAttrOption
# "Use Image Attribute" EnumeratedList Label(_("as source reference"))

# HTMLWrapper
# "Old browser friendly output CheckButton Label(_("Name HTML-wrapper file")) FileEntry
class HtmlWrapperOption(PlugOption):
    """Option to ask if a html-wrapper file should be created"""
    def __init__(self, label, value):
        """value: True/False, filename"""
        PlugOption.__init__(self, label, value)

#class GuiHtmlWrapperOption_new(GuiOptionalFileEntry):
#    def __init__(self, option, dbstate, uistate, track, tooltip):
#        GuiOptionalFileEntry.__init__(self, option, dbstate, uistate, track, tooltip)
#        self.l_w.set_label(_("Name HTML-wrapper file"))
#        self.fe_w.title = _("Save HTML-wrapper file as ...")

class GuiHtmlWrapperOption(gtk.HBox):
    """Megawidget consisting of a checkbutton and file entry box"""
    def __init__(self, option, dbstate, uistate, track):
        gtk.HBox.__init__(self)
        self.__option = option
        value_str = self.__option.get_value()
        (wrap_html, html_file) = value_str.split(', ',1)
        self.cb_w = gtk.CheckButton("")
        self.cb_w.connect('toggled', self.__value_changed)
        self.l_w = gtk.Label(_("Name HTML-wrapper file"))
        self.l_w.set_sensitive(False)
        self.fe_w = FileEntry(html_file, _("Save HTML-wrapper file as ..."))
        #self.fe_w.connect('changed', self.__value_changed)
        self.fe_w.set_sensitive(False)
        self.cb_w.set_active(wrap_html == 'True')
        self.pack_start(self.cb_w, False)
        self.pack_start(self.l_w, False)
        self.pack_start(self.fe_w, False)
        # FIXME:
        #tooltip.set_tip(self, self.__option.get_help())

    def __value_changed(self, obj):
        wrap_html = self.cb_w.get_active()
        self.l_w.set_sensitive(wrap_html)
        self.fe_w.set_sensitive(wrap_html)
        self.__option.set_value(str(wrap_html) + ", " + unicode(self.fe_w.get_full_path(0)))

# 
class GuiOptionalFileEntry(gtk.HBox):
    def __init__(self, option, dbstate, uistate, track):
        gtk.HBox.__init__(self)
        self.__option = option
        value_str = self.__option.get_value()
        (on_off_state, filename) = value_str.split(',',1)
        self.cb_w = gtk.CheckButton("")
        self.cb_w.connect('toggled', self.__value_changed)
        self.l_w = gtk.Label("")
        self.l_w.set_sensitive(False)
        self.fe_w = FileEntry(filename, _("Give a filename ..."))
        #self.fe_w.connect('changed', self.__value_changed)
        self.fe_w.set_sensitive(False)
        self.cb_w.set_active(on_off_state == 'True')
        self.pack_start(self.cb_w, False)
        self.pack_start(self.l_w, False)
        self.pack_start(self.fe_w, False)
        # FIXME
        #tooltip.set_tip(self, self.__option.get_help())

    def __value_changed(self, obj):
        on_off_state = self.cb_w.get_active()
        self.l_w.set_sensitive(on_off_state)
        self.fe_w.set_sensitive(on_off_state)
        self.__option.set_value(str(on_off_state) + ", " + unicode(self.fe_w.get_full_path(0)))

    def get_inner_label(self):
        return self.l_w.get_label()

    def set_inner_label(self, new_label):
        self.l_w.set_label(new_label)

    def get_dialog_title(self):
        return self.fe_w.title

    def set_dialog_title(self, new_title):
        self.fe_w.title = new_title

# MouseHandlerOption
# "Mouse event handler:" RadioButton("onclick") RadioButton("onmouseover")
class MouseHandlerOption(PlugOption):
    """Option to ask if a html-wrapper file should be created"""
    def __init__(self, label, value):
        """value: """
        PlugOption.__init__(self, label, value)

class GuiMouseHandlerOption(gtk.HBox):
    """Megawidget consisting of two radio buttons to chose mouse behavior"""
    def __init__(self, option, dbstate, uistate, track):
        mousegroup = None
        gtk.HBox.__init__(self)
        self.__option = option
        self.r1_w = gtk.RadioButton(mousegroup, 'onclick')
        if not mousegroup:
            mousegroup = self.r1_w
        self.r2_w = gtk.RadioButton(mousegroup, 'onmouseover')
        self.pack_start(self.r1_w, False)
        self.pack_start(self.r2_w, False)
        self.r2_w.set_active(self.__option.get_value())
        self.r2_w.connect('toggled', self.__value_changed)
        # FIXME:
        #tooltip.set_tip(self, self.__option.get_help())

    def __value_changed(self, obj):
        self.__option.set_value(int(self.r2_w.get_active()))

# LinestyleOption
# "Birth relationship linestyle:" 


class GuiTableOption(gtk.ScrolledWindow):
    # column_titles = [] ; Relation type, Use dashed linestyle, Dash length, Inter-dash length
    # signals = [] ; ,toggled, edited, edited
    def __init__(self, data, editable_column = None):
        """data should be a 2D list of lists"""
        gtk.ScrolledWindow.__init__(self)
        self.set_shadow_type(gtk.SHADOW_IN)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        lstore = self.create_lstore(data)
        self.tv_w = self.create_treeview(lstore, data, editable_column)
        # set column titles
        self.add(self.tv_w)

    def create_lstore(self,list_of_lists):
        lstore_args = []
        for cell in list_of_lists[0]:
            if type(cell) == type("string"):
                lstore_args.append(gobject.TYPE_STRING)
            elif type(cell) == type(1):
                lstore_args.append(gobject.TYPE_UINT)
            elif type(cell) == type(1L):
                lstore_args.append(gobject.TYPE_LONG)
            elif type(cell) == type(False):
                lstore_args.append(gobject.TYPE_BOOLEAN)
            else:
                raise TypeError
        lstore = gtk.ListStore(*lstore_args)
        for row in list_of_lists:
            iter = lstore.append()
            index_values = []
            for i,v in enumerate(row):
                index_values.append(i)
                index_values.append(v)
            lstore.set(iter,*index_values)
        return lstore

    def create_treeview(self, lstore, list_of_lists, editable_column = None):
        treeview = gtk.TreeView(lstore)
        treeview.set_rules_hint(True)
        treeview.get_selection().set_mode(gtk.SELECTION_SINGLE)
        for i,v in enumerate(list_of_lists[0]):
            if type(v) == type("string") or type(v) == type(1) or \
                    type(v) == type(1L):
                renderer = gtk.CellRendererText()
                if editable_column or editable_column == 0:
                    column = gtk.TreeViewColumn('',renderer, text=i, \
                            editable = editable_column)
                else:
                    column = gtk.TreeViewColumn('',renderer, text=i)
            elif type(v) == type(False):
                renderer = gtk.CellRendererToggle()
                column = gtk.TreeViewColumn('',renderer, active=i)
            else:
                raise TypeError
            treeview.append_column(column)
        return treeview

    def get_column(self, i):
        return self.tv_w.get_column(i)

    def get_treeview(self):
        return self.tv_w

    def list_of_strings2list_of_lists(self, data):
        if type(data[0]) == type([]):
            return data
        else:
            rv = []
            for i in data:
                if i[0] != '[' or i[-1] != ']':
                    raise TypeError('invalid list-option value')
                rv.append(eval(i))
            return rv

class LineStyleOption(PlugOption):
    def __init__(self, label, value):
        """value: list of strings, where each string is a str(list)"""
        PlugOption.__init__(self, label, value)

class GuiLineStyleOption(GuiTableOption):
    def __init__(self, option, dbstate, uistate, track):
        self.__option = option
        data = []
        for row in self.list_of_strings2list_of_lists(self.__option.get_value()):
            data.append(row[:])
        GuiTableOption.__init__(self, data, _cnsts.USE_DASH_COLUMN)
        column = self.get_column(_cnsts.BIRTH_REL_COLUMN)
        column.set_title(_('Relation type'))
        cellRenderer = column.get_cell_renderers()[0]
        # editable attribute is not wanted on this column.
        column.set_attributes(cellRenderer,text=0)
        column = self.get_column(_cnsts.USE_DASH_COLUMN)
        column.set_title(_('Use dashed linestyle'))
        tv = self.get_treeview()
        cellRenderer = column.get_cell_renderers()[0]
        cellRenderer.connect('toggled', self.dash_toggled, tv.get_model())
        column = self.get_column(_cnsts.DASH_LENGTH_COLUMN)
        column.set_title(_('Dash length'))
        cellRenderer = column.get_cell_renderers()[0]
        cellRenderer.connect('edited',self.on_dash_length_edited,tv.get_model())
        column = self.get_column(_cnsts.INTER_DASH_LENGTH_COLUMN)
        column.set_title(_('Inter-dash length'))
        cellRenderer = column.get_cell_renderers()[0]
        cellRenderer.connect('edited', self.on_inter_dash_length_edited, \
                tv.get_model())

    def dash_toggled(self, cell, path, model):
        # set sensitivity of dash-length and inter-dash-length cell.
        iter = model.get_iter((int(path),))
        dashed = model.get_value(iter,_cnsts.USE_DASH_COLUMN)
        dashed = not dashed
        model.set(iter,_cnsts.USE_DASH_COLUMN,dashed)
        self.__value_changed(model)

    def on_dash_length_edited(self, cell, path_string, new_text, model):
        iter = model.get_iter_from_string(path_string)
        dash_length = int(new_text)
        if dash_length > 100: dash_length = 100
        if dash_length < 0: dash_length = 0
        model.set(iter,_cnsts.DASH_LENGTH_COLUMN,dash_length)
        self.__value_changed(model)

    def on_inter_dash_length_edited(self, cell, path_string, new_text, model):
        iter = model.get_iter_from_string(path_string)
        inter_dash_length = int(new_text)
        if inter_dash_length > 100: inter_dash_length = 100
        if inter_dash_length < 0: inter_dash_length = 0
        model.set(iter,_cnsts.INTER_DASH_LENGTH_COLUMN,inter_dash_length)
        self.__value_changed(model)

    def __value_changed(self, model):
        new_val = []
        for row in model:
            new_val.append([j for j in row])
        self.__option.set_value(new_val)

# ConfidenceColor
# "Source confidence color"
class ConfidenceColorOption(PlugOption):
    def __init__(self, label, value):
        """value: list of strings, where each string is a str(list)"""
        PlugOption.__init__(self, label, value)

class GuiConfidenceColorOption(GuiTableOption):
    def __init__(self, option, dbstate, uistate, track):
        self.__option = option
        data = []
        for row in self.list_of_strings2list_of_lists(self.__option.get_value()):
            data.append(row[:])
            data[-1][0] = ext_confidence[row[0]] # num conf to string
        GuiTableOption.__init__(self, data)
        column = self.get_column(_cnsts.CONFIDENCE_COLUMN)
        column.set_title(_('Confidence'))
        column = self.get_column(_cnsts.COLOR_COLUMN)
        column.set_title(_('Color'))
        tv = self.get_treeview()
        cellRenderer = column.get_cell_renderers()[0]
        cellRenderer.set_property('editable',True)
        cellRenderer.connect('edited', self.__value_changed, tv.get_model())
        # FIXME:
        #tooltip.set_tip(self, self.__option.get_help())

    def __value_changed(self, cell, path_string, new_text, model):
        """ "['None', False, 10L, 10L]" """
        """ "[0, '#000000']" """
        if len(new_text) != 7 or new_text[0] != '#' or \
                re.search('[^0-9a-fA-F]',new_text[1:]):
            # why is there no $ at the end of the Regular Expression?
            return
        iter = model.get_iter_from_string(path_string)
        model.set(iter, _cnsts.COLOR_COLUMN, str(new_text))
        new_val = []
        for row in model:
            new_val.append([j for j in row])
            # store numerical confidence instead of string
            new_val[-1][0] = ext_confidence.keys()[ext_confidence.values().index(row[0])]
        self.__option.set_value(new_val)

from gen.plug import BasePluginManager

pmgr = BasePluginManager.get_instance()

pmgr.register_option(MyBooleanOption, MyGuiBooleanOption)
pmgr.register_option(IncAttributeOption, GuiIncAttributeOption)
pmgr.register_option(CopyImgOption, GuiCopyImgOption)
pmgr.register_option(ImageIncludeAttrOption, GuiImageIncludeAttrOption)
pmgr.register_option(HtmlWrapperOption, GuiHtmlWrapperOption)
pmgr.register_option(MouseHandlerOption, GuiMouseHandlerOption)
pmgr.register_option(LineStyleOption, GuiLineStyleOption)
pmgr.register_option(ConfidenceColorOption, GuiConfidenceColorOption)
pmgr.register_option(CliOption, GuiCliOption)
