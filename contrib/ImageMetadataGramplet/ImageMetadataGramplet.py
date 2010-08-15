#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009-2010 Rob G. Healey <robhealey1@gmail.com>
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
#
# Python Modules
#
# *****************************************************************************

import os
import datetime
import time
import re

# -----------------------------------------------------------------------------
#
# GTK modules
#
# -----------------------------------------------------------------------------

import gtk

# -----------------------------------------------------------------------------
#
# GRAMPS modules
#
# -----------------------------------------------------------------------------

from gen.plug import Gramplet
import Utils

from DateHandler import displayer as _dd

from QuestionDialog import OkDialog, WarningDialog
import gen.mime

from PlaceUtils import conv_lat_lon

from TransUtils import get_addon_translator
_ = get_addon_translator().ugettext

# import the pyexiv2 library classes for this addon
try:
    from pyexiv2 import ImageMetadata, ExifTag, XmpTag, Rational
except ImportError:
    pyexivmsg = _( "The, pyexiv2, python binding library, to exiv2 is not "
                   "installed on this computer.\n It can be downloaded either from your "
                   "ocal repository or from here\n")
    pyexivmsg += "http://tilloy.net/dev/pyexiv2"
    raise Exception( pyexivmsg )

# -----------------------------------------------------------------------------
#
# Constants
#
# -----------------------------------------------------------------------------

# available image types for exiv2
img_types = ["jpeg", "exv", "tiff", "dng", "nef", "pef", "pgf", "png", "psd", "jp2"]

# set up Abbreviated Months for select_date()
_ABBREV_MONTHS = []
_ABBREV_MONTHS.append("")
_ABBREV_MONTHS += [_dd.long_months[month] for month in range(1, 13)]

# first camera was created April 12, 1826
# http://wiki.answers.com/Q/What_date_was_the_camera_invented 
_DATE = datetime.datetime(1826, 4, 12, 14, 30, 00)

_DESCRIPTION = _( "Enter text describing this image and who might be in "
                  "the image.  It might be best to enter a location for this image, "
                  "especially if there is no GPS Latitude/ Longitude information available.")

# set up exif keys for the image
ImageDescription =  "Exif.Image.ImageDescription"
ImageDateTime =     "Exif.Image.DateTime"
ImagePhotographer = "Exif.Image.Artist"
ImageCopyright =    "Exif.Image.Copyright"
ImageLatitudeRef =  "Exif.GPSInfo.GPSLatitudeRef"
ImageLatitude =     "Exif.GPSInfo.GPSLatitude"
ImageLongitudeRef = "Exif.GPSInfo.GPSLongitudeRef"
ImageLongitude =    "Exif.GPSInfo.GPSLongitude"
XmpSubject =        "Xmp.dc.subject"

_DATAMAP = [ ImageDescription, ImageDateTime, ImagePhotographer, 
             ImageCopyright, ImageLatitudeRef, ImageLatitude, ImageLongitudeRef,
             ImageLongitude, XmpSubject ]
# ------------------------------------------------------------------------
#
# Gramplet class
#
# ------------------------------------------------------------------------

class imageMetadataGramplet(Gramplet):
    """
    degrees symbol = [Ctrl] [Shift] u \00b0 = °
    minutes symbol =                  \2032 = ′
    seconds symbol =                  \2033 = ″
    """     

    def init(self):
        """
        sets up the variables, widgets, and data fields
        """
        
        self.exif_column_width = 15
        self.dirty = False
        self.exif_widgets = {}
        self.xmp_widgets  = {}

        rows = gtk.VBox()
        for items in [
            ("Active image",  _("Active image"), None, True,  [],    False, 0),
            ("Photographer",  _("Photographer"), None, False, [],    True,  0),
            ("Copyright",     _("Copyright"),    None, False, [],    True,  0),

            ("Date",   "",                       None, True,  
            [("Select Date", _("Select Date"),   self.select_date)], True, 0),
	    ("Select:Date",  _("Media Date"),    None, False, [],    True, 0), 

	    ("Latitude",      _("Latitude"),     None, False, [],    True,  0),
	    ("Longitude",     _("Longitude"),    None, False, [],    True,  0) ]: 

            pos, text, choices, readonly, callback, dirty, default = items
            row = self.make_row(pos, text, choices, readonly, callback, dirty, default)
            rows.pack_start(row, False)

        # Xmp Subject
        row = gtk.HBox()
        label = gtk.Label()
        label.set_text("<b>%s</b>" % _("Subject"))
        label.set_use_markup(True)
        label.set_width_chars(15)
        row.pack_start(label, False)
        subject = gtk.Entry()
        self.xmp_widgets["Subject"] = subject
        row.pack_start(self.xmp_widgets["Subject"], True)
        rows.pack_start(row, True)

        # separator before description textbox
        separator = gtk.HSeparator()
        rows.pack_start(separator, True)
	
        # description textbox label
        label = gtk.Label()
        label.set_text("<b><u>%s</u></b>" % _("Description"))
        label.set_use_markup(True)
        rows.pack_start(label, False)

        # description textbox
        description_box = gtk.TextView()
        description_box.set_wrap_mode(gtk.WRAP_WORD)
        description_box.set_editable(True)
        self.exif_widgets["Description"] = description_box.get_buffer()
        self.exif_widgets["Description"].set_text(_DESCRIPTION)
        rows.pack_start(description_box, True, True, 0)

        # set up tooltip information for the fields
        self.exif_widgets["Photographer"].set_tooltip_text(_("Enter the name "
            "of the person who took this image."))

        self.exif_widgets["Copyright"].set_tooltip_text(_("Enter the copyright"
            " information for the image.  xample: (C) 2010 Smith and Wesson"))

        self.xmp_widgets["Subject"].set_tooltip_text(_("Enter words that "
            "describe this image, separated by comma.\n  Example: Kids,house,"
            "dog,car"))

        self.exif_widgets["Latitude"].set_tooltip_text(_("Enter the GPS "
            "Latitude as decimal format "))

        self.exif_widgets["Longitude"].set_tooltip_text(_("Enter the GPS "
            "Longitude as decimal format "))

        # Save, Clear
        row = gtk.HBox()
        button = gtk.Button(_("Save"))
        button.connect("clicked", self.write_image_metadata)
        row.pack_start(button, True)
        button = gtk.Button(_("Clear"))
        button.connect("clicked", self.clear_data_entry)
        row.pack_start(button, True)
        rows.pack_start(row, True)

        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(rows)
        rows.show_all()

        self.connect_signal("Media", self.media_changed)

    def media_changed(self, handle):
        """
        handles when an image has been changed

        @param: handle -- handle for an image in the database
        """

        # get media
        self.media = self.dbstate.db.get_object_from_handle( handle )

        # get the pyexiv image
        self._get_image( self.media )

        # read image metadata
        self.read_image_metadata(self.media)

    def make_row(self, pos, text, choices = None, readonly = False, callback_list=[], 
                 mark_dirty = False, default = 0):
        """
        creates the gtk row
        """

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
                row.pack_start(label, False)
                row.pack_start(self.exif_widgets[pos], True)
            else:
                eventBox = gtk.EventBox()
                self.exif_widgets[pos] = gtk.combo_box_new_text()
                eventBox.add(self.exif_widgets[pos])
                for add_type in choices:
                    self.exif_widgets[pos].append_text(add_type)
                self.exif_widgets[pos].set_active(default) 
                row.pack_start(label, False)
                row.pack_start(eventBox, True, True)
        for name, text, callback in callback_list:
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
        row.show_all()
        return row

    def str_to_date(self, str2date):
        """
        converts a date string to datetime.datetime

        @param: str2date -- a date string: will always bee in ISO format
        """

        if not str2date:
            return datetime.datetime.now()

        # return the date string to datetime.datetime format
        return datetime.datetime(*time.strptime(
            str2date, "%Y %b %d %H:%M:%S")[0:6])

    def date_to_str(self, date2str):
        """
        converts a datetime.datetime to string

        @param: date2str -- a datetime.datetime to string
        """

        if not date2str:
            return ""  

        dateType = date2str.__class__
        time = time.localtime()
        if dateType == datetime.datetime:
            date2str = "%04d %s %02d %02d:%02d:%02d" % (date2str.year, 
                _ABBREV_MONTHS[date2str.month], date2str.day, date2str.hour, 
                date2str.minute, date2str.second)
        elif dateType == datetime.date:
            date2str = "%04d %s %02d %02d:%02d:%02d" % (date2str.year, 
                _ABBREV_MONTHS[date2str.month], date2str.day, time[3], 
                time[4], time[5])
        else:
            date2str = "%04d %s %02d %02d:%02d:%02d" % (date2str.year, 
                _ABBREV_MONTHS[date2str.month], date2str.day, time[3], 
                time[4], time[5])

        # return date as a string to its callers
        return date2str
 
    def set_value(self, keyTag, keyValue):
        """
        sets the value for the Exif keys

        @param: keyTag   -- exif key
        @param: keyValue -- value to be saved
        """

        # if keyValue is equal to nothing, return without setting the value
        if not keyValue:
            return

        if "Exif" in keyTag:
            try:
                self.image[keyTag].value = keyValue
            except KeyError:
                self.image[keyTag] = ExifTag(keyTag, keyValue)

        elif "Xmp" in keyTag:
            try:
                self.image[keyTag].value = keyValue
            except KeyError:
                self.image[keyTag] = XmpTag(keyTag, keyValue)

    def write_image_metadata(self, obj):
        """
        saves the data fields to the image
        """

        # check to see if we have both latitude/ longitude, if one exists
        latitude = self.exif_widgets["Latitude"].get_text()
        longitude = self.exif_widgets["Longitude"].get_text()
        if latitude and not longitude:
            OkDialog(_( "You have etered Latitude, but not longitude.  Please enter Longitude..."))
        elif longitude and not latitude:
            OkDialog(_( "You have etered Longitude, but not Latitude.  Please enter Latitude..."))

        # get mime type and mime_type description
        if self.mime_type:

            # yes, we do have an image?
            if self.ftype  == "image":

                # check to see if we have an image type that is usable in this addon?
                if self.imgtype in img_types:
		
                    # is this image writable?
                    if self.writable:

# <!--                                      Description                                 -->
# -----------------------------------------------------------------------------------------
                        start = self.exif_widgets["Description"].get_start_iter()
                        end = self.exif_widgets["Description"].get_end_iter()
                        meta_descr = self.exif_widgets["Description"].get_text(start, end)
                        if meta_descr:
                            self.set_value(ImageDescription, meta_descr)

# <!--                                      Date/ Time                                  -->
# -----------------------------------------------------------------------------------------
                        datetime = self.exif_widgets["Select:Date"].get_text()
                        if datetime:
                            self.set_value(ImageDateTime, datetime)

# <!--                                      Photographer                                -->
# -----------------------------------------------------------------------------------------
                        photographer = self.exif_widgets["Photographer"].get_text()
                        if photographer:
                            self.set_value(ImagePhotographer, photographer)

# <!--                                      Copyright                                   -->
# -----------------------------------------------------------------------------------------
                        copyright = self.exif_widgets["Copyright"].get_text()
                        if copyright:
                            self.set_value(ImageCopyright, copyright)

# <!--                                      Latitude                                    -->
# -----------------------------------------------------------------------------------------
                        # Convert GPS Latitude / Longitude Coordinates for display
                        lat_ref, long_ref = self.convert_decimal_deg_min_sec( self.media )

                        # convert d, m, s to Rational for saving
                        if self.latitude is not None:
                            latitude = coords_to_rational( self.latitude )
                            self.set_value( ImageLatitude, latitude )

                        # save Latitude Reference
                        if lat_ref is not None: 
                            self.set_value( ImageLatitudeRef, lat_ref )   

# <!--                                      Longitude                                    -->
# ------------------------------------------------------------------------------------------
                        # convert d, m, s to Rational for saving
                        if self.longitude is not None:
                            longitude = coords_to_rational( self.longitude )
                            self.set_value( ImageLongitude, longitude )

                        # save Longitude Reference
                        if long_ref is not None:
                            self.set_value( ImageLongitudeRef, long_ref ) 

# <!--                                      Subject                                    -->
# ----------------------------------------------------------------------------------------
                        keyWords = self.xmp_widgets["Subject"].get_text()
                        if keyWords:
                            keyWords = [ subject for subject in keyWords.split(",")]
                        self.set_value( XmpSubject, keyWords )  

                        # write the metadata to the image
                        self.image.write()
                        OkDialog(_("Image metadata has been saved."))

                    else:
                        WarningDialog(_( "This image is NOT writable!  Please re- select "
                            "another image."))     

                else:
                    WarningDialog(_( "The file type of this media object is one of a few "
                                     "that can NOT be used by this Gramps addon."))

            else:
                WarningDialog(_( "This media object is NOT an image.  Please re- select "
                    "another image."))

        else:
            WarningDialog(_( "The type of this media object is not able to be "
                             "confirmed.  Please re-select a different media object."))

    def clear_data_entry(self, obj):
        """
        clears all data fields to nothing
        """

        for key in [ "Description", "Select:Date", "Photographer", "Copyright", "Latitude", "Longitude" ]:
            self.exif_widgets[key].set_text("")

        for key in ["LatitudeRef", "LongitudeRef"]:
	    self.LatitudeRef = ""
	    self.LongitudeRef = "" 

        self.xmp_widgets["Subject"].set_text("")

    def _get_image(self, media_obj):
        """
        creates the pyexiv2 image based on media object
        """

        if not media_obj:
            return None, None

        # get full image path
        self.orig_image = Utils.media_path_full( self.dbstate.db, media_obj.get_path() )
        self.media_exists = os.path.isfile( self.orig_image )
        if not self.media_exists:
            WarningDialog(_( "This media image does NOT exists on this computer.  Please "
                             "re- select another image."))

        # get image mime type and split into its pieces
        self.mime_type = self.media.get_mime_type()
        self.ftype, self.imgtype = self.mime_type.split("/")
        if self.imgtype not in img_types:
            WarningDialog(_( "The image type of this media object is NOT usable "
                             "by this addon.  Please re- select another image..." ))

        self.writable = os.access( self.orig_image, os.W_OK )
        if not self.writable:
            OkDialog(_( "This image is not writable."))

        self.readable = os.access( self.orig_image, os.R_OK )
        if not self.readable:
            OkDialog(_( "This image not readable."))

        # get the pyexiv2 image file
        self.image = ImageMetadata( self.orig_image )

    def get_value(self, key):
        """
        gets the value from the Exif Key, and returns it...

        @param: key -- exif key
        """

        # return the key value to its caller
        try:
            return self.image[key].raw_value
        except KeyError:
            return ""

    def rational_to_dms(self, rational_coords):
        """
        will return a rational set of coordinates to degrees, minutes, seconds
        """

        rd, rm, rs = rational_coords.split(" ")
        rd, rest = rd.split("/")
        rm, rest = rm.split("/")
        rs, rest = rs.split("/")

        # return degrees, minutes, seconds to its callers
        return rd, rm, rs

    def read_image_metadata(self, obj):
        """
        reads the image metadata after the pyexiv2.Image has been created
        """

        # clear all data fields first
        self.clear_data_entry(None)

        # check to see if the image is on the computer or not?
        basename = os.path.basename(self.orig_image)
        if os.path.isfile(self.orig_image):

            # get mime type and mime_type description
            mime_type = self.media.get_mime_type()
            if mime_type:

                file_type, image_ftype = mime_type.split("/")

                # yes, we do have an image?
                if file_type == "image":

                    # check to see if we have an image type that is readable?
                    if image_ftype in img_types:
		
		        # check to see if the image has read permissions?
                        if os.access(self.orig_image, os.R_OK):
 
                            # read the image metadata
                            self.image.read()

                            # set up image exif keys for use in this gramplet 
                            exifKeyTags = [ keyTag for keyTag in self.image.exif_keys
                                   if keyTag in _DATAMAP]

                            for keyTag in exifKeyTags:

# <!--                                      Description                                 -->
# -----------------------------------------------------------------------------------------
                                if keyTag == ImageDescription:
                                    self.exif_widgets["Description"].set_text(
                                        self.get_value( keyTag ) )

# <!--                                      Date/ Time                                  -->
# -----------------------------------------------------------------------------------------
                                elif keyTag == ImageDateTime:
                                    self.exif_widgets["Select:Date"].set_text(
                                        self.get_value ( keyTag ) )

# <!--                                      Photographer                                -->
# -----------------------------------------------------------------------------------------
                                elif keyTag == ImagePhotographer:
                                    self.exif_widgets["Photographer"].set_text(
                                        self.get_value( keyTag ) )

# <!--                                      Copyright                                   -->
# -----------------------------------------------------------------------------------------
                                elif keyTag == ImageCopyright:
                                    self.exif_widgets["Copyright"].set_text(
                                        self.get_value( keyTag ) )

# <!--                                      Latitude                                    -->
# -----------------------------------------------------------------------------------------
                                elif keyTag == ImageLatitude:
                                    latitude = self.get_value( keyTag )
                                    if latitude:
                                        d, m, s = self.rational_to_dms( latitude )

                                        # Latitude Reference
                                        LatitudeRef = self.get_value( ImageLatitudeRef )
                                        self.latitude = "%s %s %s %s" % ( d, m, s, LatitudeRef )

                                        latitude = """%s° %s′ %s″ %s""" % (d, m, s, LatitudeRef)
                                        self.exif_widgets["Latitude"].set_text( latitude )

# <!--                                      Longitude                                  -->
# -----------------------------------------------------------------------------------------
                                elif keyTag == ImageLongitude:
                                    longitude = self.get_value( keyTag )
                                    if longitude:
                                        d, m, s = self.rational_to_dms( longitude )

                                        # Longitude Direction Reference
                                        LongitudeRef = self.get_value( ImageLongitudeRef )
                                        self.longitude = "%s %s %s %s" % ( d, m, s, LongitudeRef )

                                        longitude = """%s° %s′ %s″ %s""" % (d, m, s, LongitudeRef)
                                        self.exif_widgets["Longitude"].set_text( longitude )

# <!--                                      Subject                                     -->
# -----------------------------------------------------------------------------------------
                            xmpKeyTags = self.image.xmp_keys
                            xmpKeyTags = [ keyTag for keyTag in xmpKeyTags
                                if keyTag in _DATAMAP]

                            subject = ""
                            for keyTag in xmpKeyTags:
                                if keyTag == XmpSubject:
                                    keyWords = self.get_value( keyTag )
                                    if keyWords:
                                        index = 1
                                        for word in keyWords:
                                            subject += word
                                            if index is not len(keyWords):
                                                subject += "," 
                                            index += 1 
                            self.xmp_widgets["Subject"].set_text( subject )

                        else:
                            WarningDialog(_( "The file permissions of this media object deny it "
                                             "from being read."))

                    else:
		        WarningDialog(_( "The file type of this media object is one of a few "
                                         "that can NOT be used by this Gramps addon."))

                else:
	            WarningDialog(_( "This media object is NOT an image.  Please re-select an image."))

            else:
                WarningDialog(_( "The type of this media object is not able to be "
                                 "confirmed.  Please re-select a different media object."))

        else:
            OkDialog(_( " The media image that you have chosen does NOT exist on this computer."))

    def select_date(self, obj):
        """
        will allow you to choose a date from the calendar widget

        @param: obj -- media object from the database
        """
 
        self.app = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.app.set_title(_("Select Date"))
        self.app.set_default_size(450, 200)
        self.app.set_border_width(10)
        self.exif_widgets["Calendar"] = gtk.Calendar()
        self.exif_widgets["Calendar"].connect('day-selected-double-click', self.double_click)
        self.app.add(self.exif_widgets["Calendar"])
        self.exif_widgets["Calendar"].show()
        self.app.show()

    def post_init(self):
        """
        disconnects the signal
        """

        self.disconnect("active-changed")

    def double_click(self, obj):
        """
        receives double-clicked and returns the selected date to "Date" 
        widget
        """

        year, month, day = self.exif_widgets["Calendar"].get_date()
        now = datetime.datetime.now()
        image_date = "%04d %s %02d %02d:%02d:%02d" % (year, 
            _ABBREV_MONTHS[(month + 1)], day, now.hour, now.minute, now.second)

        self.exif_widgets["Select:Date"].set_text(image_date)
        self.app.destroy()

    def convert_decimal_deg_min_sec(self, obj):
        """
        Converts decimal GPS coordinates to Degrees, Minutes, Seconds 
        GPS coordinates
        """

        latitude = self.exif_widgets["Latitude"].get_text()
        longitude = self.exif_widgets["Longitude"].get_text()
        lat_ref, long_ref = None, None
        self.latitude, self.longitude = None, None

        if latitude and longitude:

            if ("." in latitude and "." in longitude):

                # convert to d, m, s with a seperator of : for saving to Exif Metadata 
                self.latitude, self.longitude = conv_lat_lon( latitude,
                                                              longitude,
                                                              "DEG-:" )

                # remove negative symbol if any?
                if "-" in self.latitude:
                    self.latitude =   self.latitude[1:]

                if "-" in self.longitude:
                    self.longitude = self.longitude[1:]

                # convert to 4 point decimal
                latitude, longitude = conv_lat_lon( latitude, longitude, "D.D4" )

                # convert to deg, mins, secs  
                latitude, longitude = conv_lat_lon( latitude, longitude, "DEG" )

                # get Latitude Direction Reference
                if "N" in latitude:
                    lat_ref = "N"
                elif "S" in latitude:
                    lat_ref = "S"
                else:
                    lat_ref = None 

                # get Longitude Direction Reference
                if "E" in longitude:
                    long_ref = "E"
                elif "W" in longitude:
                    long_ref = "W"
                else:
                    long_ref = None

                self.exif_widgets["Latitude"].set_text(   latitude )
                self.exif_widgets["Longitude"].set_text( longitude )

            else:
                self.exif_widgets["Latitude"].set_text(  "" )
                self.exif_widgets["Longitude"].set_text( "" )
                WarningDialog(_( "There is an ERROR in Latitude/ Longitude conversion."))

        # return Latitude Reference and Longitude Reference back to its caller
        return lat_ref, long_ref
     
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

    return [string_to_rational(coordinate) for coordinate in coordinates.split( ":")]
