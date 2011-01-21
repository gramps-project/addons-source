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

# set up keys for Image Xmp keys
XmpTitle   = "Xmp.dc.title"
XmpSubject = "Xmp.dc.subject"

# set up keys for Image IPTC keys
IptcDateCreated = "Iptc.Application2.DateCreated"
IptcKeywords    = "Iptc.Application2.Keywords"

__EXIFMAP = [ ImageArtist, ImageCopyright, ImageDateTime, ImageDescription,
             ImageLatitude, ImageLatitudeRef, ImageLongitude, ImageLongitudeRef ]

__XMPMAP = [ XmpTitle, XmpSubject ]

__IPTCMAP = [ IptcDateCreated, IptcKeywords ]
# ------------------------------------------------------------------------
# Gramplet class
# ------------------------------------------------------------------------
class imageMetadataGramplet(Gramplet):

    def init(self):

        self.exif_column_width = 15
        self.Exif_widgets = {}
        self.Xmp_widgets  = {}
        self.Iptc_widgets = {}

        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(self.gui.WIDGET)
        self.gui.WIDGET.show()
        
        self.orig_image   = False
        self.image_path   = False
        self.plugin_image = False
        self.mime_type    = False

    def post_init(self):
        self.connect_signal("Media", self.update)
        
    def build_gui(self):
        """
        builds the gui interface
        """

        tip = _("Click on an image, read its Exif Metadata, and edit if you want "
            "to change some of its information.")
        self.gui.tooltip = tip

        rows = gtk.VBox()
        for items in [
            ("Active image",    _("Active image"), None, True,  [],         False, 0),
            ("Title",           _("Title"),        None, False, [],         True,  0),
            ("Artist",          _("Artist"),       None, False, [],         True,  0),
            ("Copyright",       _("Copyright"),    None, False, [],         True,  0),

            # calendar date entry
            ("Date",   "",                       None, True,  
            [("Select Date",    _("Select Date"),   self.select_date)],     True, 0),

            # manual date entry, example: 12 Apr 1826 00:00:00
	    ("Select:Date",     _("Creation Date"), None, False, [],        True, 0),

            # thumbnail preview
            ("Thumbnail",       "",                None, True,
            [("Thumb:Preview",  _("Thumbnail"),    self.thumbnail_window)], True,  0),

            # Latitude/ longitude GPS
	    ("Latitude",        _("Latitude"),     None, False, [],         True,  0),
	    ("Longitude",       _("Longitude"),    None, False, [],         True,  0),

            # subject and keyword entry
            ("Subject",         _("Subject"),      None, False, [],         True,  0),
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

        # set up tooltip information for the fields
        self.Exif_widgets["Artist"].set_tooltip_text(_("Enter the name "
            "of the person who took this image."))

        self.Exif_widgets["Copyright"].set_tooltip_text(_("Enter the copyright"
            " information for the image.  xample: (C) 2010 Smith and Wesson"))

        self.Exif_widgets["Subject"].set_tooltip_text(_("Enter a subject for the image."))

        self.Exif_widgets["Keywords"].set_tooltip_text(_("Enter keywords for this image "
            "seprated by a comma."))

        self.Exif_widgets["Latitude"].set_tooltip_text(_("Enter the GPS "
            "Latitude as decimal format."))

        self.Exif_widgets["Longitude"].set_tooltip_text(_("Enter the GPS "
            "Longitude as decimal format."))

        # Save, Clear
        row = gtk.HBox()
        button = gtk.Button(_("Save"))
        button.connect("clicked", self.write_image_metadata)
        row.pack_start(button, True)
        button = gtk.Button(_("Clear"))
        button.connect("clicked", self.clear_data_entry)
        row.pack_start(button, True)
        rows.pack_start(row, True)
        return rows

    def main(self): # return false finishes
        # get active object handle of Media type
        self.active_media = self.get_active("Media")
        if not self.active_media:
            return
        else:
            print 'CURRENT MEDIA HANDLE IS NOW: ', self.active_media
            return
            # HAPPY CODING
        self.mime_type = self.active_media.get_path().get_mime_type()
        media, type = self.mime_type.split()
        if not media.startswith("image/") or type not in __valid_types:
            return

        self.clear_data_entry( object )
        self.read_image_metadata( self.active_media )

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

    def str_to_date(self, str2date):
        """
        converts a date string to datetime

        @param: str2date -- a date string: will always bee in ISO format
        """

        if not str2date:
            return datetime.now()

        # return the date string to datetime format
        return datetime(*time.strptime(
            str2date, "%Y %b %d %H:%M:%S")[0:6])

    def date_to_str(self, date2str):
        """
        converts a datetime to string

        @param: date2str -- a datetime to string
        """

        if not date2str:
            return ""  

        dateType = date2str.__class__
        time = time.localtime()
        if dateType == datetime:
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
 
    def get_value(self, key):
        """
        gets the value from the Exif Key, and returns it...

        @param: key -- exif key
        """

        # return the key value to its caller
        try:
            return self.plugin_image[key].raw_value
        except KeyError:
            return self.plugin_image[key].value

    def read_image_metadata(self, obj):
        """
        reads the image metadata after the pyexiv2.Image has been created
        """
        self.image_path = Utils.media_path_full( self.dbstate.db, obj.get_path() )

        # if True, the image has read permissions
        # if False, there are errors somewhere ...
        if os.access( self.image_path, os.R_OK ):

            self.plugin_image = ImageMetadata( self.image_path )
 
            # read the image metadata
            self.plugin_image.read()

            # set up image exif keys for use in this gramplet 
            exifKeyTags = [ keyTag for keyTag in self.plugin_image.exif_keys
                if keyTag in __EXIFMAP]
            for keyTag in exifKeyTags:

                if keyTag == ImageArtist:
                    self.Exif_widgets["Artist"].set_text(
                        self.get_value( keyTag ) )

                elif keyTag == ImageCopyright:
                    self.Exif_widgets["Copyright"].set_text(
                        self.get_value( keyTag ) )

                elif keyTag == ImageDateTime:
                    self.Exif_widgets["Select:Date"].set_text(
                        self.get_value ( keyTag ) )

                elif keyTag == ImageLatitude:
                    latitude = self.get_value( keyTag )
                    if latitude:
                        deg, min, sec = self.rational_to_dms( latitude )

                        # Latitude Reference
                        LatitudeRef = self.get_value( ImageLatitudeRef )
                        self.latitude = "%s %s %s %s" % ( deg, min, sec, LatitudeRef )

                        latitude = """%s° %s′ %s″ %s""" % (deg, min, sec, LatitudeRef)
                        self.Exif_widgets["Latitude"].set_text( latitude )

                elif keyTag == ImageLongitude:
                    longitude = self.get_value( keyTag )
                    if longitude:
                        deg, min, sec = self.rational_to_dms( longitude )

                        # Longitude Direction Reference
                        LongitudeRef = self.get_value( ImageLongitudeRef )
                        self.longitude = "%s %s %s %s" % ( deg, min, sec, LongitudeRef )

                        longitude = """%s° %s′ %s″ %s""" % (deg, min, sec, LongitudeRef)
                        self.Exif_widgets["Longitude"].set_text( longitude )

                else:

                    self.Exif_widgets["Description"].set_text(
                        self.get_value( ImageDescription ) )

                xmpKeyTags = [keytsg for keytag in self.plugin_image.xmp_keys
                    if keytafg in __XMPMAP ]
                for keytag in xmpKeyTags:

                    if keytag == XmpTitle:
                        self.Exif_widgets["Title"].set_text(
                            self.get_value( keytag ) )

                    else:

                        self.Exif_widgets["Subject"].set_text(
                            self.get_value( XmpSubject ) )

                subject = ""
                keyWords = self.get_value( IptcKeywords )
                if keyWords:
                    if "," in keywords:
                        index = 1
                        for word in keyWords:
                            subject += word
                            if index is not len(keyWords):
                                subject += "," 
                            index += 1 
                        self.Iptc_widgets["Keywords"].set_text( subject )
                    else: 
                        self.Iptc_widgets["Keywords"].set_text( keywords )

        else:
            WarningDialog(_( "There is an error with this image!\n"
                "You do not have read access to this image..."))


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
                self.plugin_image[keyTag] = ExifTag( keyTag, keyValue )

        elif "Xmp" in keyTag:
            try:
                self.plugin_image[keyTag].value = keyValue
            except KeyError:
                self.plugin_image[keyTag] = XmpTag(keyTag, keyValue)

        elif "Iptc" in KeyTag:
            try:
                self.plugin_image[KeyTag].value = KeyValue
            except KeyError:
                self.plugin_image[KeyTag] = IptcTag( KeyTag, KeyValue )

    def write_image_metadata(self, obj):
        """
        saves the data fields to the image
        """

        writable = os.access( self.orig_image, os.W_OK )

        # If True, there are no errors ...
        # if False, there are errors with this image ...
        if self.dirty:

            # check to see if we have both latitude/ longitude, if one exists
            latitude = self.Exif_widgets["Latitude"].get_text()
            longitude = self.Exif_widgets["Longitude"].get_text()
            if latitude and not longitude:
                OkDialog(_( "You have etered Latitude, but not longitude.  Please enter Longitude..."))
            elif longitude and not latitude:
                OkDialog(_( "You have etered Longitude, but not Latitude.  Please enter Latitude..."))

            artist = self.Exif_widgets["Artist"].get_text()
            if artist:
                self.set_value(ImageArtist, artist)

            copyright = self.Exif_widgets["Copyright"].get_text()
            if copyright:
                self.set_value(ImageCopyright, copyright)

            datetime = self.Exif_widgets["Select:Date"].get_text()
            if datetime:
                self.set_value(ImageDateTime, datetime)

            # Convert GPS Latitude / Longitude Coordinates for display
            lat_ref, long_ref = self.convert_decimal_deg_min_sec( self.media )

            # convert d, m, s to Rational for saving
            if self.latitude is not None:
                latitude = coords_to_rational( self.latitude )
                self.set_value( ImageLatitude, latitude )

                # save Latitude Reference
                if lat_ref is not None: 
                    self.set_value( ImageLatitudeRef, lat_ref )   

            # convert d, m, s to Rational for saving
            if self.longitude is not None:
                longitude = coords_to_rational( self.longitude )
                self.set_value( ImageLongitude, longitude )

                # save Longitude Reference
                if long_ref is not None:
                    self.set_value( ImageLongitudeRef, long_ref ) 

            keyWords = self.Xmp_widgets["Subject"].get_text()
            if keyWords:
                keyWords = [ subject for subject in keyWords.split(",")]
                self.set_value( XmpSubject, keyWords )  

            start = self.Exif_widgets["Description"].get_start_iter()
            end = self.Exif_widgets["Description"].get_end_iter()
            meta_descr = self.Exif_widgets["Description"].get_text(start, end)
            if meta_descr:
                self.set_value(ImageDescription, meta_descr)

            # write the metadata to the image
            self.plugin_image.write()
            OkDialog(_("Image metadata has been saved."))

        else:
            WarningDialog(_( "There are errors with this image!"))

    def clear_data_entry(self, obj):
        """
        clears all data fields to nothing
        """

        for key in [ "Description", "Select:Date", "Artist", "Copyright", "Latitude", "Longitude" ]:
            self.Exif_widgets[key].set_text("")

        for key in ["LatitudeRef", "LongitudeRef"]:
	    self.LatitudeRef = ""
	    self.LongitudeRef = "" 

        self.Xmp_widgets["Subject"].set_text("")

    def _get_image(self, media_obj):
        """
        creates the pyexiv2 image based on media object
        """

        # determine the image read/ write permissions
        self.writable = os.access( self.image_path, os.W_OK )

        # get the pyexiv2 image file
        return ImageMetadata( self.image_path )

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

	def pressButton(self, widget, data=None):
		print "Pressed"

    def delete_event(self, widget, event, data=None):
        return False

    def destroy(self, widget, data=None):
        gtk.main_quit()

    def thumbnail_window(self, obj):
        """
        display thumbnail preview if the image has  one or
        create a thumbnail for it ...
        """

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect("delete_event", self.delete_event)
        self.window.connect("destroy", self.destroy)
        self.window.set_border_width(10)
        self.window.set_title(_("Thumbnail Preview"))
        self.window.set_default_size(200, 200)


        button = gtk.Button()
        button.connect("clicked", self.pressButton, None)
        button.connect_object("clicked", gtk.Widget.destroy, self.window)

        imgwidget = gtk.Image()

        # determine if there is a thumbnail within this image?
        previews = self.plugin_image.previews
        if previews:

            # Get the largest preview available
            preview = previews[-1]

            # Create a pixbuf loader to read the thumbnail data
            pbloader = gtk.gdk.PixbufLoader()
            pbloader.write(preview.data)

            # Get the resulting pixbuf and build an image to be displayed
            pixbuf = pbloader.get_pixbuf()
            pbloader.close()

            imgwidget.set_from_pixbuf(pixbuf)

        # create thumbnail from image
        else:

            imgwidget.set_from_file( self.orig_image )

        button.add( imgwidget )
        self.window.add( button )
        button.show()
        self.window.show()
        sys.exit(gtk.main())

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

                self.Exif_widgets["Latitude"].set_text(   latitude )
                self.Exif_widgets["Longitude"].set_text( longitude )

            else:
                self.Exif_widgets["Latitude"].set_text(  "" )
                self.Exif_widgets["Longitude"].set_text( "" )
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

