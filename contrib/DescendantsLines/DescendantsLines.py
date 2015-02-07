#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010 Adam Sampson <ats-familytree@offog.org>
# Copyright (C) 2010 Jerome Rapinat <romjerome@yahoo.fr>
# Copyright (C) 2010, 2012 lcc <lcc.mailaddress@gmail.com>
# Copyright (C) 2015 Don Piercy
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
# This program is based on the program located at
# http://offog.org/darcs/misccode/familytree. The license for that
# program is found at http://offog.org/darcs/misccode/NOTES.
# Distributed under the terms of the X11 license:
#
#  Copyright 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007,
#    2008, 2009, 2010, 2011 Adam Sampson <ats@offog.org>
#
#  Permission is hereby granted, free of charge, to any person obtaining a
#  copy of this software and associated documentation files (the
#  "Software"), to deal in the Software without restriction, including
#  without limitation the rights to use, copy, modify, merge, publish,
#  distribute, sublicense, and/or sell copies of the Software, and to
#  permit persons to whom the Software is furnished to do so, subject to
#  the following conditions:
#
#  The above copyright notice and this permission notice shall be included
#  in all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
#  OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#  MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL ADAM SAMPSON BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#  DEALINGS IN THE SOFTWARE.
#
"""
Descendants Lines - Generate a Descendant's Tree Chart - Graphic plugin for GRAMPS

Can display the Name, Image and selected Events for the head person and all descendants
Events may include, type, date, place & description, formatted as per the options menu.
Each person is linked by connection lines showing families (Spouse(s) & any children)
"""

from __future__ import print_function, unicode_literals

#-------------------------------------------------------------------------
#
# python modules
#
#-------------------------------------------------------------------------
import cairo
from gi.repository import Gtk
import getopt
import sys
import io
import os.path
import copy
import re
#-------------------------------------------------------------------------
#
# gramps modules
#
#-------------------------------------------------------------------------

import gramps.gen.datehandler
from gramps.gen.plug.menu import (TextOption, NumberOption, PersonOption, FilterOption, 
		DestinationOption, BooleanOption, EnumeratedListOption, StringOption)
from gramps.gen.plug.report import Report
from gramps.gen.plug.report import utils as ReportUtils
from gramps.gen.plug.report import MenuReportOptions
from gramps.gui.thumbnails import get_thumbnail_path    #for images
from gramps.gen.utils.file import media_path_full
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
from gramps.gen.plug.docgen import (IndexMark, FontStyle, ParagraphStyle, 
                             FONT_SANS_SERIF, FONT_SERIF, 
                             INDEX_TYPE_TOC, PARA_ALIGN_LEFT)
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.const import USER_HOME, USER_PLUGINS
import gramps.gen.lib
from gramps.plugins.lib.libtreebase import *    # for CalcLines
from gramps.plugins.lib.libsubstkeyword import (SubstKeywords, EventFormat, NameFormat,
                        ConsumableString, VarString)  # for name/event/date/place string formatting
from substkw import SubstKeywords2		# Modified version of portions of libsubstkeywords.py
from gramps.gen.lib.eventtype import EventType      # for selecting event types 
from gramps.gen.lib.eventroletype import EventRoleType	# for role in events = PRIMARY
from gramps.gen.lib.date import NextYear    # for sorting events with unknown dates
#-------------------------------------------------------------------------
#
# Set up Logging
#
#-------------------------------------------------------------------------
import logging
log = logging.getLogger("DescendantsLines")

#-------------------------------------------------------------------------
#
# variables
#
#-------------------------------------------------------------------------
S_DOWN = 20
S_UP = 10
S_VPAD = 10
FL_PAD = 20
OL_PAD = 10
O_DOWN = 30
C_PAD = 10
F_PAD = 20
C_UP = 15
SP_PAD = 10
MIN_C_WIDTH = 40
TEXT_PAD = 2
TEXT_LINE_PAD = 2
OUTPUT_FMT = 'PNG'
OUTPUT_FN = None
gender_colors = False
INC_PLACES = False
INC_MARRIAGES = False
INC_DNUM = False
MAX_GENERATION = 0
TEXT_ALIGNMENT = 'center'   # 'center', 'left'
STROKE_RECTANGLE = False

# Static variable for do_person()
CUR_GENERATION = 0
global HIGH_GENERATION # tracks the highest generation in chart, used for fill colour generation
HIGH_GENERATION = 0

# extra Padding for STROKE_RECTANGLE == True
RECTANGLE_TEXT_PAD = 1
IMAGE_PAD = 2

global BACKGROUND_COLOR
global FOREGROUND_COLOR
BACKGROUND_COLOR = (1.0, 1.0, 1.0)
FOREGROUND_COLOR = (1.0, 1.0, 1.0)
LINE_DARKNESS = 256

GRAMPS_DB = None
INC_IMAGE = True
MAX_IMAGE_H = 0
MAX_IMAGE_W = 0
IMAGE_LOC = None

REPLACEMENT_LIST = None

ctx = None
font_name = 'sans-serif'
base_font_size = 12

_event_cache = {}

def find_event(database, handle):
    if handle in _event_cache:
        obj = _event_cache[handle]
    else:
        obj = database.get_event_from_handle(handle)
        _event_cache[handle] = obj
    return obj
    
def event_type(event_name):
    """ returns the event types number if it matches the event_name string """
    for i in range(0, len(EventType._DATAMAP)):
        if event_name.capitalize() == EventType._DATAMAP[i][2]:
            return(EventType._DATAMAP[i][0])
    return(None)

def parse_event_disp(line):
    """
    Parse an event display option line
    convert the text event names into DB event types
    [event_type_list](event_format)
    """
    etl = []
    ef = ''
    r = re.search(r'(?P<el>\[[\w, ]*\])(?P<ef>.*)', line)
    if r:
        x = r.group('el')
        y = x.replace(' ','')
        el = y[1:-1].split(',')
        if el:
            for event_name in el:
                etype = event_type(event_name)
                log.debug('    Parse Event=%s ET=%s', event_name, etype)
                if etype:
                    etl.append(etype)
                else:
                    log.warning('Event type "%s" NOT found', event_name)
        ef = r.group('ef')
        log.debug('  Parsed event display list=%s, fmt=%s', etl, ef)
    return(etl, ef)


class DescendantsLinesReport(Report):
    """
    DescendantsLines Report class - Initialized and write_report are called by GRAMPS's report plugin feature
    """
    def __init__(self, database, options_class, user):
        """
        Create the object that produces the report.
        
        The arguments are:

        database        - the GRAMPS database instance
        options_class   - instance of the Options class for this report
        user            - a gen.user.User() instance
        
        This report needs the following parameters (class variables)
        that come in the options class.

        S_DOWN - The length of the vertical edge from descendant to spouse-bar
        S_UP - The length of the vertical edge from spouse-bar to spouse
        S_VPAD
        FL_PAD
        OL_PAD
        O_DOWN - The length of the vertical edge from spouse-bar to child-bar
        C_PAD
        F_PAD
        C_UP - The length of the vertical edge from child to child-bar
        SP_PAD
        MIN_C_WIDTH
        TEXT_PAD
        TEXT_LINE_PAD
        output_fmt - The output format
        output_fn - The output filename
        max_gen - Maximum number of generations to include. (0 for unlimited)
        gender_colors - Whether to use colored names indicating person gender in the output.
        name_disp - The name format
        inc_dnum - Whether to use d'Aboville descendant numbering system
        style - The predefined output style
        inc_image -
        replace_list - 
        """

        Report.__init__(self, database, options_class, user)
        self.options = {}
        menu = options_class.menu
        
        self.database = database
        global GRAMPS_DB
        GRAMPS_DB = database
        #log.debug('dB= %s', GRAMPS_DB)
        
        for name in menu.get_all_option_names():
            self.options[name] = menu.get_option_by_name(name).get_value()

        global S_DOWN
        global S_UP
        global S_VPAD
        global FL_PAD
        global OL_PAD
        global O_DOWN
        global C_PAD
        global F_PAD
        global C_UP
        global SP_PAD
        global MIN_C_WIDTH
        global TEXT_PAD
        global TEXT_LINE_PAD
        S_DOWN = self.options["S_DOWN"]
        S_UP = self.options["S_UP"]
        S_VPAD = self.options["S_VPAD"]
        FL_PAD = self.options["FL_PAD"]
        OL_PAD = self.options["OL_PAD"]
        O_DOWN = self.options["O_DOWN"]
        C_PAD = self.options["C_PAD"]
        F_PAD = self.options["F_PAD"]
        C_UP = self.options["C_UP"]
        SP_PAD = self.options["SP_PAD"]
        MIN_C_WIDTH = self.options["MIN_C_WIDTH"]
        TEXT_PAD = self.options["TEXT_PAD"]
        TEXT_LINE_PAD = self.options["TEXT_LINE_PAD"]

        self.output_fmt = self.options['output_fmt']
        self.output_fn = self.options['output_fn']
        self.max_gen = self.options['max_gen']
        self.gender_colors = self.options['gender_colors']
        self.inc_dnum = self.options['inc_dnum']
        global OUTPUT_FMT
        global OUTPUT_FN
        global MAX_GENERATION
        global GENDER_COLORS
        global FILL_COLORS
        global TEXT_ALIGNMENT
        global STROKE_RECTANGLE
        global MAX_NOTE_LEN
        global INC_DNUM
        OUTPUT_FMT = self.output_fmt
        OUTPUT_FN = self.output_fn
        MAX_GENERATION = self.max_gen
        GENDER_COLORS = self.gender_colors
        FILL_COLORS = self.options['fill_colors']
        TEXT_ALIGNMENT = self.options['text_alignment']
        STROKE_RECTANGLE = self.options['stroke_rectangle']
        MAX_NOTE_LEN = self.options['max_note_len']

        INC_DNUM = self.inc_dnum
        
        global INC_IMAGE
        global MAX_IMAGE_H
        global MAX_IMAGE_W
        global IMAGE_LOC
        global REPLACEMENT_LIST
        INC_IMAGE = self.options['inc_image']
        MAX_IMAGE_H = float(self.options['image_h'])
        MAX_IMAGE_W = float(self.options['image_w'])
        IMAGE_LOC = self.options['image_loc']
        REPLACEMENT_LIST = self.options['replace_list']
        
        global DESCEND_ALPHA
        global SPOUSE_ALPHA
        DESCEND_ALPHA = self.options['descend_alpha']
        SPOUSE_ALPHA = self.options['spouse_alpha']
        #LINE_ALPHA = constant for now (see above)
        
        global PROTECT_PRIVATE
        PROTECT_PRIVATE = self.options['protect_private']
        global PRIVATE_TEXT
        PRIVATE_TEXT = self.options['private_text']
        global NAME_FORMAT
        NAME_FORMAT = self.options['name_disp']
        
        global OR_SIMILAR_EVENTS
        OR_SIMILAR_EVENTS = {EventType.BIRTH: (EventType.BIRTH, EventType.BAPTISM, EventType.CHRISTEN),
            EventType.DEATH: (EventType.DEATH, EventType.BURIAL, EventType.CREMATION, EventType.PROBATE),
            EventType.MARRIAGE: (EventType.MARRIAGE, EventType.MARR_LIC, EventType.ENGAGEMENT),
            EventType.DIVORCE: (EventType.DIVORCE, EventType.ANNULMENT, EventType.DIV_FILING),
            }
        global FAMILY_EVENTS
        FAMILY_EVENTS = [EventType.MARRIAGE, EventType.MARR_LIC, EventType.ENGAGEMENT,
            EventType.DIVORCE, EventType.ANNULMENT, EventType.DIV_FILING]
        global OR_SIMILAR
        OR_SIMILAR = self.options['or_similar_events']
        global SORT_EVENTS
        SORT_EVENTS = self.options['sort_events']
        # used in sorting to move events with unknown dates to end (not used for birth related events)
        global FUTUREDATE
        FUTUREDATE = NextYear()
        
        global DESCEND_DISP 
        DESCEND_DISP = []
        for line in self.options['descend_disp']:
            #log.debug('ReportInit: Descendant Line=%s', line)
            DESCEND_DISP.append(parse_event_disp(line))
        log.debug('ReportInit: DESCEND_DISP=%s', DESCEND_DISP)
        
        global SPOUSE_DISP
        SPOUSE_DISP = []
        for line in self.options['spouse_disp']:
            #log.debug('ReportInit: Spouse Line=%s', line)
            SPOUSE_DISP.append(parse_event_disp(line))
        log.debug('ReportInit: SPOUSE_DISP=%s', SPOUSE_DISP)
        
        # increase text pad to allow for box's line
        if STROKE_RECTANGLE:
            TEXT_PAD += RECTANGLE_TEXT_PAD	

    def write_report(self):
        """
        This routine actually creates the report. 
        At this point, the document is opened and ready for writing.
        """
        pid = self.options_class.menu.get_option_by_name('pid').get_value()
        log.debug('Top PID=%s', pid)
        
        # Creates dummy drawing context for image sizing during creation of tree:
        init_file(self.output_fn, PNGWriter()) 
        
        # Generates a tree of person records and the family linkages for the chart:
        p = load_gramps(pid)
          
        # traverses tree and generates the chart with "person" boxes and the "family" relationship lines.
        draw_file(p, self.output_fn, PNGWriter())   
        
def draw_text(text, x, y, total_w, top_centered_lines=0):
    """
    Draw the block if text at the specified location.
    
    Total width defines the block's width to allow centering.
    Top_centered_lines overrides the Text alignment set in options menu for the
    specified # of lines. This allows centering of the first line containing the user's name
    """
    #(total_w, total_h) = size_text(text, ctx)
    n = 1
    for (size, color, line) in text:
        ctx.select_font_face(font_name)
        ctx.set_font_size(base_font_size * size)
        (ascent, _, height, _, _) = ctx.font_extents()
        (lx, _, width, _, _, _,) = ctx.text_extents(line)
        if ((TEXT_ALIGNMENT == 'center') or (n <= top_centered_lines)):
            ctx.move_to(x - lx + TEXT_PAD + (total_w - width + lx) / 2, y
                         + ascent + TEXT_PAD)
        elif TEXT_ALIGNMENT == 'left':
            ctx.move_to(x - lx + TEXT_PAD, y
                         + ascent + TEXT_PAD)
        else:
            raise AttributeError("DT: no such text alignment: '%s'" % TEXT_ALIGNMENT)
        ctx.set_source_rgb(*color)
        ctx.show_text(line)
        y += height + TEXT_LINE_PAD
        n += 1

def size_text(text, cntx):
    text_width = 0
    text_height = 0
    first = True
    for (size, color, line) in text:
        if first:
            first = False
        else:
            text_height += TEXT_LINE_PAD
        cntx.select_font_face(font_name)
        cntx.set_font_size(base_font_size * size)
        (_, _, height, _, _) = cntx.font_extents()
        (lx, _, width, _, _, _,) = cntx.text_extents(line)
        text_width = max(text_width, width - lx)
        text_height += height
    text_width += 2 * TEXT_PAD
    text_height += 2 * TEXT_PAD
    return (text_width, text_height)

def calc_image_scale(iw, ih):
	"""
	Calculate the scaling factor for the image to fit the Max size set in the Options
	
	The Max height & width from the Options are MAX_IMAGE_H & MAX_IMAGE_W
	a value of 0 means there is no limit in that direction.
	"""
	if MAX_IMAGE_H == 0:
		if MAX_IMAGE_W == 0:
			return (1.0)
		else:
			return (MAX_IMAGE_W/iw)
	else:
		if MAX_IMAGE_W == 0:
			return (MAX_IMAGE_H/ih)
		else:
# 			log.debug('Calc Scale, min of  H=%f, W=%f', MAX_IMAGE_H/ih, MAX_IMAGE_W/iw)
			return (min(MAX_IMAGE_W/iw, MAX_IMAGE_H/ih))

def size_image(image_path):
    """
    Gets the size of the image
    
    Need to use a dummy CTX (dctx) as using the final ctx to get this information
    seems to ruin the final image.
    """
    dctx.save()
    iw = 0
    ih = 0
    image = cairo.ImageSurface.create_from_png(image_path)
    if image:
        iw = cairo.ImageSurface.get_width(image)
        ih = cairo.ImageSurface.get_height(image)
    log.debug('Image Size (unscaled): height=%d width=%d', ih, iw)
    dctx.restore()
    return (iw, ih) 

def draw_image(image_path, ix, iy, iw, ih, scale_factor):
#     log.debug('Draw Image at x=%d y=%d, w=%d, h=%d, to be scaled by %d', ix, iy, iw, ih, scale_factor)
    ctx.save()
    image = cairo.ImageSurface.create_from_png(image_path)
    if scale_factor <> 1.0:
        log.debug('Draw Image: scale factor=%f; result: H=%f, W=%f', scale_factor, ih, iw)
        ctx.scale(scale_factor, scale_factor)
    ctx.set_source_surface(image, (ix+IMAGE_PAD)/scale_factor, (iy+IMAGE_PAD)/scale_factor)
    ctx.paint()
    ctx.restore()

def get_image(phandle):
    """
    Searches through a person's media and returns the first usable image.
    
    If the Privacy menu option is enabled, it will return the first non-private image.
    It will create a thumbnail image (PNG) if one does not exist.
    These currently default to a Maximum size of 96x96.
    """
    imagePath = None
    if GRAMPS_DB == None:
        log.error('get_image: No DataBase to get images from!')
    else:
        p = GRAMPS_DB.get_person_from_handle(phandle)
        if PROTECT_PRIVATE and p.private:
            log.debug('get_image: Private Person %s', p.primary_name.get_regular_name())
            return(None)
        else:
            mediaList = p.get_media_list()
            for media_item in mediaList:
                mediaHandle = media_item.get_reference_handle()
                media = GRAMPS_DB.get_object_from_handle(mediaHandle)
                if not (PROTECT_PRIVATE and media.private):
                    mediaMimeType = media.get_mime_type()
                    if mediaMimeType[0:5] == "image":
                        rect = media_item.get_rectangle()
                        # this will create a .PNG thumbnail ("NORMAL" size) if one does not exist.
                        # rect is the user defined section of the original image (TL x,y & BR x,y {1..100})
                        imagePath = get_thumbnail_path(
                                        media_path_full(GRAMPS_DB, media.get_path()),
                                        rectangle=rect)
                        if imagePath.endswith('/image-missing.png'):
                            imagePath = None    #skip GRAMPS image-missing icon
                            log.warning('get_image: %s has Missing Image', p.primary_name.get_regular_name())
                        else:
                            break   # found the first image
        if imagePath:
            log.debug('get_image, imagePath: %s', imagePath.replace(USER_HOME + '/gramps/thumb/',''))
        else:
            log.debug('get_image: No Media found for: %s', p.primary_name.get_regular_name())
    return(imagePath)
        
class Person_Block:
    """
    This class holds information to be displayed about a person (text, image location)
    and how to display it (widths & heights, image scaling)
    """
    def __init__(self, phandle, text):
        self.text = text        #array of tuples containing text.
        self.phandle = phandle  #to access image
        self.iw = 0.0     #Image Width (initially unscaled, then scaled)
        self.ih = 0.0     #Image Height (initially unscaled, then scaled)
        self.tw = 0.0     #Text Width
        self.th = 0.0     #Text Height
        self.boxw = 0.0   #Box (containing image & text) Width
        self.boxh = 0.0   #Box Height
        self.ipath = None   #Path to (thumbnail) image
        self.iscale = 1.0    #Scaling factor to use on thumbnail image
        
        (self.tw, self.th) = size_text(self.text, dctx)
        if (INC_IMAGE and (phandle <> None)):
            self.ipath = get_image(self.phandle)
            if self.ipath:
                (self.iw, self.ih) = size_image(self.ipath)
                self.iscale = calc_image_scale(self.iw, self.ih)
                self.iw = self.iw*self.iscale +2*IMAGE_PAD
                self.ih = self.ih*self.iscale +2*IMAGE_PAD
                log.debug('PBlk: Have image for %s, p_handle=%s', self.text[0][2], self.phandle)
#               log.debug('PBlk: imagePath: %s', self.ipath.replace(USER_PATH + '/gramps/thumb/',''))
            if IMAGE_LOC == 'Above Text':
                self.boxw = max(self.tw , self.iw)
                self.boxh = self.th + self.ih
            elif IMAGE_LOC == 'Left of Text':
                self.boxw = self.tw + self.iw
                self.boxh = max(self.th, self.ih)
            else:
                log.warning('PBlk: Image location not valid: %s', IMAGE_LOC)
        else:
            self.boxw = self.tw
            self.boxh = self.th
#       log.debug('PBlk Width: bw=%d, tw=%d, iw=%d', self.boxw, self.tw, self.iw)
#       log.debug('PBlk Height: bh=%d, th=%d, ih=%d', self.boxh, self.th, self.ih)

    def __str__(self):
        return (self.text[0] + '_PBlk')

    
mem_depth = 0
    
class Memorised:

    def get(self, name):
        try:
            getattr(self, '_memorised')
        except:
            self._memorised = {}

        global mem_depth
        mem_depth += 1
        if name in self._memorised:
            cached = '*'
            v = self._memorised[name]
        else:
            cached = ' '
            v = getattr(self, name)()
            self._memorised[name] = v

        mem_depth -= 1
        return v

class Person(Memorised):
    """
    This class is for each person in the descendants chart and contains:
    - linkages for the descendants tree (families, from family, prevsib, next sib)
    - information to be displayed about the person (text, ipath)
    - how to display it (generation, widths & heights, image scaling
    """
    def __init__(self, pblk, gen):
        self.text = pblk.text       # lines of text (tuples of str, colour and size)
        self.ipath = pblk.ipath
        self.iscale = pblk.iscale   # to scale thumbnail image using cario
        self.boxw = pblk.boxw   # width of box containing text & image, for chart sizing and alignment
        self.boxh = pblk.boxh
        self.iw = pblk.iw       #image width (scaled)
        self.ih = pblk.ih
        self.tw = pblk.tw       #text width
        self.th = pblk.th
        self.generation = gen   # for background colour
        self.families = []
        self.from_family = None
        self.prevsib = None
        self.nextsib = None

    def __str__(self):
        return '[' + self.text + ']'

    def add_family(self, fam):
        if self.families != []:
            self.families[-1].nextfam = fam
            fam.prevfam = self.families[-1]
        self.families.append(fam)

    def draw(self):
        #set_bg_style(ctx)
        #ctx.set_source_rgba(1, 0, 0, 0.1)  #very pale red
        #ctx.rectangle(self.get('x'), self.get('y'), self.get('w'), self.get('h'))
        #ctx.fill()
        ixo = 0.0    #image X blockoffset from box's top left corner
        iyo = 0.0    #image Y blockoffset
        txo = 0.0     #text X blockoffset
        tyo = 0.0     #text Y blockoffset
        
        if INC_IMAGE == True:
            if IMAGE_LOC == 'Above Text':
                ixo = (self.boxw - self.iw)/2
                #iyo = 0
                txo = (self.boxw - self.tw)/2
                tyo = self.ih
            elif IMAGE_LOC == 'Left of Text':
                #ixo = 0 
                iyo = (self.boxh - self.ih)/2
                txo = self.iw
                tyo = (self.boxh - self.th)/2
            else:
                log.warning('PD: Image location not valid: %s', IMAGE_LOC)
                
        log.debug('PD: Draw descendant %s Gen:%d', self.text[0][2], self.generation) 
#       log.debug('PD: bw=%d, get.bw=%d, tw=%d, iw=%d, x=%d, ixo=%d, txo=%d, get.tx=%d', self.boxw, self.get('bw'), self.tw, self.iw, self.get('x'), ixo, txo, self.get('tx'))
#       log.debug('PD: bh=%d, get.bh=%d, th=%d, ih=%d, y=%d, ixo=%d, txo=%d', self.boxh, self.get('bh'), self.th, self.ih, self.get('y'), iyo, tyo)

        #set_fg_style(ctx)
        if FILL_COLORS:
        	set_gen_style(ctx, self.generation, DESCEND_ALPHA)
        else:
        	set_fg_style(ctx)
        ctx.rectangle(self.get('tx'), self.get('y'), self.boxw, self.boxh)
        if STROKE_RECTANGLE == True:
        	ctx.fill_preserve()
        	set_line_style(ctx)
        	ctx.stroke()
        else:
            ctx.fill()

        draw_text(self.text, self.get('tx')+ txo, self.get('y')+ tyo, self.tw, top_centered_lines=1)
        
        if self.ipath <> None:
#           log.debug('PD: imagePath: %s', self.ipath.replace('/Users/ndpiercy/Library/Application Support/gramps/thumb/',''))
            draw_image(self.ipath, self.get('tx')+ ixo, self.get('y')+ iyo, self.iw, self.ih, self.iscale)
                
            
        for f in self.families:
            f.draw()

    def x(self):
        if self.from_family is None:
            return 0
        else:
            return self.from_family.get('cx') + self.get('o')

    def tx(self):
        return (self.get('x') + self.get('go')) - self.get('bw') / 2

    def y(self):
        if self.from_family is None:
            return 0
        else:
            return self.from_family.get('cy')

    def bw(self):
        return self.boxw

    def bh(self):
        return self.boxh

    def glh(self):
        total = 0
        for f in self.families:
            total += f.get('glh')
        return total

    def o(self):
        if self.prevsib is None:
            return 0
        else:
            return self.prevsib.get('o') + self.prevsib.get('w') + C_PAD

    def ch(self):
        biggest = 0
        for f in self.families:
            if f.get('ch') > biggest:
                biggest = f.get('ch')
        return biggest + O_DOWN + C_UP if biggest else 0

    def w(self):
        w = self.get('go') + self.get('bw') / 2
        w = max(w, MIN_C_WIDTH)
        if self.families != []:
            ff = self.families[0]
            to_sp = self.get('go') + ff.get('flw')
            w = max(w, to_sp + ff.spouse.get('bw') / 2)
            w = max(w, (to_sp - FL_PAD + ff.get('cw')) - ff.get('oloc'))
        return w

    def h(self):
        return self.get('bh') + self.get('glh') + self.get('ch')

    def go(self):
        go = self.get('bw') / 2
        if self.families != []:
            lf = self.families[-1]
            if lf.children != []:
                go = max(go, lf.get('oloc') - (lf.get('flw') - FL_PAD))
        return go

    def to(self):
        return self.get('go') - self.get('bw') / 2

    def glx(self):
        return self.get('x') + self.get('go')

class Family(Memorised):

    def __init__(self, main, spouse):
        self.main = main
        self.spouse = spouse

        self.children = []
        self.prevfam = None
        self.nextfam = None

        main.add_family(self)

        #self.generation = None
        self.generation = self.main.generation

    def __str__(self):
        return '(:' + str(self.main) + '+' + str(self.spouse) + ':)'

    def add_child(self, child):
        if self.children != []:
            self.children[-1].nextsib = child
            child.prevsib = self.children[-1]
        self.children.append(child)
        child.from_family = self

    def draw(self):
        #(px, py) = (self.main.get('x'), self.main.get('y'))
        # set_line_style(ctx)
        # Draw lines between spouse(s) for each "family"
        set_gen_style(ctx, self.generation, LINE_DARKNESS)
        ctx.set_dash([20, 5])
        ctx.new_path()
        ctx.move_to(self.get('glx'), self.get('gly'))   #center bottom of "Descendant" box
        ctx.rel_line_to(0, self.get('glh'))
        ctx.rel_line_to(self.get('flw'), 0)
        ctx.rel_line_to(0, -S_UP)                       #to center bottom of "Spouse" box
        ctx.stroke()
        ctx.set_dash([])    #restore line style to non-dash

        ixo = 0     #image X blockoffset from box
        iyo = 0     #image Y blockoffset from box
        txo = 0     #text X blockoffset from box
        tyo = 0     #text Y blockoffset from box
        
        if INC_IMAGE == True:
            if IMAGE_LOC == 'Above Text':
                ixo = (self.spouse.boxw - self.spouse.iw)/2
                #iyo = 0
                txo = (self.spouse.boxw - self.spouse.tw)/2
                tyo = self.spouse.ih
            elif IMAGE_LOC == 'Left of Text':
                #ixo = 0 
                iyo = (self.spouse.boxh - self.spouse.ih)/2
                txo = self.spouse.iw
                tyo = (self.spouse.boxh - self.spouse.th)/2
            else:
                log.warning('FD: Image location not valid: %s', IMAGE_LOC)
    
        log.debug('FD: Draw Fam/Sp %s Gen:%d', self.spouse.text[0][2], self.generation) 
#       log.debug('FD: bw=%d, get.bw=%d, tw=%d, iw=%d, spx=%d, ixo=%d, txo=%d', self.spouse.boxw, self.spouse.get('bw'), self.spouse.tw, self.spouse.iw, self.get('spx'), ixo, txo)
#       log.debug('FD: bh=%d, get.bh=%d, th=%d, ih=%d, spy=%d, ixo=%d, txo=%d', self.spouse.boxh, self.spouse.get('bh'), self.spouse.th, self.spouse.ih, self.get('spy'), iyo, tyo)
#       log.debug('FD: glx=%d, gly=%d, glh=%d, flw=%d', self.get('glx'), self.get('gly'), self.get('glh'), self.get('flw'))

        if FILL_COLORS:
        	set_gen_style(ctx, self.generation, SPOUSE_ALPHA)
        else:
        	set_fg_style(ctx)
        ctx.rectangle(self.get('spx'), self.get('spy'), self.spouse.boxw, self.spouse.boxh)
        if STROKE_RECTANGLE == True:
            ctx.fill_preserve()
            set_line_style(ctx)
            ctx.stroke()
        else:
            ctx.fill()

        draw_text(self.spouse.text, self.get('spx')+ txo, self.get('spy')+ tyo, self.spouse.tw, top_centered_lines=1)
        
        if self.spouse.ipath <> None:
#           log.debug('FD: imagePath: %s', self.spouse.ipath.replace('/Users/ndpiercy/Library/Application Support/gramps/thumb/',''))
            draw_image(self.spouse.ipath, self.get('spx')+ ixo, self.get('spy')+ iyo, self.spouse.iw, self.spouse.ih, self.spouse.iscale)
    
    
        if self.children != []:
            set_line_style(ctx)
            ctx.new_path()
            ctx.move_to(self.get('olx'), self.get('oly'))
            ctx.rel_line_to(0, self.get('olh'))
            ctx.stroke()

            ctx.new_path()
            ctx.move_to(self.children[0].get('glx'), self.get('cly'))
            ctx.line_to(self.children[-1].get('glx'), self.get('cly'))
            ctx.stroke()

            for c in self.children:
                set_line_style(ctx)
                ctx.new_path()
                ctx.move_to(c.get('glx'), self.get('cly'))
                ctx.rel_line_to(0, C_UP)
                ctx.stroke()

                c.draw()

    def glx(self):
        return self.main.get('glx')

    def gly(self):
        if self.prevfam is None:
            return self.main.get('y') + self.main.get('bh')
        else:
            return self.prevfam.get('gly') + self.prevfam.get('glh')

    def spx(self):
        return (self.get('glx') + self.get('flw'))\
             - self.spouse.get('bw') / 2

    def spy(self):
        return ((self.get('gly') + self.get('glh')) - S_UP)\
             - self.spouse.get('bh')

    def olx(self):
        return (self.get('glx') + self.get('flw')) - FL_PAD

    def oly(self):
        return self.get('gly') + self.get('glh')

    def cx(self):
        return ((self.main.get('x') + self.main.get('go')
                 + self.get('flw')) - FL_PAD) - self.get('oloc')

    def cly(self):
        return self.get('oly') + self.get('olh')

    def cy(self):
        return self.get('cly') + C_UP

    def glh(self):
        if self.prevfam is None:
            return S_DOWN
        else:
            return S_VPAD + self.spouse.get('bh') + S_UP

    def flw(self):
        flw = 2 * FL_PAD
        flw = max(flw, self.main.get('bw') / 2 + self.spouse.get('bw')
                   / 2 + SP_PAD)
        if self.nextfam is not None:
            flw = max(flw, self.nextfam.get('flw')
                       + self.nextfam.spouse.get('bw') + OL_PAD)
            flw = max(flw, self.nextfam.get('flw')
                       - self.nextfam.get('oloc')
                       + self.nextfam.get('cw') + F_PAD
                       + self.get('oloc'))
        return flw

    def olh(self):
        if self.nextfam is None:
            return O_DOWN
        else:
            return self.nextfam.get('olh') + self.nextfam.get('glh')

    def cw(self):
        if self.children == []:
            return 0
        else:
            return self.children[-1].get('o')\
                 + self.children[-1].get('w')

    def ch(self):
        biggest = 1
        for c in self.children:
            if c.get('h') > biggest:
                biggest = c.get('h')
        return biggest

    def oloc(self):
        if self.children == []:
            return 0
        else:
            total = 0
            for c in self.children:
                total += c.get('o') + c.get('go')
            return total / len(self.children)


def load_gramps(start):
    """
    This routine builds a tree of "person" and "family" records from the database
    with information to be displayed about the person and their relationships.
    It returns a pointer to the "Person" class at the head of the tree.
    """
    def format_event_txt(event, event_format, p_hdl):
        """ 
        returns a formated text string for the event as set in the option menu
        uses modified version of the formatting utilities from libsubstkeyword.py
        """
        if event:
            eskw = SubstKeywords2(GRAMPS_DB, glocale, name_displayer, p_hdl, max_note_len=MAX_NOTE_LEN, privacy=PROTECT_PRIVATE)
            vs = eskw.replace_and_clean([event_format], event)[0]
            log.debug('Formated event text=%s', vs)
            return vs
        return ""

    def format_event(event_ref_list, etype, event_format, p_hdl):
        """ 
        Returns a formated string + sortable date for all the events that
        matches the etype from the list of Person or Family events supplied
        If an event does not have date, the sort date will be 0, it is set to a 
        future date, unless unless the event is birth related.
        """
        et = []
        ev = []
        if event_ref_list:
            for event_ref in event_ref_list:
                event = find_event(GRAMPS_DB, event_ref.ref)
                if (event.type == etype) and not (PROTECT_PRIVATE and event.private):
                    log.debug('Format Event: type=%s, and sortdate=%s', event.type, event.get_date_object().sortval)
                    et = format_event_txt(event, event_format, p_hdl)
                    if event.get_date_object().sortval == 0: # sortval = days since 1-Jan-4713 BC
                        if etype in OR_SIMILAR_EVENTS[EventType.BIRTH]:
                            ev.append([et, event.get_date_object().sortval]) # all birth events go to top of list
                        else:
                            ev.append([et, FUTUREDATE.sortval],) # all non-birth events go to end
                    else:
                        ev.append([et, event.get_date_object().sortval],)
        return ev
        
    def format_event_or_similar(event_ref_list, event_type_list, event_format, p_hdl):
        """ 
        returns a formated string of the person's event that matchs one on the event_list
        Only the fist event that matches on the event list is returned 
        If an event does not have date, the sort date will be 0, it is set to a 
        future date, unless unless the event is birth related.
        """
        et = []
        ev = []
        if event_ref_list:
			for desired_event in event_type_list:
				for event_ref in event_ref_list:
					if ((event_ref.get_role() == EventRoleType.PRIMARY) or (event_ref.get_role() == EventRoleType.FAMILY)):
						event = find_event(GRAMPS_DB, event_ref.ref)
						if (event.type == desired_event) and not (PROTECT_PRIVATE and event.private):
							log.debug('Format EorS: type=%s, and sortdate=%s', event.type, event.get_date_object().sortval)
							et = format_event_txt(event, event_format, p_hdl)
							if event.get_date_object().sortval == 0: # no date = 0
								if event.type in OR_SIMILAR_EVENTS[EventType.BIRTH]:
									ev.append([et, event.get_date_object().sortval]) # all birth events go to top of list
								else:
									ev.append([et, FUTUREDATE.sortval],) # all non-birth events go to end
							else:
								ev.append([et, event.get_date_object().sortval],)
							return ev
        return ev

    def format_person_events(person, family, event_disp_list):
        """
        For each line of events to be displayed provided by in the options menu:
        if the "orSIMILAR" option was selected in the menu and the event type is
        BIRTH, MARRAIGE, DIVORCE or DEATH, it will get the best match.
        Otherwise it will get all events that match.
        Optionally it will sort the resulting formatted event lines by date.
        """
        elist = []
        estrings = []
        for (event_type_list, event_format) in event_disp_list:
            for etype in event_type_list:
            	#log.debug('FPE: ETYPE=%s Fmt=%s', etype, event_format)
                ev = None
                if etype in FAMILY_EVENTS:
                	if family:
						if (OR_SIMILAR and (etype in OR_SIMILAR_EVENTS)):
							ev=(format_event_or_similar(family.get_event_ref_list(), OR_SIMILAR_EVENTS[etype], event_format, person.handle))
						else:
							ev=(format_event(family.get_event_ref_list(), etype, event_format, person.handle))
                else:
                	if (OR_SIMILAR and (etype in OR_SIMILAR_EVENTS)):
                		ev=(format_event_or_similar(person.get_event_ref_list(), OR_SIMILAR_EVENTS[etype], event_format, person.handle))
                	else:
                		ev=(format_event(person.get_event_ref_list(), etype, event_format, person.handle))        
                if ev:
                    elist.extend(ev)
                    #log.debug('Add Event=%s', ev)
        if elist:
            #log.info('FPE: All Events=%s', elist)
            if SORT_EVENTS:
                el2 = sorted(elist, key=lambda x: x[1])    #sort by date
                for (etxt, esort) in el2:
                    #log.debug('FPE: etxt=%s, esort=%d', etxt, esort)
                    estrings.append(etxt)
            else:
                for (etxt, esort) in elist:
                    estrings.append(etxt)
        return estrings
    
    def get_person_text(person, display_format, f, dnum=None):
        """
        assembles all the text for a person
        """
        name_size = 1.0 # font size modifier
        event_size = 0.90
        event_colour = (0, 0, 0) # Black - for all event lines

        if PROTECT_PRIVATE and person.private:
        	s2 = [(name_size, event_colour, PRIVATE_TEXT)]
        else:
			name = None
			nskw = SubstKeywords(GRAMPS_DB, glocale, name_displayer, person.handle)
			name = nskw.replace_and_clean([NAME_FORMAT])[0]
			#log.debug('GPT: Name SubKW: %s', name)
		
			events = None
			events = format_person_events(person, f, display_format)
			log.debug('GetPersonTxt, All Events: %s', events)
		
			name_size = 1.0 # font size modifier
			event_size = 0.90
			event_colour = (0, 0, 0) # Black - for all event lines
		
			if GENDER_COLORS:      # Only for name line
				if person.get_gender() == gramps.gen.lib.Person.MALE:
					n_col = (0, 0, 1) # Blue
				elif person.get_gender() == gramps.gen.lib.Person.FEMALE:
					n_col = (1, 0, 0) # Red
				else:
					n_col = (0, 0.5, 0) # Green             
			else:
				n_col = (0, 0, 0) # Black
			
			if INC_DNUM and dnum is not None:   # Prepend DNUM to name text str
				if name is None:
					s = [(name_size, n_col, dnum)]
				else:
					s = [(name_size, n_col, dnum + ' ' + name)]
			elif name is None:
				s = []
			else:
				s = [(name_size, n_col, name)]

			if events:
				for ev in events:
					s.append((event_size, event_colour, ev))

			# Apply the replacement list to all the text strings
			#    borrowed from calc_lines in libtreebase.py
			s2=[]
			for (size, color, line) in s:
				for pair in REPLACEMENT_LIST:
					if pair.count("/") == 1:
						repl = pair.split("/", 1)
						line = line.replace(repl[0], repl[1])
				s2.append((size, color, line))
        return s2
        
    def do_person(p_id, dnum="1."):
        """
        This routine creates a tree of "Person" and Family" records,
        containing linkages between the records for the tree, 
        and the information to be displayed for each person (name, events, image)
        """
        global CUR_GENERATION
        CUR_GENERATION += 1
        global HIGH_GENERATION
        HIGH_GENERATION = max(HIGH_GENERATION, CUR_GENERATION)
        UNKNOWN_PERSON_TXT = [(1.0, (0,0,0), 'Unknown'),]
        
        descendant = GRAMPS_DB.get_person_from_gramps_id(p_id)
#       log.debug('Do_Person: Descendant %s, DB ID:%s', descendant.primary_name.get_regular_name(), p_id)
        blk_txt = get_person_text(descendant, DESCEND_DISP, None, dnum)  # assembles array of text tuples(size, colour, txt-str)
        p = Person(Person_Block(descendant.handle, blk_txt), CUR_GENERATION)
        for fhandle in descendant.get_family_handle_list():
            cnum = 1
            fmly = GRAMPS_DB.get_family_from_handle(fhandle)
            if fmly:
                sph = fmly.get_father_handle()
                if sph == descendant.handle:
                    sph = fmly.get_mother_handle()
                if sph:
                    spouse = GRAMPS_DB.get_person_from_handle(sph)
                    if spouse:
                        log.debug('Do_Person: Spouse %s, DB ID=%s', spouse.primary_name.get_regular_name(), spouse.get_gramps_id())
                        spo_txt = get_person_text(spouse, SPOUSE_DISP, fmly, dnum)
                        fm = Family(p, Person(Person_Block(spouse.handle, spo_txt), CUR_GENERATION))
                        if MAX_GENERATION == 0 or CUR_GENERATION < MAX_GENERATION:
                            for chandle in fmly.get_child_ref_list():
                                if chandle:
                                    child = GRAMPS_DB.get_person_from_handle(chandle.ref)
                                    if child:
                                        log.debug('Do_Person: Child %s, DB ID=%s', child.primary_name.get_regular_name(), child.get_gramps_id())
                                        fm.add_child(do_person(child.get_gramps_id(), dnum + str(cnum) + "."))
                                        cnum += 1
                                    else:
                                        log.warning('Do_Person: Failed to get child from handle: %s', chandle)
                    else:
                        log.warning('Do_Person: Failed to get spouse from handle: %s', dbsph)
                else:
                    log.info('Do_Person: Unknown spouse of %s', descendant.primary_name.get_regular_name())
                    fm = Family(p, Person(Person_Block(None, UNKNOWN_PERSON_TXT), CUR_GENERATION))
            else:
                log.debug('Do_Person: %s has no spouse(s)', descendant.primary_name.get_regular_name())

        CUR_GENERATION -= 1
        return p

    CUR_GENERATION=0
    return do_person(start, "1.")


def set_bg_style(ctx):
    ctx.set_source_rgb(*BACKGROUND_COLOR)

def set_fg_style(ctx):
    ctx.set_source_rgb(*FOREGROUND_COLOR)

def set_gen_style(ctx, gen, darkness):
    """
    Set the colour based on the generation such as to spread the colours across the 
    spectrum (from Red to Violet), with reference to the HIGH_GENERATION global
    Darkeness controls the intensity of the clolour, with 0 being very pale, 
    and higher numbers resulting in more intense (darker) colours
    Modified from __set_fill_color in FamilyTree.py
    """
    if (gen and (FILL_COLORS)):
        index = (HIGH_GENERATION / 2.0 + gen) % HIGH_GENERATION
        step = darkness * 3.0 / HIGH_GENERATION
        r = min(index, abs(index - HIGH_GENERATION))
        g = abs(index - (HIGH_GENERATION / 3.0))
        b = abs(index - (2 * HIGH_GENERATION / 3.0))
        r = 255.0 - max(0, darkness - r * step)
        g = 255.0 - max(0, darkness - g * step)
        b = 255.0 - max(0, (darkness - b * step) * 2.0)
#       log.debug('SGS: colour r=%d, g=%d, b=%d, number=%d, count=%d, index=%d, step=%d', r, g, b, gen, HIGH_GENERATION, index, step)
        rgba=(r/255, g/255, b/255, 1)
    else:
        rgba=(0.0, 0.0, 0.0, 1) # black
    ctx.set_source_rgba(*rgba)

def set_line_style(ctx):
    ctx.set_source_rgb(0.3, 0.3, 0.3)


def init_file(fn, writer):
    """dummy surface for image size calculations, to avoid mucking up final image"""
    global dctx
    surface = writer.start(fn, 10, 10)
    dctx = cairo.Context(surface)

def draw_tree(head):
    ctx.select_font_face(font_name)
    ctx.set_font_size(base_font_size)
    ctx.set_line_width(2)
    ctx.set_line_cap(cairo.LINE_CAP_SQUARE)
    ctx.set_line_join(cairo.LINE_JOIN_MITER)
    set_line_style(ctx)
    head.draw()

class PNGWriter:

    def start(self, fn, w, h,):
        self.fn = fn
        if OUTPUT_FMT == 'PNG':
            self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(w
                     + 1), int(h + 1))
        elif OUTPUT_FMT == 'SVG':
            self.surface = cairo.SVGSurface(OUTPUT_FN, int(w
                 + 1), int(h + 1))
        elif OUTPUT_FMT == 'PDF':
            self.surface = cairo.PDFSurface(OUTPUT_FN, int(w
                 + 1), int(h + 1))
        elif OUTPUT_FMT == 'PS':
            self.surface = cairo.PSSurface(OUTPUT_FN, int(w
                 + 1), int(h + 1))
        else:
            raise AttributeError("no such output format: '%s'" % OUTPUT_FMT)
        return self.surface

    def finish(self):

        if OUTPUT_FMT == 'PNG':
            self.surface.write_to_png(self.fn)
        elif (OUTPUT_FMT == 'SVG') \
             or (OUTPUT_FMT == 'PDF') \
             or (OUTPUT_FMT == 'PS'):
            self.surface.flush()
            self.surface.finish()
        else:
            raise AttributeError("no such output format: '%s'" % OUTPUT_FMT)

def draw_file(p, fn, writer):
    """
    called by write_report to generate the chart
    Uses the tree of person & family records, "p", created by load_gramps
    """
    global ctx

    surface = writer.start(fn, 10, 10) # 1st pass is just to get size of chart
    ctx = cairo.Context(surface)
    draw_tree(p)
    (w, h) = (p.get('w'), p.get('h'))
    log.debug('### End of 1st Pass. Surface w=%d, h=%d', w, h)

    surface = writer.start(fn, w, h)
    ctx = cairo.Context(surface)
    draw_tree(p)
    ctx.show_page()
    writer.finish()
 

#------------------------------------------------------------------------
#
# DescendantsLines
#
#------------------------------------------------------------------------
class DescendantsLinesOptions(MenuReportOptions):
    """
    Defines options.
    """

    def __init__(self, name, dbase):
        self.__db = dbase
        self.__pid = None
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):
        """
        Add options to the menu for the report.
        """

        category_name = _('Report Options')

        pid = PersonOption(_('Center Person'))
        pid.set_help(_('The center person for the report'))
        menu.add_option(category_name, 'pid', pid)

        output_fmt = EnumeratedListOption(_("Output format"), "PNG")
        output_fmt.set_items([
                ("PNG", _("PNG format")),
                ("SVG", _("SVG format")),
                ("PDF", _("PDF format")),
                ("PS", _("PS format"))])
        output_fmt.set_help(_("The output format to be used"))
        menu.add_option(category_name, "output_fmt", output_fmt)


        output_fn = DestinationOption(_("Destination"),
            os.path.join(USER_HOME,"DescendantsLines.png"))
        output_fn.set_help(_("The destination file for the content."))
        menu.add_option(category_name, "output_fn", output_fn)

        max_gen = NumberOption(_("Generations"), 10, 0, 25)
        max_gen.set_help(_("The number of generations to include in the chart." \
                " (0 for unlimited)"))
        menu.add_option(category_name, "max_gen", max_gen)
                
        stroke_rectangle = BooleanOption(_("Box around Person's block"), False)
        stroke_rectangle.set_help(_('Draw a thin black box around each person\' text block.'))
        menu.add_option(category_name, 'stroke_rectangle', stroke_rectangle)

        fill_colors = BooleanOption(_('Colour blocks by Generation'), False)
        fill_colors.set_help(_('Colour the background of text blocks by generation.'))
        menu.add_option(category_name, 'fill_colors', fill_colors)

        d_alpha = NumberOption(_("Descend block colour intensity"), 64, 0, 255)
        d_alpha.set_help(_("Intensity of backgound colour in Descendant's Block, 0=faint, 255=intense colour"))
        menu.add_option(category_name, "descend_alpha", d_alpha)
        
        s_alpha = NumberOption(_("Spouse block colour intensity"), 32, 0, 255)
        s_alpha.set_help(_("Intensity of backgound colour in Spouse's Block, 0=faint 255=intense colour"))
        menu.add_option(category_name, "spouse_alpha", s_alpha)
                
        inc_image = BooleanOption(_('Include an image'), True)
        inc_image.set_help(_('Whether to include an image if one is available.'))
        menu.add_option(category_name, 'inc_image', inc_image)

        image_h = NumberOption(_("Max Image height"), 0, 0, 250)
        image_h.set_help(_("Maximum image height in pixels, 0=don't scale for height."))
        menu.add_option(category_name, "image_h", image_h)
        
        image_w = NumberOption(_("Max Image width"), 0, 0, 250)
        image_w.set_help(_("Maximum image width in pixels, 0=don't scale for width."))
        menu.add_option(category_name, "image_w", image_w)

        image_loc = EnumeratedListOption(_("Image Location"), "Above Text")
        image_loc.set_items([
                ("Above Text", _("Above text")),
                ("Left of Text", _("Left of text"))])
        image_loc.set_help(_("Position of image relative to text"))
        menu.add_option(category_name, "image_loc", image_loc)

      ##################
        category_name = _("Display")
        
        namedisp = StringOption(_("Name Display Format"), "$n(f L){ \($n(n)\)}") 
        namedisp.set_help(_("f=first & middle names, l=surname, n=nickname,\nc=commonly used given name, t=title, s=suffix, g=family nick name\nSee Wiki Manual > Reports > part 2"))
        menu.add_option(category_name, "name_disp", namedisp)

        inc_dnum = BooleanOption(_("Use d'Aboville descendant numbering system"), False)
        inc_dnum.set_help(_("Prepend name with d'Aboville descendant number in the chart."))
        menu.add_option(category_name, 'inc_dnum', inc_dnum)
        
        gender_colors = BooleanOption(_('Colour Name by Gender'), False)
        gender_colors.set_help(_('Color the name to indicate a person\'s gender in the chart.'))
        menu.add_option(category_name, 'gender_colors', gender_colors)
                
        disp = TextOption(_("Descendant\nDisplay Format"),
                           ["[ BIRTH   ]$e(t d(yyyy)< @ >D(t))",
                           "[ Occupation, Degree, Education ]$e(t d(o yyyy/mm/dd)< >n< at >D(t))",
                           "[ census,RESIDENCE,Property]$e(t d(dd-MMM-yy)){ Position: Lat=$e(D(x)), Long=$e(D(y))}",
                           "[Death]$e(t d(o yyyy)< @ >D(e<, >l<, >c<, >u<, >s<, >p<, >n))"])
        disp.set_help(_("[event, list]$e(formating)\nSee Wiki Manual > Reports > part 2\nformating: dates=d(ymdMo) places=D(elcuspnoitxy) notes=n abbreviated_type=t"))
        menu.add_option(category_name, "descend_disp", disp)

        #bug 4767
        #diffspouse = BooleanOption(
        #    _("Use separate display format for spouses"),
        #    True)
        #diffspouse.set_help(_("Whether spouses can have a different format."))
        #menu.add_option(category_name, "diffspouse", diffspouse)

        sdisp = TextOption(_("Spousal\nDisplay Format"),
                           ["[ Birth ]$e(t d(yyyy)< @ >D(t))",
                           "[ Occupation, Degree, Education ]$e(t d(yyyy)<, >n< @ >D(t))",
                           "[ Census, Residence, Property ]$e(t d(yyyy)< @ >D(t))",
                           "[ Marriage, Divorce ]$e(t d(yyyy)< @ >D(t))",
                           "[ Death ]$e(t d(yyyy)< @ >D(t))"])
        sdisp.set_help(_("[event, list]$e(formating)\nSee Wiki Manual > Reports > part 2\nformating: dates=d(ymdMo) places=D(elcuspnoitxy) notes=n abbreviated_type=t"))
        menu.add_option(category_name, "spouse_disp", sdisp)
        
        or_similar_events = BooleanOption(_('Use alternate events, if Primary event is not found'), False)
        or_similar_events.set_help(_("For Birth (baptism, christen)\n   Marriage (marr_lic, engagement)\n   Divorce (annulment, div_filing),\n   Death (burial, cremation, probate)."))
        menu.add_option(category_name, "or_similar_events", or_similar_events)

        sort_events = BooleanOption(_('Sort Events by Date'), False)
        sort_events.set_help(_("Sort events by date (else use the order of the 'Display Format' above)."))
        menu.add_option(category_name, "sort_events", sort_events)

        protect_private = BooleanOption(_("Protect People, Images or Events that are marked Private"), True)
        protect_private.set_help(_("The Privacy setting of only these types of Gramps objects are checked"))
        menu.add_option(category_name, 'protect_private', protect_private)
   
        private_text = StringOption(_("Privacy text"), 'Private') 
        private_text.set_help(_("Text to display in block, when a Person is marked private"))
        menu.add_option(category_name, "private_text", private_text)

        text_alignment = EnumeratedListOption(_("Text style"), "center")
        text_alignment.set_items([
                ("center", _("Center-aligned text")),
                ("left", _("Left-aligned text"))])
        text_alignment.set_help(_("Alignment of the text in the block for each person on the chart"))
        menu.add_option(category_name, "text_alignment", text_alignment)

        max_note_len = NumberOption(_("Max Note Length"), 0, 0, 250)
        max_note_len.set_help(_("Maximum length of an event's note field in a text block, '$e(n)'\n 0=no limit "))
        menu.add_option(category_name, "max_note_len", max_note_len)
        
       ##################
        category_name = _("Replace")

        repldisp = TextOption(
            _("Replace Display Format:\n'Replace this'/' with this'"),
            [])
        repldisp.set_help(_("i.e.\nUnited States of America/USA"))
        menu.add_option(category_name, "replace_list", repldisp)

       ##################
        category_name = _('S  &amp; F Options')
       
        s_down = NumberOption(_("S_DOWN"), 20, 0, 50)
        s_down.set_help(_("The length of the vertical edge from descendant to spouse-bar."))
        menu.add_option(category_name, "S_DOWN", s_down)
        
        s_up = NumberOption(_("S_UP"), 10, 0, 50)
        s_up.set_help(_("The length of the vertical edge from spouse-bar to spouse."))
        menu.add_option(category_name, "S_UP", s_up)
        
        s_vpad = NumberOption(_("S_VPAD"), 10, 0, 50)
        s_vpad.set_help(_("The number of ??? vpad"))
        menu.add_option(category_name, "S_VPAD", s_vpad)
        
        sp_pad = NumberOption(_("SP_PAD"), 10, 0, 50)
        sp_pad.set_help(_("The number of ??? pad"))
        menu.add_option(category_name, "SP_PAD", sp_pad)
        
#         category_name = _('Options F')
        
        f_pad = NumberOption(_("F_PAD"), 20, 0, 50)
        f_pad.set_help(_("The number of ??? pad"))
        menu.add_option(category_name, "F_PAD", f_pad)
        
        fl_pad = NumberOption(_("FL_PAD"), 20, 0, 50)
        fl_pad.set_help(_("The number of ??? pad"))
        menu.add_option(category_name, "FL_PAD", fl_pad)
        
        category_name = _('O, C &amp; Text Options')
        
        ol_pad = NumberOption(_("OL_PAD"), 10, 0, 50)
        ol_pad.set_help(_("The number of ??? pad"))
        menu.add_option(category_name, "OL_PAD", ol_pad)
        
        o_down = NumberOption(_("O_DOWN"), 30, 0, 50)
        o_down.set_help(_("The length of the vertical edge from spouse-bar to child-bar."))
        menu.add_option(category_name, "O_DOWN", o_down)
        
#         category_name = _('Options C')
        
        c_pad = NumberOption(_("C_PAD"), 10, 0, 50)
        c_pad.set_help(_("The number of ??? pad"))
        menu.add_option(category_name, "C_PAD", c_pad)
    
        c_up = NumberOption(_("C_UP"), 15, 0, 50)
        c_up.set_help(_("The length of the vertical edge from child to child-bar."))
        menu.add_option(category_name, "C_UP", c_up)
        
        min_c_width = NumberOption(_("MIN_C_WIDTH"), 40, 0, 50)
        min_c_width.set_help(_("The number of ??? min width"))
        menu.add_option(category_name, "MIN_C_WIDTH", min_c_width)
        
#         category_name = _('Options Text')
        
        text_pad = NumberOption(_("TEXT_PAD"), 2, 0, 50)
        text_pad.set_help(_("The number of text pad ???"))
        menu.add_option(category_name, "TEXT_PAD", text_pad)
        
        text_line_pad = NumberOption(_("TEXT_LINE_PAD"), 2, 0, 50)
        text_line_pad.set_help(_("The number of text line pad ??? "))
        menu.add_option(category_name, "TEXT_LINE_PAD", text_line_pad)
        
    def make_default_style(self, default_style):
        """Make the default output style"""

        font = FontStyle()
        font.set_size(12)
        font.set_type_face(FONT_SANS_SERIF)
        font.set_bold(1)
        para = ParagraphStyle()
        para.set_top_margin(ReportUtils.pt2cm(base_font_size))
        para.set_font(font)
        para.set_alignment(PARA_ALIGN_LEFT)
        para.set_description(_('The default style.'))
        default_style.add_paragraph_style('DL-name', para)
