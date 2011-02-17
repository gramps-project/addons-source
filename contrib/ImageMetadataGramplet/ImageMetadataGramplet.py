#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009-2011 Rob G. Healey <robhealey1@gmail.com>
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

# $Id$

# *****************************************************************************
# Python Modules
# *****************************************************************************
from __future__ import division

import os, sys
from datetime import datetime, date
import time

# -----------------------------------------------------------------------------
# GTK modules
# -----------------------------------------------------------------------------
import gtk

# -----------------------------------------------------------------------------
# GRAMPS modules
# -----------------------------------------------------------------------------
from TransUtils import get_addon_translator
_ = get_addon_translator().ugettext

# import the pyexiv2 library classes for this addon
try:
    from pyexiv2 import ImageMetadata, ExifTag, IptcTag, Rational, XmpTag
except ImportError:
    pyexiv2msg = _( "The, pyexiv2, python binding library, to exiv2 is not "
                   "installed on this computer.\n It can be downloaded either from your "
                   "ocal repository or from here\n")
    pyexiv2msg += "http://tilloy.net/dev/pyexiv2"
    raise Exception( pyexiv2msg )

# import html_escape from libhtml
from libhtml import html_escape as html_escape

from gen.plug import Gramplet
from DateHandler import displayer as _dd

from QuestionDialog import OkDialog, WarningDialog

import Utils
from PlaceUtils import conv_lat_lon
# -----------------------------------------------------------------------------
# Set up logging
# -----------------------------------------------------------------------------
import logging
log = logging.getLogger(".ImageMetadata")

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
# available image types for exiv2
_valid_types = ["jpeg", "exv", "tiff", "dng", "nef", "pef", "pgf", "png", "psd", "jp2"]

# set up Exif keys for Image.exif_keys
ImageArtist        = "Exif.Image.Artist"
ImageCopyright    = "Exif.Image.Copyright"
ImageDateTime     = "Exif.Image.DateTime"
ImageLatitude     = "Exif.GPSInfo.GPSLatitude"
ImageLatitudeRef  = "Exif.GPSInfo.GPSLatitudeRef"
ImageLongitude    = "Exif.GPSInfo.GPSLongitude"
ImageLongitudeRef = "Exif.GPSInfo.GPSLongitudeRef"
ImageDescription  = "Exif.Image.ImageDescription"

# set up keys for Image IPTC keys
IptcKeywords = "Iptc.Application2.Keywords"

_DATAMAP = [ ImageArtist, ImageCopyright, ImageDateTime,
             ImageLatitude, ImageLatitudeRef, ImageLongitude, ImageLongitudeRef,
             ImageDescription ]

_allmonths = list( [ _dd.short_months[i], _dd.long_months[i], i ] for i in range(1, 13) )

def return_month(rmonth):
    """
    returns either an integer of the month number or the abbreviated month name

    @param: rmonth -- can be one of:
        10, "10", or ( "Oct" or "October" )
    """

    if isinstance(rmonth, str):
        try: 
            if int( rmonth[0] ) in [i for i in range(0, 10) ]:
                return int( rmonth )

        except ValueError:
            for s, l, i in _allmonths:
                if rmonth == s or rmonth == l:
                    return int( i )
    else:
        for s, l, i in _allmonths:
            if str( rmonth ) == i:
                return s
# ------------------------------------------------------------------------
# Gramplet class
# ------------------------------------------------------------------------
class imageMetadataGramplet(Gramplet):

    def init(self):

        self.exif_column_width = 15
        self.exif_widgets = {}

        # set all dirty variables to False to begin this gramplet
        self._dirty_image = False
        self._dirty_read  = False
        self._dirty_write = False

        self.orig_image   = False
        self.image_path   = False
        self.plugin_image = False
        self.mime_type    = False
        self.LATitude     = None
        self.LONGitude    = None

        rows = gtk.VBox()
        for items in [
            ("ActiveImage",     _("Active Image"), None, True,  [],  False, 0, None),
            ("Artist",          _("Artist"),       None, False, [],  True,  0, None),
            ("Copyright",       _("Copyright"),    None, False, [],  True,  0, None),

            # calendar date clickable entry
            ("Date",   "",                         None, True,
            [("Select Date",    _("Select Date"),  "button", self.select_date)],
                                                                     True,  0, None),

            # Manual Date Entry, Example: 1826-Apr-12
            ("NewDate",         _("Date"),         None, False,  [], True,  0, None),

            # Manual Time entry, Example: 14:06:00
            ("NewTime",         _("Time"),         None, False,  [], True,  0, None),

            ("GPSFormat",       "",                None, True,
            [("Decimal",        _("Decimal"),        "button", self.convert2decimal),
             ("DMS",            _("Deg. Min. Sec."), "button", self.convert2dms)], 
                                                                     False, 0, None),    
  
            # Latitude and Longitude for this image 
            ("Latitude",        _("Latitude"),     None, False, [],  True,  0, None),
	    ("Longitude",       _("Longitude"),    None, False, [],  True,  0, None),

            # keywords describing your image
            ("Keywords",        _("Keywords"),     None, False, [],  True,  0, None) ]:

            pos, text, choices, readonly, callback, dirty, default, source = items
            row = self.make_row(pos, text, choices, readonly, callback, dirty, default, source)
            rows.pack_start(row, False)

        # separator before description textbox
        rows.pack_start( gtk.HSeparator(), True )
	
        # description textbox label
        label = gtk.Label()
        label.set_text("<b><u>%s</u></b>" % _("Description"))
        label.set_use_markup(True)
        rows.pack_start(label, False)

        # description textbox field
        description_box = gtk.TextView()
        description_box.set_wrap_mode(gtk.WRAP_WORD)
        description_box.set_editable(True)
        self.exif_widgets["Description"] = description_box.get_buffer()
        rows.pack_start(description_box, True, True, 0)

        # provide tooltips for this gramplet
        self.setup_tooltips(object)

        # Save Metadata
        row = gtk.HBox()
        button = gtk.Button(_("Save Metadata"))
        button.connect("clicked", self.save_metadata)
        row.pack_start(button, True)
        rows.pack_start(row, True)

        # Clear Image Metadata
        button = gtk.Button(_("Clear Metadata"))
        button.connect("clicked", self.clear_metadata)
        row.pack_start(button, True)

        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(rows)
        rows.show_all()

    def post_init(self):
        self.connect_signal("Media", self.update)
        
    def setup_tooltips(self, obj):
        """
        setup tooltips for each field
        """

        # Artist
        self.exif_widgets["Artist"].set_tooltip_text(_("Enter the name "
            "of the person or company who took this image."))

        # Copyright
        self.exif_widgets["Copyright"].set_tooltip_text(_("Enter the copyright"
            " information for the image.  xample: (C) 2010 Smith and Wesson"))

        # Manual Date Entry 
        self.exif_widgets[ "NewDate"].set_tooltip_text(_("Manual Date Entry, \n"
            "Example: 1826-Apr-12"))

        # Manual Time Entry
        self.exif_widgets["NewTime"].set_tooltip_text(_( "Manual Time entry, \n"
            "Example: 14:06:00"))

        # Leaning Tower of Pisa, Pisa, Italy
        # GPS Latitude Coordinate
        self.exif_widgets["Latitude"].set_tooltip_text(_("Enter the GPS Latitude Coordinates for your image, \n"
            "Example: 43.722965, 43 43 22 N"))

        # GPS Longitude Coordinate
        self.exif_widgets["Longitude"].set_tooltip_text(_("Enter the GPS Longitude Coordinates for your image, \n"
            "Example: 10.396378, 10 23 46 E"))

        # Keywords
        self.exif_widgets["Keywords"].set_tooltip_text(_("Enter keywords that describe this image "
            "seprated by a comma."))

# -----------------------------------------------
# Error Checking functions
# -----------------------------------------------
    def _clear_image(self, object):
        self._dirty_image = False
        self._dirty_read  = False
        self._dirty_write = False

    def _mark_dirty_image(self, object):
        self._dirty_image = True

    def _mark_dirty_read(self, object):
        self._dirty_read = True

    def _mark_dirty_write(self, object):
        self._dirty_write = True

    def main(self): # return false finishes
        """
        get the active media, mime type, and reads the image metadata
        """

        # get active object handle of Media type
        self.active_media = self.get_active("Media")
        if not self.active_media:
            return

        # get media object from database
        self.orig_image = self.dbstate.db.get_object_from_handle( self.active_media )
        if not self.orig_image:
            self._mark_dirty_image(None)
            log.debug( "There is no image on file system!")
        else:
            self._clear_image(None)
            log.debug( "CURRENT MEDIA HANDLE IS NOW: ", self.active_media )

        if not self._dirty_image:

            # get image's full path on local filesystem
            self.image_path = Utils.media_path_full( self.dbstate.db, self.orig_image.get_path() )

            if not os.access( self.image_path, os.R_OK ):
                self._mark_dirty_read(None)

            if not os.access( self.image_path, os.W_OK ):
                self._mark_dirty_write(None)

            # get image mime type
            self.mime_type = self.orig_image.get_mime_type()
            if self.mime_type and self.mime_type.startswith("image"):
                _type, _imgtype = self.mime_type.split("/")
                if _imgtype not in _valid_types:
                    self._mark_dirty_read( None)
                    self._mark_dirty_write(None)  

            # if self._dirty_read is True, then the image is not readable,
            # Example: insufficient read permissions or invalid image type
            if not self._dirty_read:

                # clear all data entry fields
                self.clear_metadata(None)

                # get the pyexiv2 metadata instance
                self.plugin_image = ImageMetadata( self.image_path )

                # read the image metadata
                self.read_metadata( self.image_path )

    def make_row(self, pos, text, choices=None, readonly=False, callback_list=[],
                 mark_dirty=False, default=0, source=None):
        import gtk
        # Data Entry: Active Person
        row = gtk.HBox()
        label = gtk.Label()
        if readonly:
            label.set_text("<b>%s</b>" % text)
            label.set_width_chars(self.exif_column_width)
            label.set_use_markup(True)
            self.exif_widgets[pos] = gtk.Label()
            self.exif_widgets[pos].set_alignment(0.0, 0.5)
            self.exif_widgets[pos].set_use_markup(True)
            label.set_alignment(0.0, 0.5)
            row.pack_start(label, False)
            row.pack_start(self.exif_widgets[pos], False)
        else:
            label.set_text("%s: " % text)
            label.set_width_chars(self.exif_column_width)
            label.set_alignment(1.0, 0.5) 
            if choices == None:
                self.exif_widgets[pos] = gtk.Entry()
                if mark_dirty:
                    self.exif_widgets[pos].connect("changed", self._mark_dirty_image)
                row.pack_start(label, False)
                row.pack_start(self.exif_widgets[pos], True)
            else:
                eventBox = gtk.EventBox()
                self.exif_widgets[pos] = gtk.combo_box_new_text()
                eventBox.add(self.exif_widgets[pos])
                for add_type in choices:
                    self.exif_widgets[pos].append_text(add_type)
                self.exif_widgets[pos].set_active(default) 
                if mark_dirty:
                    self.exif_widgets[pos].connect("changed", self._mark_dirty_image)
                row.pack_start(label, False)
                row.pack_start(eventBox, True)
            if source:
                label = gtk.Label()
                label.set_text("%s: " % source[0])
                label.set_width_chars(self.de_source_width)
                label.set_alignment(1.0, 0.5) 
                self.exif_widgets[source[1] + ":Label"] = label
                self.exif_widgets[source[1]] = gtk.Entry()
                if mark_dirty:
                    self.exif_widgets[source[1]].connect("changed", self._mark_dirty_image)
                row.pack_start(label, False)
                row.pack_start(self.exif_widgets[source[1]], True)
                if not self.show_source:
                    self.exif_widgets[source[1]].hide()
        for name, text, cbtype, callback in callback_list:
            if cbtype == "button":
                label = gtk.Label()
                label.set_text(text)
                self.exif_widgets[pos + ":" + name + ":Label"] = label
                row.pack_start(label, False)
                icon = gtk.STOCK_EDIT
                size = gtk.ICON_SIZE_MENU
                button = gtk.Button()
                image = gtk.Image()
                image.set_from_stock(icon, size)
                button.add(image)
                button.set_relief(gtk.RELIEF_NONE)
                button.connect("clicked", callback)
                self.exif_widgets[pos + ":" + name] = button
                row.pack_start(button, False)
            elif cbtype == "checkbox":
                button = gtk.CheckButton(text)
                button.set_active(True)
                button.connect("clicked", callback)
                self.exif_widgets[pos + ":" + name] = button
                row.pack_start(button, False)
        row.show_all()
        return row

    def read_metadata(self, obj):
        """
        reads the image metadata after the pyexiv2.Image has been created
        """

        log.debug("Image, ", self.image_path, ' has bean read...')

        # image description
        self.exif_widgets["ActiveImage"].set_text( html_escape( self.orig_image.get_description() ) )

        log.debug( self.plugin_image, "is now the ImageMetadata object!" )
 
        # read the image metadata
        self.plugin_image.read()

        # set up image metadata keys for use in this gramplet
        dataKeyTags = [ KeyTag for KeyTag in self.plugin_image.exif_keys if KeyTag in _DATAMAP ]

        for KeyTag in dataKeyTags:

            # Media image Artist
            if KeyTag == ImageArtist:
                self.exif_widgets["Artist"].set_text( _get_value( KeyTag, self.plugin_image ) )

            # media image Copyright
            elif KeyTag == ImageCopyright:
                self.exif_widgets["Copyright"].set_text( _get_value( KeyTag, self.plugin_image ) )

            # media image DateTime
            elif KeyTag == ImageDateTime:

                # get the dates that an image can have in Gramps
                # date1 may come from the image metadata
                # date2 may come from the Gramps database 
                date1 = _get_value( KeyTag, self.plugin_image )
                date2 = self.orig_image.get_date_object()

                use_date = date1 or date2
                if use_date:
                    self.process_date( use_date )

            # Latitude and Latitude Reference
            elif KeyTag == ImageLatitude:

                # self.LATitude is used for processing, and latitude is used for displaying
                latitude = _get_value( ImageLatitude,   self.plugin_image )
                longitude = _get_value( ImageLongitude, self.plugin_image )

                # if latitude and longitude exist, display them...
                if latitude and longitude:

                    # split latitude metadata into degrees, minutes, and seconds
                    deg, min, sec = rational_to_dms( latitude )

                    # Latitude Direction Reference
                    LatitudeRef = _get_value( ImageLatitudeRef, self.plugin_image )

#                    self.exif_widgets["Latitude"].set_text(
#                            """%s° %s′ %s″ %s""" % ( deg, min, sec, LatitudeRef ) )

                    self.exif_widgets["Latitude"].set_text(
                            "%s %s %s %s" % ( deg, min, sec, LatitudeRef ) )

                    # split longitude metadata into degrees, minutes, and seconds
                    deg, min, sec = rational_to_dms( longitude )

                    # Longitude Direction Reference
                    LongitudeRef = _get_value( ImageLongitudeRef, self.plugin_image )

#                    self.exif_widgets["Longitude"].set_text(
#                            """%s° %s′ %s″ %s""" % ( deg, min, sec, LongitudeRef ) )

                    self.exif_widgets["Longitude"].set_text(
                            "%s %s %s %s" % ( deg, min, sec, LongitudeRef ) )

            # Image Description Field
            elif KeyTag == ImageDescription:

                # metadata Description field 
                self.exif_widgets["Description"].set_text(
                    _get_value( ImageDescription, self.plugin_image ) )

            # image Keywords
            words = ""
            keyWords = _get_value( IptcKeywords, self.plugin_image )
            if keyWords:
                index = 1 
                for word in keyWords:
                    words += word
                    if index is not len(keyWords):
                        words += "," 
                    index += 1 
            self.exif_widgets["Keywords"].set_text( words )

    def save_metadata(self, obj):
        """
        gets the information from the plugin data fields
        and sets the keytag = keyvalue image metadata
        """

        # Artist data field
        artist = self.exif_widgets["Artist"].get_text()
        _set_value( ImageArtist, artist, self.plugin_image )

        # Copyright data field
        copyright = self.exif_widgets["Copyright"].get_text()
        _set_value( ImageCopyright, copyright, self.plugin_image )

        # get date from data field for saving
        # the False flag signifies that we will get the date and time from process_date()
        _set_value( ImageDateTime, self.process_date( None, False ), self.plugin_image )

        # Convert GPS Latitude / Longitude directional Reference
        self.LatitudeRef, self.LongitudeRef = self.getDirectionRef()

        # convert degrees, minutes, seconds to Rational for saving
        if self.LATitude and self.LatitudeRef:
            latitude = coords_to_rational( self.LATitude )

            _set_value( ImageLatitude, latitude, self.plugin_image )
            _set_value( ImageLatitudeRef, self.LatitudeRef, self.plugin_image )

        if self.LONGitude and self.LongitudeRef:
            longitude = coords_to_rational( self.LONGitude )

            _set_value( ImageLongitude, longitude, self.plugin_image )
            _set_value( ImageLongitudeRef, self.LongitudeRef, self.plugin_image )

        # keywords data field
        keywords = [ word for word in self.exif_widgets["Keywords"].get_text().split(",") ]
        _set_value( IptcKeywords, keywords, self.plugin_image )

        # description data field
        start = self.exif_widgets["Description"].get_start_iter()
        end = self.exif_widgets["Description"].get_end_iter()
        meta_descr = self.exif_widgets["Description"].get_text(start, end)
        _set_value( ImageDescription, meta_descr, self.plugin_image )

        # check write permissions for this image
        if not self._dirty_write:
            self.plugin_image.write()

            # notify the user of successful write 
            OkDialog(_("Image metadata has been saved."))

        else:
            WarningDialog(_( "There is an error with this image!\n"
                "You do not have write access..."))

    def clear_metadata(self, obj, cleartype = "All"):
        """
        clears all data fields to nothing

        @param: cleartype -- 
            "Date" = clears only Date entry fields
            "All" = clears all data fields
        """

        # clear all data fields
        if cleartype == "All":
            for key in [ "ActiveImage", "Artist", "Copyright", "NewDate", "NewTime",
                "Latitude", "Longitude", "Keywords", "Description" ]:
                self.exif_widgets[key].set_text( "" )

            self.LATitude     = ""
            self.LatitudeRef  = ""
            self.LONGitude    = ""
            self.LongitudeRef = ""

        # clear only the date and time fields
        else:
            for key in ["NewDate", "NewTime"]:
                self.exif_widgets[key].set_text( "" )

    def process_date(self, tmpDate, read = True):
        """
        Process the date for read and write processes
        year, month, day, hour, minutes, seconds

        @param: tmpDate = variable to be processed
        @param: read -- if True, then process date from the image
                     -- if False, then process date from the data fields
        """

        def split_values(text):
            """
            splits a variable into its pieces
            """

            if "-" in text:
                separator = "-"
            elif "." in text:
                separator = "."
            elif ":" in text:
                separator = ":"
            else:
                separator = " "
            return [value for value in text.split(separator)]
          
        now = time.localtime()

        # get date type
        datetype = tmpDate.__class__

        # data is coming from the image
        if read:

            if ( datetype == datetime ) or ( datetype == date ):
                ddate = "%04d-%s-%02d" % ( tmpDate.year, return_month( tmpDate.month ), tmpDate.day )

            # ImageDateTime is in datetime format
            if datetype == datetime:

                dtime = "%02d:%02d:%02d" % ( tmpDate.hour, tmpDate.minute, tmpDate.second )

            # ImageDateTime is in date format
            elif datetype == date:

                dtime = "%02d:%02d:%02d" % ( now[3], now[4], now[5] )

            # ImageDateTime is in list format
            elif datetype == list:

                ddate = "%04d-%s-%02d" % ( tmpDate[0].year, return_month( tmpDate[0].month ), tmpDate[0].day )
                dtime = "%02d:%02d:%02d" % ( now[3], now[4], now[5] )

            # ImageDateTime is in string format
            elif datetype == str:

                # separate date and time from the string
                if "/" in tmpDate:
                    separator = "/"
                else:
                    separator = " "
                ddate, dtime = tmpDate.split( separator )

                year, month, day = split_values( ddate )
                year, day = int( year ), int( day )
 
                if isinstance(month, int): 
                    ddate = "%04d-%s-%02d" % ( year, _dd.short_months[month], day )
                elif isinstance(month, str):
                    ddate = "%04d-%s-%02d" % ( year, month, day )

            self.exif_widgets["NewDate"].set_text( ddate )
            self.exif_widgets["NewTime"].set_text( dtime )

        # process date for saving to the image
        else:

            # get date and time from their data fields...
            ddate = self.exif_widgets["NewDate"].get_text()
            dtime = self.exif_widgets["NewTime"].get_text()

            # if date is in proper format: 1826-Apr-12 or 1826 April 12
            if ( ddate and ( ddate.count("-") == 2 or ddate.count(" ") == 2 ) ):
                year, month, day = split_values( ddate )

                year, day = int( year ), int( day )
            else:
                year, month, day = False, False, False

            # if time is in proper format: 14:00:00 
            if ( dtime and ( dtime.count(":") == 2 or dtime.count(" ") == 2 ) ):
                hour, minutes, seconds = split_values( dtime )
                hour, minutes, seconds = int( hour ), int( minutes ), int( seconds )
            else:
                hour, minutes, seconds = False, False, False

            # if any value for date or time is False, then do not save date
            if any(value == False for value in [year, month, day, hour, minutes, seconds] ):

                wdate = False

            else:

                # if month == "10", return integer?
                # if ( month == "October" or wmonth == "Oct"), return integer?
                month = return_month( month )

                # ExifImage Year must be greater than or equal to 1900
                # if not, we save it as a string
                if 1826 < year <= 1899:
                    wdate = "%04(year)d-%(month)s-%02(day)d %02(hour)d:%02(minutes)d:%02(seconds)d" % {
                            'year' : wyear, 'month' : wmonth, 'day' : wday,
                            'hour' : whour, "minutes" : wminutes, "seconds" : wseconds }

                # year -> 1900
                else:

                    # check to make sure all values are valid?
                    try:
                        wdate = datetime( year, month, day, hour, minutes, seconds )

                    # one or more values are invalid
                    except ValueError:
                            wdate = False

            if wdate is not False:
                _set_value( ImageDateTime, wdate, self.plugin_image )

            else:
                WarningDialog(_("The date is invalid.\n "
                    "%s\n  Date will NOT be saved.") % tmpDate )
 
# -------------------------------------------------------------------
#                          Date Calendar functions
# -------------------------------------------------------------------
    def select_date(self, obj):
        """
        will allow you to choose a date from the calendar widget
        """
 
        tip = _("Double click a date to return the date.")

        self.app = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.app.tooltip = tip
        self.app.set_title(_("Select Date"))
        self.app.set_default_size(450, 200)
        self.app.set_border_width(10)
        self.exif_widgets["Calendar"] = gtk.Calendar()
        self.exif_widgets["Calendar"].connect('day-selected-double-click', self.double_click)
        self.app.add(self.exif_widgets["Calendar"])
        self.exif_widgets["Calendar"].show()
        self.app.show()

    def double_click(self, obj):
        """
        receives double-clicked and returns the selected date to "NewDate"
        widget
        """

        year, month, day = self.exif_widgets["Calendar"].get_date()
        self.exif_widgets["NewDate"].set_text( "%04d-%s-%02d" % ( year, _dd.short_months[month], day ) )

        now = time.localtime()
        self.exif_widgets["NewTime"].set_text( "%02d:%02d:%02d" % ( now[3], now[4], now[5] ) )

        # close this window
        self.app.destroy()

# -------------------------------------------------------------------
#          GPS Coordinates functions
# -------------------------------------------------------------------
    def getDirectionRef(self):
        """
        get lat/ long direction references
        """
        latref, longref = "N", "W"

        latitude = self.exif_widgets["Latitude"].get_text()
        longitude = self.exif_widgets["Longitude"].get_text()

        if "." in latitude and "." in longitude:
            if latitude[0] == "-":
                latref = "S"
            if longitude[0] == "-":
                longref = "E"

        # Degrees, Minutes, and Seconds Format is selected
        elif (latitude and latitude.count(" ") >= 2) and (longitude and longitude.count(" ") >= 2):

            if "S" in latitude:
                latref = "S"
            if "E" in longitude:
                longref = "E"

        # return the GPS Directional References
        return latref, longref

    def convert2decimal(self, obj):
        """
        will convert a decimal GPS Coordinates into decimal format
        """

        latitude =   self.exif_widgets["Latitude"].get_text()
        longitude = self.exif_widgets["Longitude"].get_text()

        # if latitude and longitude exist and if they are in decimal format?
        if (latitude and latitude.count(" ") >= 2) and (longitude and longitude.count(" ") >= 2):

            # split latitude degrees, minutes, seconds, direction into its pieces
            if "N" or "S" in latitude:
                deg, min, sec, LatitudeRef = latitude.split(" ", 3)
            else:
                deg, min, sec = latitude.split(" ", 2)
                LatitudeRef = "N"

                if latitude[0] == "-": 
                    LatitudeRef = "S"
                    latitude = latitude.replace("-", "")

            # if there is a decimal point, remove it or we can't do math?
            if "." in sec:
                sec, dump = sec.split(".")

            # convert values to integers 
            deg, min, sec = int( deg ), int( min ), int( sec ) 
            latitude = str( (deg + (min / 60) + (sec / 3600) ) )

            if LatitudeRef == "S":
                latitude = "-" + latitude

            # split longitude degrees, minutes, seconds, direction into its pieces
            if "E" or "W" in longitude:
                deg, min, sec, LongitudeRef = longitude.split(" ", 3)
            else:
                deg, min, sec = latitude.split(" ", 2)
                LongitudeRef = "E"

                if longitude[0] == "-":
                    LongitudeRef = "W"
                    longitude = longitude.replace("-", "")

            # if there is a decimal point, remove it or we can't do math?
            if "." in sec:
                sec, dump = sec.split(".")

            # convert values to integers
            deg, min, sec = int( deg ), int( min ), int( sec )
            longitude = str( (deg + (min / 60) + (sec / 3600) ) )

            if LongitudeRef == "W":
                longitude = "-" + longitude

            self.exif_widgets["Latitude"].set_text(   latitude )
            self.exif_widgets["Longitude"].set_text( longitude ) 

    def convert2dms(self, obj):
        """
        will convert a decimal GPS Coordinates into degrees, minutes, seconds
        for display only
        """

        latitude =   self.exif_widgets["Latitude"].get_text()
        longitude = self.exif_widgets["Longitude"].get_text()

        if (latitude and latitude.count(".") == 1) and (longitude and longitude.count(".") == 1):

            # convert latitude and longitude to a DMS with separator of ":"
            latitude, longitude = conv_lat_lon( latitude, longitude, "DEG-:" )
 
            # remove negative symbol if there is one?
            LatitudeRef = "N"
            if latitude[0] == "-":
                latitude = latitude.replace("-", "")
                LatitudeRef = "S"
            deg, min, sec = latitude.split(":", 2)

#            self.exif_widgets["Latitude"].set_text(
#                    """%s° %s′ %s″ %s""" % ( deg, min, sec, LatitudeRef ) )

            self.exif_widgets["Latitude"].set_text(
                    "%s %s %s %s" % ( deg, min, sec, LatitudeRef ) )

           # remove negative symbol if there is one?
            LongitudeRef = "E"
            if longitude[0] == "-":
                longitude = longitude.replace("-", "")
                LongitudeRef = "W"
            deg, min, sec = longitude.split(":", 2)

#            self.exif_widgets["Longitude"].set_text(
#                    """%s° %s′ %s″ %s""" % ( deg, min, sec, LongitudeRef ) )

            self.exif_widgets["Longitude"].set_text(
                    "%s %s %s %s" % ( deg, min, sec, LongitudeRef ) )

def string_to_rational(coordinate):
    """
    convert string to rational variable for GPS
    """

    if '.' in coordinate:
        value1, value2 = coordinate.split('.')
        return Rational(int(float(value1 + value2)), 10**len(value2))
    else:
        return Rational(int(coordinate), 1)

def coords_to_rational(coordinates):
    """
    returns the GPS coordinates to Latitude/ Longitude
    """

    return [string_to_rational(coordinate) for coordinate in coordinates.split( " ")]

def rational_to_dms(rational_coords):
    """
    will return a rational set of coordinates to degrees, minutes, seconds
    """

    rd, rm, rs = rational_coords.split(" ")
    rd, rest = rd.split("/")
    rm, rest = rm.split("/")
    rs, rest = rs.split("/")
    rs = rs.replace(".", "")

    # return degrees, minutes, seconds to its callers
    return rd, rm, rs

def _get_value(KeyTag, image):
    """
    gets the value from the Exif Key, and returns it...

    @param: KeyTag -- image metadata key
    @param: image -- pyexiv2 ImageMetadata instance
    """

    # if keytag is from Iptc family?
    if "Iptc" in KeyTag:
        try:
            KeyValue = image[KeyTag].value

        except KeyError:
            KeyValue = ""

    # Xmp Family
    elif "Xmp" in KeyTag:

        try:
            KeyValue = image[KeyTag].raw_value

        except KeyError:
            KeyValue = ""

    # Exif Family
    else:
  
        try:
            KeyValue = image[KeyTag].raw_value

        except KeyError:
            KeyValue = image[KeyTag].value

    # return metadata value
    return KeyValue

def _set_value(KeyTag, KeyValue, image):
    """
    sets the value for the Exif keys

    @param: KeyTag   -- exif key
    @param: KeyValue -- value to be saved
    @param: image -- pyexiv2 ImageMetadata instance
    """

    if "Exif" in KeyTag:
        try:
            image[KeyTag].value = KeyValue
        except KeyError:
            image[KeyTag] = ExifTag( KeyTag, KeyValue )
        except ValueError:
            pass

    elif "Xmp" in KeyTag:
        try:
            image[KeyTag].value = KeyValue
        except KeyError:
            image[KeyTag] = XmpTag(KeyTag, KeyValue)
        except ValueError:
            pass

    elif "Iptc" in KeyTag:
        try:
            image[KeyTag].value = KeyValue
        except KeyError:
            image[KeyTag] = IptcTag( KeyTag, KeyValue )
        except ValueError:
            pass
