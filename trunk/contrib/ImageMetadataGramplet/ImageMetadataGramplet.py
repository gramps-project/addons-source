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
import re

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
    from pyexiv2 import ImageMetadata, ExifTag, XmpTag, IptcTag, Rational
except ImportError:
    pyexivmsg = _( "The, pyexiv2, python binding library, to exiv2 is not "
                   "installed on this computer.\n It can be downloaded either from your "
                   "ocal repository or from here\n")
    pyexivmsg += "http://tilloy.net/dev/pyexiv2"
    raise Exception( pyexivmsg )

from gen.plug import Gramplet

from DateHandler import displayer as _dd
from DateHandler import parser as _dp

from QuestionDialog import OkDialog, WarningDialog

import gen.mime
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
__valid_types = ["jpeg", "exv", "tiff", "dng", "nef", "pef", "pgf", "png", "psd", "jp2"]

# set up Abbreviated Months for select_date()
_ABBREV_MONTHS = []
_ABBREV_MONTHS.append("")
_ABBREV_MONTHS += [_dd.long_months[month] for month in range(1, 13)]

# first camera was created April 12, 1826
# http://wiki.answers.com/Q/What_date_was_the_camera_invented 
_DATE = datetime(1826, 4, 12, 00, 00, 00)

_DESCRIPTION = _( "Enter text describing this image and who might be in "
                  "the image.  It might be best to enter a location for this image, "
                  "especially if there is no GPS Latitude/ Longitude information available.")

# set up Exif keys for Image Exif keys
ImageArtist        = "Exif.Image.Artist"
ImageCopyright    = "Exif.Image.Copyright"
ImageDateTime     = "Exif.Image.DateTime"
ImageLatitude     = "Exif.GPSInfo.GPSLatitude"
ImageLatitudeRef  = "Exif.GPSInfo.GPSLatitudeRef"
ImageLongitude    = "Exif.GPSInfo.GPSLongitude"
ImageLongitudeRef = "Exif.GPSInfo.GPSLongitudeRef"
ImageDescription  = "Exif.Image.ImageDescription"

# set up keys for Image IPTC keys
IptcKeywords    = "Iptc.Application2.Keywords"

_EXIFMAP = [ ImageArtist, ImageCopyright, ImageDateTime, ImageDescription,
             ImageLatitude, ImageLatitudeRef, ImageLongitude, ImageLongitudeRef ]

# ------------------------------------------------------------------------
# Gramplet class
# ------------------------------------------------------------------------
class imageMetadataGramplet(Gramplet):

    def init(self):

        self.exif_column_width = 15
        self.Exif_widgets = {}

        self.orig_image   = False
        self.image_path   = False
        self.plugin_image = False
        self.mime_type    = False

        rows = gtk.VBox()
        for items in [
            ("Active:Image",    _("Active:Image"), None, True,  [],         False, 0),
            ("Artist",          _("Artist"),       None, False, [],         True,  0),
            ("Copyright",       _("Copyright"),    None, False, [],         True,  0),

            # calendar date entry
            ("Date",   "",                       None, True,  
            [("Select Date",    _("Select Date"),   self.select_date)],     True, 0),

            # manual date entry, example: 12 Apr 1826 00:00:00
	    ("Select:Date",     _("Creation Date"), None, False, [],        True, 0),

            # Latitude/ longitude GPS
	    ("Latitude",        _("Latitude"),     None, False, [],         True,  0),
	    ("Longitude",       _("Longitude"),    None, False, [],         True,  0),

            # keyword entry
            ("Keywords",        _("Keywords"),     None, False, [],         True,  0) ]: 

            pos, text, choices, readonly, callback, dirty, default = items
            row = self.make_row(pos, text, choices, readonly, callback, dirty, default)
            rows.pack_start(row, False)

        # separator before description textbox
        separator = gtk.HSeparator()
        rows.pack_start(separator, True)
	
        # description textbox label
        label = gtk.Label()
        label.set_text("<b><u>%s</u></b>" % _("Description"))
        label.set_use_markup(True)
        rows.pack_start(label, False)

        # description textbox field
        description_box = gtk.TextView()
        description_box.set_wrap_mode(gtk.WRAP_WORD)
        description_box.set_editable(True)
        self.Exif_widgets["Description"] = description_box.get_buffer()
        self.Exif_widgets["Description"].set_text(_DESCRIPTION)
        rows.pack_start(description_box, True, True, 0)

        # provide tooltips for this gramplet
        self.setup_tooltips(object)

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

        # clear up the data fields
        self.clear_data_entry(None)

    def post_init(self):
        self.connect_signal("Media", self.update)
        
    def setup_tooltips(self, obj):
        """
        setup tooltips for each field
        """

        self.Exif_widgets["Artist"].set_tooltip_text(_("Enter the name "
            "of the person who took this image."))

        self.Exif_widgets["Copyright"].set_tooltip_text(_("Enter the copyright"
            " information for the image.  xample: (C) 2010 Smith and Wesson"))

        self.Exif_widgets["Keywords"].set_tooltip_text(_("Enter keywords for this image "
            "seprated by a comma."))

        self.Exif_widgets["Latitude"].set_tooltip_text(_("Enter the GPS "
            "Latitude as decimal format."))

        self.Exif_widgets["Longitude"].set_tooltip_text(_("Enter the GPS "
            "Longitude as decimal format."))

    def main(self): # return false finishes
        """
        get the active media, mime type, and reads the image metadata
        """
        self.plugin_image = False

        # get active object handle of Media type
        self.active_media = self.get_active("Media")
        if not self.active_media:
            return
        else:
            log.debug( 'CURRENT MEDIA HANDLE IS NOW: ', self.active_media )

        # get media object from database
        self.orig_image = self.dbstate.db.get_object_from_handle( self.active_media )

        # get media object full path
        self.image_path = Utils.media_path_full( self.dbstate.db, self.orig_image.get_path() )

        # clear data entry fields
        self.clear_data_entry( object )

        # get image mime type
        mime_type = gen.mime.get_type( self.image_path )
        if mime_type and mime_type.startswith("image/"):
            try:

                # get the pyexiv2 instance
                self.plugin_image = ImageMetadata( self.image_path )

                # read the image metadata
                self.read_image_metadata( self.image_path )

            except IOError:
                WarningDialog(_( "This media object is NOT usable by this addon!\n"
                                 "Choose another media object..."))

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
            self.Exif_widgets[pos] = gtk.Label()
            self.Exif_widgets[pos].set_alignment(0.0, 0.5)
            self.Exif_widgets[pos].set_use_markup(True)
            label.set_alignment(0.0, 0.5)
            row.pack_start(label, False)
            row.pack_start(self.Exif_widgets[pos], False)
        else:
            label.set_text("%s: " % text)
            label.set_width_chars(self.exif_column_width)
            label.set_alignment(1.0, 0.5) 
            if choices == None:
                self.Exif_widgets[pos] = gtk.Entry()
                row.pack_start(label, False)
                row.pack_start(self.Exif_widgets[pos], True)
            else:
                eventBox = gtk.EventBox()
                self.Exif_widgets[pos] = gtk.combo_box_new_text()
                eventBox.add(self.Exif_widgets[pos])
                for add_type in choices:
                    self.Exif_widgets[pos].append_text(add_type)
                self.Exif_widgets[pos].set_active(default) 
                row.pack_start(label, False)
                row.pack_start(eventBox, True, True)
        for name, text, callback in callback_list:
            label = gtk.Label()
            label.set_text(text)
            self.Exif_widgets[pos + ":" + name + ":Label"] = label
            row.pack_start(label, False)
            icon = gtk.STOCK_EDIT
            size = gtk.ICON_SIZE_MENU
            button = gtk.Button()
            image = gtk.Image()
            image.set_from_stock(icon, size)
            button.add(image)
            button.set_relief(gtk.RELIEF_NONE)
            button.connect("clicked", callback)
            self.Exif_widgets[pos + ":" + name] = button
            row.pack_start(button, False)
        row.show_all()
        return row

    def _get_value(self, key):
        """
        gets the value from the Exif Key, and returns it...

        @param: key -- exif key
        """

        # return the key value to its caller
        try:
            return self.plugin_image[key].raw_value
        except KeyError:
            return ""

    def read_image_metadata(self, obj):
        """
        reads the image metadata after the pyexiv2.Image has been created
        """

        # if True, the image has read permissions
        # if False, there are errors somewhere ...
        if os.access( obj, os.R_OK ):

            log.debug("Image, ", self.image_path, ' has bean read...')

            self.Exif_widgets["Active:Image"].set_text( self.orig_image.get_description() )

            log.debug( self.plugin_image, "is the ImageMetadata object!" )
 
            # read the image metadata
            self.plugin_image.read()

            # set up image exif keys for use in this gramplet 
            exifKeyTags = [ KeyTag for KeyTag in self.plugin_image.exif_keys
                if KeyTag in _EXIFMAP]

            for KeyTag in exifKeyTags:

                if KeyTag == ImageArtist:
                    self.Exif_widgets["Artist"].set_text(
                        self._get_value( KeyTag ) )

                elif KeyTag == ImageCopyright:
                    self.Exif_widgets["Copyright"].set_text(
                        self._get_value( KeyTag ) )

                elif KeyTag == ImageDateTime:
                    self.Exif_widgets["Select:Date"].set_text(
                        self._get_value ( KeyTag )
                    )

                elif KeyTag == ImageLatitude:
                    latitude = self._get_value( KeyTag )
                    if latitude:
                        deg, min, sec = self.rational_to_dms( latitude )
                        sec = sec.replace(".", "")

                        # Latitude Reference
                        LatitudeRef = self._get_value( ImageLatitudeRef )
                        self.latitude = "%s %s %s %s" % ( deg, min, sec, LatitudeRef )

                        latitude = """%s° %s′ %s″ %s""" % (deg, min, sec, LatitudeRef)
                        self.Exif_widgets["Latitude"].set_text( latitude )

                elif KeyTag == ImageLongitude:
                    longitude = self._get_value( KeyTag )
                    if longitude:
                        deg, min, sec = self.rational_to_dms( longitude )
                        sec = sec.replace(".", "")

                        # Longitude Direction Reference
                        LongitudeRef = self._get_value( ImageLongitudeRef )
                        self.longitude = "%s %s %s %s" % ( deg, min, sec, LongitudeRef )

                        longitude = """%s° %s′ %s″ %s""" % (deg, min, sec, LongitudeRef)
                        self.Exif_widgets["Longitude"].set_text( longitude )

                else:

                    self.Exif_widgets["Description"].set_text(
                        self._get_value( ImageDescription ) )

                subject = ""
                keyWords = self._get_value( IptcKeywords )
                if keyWords:
                    index = 1 
                    for word in keyWords:
                        subject += word
                        if index is not len(keyWords):
                            subject += "," 
                        index += 1 
                self.Exif_widgets["Keywords"].set_text( subject )

        else:
            WarningDialog(_( "There is an error with this image!\n"
                "You do not have read access to this image..."))


    def _set_value(self, KeyTag, KeyValue):
        """
        sets the value for the Exif keys

        @param: KeyTag   -- exif key
        @param: KeyValue -- value to be saved
        """
        # if KeyValue is equal to nothing, return without setting the value
        if not KeyValue:
            return

        if "Exif" in KeyTag:
            try:
                self.plugin_image[KeyTag].value = KeyValue
            except KeyError:
                self.plugin_image[KeyTag] = ExifTag( KeyTag, KeyValue )

        elif "Xmp" in KeyTag:
            try:
                self.plugin_image[KeyTag].value = KeyValue
            except KeyError:
                self.plugin_image[KeyTag] = XmpTag(KeyTag, KeyValue)

        else:
            try:
                self.plugin_image[KeyTag].value = KeyValue
            except KeyError:
                self.plugin_image[KeyTag] = IptcTag( KeyTag, KeyValue )

    def write_image_metadata(self, obj):
        """
        saves the data fields to the image
        """

        # make sure the image is writable permissions
        if os.access( self.image_path, os.W_OK ):

            # check to see if we have both latitude/ longitude, if one exists
            latitude = self.Exif_widgets["Latitude"].get_text()
            longitude = self.Exif_widgets["Longitude"].get_text()
            if latitude and not longitude:
                OkDialog(_( "You have etered Latitude, but not longitude.  Please enter Longitude..."))
            elif longitude and not latitude:
                OkDialog(_( "You have etered Longitude, but not Latitude.  Please enter Latitude..."))

            artist = self.Exif_widgets["Artist"].get_text()
            if artist:
                self._set_value( ImageArtist, artist )

            copyright = self.Exif_widgets["Copyright"].get_text()
            if copyright:
                self._set_value( ImageCopyright, copyright )

            dtime = self.Exif_widgets["Select:Date"].get_text()
            if dtime:
                self._set_value( ImageDateTime, dtime )

            # Convert GPS Latitude / Longitude Coordinates for display
            lat_ref, long_ref = self.convert_decimal_deg_min_sec( self.plugin_image )

            # convert d, m, s to Rational for saving
            if self.latitude is not None:
                latitude = coords_to_rational( self.latitude )
                self._set_value( ImageLatitude, latitude )

                # save Latitude Reference
                if lat_ref is not None: 
                    self._set_value( ImageLatitudeRef, lat_ref )   

            # convert d, m, s to Rational for saving
            if self.longitude is not None:
                longitude = coords_to_rational( self.longitude )
                self._set_value( ImageLongitude, longitude )

                # save Longitude Reference
                if long_ref is not None:
                    self._set_value( ImageLongitudeRef, long_ref ) 

            keywords = [ word for word in self.Exif_widgets["Keywords"].get_text().split(",") ]
            self._set_value( IptcKeywords, keywords )

            start = self.Exif_widgets["Description"].get_start_iter()
            end = self.Exif_widgets["Description"].get_end_iter()
            meta_descr = self.Exif_widgets["Description"].get_text(start, end)
            if meta_descr:
                self._set_value(ImageDescription, meta_descr)

            # write the metadata to the image
            self.plugin_image.write()
            OkDialog(_("Image metadata has been saved."))

        else:
            WarningDialog(_( "There are errors with this image!"))

    def clear_data_entry(self, obj):
        """
        clears all data fields to nothing
        """

        for key in [ "Active:Image", "Description", "Select:Date", "Artist", "Copyright",
            "Latitude", "Longitude", "Keywords" ]:
            self.Exif_widgets[key].set_text( "" )

        for key in ["LatitudeRef", "LongitudeRef"]:
	    self.LatitudeRef = ""
	    self.LongitudeRef = "" 

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

    def select_date(self, obj):
        """
        will allow you to choose a date from the calendar widget

        @param: obj -- media object from the database
        """
 
        self.app = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.app.set_title(_("Select Date"))
        self.app.set_default_size(450, 200)
        self.app.set_border_width(10)
        self.Exif_widgets["Calendar"] = gtk.Calendar()
        self.Exif_widgets["Calendar"].connect('day-selected-double-click', self.double_click)
        self.app.add(self.Exif_widgets["Calendar"])
        self.Exif_widgets["Calendar"].show()
        self.app.show()

    def double_click(self, obj):
        """
        receives double-clicked and returns the selected date to "Date" 
        widget
        """

        year, month, day = self.Exif_widgets["Calendar"].get_date()
        now = datetime.now()
        image_date = "%04d %s %02d %02d:%02d:%02d" % (
            year, _ABBREV_MONTHS[(month + 1)], day, now.hour, now.minute, now.second )

        self.Exif_widgets["Select:Date"].set_text( image_date )
        self.app.destroy()

    def convert_decimal_deg_min_sec(self, obj):
        """
        Converts decimal GPS coordinates to Degrees, Minutes, Seconds 
        GPS coordinates
        """

        latitude = self.Exif_widgets["Latitude"].get_text()
        longitude = self.Exif_widgets["Longitude"].get_text()
        lat_ref, long_ref = None, None
        self.latitude, self.longitude = None, None

        if latitude and longitude:

            if ("." in latitude or "." in longitude):

                # convert to d, m, s with a seperator of : for saving to Exif Metadata 
                self.latitude, self.longitude = conv_lat_lon( latitude, longitude, "DEG-:" )

                if "-" in latitude:
                    self.latitude = self.latitude[1:]
                    lat_ref = "S"
                else:
                    lat_ref = "N"

                if "-" in longitude:
                    self.longitude = self.longitude[1:]
                    long_ref = "W"
                else:
                    long_ref = "E"

                # convert to 4 point decimal
                latitude, longitude = conv_lat_lon( latitude, longitude, "D.D4" )

            # convert to deg, mins, secs  
            latitude, longitude = conv_lat_lon( latitude, longitude, "DEG" )

        elif latitude:
            WarningDialog(_( "You have only entered a Latitude GPS Coordinate!"))
            latitude = ""

        elif longitude:
            WarningDialog(_( "You have only entered a Longitude GPS Coordinate!"))
            longitude = ""

        self.Exif_widgets["Latitude"].set_text(   latitude )
        self.Exif_widgets["Longitude"].set_text( longitude )

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
