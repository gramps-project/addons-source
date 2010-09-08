#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009-2010    Rob G. Healey    <robhealey1@gmail.com>
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
from datetime import datetime
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

from gen.lib import Date

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
_DATE = Date()
_DATE.set_yr_mon_day(1826, 4, 12)

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
#------------------------------------------------------------------------
#
# Gramplet class
#
#------------------------------------------------------------------------
class ImageMetadataGramplet(Gramplet):
    def init(self):
        self.exif_column_width = 20
        self.exif_widgets = {}
        self.xmp_widgets  = {}
        self._dirty_image = False
        self._dirty = False

        self.plugin_image = False
        self.orig_image = False

        rows = gtk.VBox()
        for items in [
            ("Active:Image", _("Active Image"),   None, True,  [],      False, 0, None), 

            ("Photographer", _("Photographer"),  None, False, [],      True,   0, None),
            ("Copyright",    _("Copyright"),     None, False, [],      True,   0, None),
            ("Select:Date",  _("Select Date"),   None, True,
                [("Select:Date",   "",  "button", self.select_date)],  True,   0, None),

            ("Date",         _("Date"),          None, False, [],      True,   0, None),
            ("Latitude",     _("Latitude"),      None, False, [],      True,   0, None),
            ("Longitude",    _("Longitude"),     None, False, [],      True,   0, None) ]:

            pos, text, choices, readonly, callback, dirty, default, source = items
            row = self.make_row(pos, text, choices, readonly, callback, dirty, default, source)
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

        self.clear_data_entry(None)
        self.connect_signal("Media", self.media_changed)

    def media_changed(self, handle):
        """
        handles when an image has been changed

        @param: handle -- handle for an image in the database
        """

        # get media image from database and get full media path
        self.orig_image = self.dbstate.db.get_object_from_handle( handle )
        self.image_path = Utils.media_path_full( self.dbstate.db, self.orig_image.get_path() )

        # get the pyexiv2 image
        self.plugin_image = self.get_plugin_image( self.orig_image )

        if self.plugin_image:

            # read image metadata
            self.read_image_metadata( self.plugin_image )

            # update all data fields
            self.update()

    def get_plugin_image(self, media_obj):
        """
        creates the pyexiv2 image based on media object
        """

        if not media_obj:
            return False

        # get full image path
        self.image_path = Utils.media_path_full( self.dbstate.db, media_obj.get_path() )
        media_exists = os.path.isfile( self.image_path )

        if not media_exists:
            WarningDialog(_( "This image does NOT exists on this computer.  Please "
                             "select another image."))
            return False

        # get image mime type and split into its pieces
        mime_type = self.orig_image.get_mime_type()
        ftype, imgtype = mime_type.split("/")
        if imgtype not in img_types:
            WarningDialog(_( "The image type of this media object is NOT usable "
                             "by this addon.  Please select another image..." ))
            return False

        # get image read/ write permissions
        self.writable = os.access( self.image_path, os.W_OK )
        self.readable = os.access( self.image_path, os.R_OK )

        # get the pyexiv2 image file
        return ImageMetadata( self.image_path )

    def update(self):

        if not self.orig_image:
            return

        # Fill in current image metadata
        image_title = self.orig_image.get_description()
        self.exif_widgets["Active:Image"].set_text("<i>%s</i> " % image_title)
        self.exif_widgets["Active:Image"].set_use_markup(True)

        # Photographer
        if self.photographer:
            self.exif_widgets["Photographer"].set_text( self.photographer )

        # Copyright
        if self.copyright:
            self.exif_widgets["Copyright"].set_text( self.copyright )

        # Date
        if self.date:
            self.exif_widgets["Date"].set_text( self.date )

        # Latitude
        if self.latitude:
            self.exif_widgets["Latitude"].set_text( self.latitude )

        # Longitude
        if self.longitude:
            self.exif_widgets["Longitude"].set_text( self.longitude )

        # Xmp Subject
        if self.subject:
            self.xmp_widgets["Subject"].set_text( self.subject )

        # Description
        self.description = self.description if self.description else _DESCRIPTION
        self.exif_widgets["Description"].set_text( self.description )

        self._dirty = False

    def main(self): # return false finishes
        if self._dirty:
            return

        self._dirty_image = self.orig_image
        if self.orig_image:
            self.exif_widgets["Active:Image"].show()
            self.exif_widgets["Active:Image"].set_text( self.orig_image.get_description() )

    def make_row(self, pos, text, choices=None, readonly=False, callback_list=[],
                 mark_dirty=False, default=0, source=None):

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
                    self.exif_widgets[pos].connect("changed", self.mark_dirty)
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
                    self.exif_widgets[pos].connect("changed", self.mark_dirty)
                row.pack_start(label, False)
                row.pack_start(eventBox, True)
            if source:
                label = gtk.Label()
                label.set_text("%s: " % source[0])
                label.set_width_chars(self.exif_source_width)
                label.set_alignment(1.0, 0.5) 
                self.exif_widgets[source[1] + ":Label"] = label
                self.exif_widgets[source[1]] = gtk.Entry()
                if mark_dirty:
                    self.exif_widgets[source[1]].connect("changed", self.mark_dirty)
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

    def mark_dirty(self, obj):
        self._dirty = True

    def convert_decimal_deg_min_sec(self, obj):
        """
        Converts decimal GPS coordinates to Degrees, Minutes, Seconds 
        GPS coordinates
        """

        lat_ref, long_ref = None, None
        latitude = self.exif_widgets["Latitude"].get_text()
        longitude = self.exif_widgets["Longitude"].get_text()
        if latitude and longitude:

            if ("." in latitude and "." in longitude):

                # convert to d, m, s with a seperator of : for saving to Exif Metadata 
                latitude, longitude = conv_lat_lon( latitude,
                                                    longitude,
                                                    "DEG" )
                self.exif_widgets["Latitude"].set_text(   latitude )
                self.exif_widgets["Longitude"].set_text( longitude )

            # get Latitude Direction Reference
            if "N" in latitude:
                lat_ref = "N"
            elif "S" in latitude:
                lat_ref = "S"

            # get Longitude Direction Reference
            if "E" in longitude:
                long_ref = "E"
            elif "W" in longitude:
                long_ref = "W"

            # return latitude and longitude reference directions
            return lat_ref, long_ref

        # return None
        return lat_ref, long_ref

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
                self.plugin_image[keyTag].value = keyValue
            except KeyError:
                self.plugin_image[keyTag] = ExifTag(keyTag, keyValue)

        elif "Xmp" in keyTag:
            try:
                self.plugin_image[keyTag].value = keyValue
            except KeyError:
                self.plugin_image[keyTag] = XmpTag(keyTag, keyValue)

    def write_image_metadata(self, obj):
        """
        saves the data fields to the image
        """

        # if image is not writable because of permissions, return
        if not self.writable:
            return

        # check to see if we have both latitude/ longitude, if one exists
        latitude = self.exif_widgets["Latitude"].get_text()
        longitude = self.exif_widgets["Longitude"].get_text()
        if latitude and not longitude:
            OkDialog(_( "You have etered Latitude, but not longitude.  Please enter Longitude..."))
        elif longitude and not latitude:
            OkDialog(_( "You have etered Longitude, but not Latitude.  Please enter Latitude..."))
        elif not latitude and not longitude:
            pass

# <!--  Description                                 -->
# -----------------------------------------------------------------------------------------
        start = self.exif_widgets["Description"].get_start_iter()
        end = self.exif_widgets["Description"].get_end_iter()
        meta_descr = self.exif_widgets["Description"].get_text(start, end)
        if meta_descr:
            self.set_value(ImageDescription, meta_descr)

# <!--  Date/ Time                                  -->
# -----------------------------------------------------------------------------------------
        datetime = self.exif_widgets["Select:Date"].get_text()
        if datetime:
            self.set_value(ImageDateTime, datetime)

# <!--  Photographer                                -->
# -----------------------------------------------------------------------------------------
        photographer = self.exif_widgets["Photographer"].get_text()
        if photographer:
            self.set_value(ImagePhotographer, photographer)

# <!--  Copyright                                   -->
# -----------------------------------------------------------------------------------------
        copyright = self.exif_widgets["Copyright"].get_text()
        if copyright:
            self.set_value(ImageCopyright, copyright)

# <!--  Latitude                                    -->
# -----------------------------------------------------------------------------------------
        # Convert GPS Latitude / Longitude Coordinates for display
        lat_ref, long_ref = self.convert_decimal_deg_min_sec( self.plugin_image )

        # convert d, m, s to Rational for saving
        if self.image_latitude is not None:
            latitude = coords_to_rational( self.image_latitude )
            self.set_value( ImageLatitude, latitude )

            # save Latitude Reference
            if lat_ref is not None: 
                self.set_value( ImageLatitudeRef, lat_ref )   

# <!--  Longitude                                    -->
# ------------------------------------------------------------------------------------------
        # convert d, m, s to Rational for saving
        if self.image_longitude is not None:
            longitude = coords_to_rational( self.image_longitude )
            self.set_value( ImageLongitude, longitude )

            # save Longitude Reference
            if long_ref is not None:
                self.set_value( ImageLongitudeRef, long_ref ) 

# <!--  Subject                                    -->
# ----------------------------------------------------------------------------------------
        keyWords = self.xmp_widgets["Subject"].get_text()
        if keyWords:
            keyWords = [ subject for subject in keyWords.split(",")]
            self.set_value( XmpSubject, keyWords )  

        # write the metadata to the image
        self.plugin_image.write()
        OkDialog(_("Image metadata has been saved."))

    def clear_data_entry(self, obj):
        """
        clears all data fields to nothing
        """

        for key in ["Description", "Select:Date", "Photographer", "Copyright",
            "Latitude", "Longitude"]:
            self.exif_widgets[key].set_text("")

        self.LatitudeRef  = None
        self.LongitudeRef = None
        self.image_latitude = None
        self.image_longitude = None

        self.xmp_widgets["Subject"].set_text("")

        # set up variables for ImageMetadata
        self.photographer = None
        self.copyright = None
        self.date = None
        self.latitude = None
        self.longitude = None
        self.subject = None
        self.description = _DESCRIPTION

    def get_value(self, keyTag):
        """
        gets the value from the Exif Key, and returns it...

        @param: keyTag -- exif key
        """

        # return the key value to its caller
        try:
            return self.plugin_image[keyTag].raw_value
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

        if not obj or not self.readable:
            return

        # clear all data fields first
        self.clear_data_entry( obj )

        # read the image metadata
        obj.read()

        # set up image exif keys for use in this gramplet 
        exifKeyTags = [ keyTag for keyTag in self.plugin_image.exif_keys
            if keyTag in _DATAMAP]

        for keyTag in exifKeyTags:

# <!--      Description                                 -->
# -----------------------------------------------------------------------------------------
            if keyTag == ImageDescription:
                self.description = self.get_value( keyTag )

# <!--      Date/ Time                                  -->
# -----------------------------------------------------------------------------------------
            elif keyTag == ImageDateTime:
                self.date = self.get_value( keyTag )
                if self.date:
                    pass
                elif self.orig_image.get_date_object():
                    self.date = self.orig_image.get_date_object()
                else:
                    self.date = _DATE  

# <!--      Photographer                                -->
# -----------------------------------------------------------------------------------------
            elif keyTag == ImagePhotographer:
                self.photographer = self.get_value( keyTag )

# <!--      Copyright                                   -->
# -----------------------------------------------------------------------------------------
            elif keyTag == ImageCopyright:
                self.copyright = self.get_value( keyTag )

# <!--      Latitude                                    -->
# -----------------------------------------------------------------------------------------
            elif keyTag == ImageLatitude:
                latitude = self.get_value( keyTag )
                if latitude:
                    deg, min, sec = self.rational_to_dms( latitude )
                    sec = sec.replace("0", '')

                    # Latitude Reference
                    LatitudeRef = self.get_value( ImageLatitudeRef )
                    self.image_latitude = "%s %s %s" % ( deg, min, sec )

                    self.latitude = """%s° %s′ %s″ %s""" % (deg, min, sec, LatitudeRef)

# <!--      Longitude                                  -->
# -----------------------------------------------------------------------------------------
            elif keyTag == ImageLongitude:
                longitude = self.get_value( keyTag )
                if longitude:
                    deg, min, sec = self.rational_to_dms( longitude )
                    sec = sec.replace("0", '')

                    # Longitude Direction Reference
                    LongitudeRef = self.get_value( ImageLongitudeRef )
                    self.image_longitude = "%s %s %s" % ( deg, min, sec )

                    self.longitude = """%s° %s′ %s″ %s""" % (deg, min, sec, LongitudeRef)

# <!--      Subject                                     -->
# -----------------------------------------------------------------------------------------
            xmpKeyTags = self.plugin_image.xmp_keys
            xmpKeyTags = [ keyTag for keyTag in xmpKeyTags
                if keyTag in _DATAMAP]

            self.subject = ""
            for keyTag in xmpKeyTags:
                if keyTag == XmpSubject:
                    keyWords = self.get_value( keyTag )
                    if keyWords:
                        index = 1
                        for word in keyWords:
                            self.subject += word
                            if index is not len(keyWords):
                                self.subject += "," 
                                index += 1 

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
        now = datetime.now()
        image_date = "%04d %s %02d %02d:%02d:%02d" % (year, 
            _ABBREV_MONTHS[(month + 1)], day, now.hour, now.minute, now.second)

        self.exif_widgets["Date"].set_text( image_date )
        self.app.destroy()

    def post_init(self):
        """
        disconnects the signal
        """

        self.disconnect("active-changed")

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
    returns the GPS coordinates for Latitude/ Longitude
    """

    return [string_to_rational(coordinate) for coordinate in coordinates.split( " ")]
