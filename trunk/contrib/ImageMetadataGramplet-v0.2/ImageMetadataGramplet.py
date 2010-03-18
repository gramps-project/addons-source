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

#*****************************************************************************
# Python Modules
#*****************************************************************************
import os, datetime, time 
from decimal import Decimal

from TransUtils import get_addon_translator
_gt = get_addon_translator().ugettext

# import the pyexiv2 python library classes that we will be needing
try:
    from pyexiv2 import ImageMetadata, ExifTag, XmpTag, Rational
except ImportError:
    pyexivmsg = _gt("The, pyexiv2, python binding library, to exiv2 is not "
        "installed on this computer.\n It can be downloaded either from your "
        "local repository or from here\n")
    pyexivmsg += "http://tilloy.net/dev/pyexiv2"
    raise Exception(pyexivmsg)

#-----------------------------------------------------------------------------
# Set up Logging
#-----------------------------------------------------------------------------
import logging
LOG = logging.getLogger(".ImageMetadataGramplet")

#-----------------------------------------------------------------------------
# GTK modules
#-----------------------------------------------------------------------------
import gtk

#-----------------------------------------------------------------------------
# GRAMPS modules
#-----------------------------------------------------------------------------
from gen.plug import Gramplet
import Utils

from DateHandler import displayer as _dd

from TransUtils import get_addon_translator
_ = get_addon_translator(__file__).gettext

from QuestionDialog import OkDialog, WarningDialog
#-----------------------------------------------------------------------------
# Constants
#-----------------------------------------------------------------------------
# set up Abbreviated Months for select_date()
_ABBREV_MONTHS = []
_ABBREV_MONTHS.append("")
_ABBREV_MONTHS.extend(
                      [(_dd.long_months[month]) for month in range(1, 13)]
                      )

# first camera was created April 12, 1826
# http://wiki.answers.com/Q/What_date_was_the_camera_invented 
FIRST_DATE = datetime.datetime(1826, 4, 12, 14, 30, 00)

FIRST_DESCRIPTION = _("Enter text describing this image and who might be in "
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
# Gramplet class
#------------------------------------------------------------------------
class imageMetadataGramplet(Gramplet):
    """
    degrees symbol = [Ctrl] [Shift] u \00b0
    minutes symbol =                  \2032
    seconds symbol =                  \2033
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
            ("Active image",  _("Active image"), None, True,  [], False, 0),
            ("Photographer",  _("Photographer"), None, False, [], True,  0),
            ("Date:Select",   "",                None, True,  
            [("Select Date", _("Select Date"), self.select_date)], True, 0),

            ("Date",          _("Date/ Time"),   None, False, [], True,  0),
            ("Copyright",     _("Copyright"),    None, False, [], True,  0) ]:

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

        # Latitude Degrees, Minutes, Seconds/ Decimal
        row = gtk.HBox()
        label = gtk.Label()
        label.set_text("<b>%s</b>" % _("Latitude"))
        label.set_use_markup(True)
        label.set_width_chars(10)
        row.pack_start(label, True)
        latitude = gtk.Entry()
        latitude.set_width_chars(10)
        self.exif_widgets["Latitude"] = latitude
        row.pack_start(self.exif_widgets["Latitude"], True)

        # Latitude Reference
        label = gtk.Label()
        label.set_text(_("Lat. Ref"))
        label.set_width_chars(10)
        row.pack_start(label, True)
        eventBox = gtk.EventBox()
        self.exif_widgets["LatitudeRef"] = gtk.combo_box_new_text()
        eventBox.add(self.exif_widgets["LatitudeRef"])
        for direction in ["", "N", "S"]:
            self.exif_widgets["LatitudeRef"].append_text(direction)
        self.exif_widgets["LatitudeRef"].set_active(0)
        row.pack_start(eventBox, True, True)
        rows.pack_start(row, True)

        # Longitude Degrees, Minutes, Seconds/ Decimal
        row = gtk.HBox()
        label = gtk.Label()
        label.set_text("<b>%s</b>" % _("Longitude"))
        label.set_use_markup(True)
        label.set_width_chars(10)
        row.pack_start(label, True)
        longitude = gtk.Entry()
        longitude.set_width_chars(10)
        self.exif_widgets["Longitude"] = longitude
        row.pack_start(self.exif_widgets["Longitude"], True)

        # Longitude Reference
        label = gtk.Label()
        label.set_text(_("Long. Ref."))
        label.set_width_chars(10)
        row.pack_start(label, True)
        eventBox = gtk.EventBox()
        self.exif_widgets["LongitudeRef"] = gtk.combo_box_new_text()
        eventBox.add(self.exif_widgets["LongitudeRef"])
        for direction in ["", "E", "W"]:
            self.exif_widgets["LongitudeRef"].append_text(direction)
        self.exif_widgets["LongitudeRef"].set_active(0)
        row.pack_start(eventBox, True, True)
        rows.pack_start(row, True)

        # show separator before description textbox
        separator = gtk.HSeparator()
        rows.pack_start(separator, False)

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
        self.exif_widgets["Description"].set_text(FIRST_DESCRIPTION)
        rows.pack_start(description_box, True, True, 0)

        # set up tooltip information for the fields
        self.exif_widgets["Photographer"].set_tooltip_text(_("Enter the name "
            "of the person who took this image."))

        self.exif_widgets["Date"].set_tooltip_text(_("Press the Select Date "
            "Button to bring up a calendar where you can choose a date."))

        self.exif_widgets["Copyright"].set_tooltip_text(_("Enter the copyright"
            " information for the image.  xample: (C) 2010 Smith and Wesson"))

        self.xmp_widgets["Subject"].set_tooltip_text(_("Enter words that "
            "describe this image, separated by comma.\n  Example: Kids,house,"
            "dog,car"))

        GPSLatRefMsg = _("If using decimal format in Latitude, leave blank.  "
            "If using Degrees, Minutes, Seconds, please enter either a N or S")
        self.exif_widgets["LatitudeRef"].set_tooltip_text(GPSLatRefMsg)

        self.exif_widgets["Latitude"].set_tooltip_text(_("Enter the GPS "
            "Latitude as either Degrees, Minutes, Seconds or Decimal "
            "formats."))

        GPSLongRefMsg = _("If using decimal format in Longitude, leave blank.  "
            "If using Degrees, Minutes, Seconds,  please enter either a W or E")
        self.exif_widgets["LongitudeRef"].set_tooltip_text(GPSLongRefMsg)

        self.exif_widgets["Longitude"].set_tooltip_text(_("Enter the GPS "
            "Longitude as either in Degrees, Minutes, Seconds or Decimal "
            "formats."))

        # Save, Clear, Convert GPS
        row = gtk.HBox()
        button = gtk.Button(_("Save"))
        button.connect("clicked", self.write_image_metadata)
        row.pack_start(button, True)
        button = gtk.Button(_("Clear"))
        button.connect("clicked", self.clear_data_entry)
        row.pack_start(button, True)
        button = gtk.Button(_("Convert GPS Coordinates"))
        button.connect("clicked", self.convert_gps)
        row.pack_start(button, True)
        rows.pack_start(row, False)

        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(rows)
        rows.show_all()

        self.connect_signal("Media", self.media_changed)

    def media_changed(self, handle):
        """
        handles when an image has been changed

        @param: handle -- handle for the image in the database
        """

        # get media and pyexiv2 image
        self.media = self.dbstate.db.get_object_from_handle(handle)
        self._get_image(self.media)

        # update all widgets
        self.update_widgets()

    def main(self):
        """
        Does Nothing
        """

        pass

    def update_widgets(self):
        """
        update the image exif Metadata
        """
        if self.media is None:
            return

        # display image title/ description
        image_descr = self.media.get_description()
        if not image_descr:
            image_descr = self.media.get_path()
        self.exif_widgets["Active image"].show()
        self.exif_widgets["Active image"].set_text(image_descr)

        # read image metadata
        self.read_image_metadata(None)

    def make_row(self, pos, text, choices=None, readonly=False, callback_list=[], 
                 mark_dirty=False, default=0):
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
 
    def set_value(self, keytag, KeyValue):
        """
        sets the value for the Exif keys

        @param: keytag   -- exif key
        @param: KeyValue -- value to be set
        """

        if "Exif" in keytag:
            try:
                self.image[keytag].value = KeyValue

            except KeyError:
                self.image[keytag] = ExifTag(keytag, KeyValue)

        elif "Xmp" in keytag:
            try:
                self.image[keytag].value = KeyValue

            except KeyError:
                self.image[keytag] = XmpTag(keytag, KeyValue)

    def write_image_metadata(self, obj):
        """
        saves the data fields to the image
        """

        # image is writable
        can_write = os.access(self.orig_image, os.W_OK)
        if can_write:

            # Image Description
            start = self.exif_widgets["Description"].get_start_iter()
            end = self.exif_widgets["Description"].get_end_iter()
            meta_descr = self.exif_widgets["Description"].get_text(start, end)
            if meta_descr:
                self.set_value(ImageDescription, meta_descr)

            # image Date/ Time
            datetime = self.exif_widgets["Date"].get_text()
            if datetime:
                self.set_value(ImageDateTime, datetime)

            # Image Photographer
            photographer = self.exif_widgets["Photographer"].get_text()
            if photographer:
                self.set_value(ImagePhotographer, photographer)

            # Image Copyright
            copyright = self.exif_widgets["Copyright"].get_text()
            if copyright:
                self.set_value(ImageCopyright, copyright)

            # GPS Latitude
            latitude = self.exif_widgets["Latitude"].get_text()
            if latitude:

                # Convert Decimal to deg, min, sec
                if "." in latitude:
                    degrees, minutes, seconds, latref = \
                        self.convert_decimal_deg_min_sec( latitude )

                    latitude = "%(deg)s %(mins)s %(secs)s" % {
                        'deg' : degrees, 'mins' : minutes, 'secs' : seconds }
                    self.exif_widgets["Latitude"].set_text( latitude )
                    self.exif_widgets["LatitudeRef"].set_active( latref )   
                    latitude = coords_to_rational( latitude )
                else:
                    latitude = coords_to_rational( latitude )
                    latref = self.exif_widgets["LatitudeRef"].get_active()
                if latref == 1:
                    latref = "N"
                elif latref == 2:
                    latref = "S"
                self.set_value( ImageLatitude, latitude )
                self.set_value( ImageLatitudeRef, latref )

            # GPS Longitude
            longitude = self.exif_widgets["Longitude"].get_text()
            if longitude:

                # Convert Decimal to DDMMSS 
                if "." in longitude:
                    degrees, minutes, seconds, longref = \
                        self.convert_decimal_deg_min_sec( longitude )

                    longitude = "%(deg)s %(mins)s %(secs)s" % {
                        'deg' : degrees, 'mins' : minutes, 'secs' : seconds }
                    self.exif_widgets["Longitude"].set_text( longitude )
                    self.exif_widgets["LongitudeRef"].set_active( longref )
                    longitude = coords_to_rational( longitude )
                else:
                    longitude = coords_to_rational( longitude )
                    longref = self.exif_widgets["LongitudeRef"].get_active()
                if longref == 1:
                    longref = "E"
                elif longref == 2:
                    longref = "W"  
                self.set_value( ImageLongitude, longitude )
                self.set_value( ImageLongitudeRef, longref )

            # Xmp Subject
            keywords = self.xmp_widgets["Subject"].get_text()
            if keywords:
                keywords = [(subject) for subject in keywords.split(",")]
            self.set_value( XmpSubject, keywords )  

            # write the metadata to the image
            self.image.write()
            OkDialog(_("Image metadata has been saved."))  

        else:
            basename = os.path.basename(self.media)
            WarningDialog(_("The image file %s does NOT have write access/ "
                "permissions. If you have access and rights to change the "
                "permissions, then please do it now." % basename))
            return None

    def clear_data_entry(self, obj):
        """
        clears all data fields to nothing
        """

        for key in [ "Description", "Date", "Photographer", "Copyright", 
            "Latitude", "Longitude" ]:
            self.exif_widgets[key].set_text("")

        for key in ["LatitudeRef", "LongitudeRef"]:
            self.exif_widgets[key].set_active(0)

        self.xmp_widgets["Subject"].set_text("")

    def _get_media(self, media_id):
        """
        returns an image object from the database
        """

        if not media_id:
            return None 

        # ge media object from the database
        media = self.dbstate.db.get_object_from_gramps_id(media_id)

        # return the media object to its callers
        return media
    
    def _get_image(self, media_obj):
        """
        creates the pyexiv2 image based on media object
        """

        if not media_obj:
            return None, None

        # get full image path
        self.orig_image = Utils.media_path_full( self.dbstate.db, 
            media_obj.get_path() )

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

    def read_image_metadata(self, obj):
        """
        reads the image metadata after the pyexiv2.Image has been created
        """

        # clear all data fields first
        self.clear_data_entry(None)

        # check to see if the image is on the computer or not?
        basename = os.path.basename(self.orig_image)
        if os.path.isfile(self.orig_image):

            # check to see if the image is readable
            can_read = os.access(self.orig_image, os.R_OK)
            if can_read:

                # read the image metadata
                self.image.read()

                # set up image exif keys for use in this gramplet 
                exifKeyTags = [(keytag) for keytag in self.image.exif_keys
                               if keytag in _DATAMAP]

                exifKeyTags += [(keytag) for keytag in self.image.xmp_keys
                                if keytag in _DATAMAP]

                for keytag in exifKeyTags:

                    # Image description
                    if keytag == ImageDescription:
                        self.exif_widgets["Description"].set_text(
                            self.get_value( keytag ) )

                    # Image DateTime
                    elif keytag == ImageDateTime:
                        self.exif_widgets["Date"].set_text(
                            self.get_value ( keytag ) )

                    # image photographer
                    elif keytag == ImagePhotographer:
                        self.exif_widgets["Photographer"].set_text(
                            self.get_value( keytag ) )

                    # Image Copyright
                    elif keytag == ImageCopyright:
                        self.exif_widgets["Copyright"].set_text(
                            self.get_value( keytag ) )

                    # GPS Latitude
                    elif keytag == ImageLatitude:
                        latitude = self.get_value( keytag )
                        if latitude:
                            degrees, minutes, seconds = latitude.split(" ")
                            degrees, rest = degrees.split("/")
                            minutes, rest = minutes.split("/")
                            seconds, rest = seconds.split("/")
                            latitude = "%(deg)s %(mins)s %(sec)s" % {
                                'deg' : degrees, 'mins' : minutes, 
                                'sec' : seconds }
                            self.exif_widgets["Latitude"].set_text( latitude )

                            # Latitude Reference
                            latref = self.get_value( ImageLatitudeRef )
                            if latref == "N":
                                self.exif_widgets["LatitudeRef"].set_active(1)
                            elif latref == "S":
                                self.exif_widgets["LatitudeRef"].set_active(2)

                    # GPS Longitude
                    elif keytag == ImageLongitude:
                        longitude = self.get_value( keytag )
                        if longitude:
                            degrees, minutes, seconds = longitude.split(" ")
                            degrees, rest = degrees.split("/")
                            minutes, rest = minutes.split("/")
                            seconds, rest = seconds.split("/")
                            longitude = "%(deg)s %(mins)s %(sec)s" % {
                                'deg' : degrees, 'mins' : minutes, 
                                'sec' : seconds}
                            self.exif_widgets["Longitude"].set_text( longitude )

                            # Longitude Reference
                            longref = self.get_value( ImageLongitudeRef )
                            if longref == "E":
                                self.exif_widgets["LongitudeRef"].set_active(1)
                            elif longref == "W":
                                self.exif_widgets["LongitudeRef"].set_active(2)

                # Xmp Subject
                xmpKeyTags = self.image.xmp_keys
                xmpKeyTags = [(keytag) for keytag in xmpKeyTags
                              if keytag in _DATAMAP]

                for keytag in xmpKeyTags:
                    if keytag == XmpSubject:
                        keywords = self.get_value( keytag )
                        subject = ""
                        if keywords:
                            index = 0 
                            for word in keywords:
                                subject += word
                                if index is not len(keywords):
                                    subject += "," 
                        self.xmp_widgets["Subject"].set_text( subject )

            # image is not readable
            else:
                WarningDialog(_("The image file %s does NOT have read access/ permissions. "
                    "If you have access and rights to change the permissions, "
                    "then please do it now." % basename))

        # image does not exists at all
        else:
            WarningDialog(_("The image file is missing.  Please select another image or "
                       "edit the media object to fix this problem."))

    def select_date(self, obj):
        """
        will allow you to choose a date from the calendar widget
        """
 
        self.app = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.app.set_title(_("Select Date"))
        self.app.set_default_size(450, 200)
        self.app.set_border_width(5)
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

        self.exif_widgets["Date"].set_text(image_date)
        self.app.destroy()

    def convert_decimal_deg_min_sec(self, coordinates):
        """
        Converts Decimal GPS coordinates to Degrees, Minutes, Seconds 
        GPS coordinates

        @param: coordinates    -- GPS Decimal coordinates
        """

        if coordinates is not None and coordinates is not "":

            if "." in coordinates:

                if coordinates[0] == "-":
                    coordinateref = 2
                    coordinates = coordinates[1:]
                else:
                    coordinateref = 1

                degrees = int(float(coordinates))
                degrees = str(degrees)
                rest, minutes = coordinates.split(".", 1)
                minutes = "." + minutes

                minutes = Decimal(minutes) * 60
                minutes = str(minutes)
                minutes, seconds = minutes.split(".", 1)

                seconds = "." + seconds
                seconds = Decimal(seconds) * 60

                seconds = int(float(seconds))
                seconds = str(seconds)  

                # return degrees, minutes, seconds, coordinatereference 
                # to its callers
                return degrees, minutes, seconds, coordinateref

    def convert_latitude(self, coordinates):
        """
        converts GPS Latitude

        @param: coordinate = Latitude GPS Coordinates
        """

        if coordinates and "." in coordinates:
            deg, min, sec, latref = self.convert_decimal_deg_min_sec( coordinates )

            latitude = "%(deg)s %(mins)s %(sec)s" % {
                'deg' : deg, 'mins' : min, 'sec' : sec }
            self.exif_widgets["Latitude"].set_text( latitude )
            self.exif_widgets["LatitudeRef"].set_active( latref ) 

    def convert_longitude(self, coordinates):
        """
        converts GPS Longitude

        @param: coordinate = Longitude GPS Coordinates
        """

        if coordinates and "." in coordinates:
            deg, min, sec, longref = self.convert_decimal_deg_min_sec( coordinates )

            longitude = "%(deg)s %(mins)s %(sec)s" % {
                'deg' : deg, 'mins' : min, 'sec' : sec }
            self.exif_widgets["Longitude"].set_text( longitude )
            self.exif_widgets["LongitudeRef"].set_active( longref )

    def convert_gps(self, obj):
        """
        converts the GPS Coordinates passed to it
        """

        self.convert_latitude( self.exif_widgets["Latitude"].get_text()  )
        self.convert_longitude(self.exif_widgets["Longitude"].get_text() )
  
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

    return [string_to_rational(coordinate) for coordinate in coordinates.split(' ')]
