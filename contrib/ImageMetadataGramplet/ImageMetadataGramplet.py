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
import os, sys
from datetime import datetime, date
import time

# abilty to escape certain characters from html output...
from xml.sax.saxutils import escape as _html_escape

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
_DOWNLOAD_LINK = "http://tilloy.net/dev/pyexiv2/"
pyexiv2_required = True
try:
    import pyexiv2
    REQ_pyexiv2_VERSION = (0, 2, 0)
    if pyexiv2.version_info < REQ_pyexiv2_VERSION:
        pyexiv2_required = False

except ImportError:
    raise Exception(_("The, pyexiv2, python binding library, to exiv2 is not "
        "installed on this computer.\n It can be downloaded from here: %s\n"
        "You will need to download at least pyexiv2-%d.%d.%d .") % (
            REQ_pyexiv2_VERSION, _DOWNLOAD_LINK))
               
except AttributeError:
    pyexiv2_required = False

if not pyexiv2_required:
    raise Exception(_("The minimum required version for pyexiv2 must be pyexiv2-%d.%d.%d\n"
        "or greater.  You may download it from here: %s\n\n") % (
            REQ_pyexiv2_VERSION, _DOWNLOAD_LINK))

# import the required classes for use in this gramplet
from pyexiv2 import ExifTag, ImageMetadata, IptcTag, Rational

from gen.plug import Gramplet
from DateHandler import displayer as _dd

from QuestionDialog import OkDialog, WarningDialog

import gen.lib
import Utils
from PlaceUtils import conv_lat_lon

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

def _return_month(month):
    """
    returns either an integer of the month number or the abbreviated month name

    @param: rmonth -- can be one of:
        10, "10", or ( "Oct" or "October" )
    """

    if isinstance(month, str):
        for s, l, i in _allmonths:
            found = any(month == value for value in [s, l])
            if found:
                month = int(i)
                break
    else:
        for s, l, i in _allmonths:
            if str(month) == i:
                month = l
                break
    return month

def _split_values(text):
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

# ------------------------------------------------------------------------
# Gramplet class
# ------------------------------------------------------------------------
class imageMetadataGramplet(Gramplet):

#------------------------------------------------
#     User interface
#------------------------------------------------
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

        # Save and Abandon
        row = gtk.HBox()
        button = gtk.Button(_("Save"))
        button.connect("clicked", self.save_metadata)
        row.pack_start(button, True)
        button = gtk.Button(_("Abandon"))
        button.connect("clicked", self.clear_metadata)
        row.pack_start(button, True)
        rows.pack_start(row, False)

        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(rows)
        rows.show_all()

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
        else:
            self._clear_image(None)

        # if dirty_image, there is a problem?
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
                found = any(_imgtype == filetype for filetype in _valid_types)
                if not found:
                    self._mark_dirty_read(None)
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
            "Example: 1826-Apr-12 or 1826-April-12"))

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

#------------------------------------------------
#     Reads metadata from image
#------------------------------------------------
    def read_metadata(self, obj):
        """
        reads the image metadata after the pyexiv2.Image has been created
        """

        # setup initial values in case there is no image metadata to be read?
        self.artist, self.copyright, self.description = "", "", ""
        self.LATitude, self.LONGitude = "", ""

        # image description
        self.exif_widgets["ActiveImage"].set_text(
            _html_escape(self.orig_image.get_description() )
        )

        # read the image metadata
        self.plugin_image.read()

        # set up image metadata keys for use in this gramplet
        dataKeyTags = [ KeyTag for KeyTag in self.plugin_image.exif_keys if KeyTag in _DATAMAP ]

        for KeyTag in dataKeyTags:

            # Media image Artist
            if KeyTag == ImageArtist:
                self.artist = _get_value(KeyTag, self.plugin_image)
                self.exif_widgets["Artist"].set_text(self.artist)

            # media image Copyright
            elif KeyTag == ImageCopyright:
                self.copyright = _get_value(KeyTag, self.plugin_image)
                self.exif_widgets["Copyright"].set_text(self.copyright)

            # media image DateTime
            elif KeyTag == ImageDateTime:

                # date1 may come from the image metadata
                # date2 may come from the Gramps database 
                date1 = _get_value( KeyTag, self.plugin_image )
                date2 = _get_value("Iptc.Application2.DateCreated", self.plugin_image)
                date3 = self.orig_image.get_date_object()

                use_date = date1 or date2 or date3
                if use_date:
                    self.process_date(use_date)
                else:
                    self.process_date(None)

            # Latitude and Latitude Reference
            elif KeyTag == ImageLatitude:

                latitude  =  _get_value(ImageLatitude, self.plugin_image)
                longitude = _get_value(ImageLongitude, self.plugin_image)

                # if latitude and longitude exist, display them...
                if (latitude and longitude):

                    # split latitude metadata into (degrees, minutes, and seconds) from Rational
                    deg, min, sec = rational_to_dms(latitude)

                    # Latitude Direction Reference
                    self.LatitudeRef = _get_value(ImageLatitudeRef, self.plugin_image)

                    self.exif_widgets["Latitude"].set_text(
                        """%s° %s′ %s″ %s""" % (deg, min, sec, self.LatitudeRef)
                    )
                    self.LATitude = "%s %s %s" % (deg, min, sec)

                    # split longitude metadata into degrees, minutes, and seconds
                    deg, min, sec = rational_to_dms(longitude)

                    # Longitude Direction Reference
                    self.LongitudeRef = _get_value(ImageLongitudeRef, self.plugin_image)

                    self.exif_widgets["Longitude"].set_text(
                        """%s° %s′ %s″ %s""" % (deg, min, sec, self.LongitudeRef)
                    )
                    self.LONGitude = "%s %s %s" % (deg, min, sec)

            # Image Description Field
            elif KeyTag == ImageDescription:
                self.description = _get_value(ImageDescription, self.plugin_image)
                self.exif_widgets["Description"].set_text(self.description)

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
                self.exif_widgets["Keywords"].set_text(words)

#------------------------------------------------
#     Writes/ saves metadata to image
#------------------------------------------------
    def save_metadata(self, obj):
        """
        gets the information from the plugin data fields
        and sets the keytag = keyvalue image metadata
        """

        # Artist data field
        artist = self.exif_widgets["Artist"].get_text()
        if (artist and (self.artist is not artist)):
            _set_value(ImageArtist, artist, self.plugin_image)

        # Copyright data field
        copyright = self.exif_widgets["Copyright"].get_text()
        if (copyright and (self.copyright is not copyright)):
            _set_value(ImageCopyright, copyright, self.plugin_image)

        # get date from data field for saving
        # the False flag signifies that we will get the date and time from process_date()
        wdate = self.exif_widgets["NewDate"].get_text()
        wtime = self.exif_widgets["NewTime"].get_text()
        wdate = _write_date(wdate, wtime)
        if wdate is not False: 
            _set_value(ImageDateTime, wdate, self.plugin_image)

        # if lat/ long is in decimal, convert to (degrees, minutes, seconds)
        latitude =   self.exif_widgets["Latitude"].get_text()
        longitude = self.exif_widgets["Longitude"].get_text()
        if ((latitude and latitude.count(".") == 1) and (longitude and longitude.count(".") == 1)):
            self.convert2dms(self.plugin_image)

        # convert (degrees, minutes, seconds) to Rational for saving
        if (self.LATitude and self.LatitudeRef):
            _set_value(ImageLatitude, coords_to_rational(self.LATitude), self.plugin_image)
            _set_value(ImageLatitudeRef, self.LatitudeRef, self.plugin_image)

        # convert (degrees, minutes, seconds) to Rational for saving
        if (self.LONGitude and self.LongitudeRef):
            _set_value(ImageLongitude, coords_to_rational(self.LONGitude), self.plugin_image)
            _set_value(ImageLongitudeRef, self.LongitudeRef, self.plugin_image)

        # keywords data field
        keywords = [word for word in self.exif_widgets["Keywords"].get_text().split(",") if word]
        if keywords:
            _set_value(IptcKeywords, keywords, self.plugin_image)

        # description data field
        start = self.exif_widgets["Description"].get_start_iter()
        end = self.exif_widgets["Description"].get_end_iter()
        meta_descr = self.exif_widgets["Description"].get_text(start, end)
        if (meta_descr and (self.description is not meta_descr)):
            _set_value(ImageDescription, meta_descr, self.plugin_image)

        # check write permissions for this image
        if not self._dirty_write:
            self.plugin_image.write()

            # update when completed saving
            self.update() 

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

#------------------------------------------------
#     Date/ Time functions
#------------------------------------------------
    def process_date(self, tmpDate):
        """
        Process the date for read and write processes
        year, month, day, hour, minutes, seconds

        @param: tmpDate = variable to be processed
        """

        year, month, day = False, False, False
        now = time.localtime()
        datetype = tmpDate.__class__

        # get local time for when if it is not available?
        hour, minutes, seconds = now[3:6]

        found = any(datetype == _type for _type in [datetime, date, gen.lib.date.Date, list])
        if found:

            #ImageDateTime is in datetime.datetime format
            if datetype == datetime:
                year, month, day = tmpDate.year, tmpDate.month, tmpDate.day
                hour, minutes, seconds = tmpDate.hour, tmpDate.minute, tmpDate.second

            # ImageDateTime is in datetime.date format
            elif datetype == date:
                year, month, day = tmpDate.year, tmpDate.month, tmpDate.day

            # ImageDateTime is in gen.lib.date.Date format
            elif datetype == gen.lib.date.Date:
                year, month, day = tmpDate.get_year(), tmpDate.get_month(), tmpDate.get_day()

            # ImageDateTime is in list format
            else:
                year, month, day = tmpDate[0].year, tmpDate[0].month, tmpDate[0].day

        # ImageDateTime is in string format
        elif datetype == str:

            # separate date and time from the string
            if "/" in tmpDate:
                rdate, rtime = tmpDate.split("/")
            elif tmpDate.count(" ") == 1:
                rdate, rtime = tmpDate.split(" ")
            else: 
                rdate = tmpDate
                rtime = False

            # split date elements
            year, month, day = _split_values(rdate)

            # split time elements if not False
            if rtime is not False:
                hour, minutes, seconds = _split_values(rtime)
                hour, minutes, seconds = int(hour), int(minutes), int(seconds) 
 
        found = any(value == False for value in [year, month, day] )
        if not found:

            # convert values to integers
            year, day = int(year), int(day)
            month = _return_month(month)
 
            if isinstance(month, int): 
                rdate = "%04d-%s-%02d" % (year, _dd.long_months[month], day)
            elif isinstance(month, str):
                rdate = "%04d-%s-%02d" % (year, month, day)
            rtime = "%02d:%02d:%02d" % (hour, minutes, seconds)

            # display the date from the image
            self.exif_widgets["NewDate"].set_text(rdate)

            # display the time from the image
            self.exif_widgets["NewTime"].set_text(rtime)

# -----------------------------------------------
#              Date Calendar functions
# -----------------------------------------------
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

#------------------------------------------------
#     Database functions
#------------------------------------------------
    def post_init(self):
        self.connect_signal("Media", self.update)
        
    def db_changed(self):
        self.dbstate.db.connect('media-update', self.update)
        self.update()

# -------------------------------------------------------------------
#          GPS Coordinates functions
# -------------------------------------------------------------------
    def convert2decimal(self, obj):
        """
        will convert a decimal GPS Coordinates into decimal format
        """

        # get lat/ long from the data fields
        latitude  =  self.exif_widgets["Latitude"].get_text()
        longitude = self.exif_widgets["Longitude"].get_text()

        # if latitude and longitude exist and if they are in decimal format?
        if (latitude and latitude.count(" ") >= 2) and (longitude and longitude.count(" ") >= 2):

            # convert degrees, minutes, seconds to an eight (8) point decimal
            latitude, longitude = conv_lat_lon( unicode(latitude), unicode(longitude), "D.D8")

            # display lat/ long in decimal format 
            self.exif_widgets["Latitude"].set_text(  latitude)
            self.exif_widgets["Longitude"].set_text(longitude)

    def convert2dms(self, obj):
        """
        will convert a decimal GPS Coordinates into degrees, minutes, seconds
        for display only
        """

        # get Latitude/ Longitude from data fields
        latitude =   self.exif_widgets["Latitude"].get_text()
        longitude = self.exif_widgets["Longitude"].get_text()

        if (latitude and latitude.count(".") == 1) and (longitude and longitude.count(".") == 1):

            # convert latitude and longitude to a DMS with separator of ":"
            latitude, longitude = conv_lat_lon(latitude, longitude, "DEG-:")
 
            # remove negative symbol if there is one?
            self.LatitudeRef = "N"
            if latitude[0] == "-":
                latitude = latitude.replace("-", "")
                self.LatitudeRef = "S"
            deg, min, sec = latitude.split(":", 2)

            self.exif_widgets["Latitude"].set_text(
                """%s° %s′ %s″ %s""" % (deg, min, sec, self.LatitudeRef)
            )
            self.LATitude = "%s %s %s" % (deg, min, sec)

           # remove negative symbol if there is one?
            self.LongitudeRef = "E"
            if longitude[0] == "-":
                longitude = longitude.replace("-", "")
                self.LongitudeRef = "W"
            deg, min, sec = longitude.split(":", 2)

            self.exif_widgets["Longitude"].set_text(
                """%s° %s′ %s″ %s""" % (deg, min, sec, self.LongitudeRef)
            )
            self.LONGitude = "%s %s %s" % (deg, min, sec)

def string_to_rational(coordinate):
    """
    convert string to rational variable for GPS
    """

    if '.' in coordinate:
        value1, value2 = coordinate.split('.')
        return Rational(int(float(value1 + value2)), 10**len(value2))
    else:
        return Rational(int(coordinate), 1)

def coords_to_rational(Coordinates):
    """
    returns the GPS coordinates to Latitude/ Longitude
    """

    return [string_to_rational(coordinate) for coordinate in Coordinates.split( " ")]

def rational_to_dms(rational_coords):
    """
    will return a rational set of coordinates to degrees, minutes, seconds
    """

    ratdeg, ratmin, ratsec= _split_values( rational_coords )
    ratdeg, rest = ratdeg.split("/")
    ratmin, rest = ratmin.split("/")
    ratsec, rest = ratsec.split("/")

    if len(rest) > 1:
        ratsec = str( float( int(ratsec) / int(rest) ) )

    return ratdeg, ratmin, ratsec

#------------------------------------------------
# Get and Set image metadata KeyTags
#------------------------------------------------
def _get_value(KeyTag, image):
    """
    gets the value from the Exif Key, and returns it...

    @param: KeyTag -- image metadata key
    @param: image -- pyexiv2 ImageMetadata instance
    """

    try:
        KeyValue = image[KeyTag].raw_value

    except KeyError:
        KeyValue = "[not set]"

    return KeyValue

def _set_value(KeyTag, KeyValue, image):
    """
    sets the value for the Exif keys

    @param: KeyTag   -- exif key
    @param: KeyValue -- value to be saved
    @param: image -- pyexiv2 ImageMetadata instance
    """

    # Exif KeyValue family?
    if "Exif" in KeyTag:
        try:
            image[KeyTag].value = KeyValue

        except KeyError:
            image[KeyTag] = ExifTag(KeyTag, KeyValue)

        except ValueError:
            pass

    # Iptc KeyValue family?
    else:
        try:
            image[KeyTag].value = KeyValue

        except KeyError:
            image[KeyTag] = IptcTag(KeyTag, KeyValue)

        except ValueError:
            pass

#------------------------------------------------
# Process Date/ Time fields for saving to image
#------------------------------------------------
def _write_date(wdate, wtime):
    """
    process the date/ time for writing to image

    @param: wdate -- date from the interface
    @param: wtime -- time from the interface
    """

    # if date is in proper format: 1826-Apr-12 or 1826-April-12
    if (wdate and wdate.count("-") == 2):
        year, month, day = _split_values(wdate)
    elif not wdate:
        year, month, day = False, False, False   

    # if time is in proper format: 14:06:00
    if (wtime and wtime.count(":") == 2):
        hour, minutes, seconds = _split_values(wtime)
    elif not wtime:
        hour, minutes, seconds = False, False, False

    # if any value for date or time is False, then do not save date
    bad_datetime = any(value == False for value in [year, month, day, hour, minutes, seconds] )
    if not bad_datetime:

        # convert each value for date/ time
        year, day = int(year), int(day)
        hour, minutes, seconds = int(hour), int(minutes), int(seconds)

        # do some error trapping...
        if year < 1826:  year = 1826
        if day == 0:  day = 1
        if hour >= 24: hour = 0
        if minutes > 59:  minutes = 59
        if seconds > 59:  seconds = 59

        # convert month, and do error trapping
        try:
            month = int(month)
        except ValueError:
            month = _return_month(month)
        if month > 12:  month = 12

        # ExifImage Year must be greater than 1900
        # if not, we save it as a string
        if year < 1900:
            wdate = "%04d-%s-%02d %02d:%02d:%02d" % (
                    year, _dd.long_months[month], day, hour, minutes, seconds)

        # year -> or equal to 1900
        else:

            # check to make sure all values are valid for datetime?
            # if not, date becomes False and will not be saved?  
            try:
                wdate = datetime(year, month, day, hour, minutes, seconds)
            except ValueError:
                    wdate = False
    else:
        wdate = False

    # return the modified date/ time
    return wdate
