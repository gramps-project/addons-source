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

# set Xmp keys
XmpSubject = "Xmp.dc.subject"

# set up keys for Image IPTC keys
IptcKeywords    = "Iptc.Application2.Keywords"
IptcDateCreated = "Iptc.Application2.DateCreated"

_DATAMAP = [ ImageArtist, ImageCopyright, ImageDateTime,
             ImageLatitude, ImageLatitudeRef, ImageLongitude, ImageLongitudeRef,
             ImageDescription ]

IptcMap = [ IptcDateCreated, IptcKeywords ]
# ------------------------------------------------------------------------
# Support functions
# ------------------------------------------------------------------------

def _check_readable(image_obj):
    """
    check to see if the image is readable

    @param: image_obj -- image object and its full path
    """

    # if True, the image has read permissions
    # if False, there are errors somewhere ...
    return os.access( image_obj, os.R_OK )

def _check_writable(image_obj):
    """
    determine if image is writable or not?

    @param: image_object and its full image path
    """

    # make sure the image has write permissions
    return os.access( image_obj, os.W_OK )

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
        self.LATitude     = None
        self.LONGitude    = None

        rows = gtk.VBox()
        for items in [
            ("Active:Image",    _("Active:Image"), None, True,  [],         False, 0),
            ("Artist",          _("Artist"),       None, False, [],         True,  0),
            ("Copyright",       _("Copyright"),    None, False, [],         True,  0),

            # calendar date clickable entry
            ("Date",   "",                         None, True,  
            [("Select Date",    _("Select Date"),  self.select_date)],     True, 0) ]:

            pos, text, choices, readonly, callback, dirty, default = items
            row = self.make_row(pos, text, choices, readonly, callback, dirty, default)
            rows.pack_start(row, False)

        # manual date entry, example: 1826 04 12
        row = gtk.HBox()

        now = time.localtime()
        nyear, nmonth, nday, nhour, nminutes, nseconds = now[0:6]
        self.make_event_box(row, _("Year"),  "Year",  [year  for year in range(1826, 2021)], (nyear - 1826) )
        self.make_event_box(row, _("Month"), "Month", [month for month in range(1, 13)], (nmonth - 1) )
        self.make_event_box(row, _("Day"),   "Day",   [day   for day in range(1, 32)], (nday - 1) )

        rows.pack_start(row, True)

        # manual time entry, Example: Hour Minutes Seconds
        row = gtk.HBox()

        self.make_event_box(row, _("Hour"), "Hour",    [hour for hour in range(0, 24)], nhour)
        self.make_event_box(row, _("Mins"), "Minutes", [mins for mins in range(0, 60)], nminutes)
        self.make_event_box(row, _("Secs"), "Seconds", [secs for secs in range(0, 60)], nseconds)
        rows.pack_start(row, True)

        # Latitude/ longitude GPS
        for items in [
	    ("Latitude",        _("Latitude"),     None, False, [],         True,  0),
	    ("Longitude",       _("Longitude"),    None, False, [],         True,  0),

            # keywords entry
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
        self.setup_tooltips(self.plugin_image)

        # Save, Clear
        row = gtk.HBox()
        button = gtk.Button(_("Save"))
        button.connect("clicked", self.write_metadata)
        row.pack_start(button, True)
        button = gtk.Button(_("Clear"))
        button.connect("clicked", self.clear_data_entry)
        row.pack_start(button, True)
        rows.pack_start(row, True)

        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(rows)
        rows.show_all()

    def post_init(self):
        self.connect_signal("Media", self.update)
        
    def setup_tooltips(self, obj):
        """
        setup tooltips for each field
        """

        self.Exif_widgets["Artist"].set_tooltip_text(_("Enter the name "
            "of the person or company who took this image."))

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

        log.debug( 'CURRENT MEDIA HANDLE IS NOW: ', self.active_media )

        # get media object from database
        self.orig_image = self.dbstate.db.get_object_from_handle( self.active_media )

        # get media object full path
        self.image_path = Utils.media_path_full( self.dbstate.db, self.orig_image.get_path() )

        # clear all data entry fields
        self.clear_data_entry( object )

        # get image mime type
        mime_type = gen.mime.get_type( self.image_path )
        if mime_type and mime_type.startswith("image/"):
            try:

                # get the pyexiv2 instance
                self.plugin_image = ImageMetadata( self.image_path )

                # read the image metadata
                self.read_metadata( self.image_path )

            except IOError:
                WarningDialog(_( "This media object is NOT usable by this addon!\n"
                                 "Choose another media object..."))

    def make_event_box(self, row, text, pos, choices, default):
        """
        creates an eventBox for options such as Year, Month, Day, Hour, Minutes, and Seconds

        @param: row -- current row being used to hold the line
        @param: text -- translated text for use in the label
        @param: pos -- the name of the widget to be created
        @param: choices -- options for the eventBox
        @param: default -- position for set in the choices
        """

        label = gtk.Label()
        label.set_width_chars(6)
        label.set_text("<b>%s</b>" % text)
        label.set_use_markup(True)
        label.show()

        eventBox = gtk.EventBox()
        self.Exif_widgets[pos] = gtk.combo_box_new_text()
        eventBox.add(self.Exif_widgets[pos])
        for option in choices:
            if option.__class__ == int:

                # if option is between 0 and 9, add a zero in front of integer?
                if -1 < option <= 9:
                    option = "%02d" % option
                option = str( option )
            self.Exif_widgets[pos].append_text( option )
        self.Exif_widgets[pos].set_active( default )
        row.pack_start(label, False)
        row.pack_start(eventBox, True, True)
        return row

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

    def _get_value(self, KeyTag):
        """
        gets the value from the Exif Key, and returns it...

        @param: KeyTag -- image metadata key
        """

        # if keytag is from Iptc family?
        if "Iptc" in KeyTag:
            try:
                KeyValue = self.plugin_image[KeyTag].value

            except KeyError:
                KeyValue = ""

        # Xmp Family
        elif "Xmp" in KeyTag:

            try:
                KeyValue = self.plugin_image[KeyTag].raw_value

            except KeyError:
                KeyValue = "" 

        # Exif Family
        else:
  
            try:
                KeyValue = self.plugin_image[KeyTag].raw_value

            except KeyError:
                KeyValue = self.plugin_image[KeyTag].value

        # return metadata value back to its callers
        return KeyValue

    def read_metadata(self, obj):
        """
        reads the image metadata after the pyexiv2.Image has been created
        """

        # check to see if the image is readable?
        if _check_readable(self.image_path):

            log.debug("Image, ", self.image_path, ' has bean read...')

            self.Exif_widgets["Active:Image"].set_text( self.orig_image.get_description() )

            log.debug( self.plugin_image, "is now the ImageMetadata object!" )
 
            # read the image metadata
            self.plugin_image.read()

            # set up image metadata keys for use in this gramplet only
            dataKeyTags = [ KeyTag for KeyTag in self.plugin_image.exif_keys if KeyTag in _DATAMAP ]

            for KeyTag in dataKeyTags:

                # Media image Artist
                if KeyTag == ImageArtist:
                    self.Exif_widgets["Artist"].set_text( self._get_value( KeyTag ) )

                # media image Copyright
                elif KeyTag == ImageCopyright:
                    self.Exif_widgets["Copyright"].set_text( self._get_value( KeyTag ) )

                # media image DateTime
                elif KeyTag == ImageDateTime:

                    # get the dates that an image can have in Gramps
                    # date1 and date2 may come from the image metadata
                    # date3 may come from the Gramps database 
                    date1 = self._get_value( KeyTag )
                    date2 = self._get_value( IptcDateCreated )
                    date3 = self.orig_image.get_date_object()

                    use_date = date1 or date2 or date3
                    if use_date:
                        self.process_date( use_date )
                    else:
                        self.process_date( None, False )

                # Latitude and Latitude Reference
                elif KeyTag == ImageLatitude:

                    # self.LATitude is used for processing, and latitude is used for displaying
                    latitude = self._get_value( KeyTag )
                    if latitude:
                        deg, min, sec = rational_to_dms( latitude )

                        # if seconds has a period in it, get rid of it...
                        sec = sec.replace(".", "")

                        # Latitude Direction Reference
                        self.LatitudeRef = self._get_value( ImageLatitudeRef )
                        self.LATitude = "%s %s %s" % ( deg, min, sec )

                        self.Exif_widgets["Latitude"].set_text(
                                """%s° %s′ %s″ %s""" % ( deg, min, sec, self.LatitudeRef ) )

                # Longitude and Longitude Reference
                elif KeyTag == ImageLongitude:

                    # lself.LONGitude is used for processing, and longitude is used for displaying
                    longitude = self._get_value( KeyTag )
                    if longitude:
                        deg, min, sec = rational_to_dms( longitude )

                        # if there is a persiod, get rid of it...
                        sec = sec.replace(".", "")

                        # Longitude Direction Reference
                        self.LongitudeRef = self._get_value( ImageLongitudeRef )
                        self.LONGitude = "%s %s %s" % ( deg, min, sec )

                        self.Exif_widgets["Longitude"].set_text(
                                """%s° %s′ %s″ %s""" % ( deg, min, sec, self.LongitudeRef ) )

                elif KeyTag == ImageDescription:

                    # metadata Description field 
                    self.Exif_widgets["Description"].set_text(
                        self._get_value( ImageDescription ) )

                # Subject
                subject = self._get_value( XmpSubject )
 
                for KeyTag in IptcMap:

                    # Keywords 
                    if KeyTag == IptcKeywords:
                        words = ""
                        keyWords = self._get_value( KeyTag )
                        if keyWords:
                            index = 1 
                            for word in keyWords:
                                words += word
                                if index is not len(keyWords):
                                    words += "," 
                                index += 1 
                        self.Exif_widgets["Keywords"].set_text( words )

                    elif KeyTag == IptcDateCreated:
                        self.DateCreated = self._get_value( KeyTag )
        else:
            WarningDialog(_( "There is an error with this image!\n"
                "You do not have read access..."))

    def _set_value(self, KeyTag, KeyValue):
        """
        sets the value for the Exif keys

        @param: KeyTag   -- exif key
        @param: KeyValue -- value to be saved
        """

        if "Exif" in KeyTag:
            try:
                self.plugin_image[KeyTag].value = KeyValue
            except KeyError:
                self.plugin_image[KeyTag] = ExifTag( KeyTag, KeyValue )
            except ValueError:
                pass

        elif "Xmp" in KeyTag:
            try:
                self.plugin_image[KeyTag].value = KeyValue
            except KeyError:
                self.plugin_image[KeyTag] = XmpTag(KeyTag, KeyValue)
            except ValueError:
                pass

        elif "Iptc" in KeyTag:
            try:
                self.plugin_image[KeyTag].value = KeyValue
            except KeyError:
                self.plugin_image[KeyTag] = IptcTag( KeyTag, KeyValue )
            except ValueError:
                pass

    def write_metadata(self, obj):
        """
        gets the information from the plugin data fields
        and sets the keytag = keyvalue image metadata
        """

        # Artist data field
        artist = self.Exif_widgets["Artist"].get_text()
        self._set_value( ImageArtist, artist )

        # Copyright data field
        copyright = self.Exif_widgets["Copyright"].get_text()
        self._set_value( ImageCopyright, copyright )

        # get date from data field for saving
        # the False flag signifies that we will get the date and time from process_date()
        self._set_value( ImageDateTime, self.process_date( None, False ) )

        # Convert GPS Latitude / Longitude Coordinates for display
        self.get_LatRef_LongRef()

        # convert degrees, minutes, seconds to Rational for saving
        if self.LATitude and self.LatitudeRef:
            latitude = coords_to_rational( self.LATitude )

            self._set_value( ImageLatitude, latitude )
            self._set_value( ImageLatitudeRef, self.LatitudeRef )

        else:
            self._set_value( ImageLatitude,    "") 
            self._set_value( ImageLatitudeRef, "")

        if self.LONGitude and self.LongitudeRef:
            longitude = coords_to_rational( self.LONGitude )

            self._set_value( ImageLongitude, longitude )
            self._set_value( ImageLongitudeRef, self.LongitudeRef )

        else:
            self._set_value( ImageLongitude,    "") 
            self._set_value( ImageLongitudeRef, "")

        # keywords data field
        keywords = [ word for word in self.Exif_widgets["Keywords"].get_text().split(",") ]
        self._set_value( IptcKeywords, keywords )

        # description data field
        start = self.Exif_widgets["Description"].get_start_iter()
        end = self.Exif_widgets["Description"].get_end_iter()
        meta_descr = self.Exif_widgets["Description"].get_text(start, end)
        self._set_value( ImageDescription, meta_descr)

        # check write permissions for this image
        if _check_writable(self.image_path):
            self.plugin_image.write()

            # notify the user of successful write 
            OkDialog(_("Image metadata has been saved."))

        else:
            WarningDialog(_( "There is an error with this image!\n"
                "You do not have write access..."))

    def clear_data_entry(self, obj, cleartype = "All"):
        """
        clears all data fields to nothing

        @param: cleartype -- 
            "Date" = clears only Date entry fields
            "All" = clears all data fields
        """

        if cleartype == "All":
            for key in [ "Active:Image", "Artist", "Copyright",
                "Latitude", "Longitude", "Keywords", "Description" ]:
                self.Exif_widgets[key].set_text( "" )

            for key in ["Year", "Month", "Day", "Hour", "Minutes", "Seconds"]:
                self.Exif_widgets[key].set_active(0)

            self.LATitude = ""
            self.LatitudeRef = ""
            self.LONGitude
            self.LongitudeRef = ""

        else:
            for key in ["Year", "Month", "Day", "Hour", "Minutes", "Seconds"]:
                self.Exif_widgets[key].set_active(0)

    def process_date(self, tmpDate, read = True):
        """
        Process the date for read and write processes
        year, month, day, hour, minutes, seconds

        @param: tmpDate = variable to be processed
        @param: read -- if True, then process date from the read process...
                     -- if False, then process date from the write process...  
        """

        # get date type
        datetype = tmpDate.__class__

        # if date type is either datetime.date or list,
        # hour, minutes, seconds will need to be specified
        if datetype in [date, list]:

            rhour, rminutes, rseconds = time.localtime()[3:5]

        # if type is datetime.datetime or datetime.date,
        # we will get the year, month, and day from tmpDate
        if datetype in [datetime, date]:
            ryear = tmpDate.year
            rmonth = tmpDate.month
            rday = tmpDate.day

        # process the image date for the read process...
        if read:

            # clear the date/ time fields only!
            self.clear_data_entry(self.plugin_image, "Date")

            # if type is equal to datetime.datetime,
            # we need to get the time?
            if datetype == datetime:

                rhour = tmpDate.hour
                rminutes = tmpDate.minute
                seconds = tmpDate.second  

            # if tpe is equal to list, get the date?
            elif datetype == list:

                ryear = tmpDate[0].year
                rmonth = tmpDate[0].month
                rday = tmpDate[0].day

            # date was saved as a string instead
            elif datetype == str:

                # get the date from the string...
                ddate, dtime = tmpDate.split(" ")
                ryear, rmonth, rday = ddate.split(".")

                # get the time from the string...
                rhour, rminutes, rseconds = dtime.split(":")

            # type is NoneType
            else:

                # set the values for the date
                ryear, rmonth, rdat = 0, 0, 0

                # set the values for the time
                rhour, rminutes, rseconds = 0, 0, 0

            # set the data fields for the date
            self.Exif_widgets["Year"].set_active( (int(ryear) - 1826) )
            self.Exif_widgets["Month"].set_active( (int(rmonth) - 1) )
            self.Exif_widgets["Day"].set_active( (int(rday) - 1) )

            # set data fields for the time
            self.Exif_widgets["Hour"].set_active( (int(rhour) ) )
            self.Exif_widgets["Minutes"].set_active( (int(rminutes) ) )
            self.Exif_widgets["Seconds"].set_active( (int(rseconds) ) ) 
        
        # used for processing the date for the write process...
        # used for creating datetime.datetime if possible, otherwise create a date string?
        else:

            wyear = self.Exif_widgets["Year"].get_active()
            wmonth = self.Exif_widgets["Month"].get_active()
            wday = self.Exif_widgets["Day"].get_active()

            whour = self.Exif_widgets["Hour"].get_active()
            wminutes = self.Exif_widgets["Minutes"].get_active()
            wseconds = self.Exif_widgets["Seconds"].get_active()

            if -1 < wyear <= 75:
                wdate = "%04d.%02d.%02d %02d:%02d:%02d" % (
                    (wyear + 1826), (wmonth + 1), (wday + 1), whour, wminutes, wseconds )
            else:
                wdate = datetime( (wyear + 1826), (wmonth +1), (wday +1), whour, wminutes, wseconds )
                self._set_value( IptcDateCreated, 
                       [date( (wyear + 1826), (wmonth +1), (wday +1) ) ]
                ) 

            self._set_value( ImageDateTime, wdate ) 

# -------------------------------------------------------------------
#                          Date Calendar functions
# -------------------------------------------------------------------
    def select_date(self, obj):
        """
        will allow you to choose a date from the calendar widget

        @param: obj -- media object from the database
        """
 
        tip = _("Double click a date to return to Addon.")

        self.app = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.app.tooltip = tip
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
        self.Exif_widgets["Year"].set_active( ( year - 1826 ) )
        self.Exif_widgets["Month"].set_active( month )
        self.Exif_widgets["Day"].set_active( ( day - 1 ) )

        now = time.localtime()
        self.Exif_widgets["Hour"].set_active( now[3] )
        self.Exif_widgets["Minutes"].set_active( now[4] )
        self.Exif_widgets["Seconds"].set_active( now[5] )
        self.app.destroy()

# -------------------------------------------------------------------
#                            GPS Coordinate functions
# -------------------------------------------------------------------
    def get_LatRef_LongRef(self):
        """
        Converts decimal GPS coordinates to Degrees, Minutes, Seconds 
        GPS coordinates
        """

        if self.LatitudeRef and self.LongitudeRef:
            return

        if self.LATitude and self.LONGitude:
            latitude   = self.LATitude
            longitude = self.LONGitude
        else:
            latitude = self.Exif_widgets[  "Latitude"].get_text()
            longitude = self.Exif_widgets["Longitude"].get_text()

        if latitude and longitude:

            # latitude and longitude are in decimal format
            if ("." in latitude and longitude):

                # convert to degress, minutes, seconds with a seperator of : for saving to Exif Metadata 
                latitude, longitude = conv_lat_lon( latitude, longitude, "DEG-:" )

                # remove negative symbol in there is one?
                if "-" in latitude[0]:
                    latitude = latitude.replace("-", "")
                    self.LatitudeRef = "S"
                else:
                    self.LatitudeRef = "N" 

                # remove negative symbol if there is one?
                if "-" in longitude[0]:
                    longitude = longitude.replace("-", "")
                    self.LongitudeRef = "W"
                else:
                    self.LongitudeRef = "E"

            deg, min, sec = latitude.split(":")
            sec, dump = sec.split(".")
            self.LATitude = "%s %s %s" % ( deg, min, sec )
            self.Exif_widgets["Latitude"].set_text(
                    """%s° %s′ %s″ %s""" % ( deg, min, sec, self.LatitudeRef )
            )

            deg, min, sec = longitude.split(":")
            sec, dump = sec.split(".")
            self.LONGitude = "%s %s %s" % ( deg, min, sec )
            self.Exif_widgets["Longitude"].set_text(
                    """%s° %s′ %s″ %s""" % ( deg, min, sec, self.LongitudeRef )
            )

            # ewmove Latitude Direction Reference so that it is not showing for save
            direction = " S" or " N"
            if direction:
                self.LATitude.replace(direction, "")

            # ewmove Longitude Direction Reference so that it is not showing for save
            direction = " E" or " W"
            if direction:
                self.LONGitude.replace(direction, "")

        elif latitude and not longitude:
            WarningDialog(_( "You have only entered a Latitude but no Longitude."))
            self.LatitudeRef, self.LongitudeRef = None, None

        elif longitude and not latitude:
            WarningDialog(_( "You have only entered a Longitude but no Latitude."))
            self.LatitudeRef, self.LongitudeRef = None, None

        else:
            self.LatitudeRef, self.LongitudeRef = None, None

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
