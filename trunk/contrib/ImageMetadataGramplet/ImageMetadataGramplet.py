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
import time, calendar
from decimal import *
getcontext().prec = 4

# abilty to escape certain characters from html output...
from xml.sax.saxutils import escape as _html_escape

# pyexiv2 download page (C) Olivier Tilloy
_DOWNLOAD_LINK = "http://tilloy.net/dev/pyexiv2/download.html"

# make sure the pyexiv2 library is installed and at least a minimum version
pyexiv2_req_install = True
Min_VERSION = (0, 1, 3)
Min_VERSION_str = "pyexiv2-%d.%d.%d" % Min_VERSION
PrefVersion_str = "pyexiv2-%d.%d.%d" % (0, 3, 0)

# to be able for people that have pyexiv2-0.1.3 to be able to use this addon also...
LesserVersion = False

try:
    import pyexiv2
    if pyexiv2.version_info < Min_VERSION:
        pyexiv2_req_install = False

except ImportError:
    pyexiv2_req_install = False
               
except AttributeError:
    LesserVersion = True

#------------------------------------------------
#   Internaturlization
#------------------------------------------------
from TransUtils import get_addon_translator
_ = get_addon_translator().ugettext

# -----------------------------------------------------------------------------
# GRAMPS/ GTK modules
# -----------------------------------------------------------------------------
import gtk

# the python library, pyexiv2, is either not installed or does not meet 
# minimum required version for this addon....
if not pyexiv2_req_install:
    raise Exception(_("The minimum required version for pyexiv2 must be %s \n"
        "or greater.  Or you do not have the python library installed yet.  "
        "You may download it from here: %s\n\n  I recommend getting, %s") % (
         Min_VERSION_str, _DOWNLOAD_LINK, PrefVersion_str) )

from gen.plug import Gramplet
from DateHandler import displayer as _dd
import GrampsDisplay

from QuestionDialog import OkDialog, ErrorDialog

import gen.lib
import Utils
from PlaceUtils import conv_lat_lon

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
# available image types for exiv2
_valid_types = ["jpeg", "jpg", "exv", "tiff", "dng", "nef", "pef", "pgf", "png", "psd", "jp2"]

# set up Exif keys for Image.exif_keys
ImageArtist       = "Exif.Image.Artist"
ImageCopyright    = "Exif.Image.Copyright"
ImageDateTime     = "Exif.Image.DateTime"
ImageDescription  = "Exif.Image.ImageDescription"

ImageLatitude     = "Exif.GPSInfo.GPSLatitude"
ImageLatitudeRef  = "Exif.GPSInfo.GPSLatitudeRef"
ImageLongitude    = "Exif.GPSInfo.GPSLongitude"
ImageLongitudeRef = "Exif.GPSInfo.GPSLongitudeRef"

_DATAMAP = [ImageDescription, ImageDateTime, ImageArtist, ImageCopyright,
            ImageLatitudeRef, ImageLatitude, ImageLongitudeRef, ImageLongitude]

_allmonths = list([_dd.short_months[i], _dd.long_months[i], i] for i in range(1, 13))

def _return_month(month):
    """
    returns either an integer of the month number or the abbreviated month name

    @param: rmonth -- can be one of:
        10, "10", or ("Oct" or "October")
    """

    for sm, lm, index in _allmonths:
        if isinstance(month, str):
            found = any(month == value for value in [sm, lm])
            if found:
                month = int(index)
                break

        else:
            if str(month) == index:
                month = lm
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

    def init(self):

        self.exif_column_width = 15
        self.exif_widgets = {}

        # set all dirty variables to False to begin this addon...
        self._dirty_image = False
        self._dirty_write = False

        self.orig_image   = False
        self.plugin_image = False

        root = self.__create_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(root)
        root.show_all()

        self.dbstate.db.connect('media-update', self.update)
        self.dbstate.db.connect("media-rebuild", self.update)

    def __create_gui(self):
        """
        Create and display the GUI components of the gramplet.
        """
        vbox = gtk.VBox()
        hbox = gtk.HBox(False)

        media_label = gtk.Label(_("Click a media object to begin..."))
        media_label.set_alignment(0.0, 0.5)
        hbox.pack_start(media_label, expand=False)

        self.media_text = gtk.Label()
        self.media_text.set_alignment(0.0, 0.5)
        hbox.pack_start(self.media_text, expand=True, fill=True)

        self.model = gtk.ListStore(object, str, str, str)
        view = gtk.TreeView(self.model)

        # Key Tag Column
        view.append_column(
            self.__create_column( _("Key Tag"), 1, 40, True) )

        # Key Value Column
        view.append_column(
            self.__create_column( _("Key Value"), 2, 60) )

        button_box = gtk.HButtonBox()
        button_box.set_layout(gtk.BUTTONBOX_START)

        # description metadata button in button box...
        description = gtk.Button(_("Description"))
        description.connect("clicked", self.__image_metadata )
        self.exif_widgets["Description"] = description
        button_box.add(self.exif_widgets["Description"] )

        # image metadata button in button box...
        origin = gtk.Button(_("Origin"))
        origin.connect("clicked", self.__image_metadata )
        self.exif_widgets["Origin"] = origin
        button_box.add(self.exif_widgets["Origin"] )

        # image metadata button in button box...
        image = gtk.Button(_("Image"))
        image.connect("clicked", self.__image_metadata )
        self.exif_widgets["Image"] = image
        button_box.add(self.exif_widgets["Image"] )
        vbox.pack_start(button_box, expand=False, fill=False)

        button_box = gtk.HButtonBox()
        button_box.set_layout(gtk.BUTTONBOX_START)

        # camera metadata button in button box...
        camera = gtk.Button(_("Camera"))
        camera.connect("clicked", self.__photo_metadata)
        self.exif_widgets["Camera"] = camera
        button_box.add(self.exif_widgets["Camera"])

        # advanced metadata  button in button box...
        advanced = gtk.Button(_("Advanced"))
        advanced.connect("clicked", self.__advanced_metadata)
        self.exif_widgets["Advanced"] = advanced
        button_box.add(self.exif_widgets["Advanced"])
        vbox.pack_start(button_box, expand=False, fill=False)

        button_box = gtk.HButtonBox()
        button_box.set_layout(gtk.BUTTONBOX_START)

        # save button in button box...
        save = gtk.Button(stock=gtk.STOCK_SAVE)
        save.connect("clicked", self.__save_metadata, view.get_selection() )
        self.exif_widgets["Save"] = save
        button_box.add(self.exif_widgets["Save"])
                
        # edit button in button box...
        edit = gtk.Button(stock=gtk.STOCK_EDIT)
        edit.connect("clicked", self.__edit_metadata, view.get_selection() )
        self.exif_widgets["Edit"] = edit
        button_box.add(self.exif_widgets["Edit"])

        # clear button in button box...
        clear = gtk.Button(stock=gtk.STOCK_CLEAR)
        clear.connect("clicked", self.clear_metadata)
        self.exif_widgets["Clear"] = clear
        button_box.add(self.exif_widgets["Clear"])

        vbox.pack_start(hbox, expand=False, padding=10)
        vbox.pack_start(view, padding=10)
        vbox.pack_end(button_box, expand=False, fill=False)
        
        return vbox

    def __create_column(self, text, value, min_width, fixed = True):
        """
        will create the column for the column row...

        @param: text -- Column Text
        @param: value -- Column Number
        @param: min_width -- minimun width of the column
        @param: fixed -- is it allowed to expad?
        """

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(text, renderer, text = value)

        column.set_expand(fixed)
        column.set_alignment(0.5)
        column.set_sort_column_id(value)

        return column

    def __image_metadata(self, obj):
        pass

    def __photo_metadata(self, obj):
        pass

    def __advanced_metadata(self, obj):
        pass

    def active_changed(self, handle):
        """
        Called when the active person is changed.
        """
        self.update()

    def help_clicked(self, obj):
        """
        Display the relevant portion of GRAMPS manual
        """
        GrampsDisplay.help(webpage = 'Image Metadata Gramplet-v0.2')

    def __save_metadata(self, widget, selection):
        """
        Saves the image metadata.
        """
        model, iter_ = selection.get_selected()
        if iter_ and not self._dirty_write:
            media = model.get_value(iter_, 0)
            try:
                MetadataSave(self.gui.dbstate, self.gui.uistate, [], media)
            except Errors.WindowActiveError:
                pass

    def __edit_metadata(self, widget, selection):
        """
        Edit the selected media.
        """
        model, iter_ = selection.get_selected()
        if iter_:
            media = model.get_value(iter_, 0)
            try:
                MetadataEditor(self.gui.dbstate, self.gui.uistate, [], media)
            except Errors.WindowActiveError:
                pass

    def main(self): # return false finishes
        """
        get the active media, mime type, and reads the image metadata
        """

        active_media = self.get_active("Media")
        if not active_media:
            return

        self.orig_image = self.dbstate.db.get_object_from_handle(active_media)
        self.media_text.set_text("")
        if self.orig_image:
            self.media_text.set_text( self.orig_image.get_description() )
        else:
            self.media_text.set_text(_('No active media...'))
            return

        # clear all dirty flags against media
        self._clear_image(self.orig_image)

        # check media read priviledges?
        if not os.access(self.orig_image.get_path(), os.R_OK):
            return

        # check media write priviledges?
        if not os.access(self.orig_image.get_path(), os.W_OK):
            self._mark_dirty_write(self.orig_image)

        # get image mime type
        mime_type = self.orig_image.get_mime_type()
        if mime_type and mime_type.startswith("image"):
            _type, _imgtype = mime_type.split("/")

            # check to make sure imagetype is within valid image types? 
            found = any(_imgtype == filetype for filetype in _valid_types)
            if not found:
                self._mark_dirty_write(self.orig_image)
                return
        else:
            # prevent non mime images from attempting to write to non MIME images...
            self._mark_dirty_write(self.orig_image)
            return

        self.model.clear()

        # read the image metadata and display it
        self.display_exif_keys(self.orig_image)

        # set up tooltips text
        self.setup_tooltips(self.orig_image)

    def setup_tooltips(self, obj):
        """
        setup tooltips for each field
        """

        # sets tooltip text for the Save button
        self.exif_widgets["Save"].set_tooltip_text(_("Saves the media "
            "metadata to the image."))

        # sets tooltip text for the Edit button
        self.exif_widgets["Edit"].set_tooltip_text(_("Edits the active "
            "media's metadata."))

        # sets tooltip text for the Clear button
        self.exif_widgets["Clear"].set_tooltip_text(_("Clears all the image "
            "metadata key values."))

    def _clear_image(self, obj):
        self._dirty_image = False
        self._dirty_write = False

    def _mark_dirty_image(self, obj):
        self._dirty_image = True

    def _mark_dirty_write(self, obj):
        self._dirty_write = True

    def clear_metadata(self, obj):
        """
        clears all data fields to nothing
        """

        self.model.clear()

    def display_exif_keys(self, media):
        """
        reads the image metadata after the pyexiv2.Image has been created
        """

        full_path = Utils.media_path_full(self.dbstate.db, media.get_path() )
        if LesserVersion: # prior to pyexiv2-0.2.0
            try:
                metadata = pyexiv2.Image(full_path)
            except IOError:
                return
            metadata.readMetadata()
            for key in metadata.exifKeys():
                label = metadata.tagDetails(key)[0]
                human_value = metadata.interpretedExifValue(key)
                self.model.add((label, human_value))

        else: # pyexiv2-0.2.0 and above
            metadata = pyexiv2.ImageMetadata(full_path)
            try:
                metadata.read()
            except IOError:
                return
            for key in metadata.exif_keys:
                tag = metadata[key]
                self.model.add((tag.label, tag.human_value))

    def post_init(self):
        self.connect_signal("Media", self.update)
        
#################################################
#    Metadata Editor Class
#################################################
import ManagedWindow
from gui.widgets import MonitoredEntry

class MetadataEditor(ManagedWindow.ManagedWindow):
    """
    Media Metadata Editor.
    """

    def __init__(self, dbstate, uistate, track, media):

        self.dbstate = dbstate
        self.uistate = uistate
        self.track = track
        self.db = dbstate.db
        
        self.media = media

        ManagedWindow.ManagedWindow.__init__(self, uistate, track, media)

        self.widgets = {}
        top = self.__create_gui()
        self.set_window(top, None, self.get_menu_title() )

    def get_menu_title(self):
        """
        Get the menu title.
        """
        if self.media.get_handle():
            title = self.media.get_description()
            if not title:
                title = _("Unknoen") 
            dialog_title = _('Media: %s') % title
        else:
            dialog_title = _('New Media')
        return dialog_title

#################################################
#          Metadata Save
#################################################
import ManagedWindow
from gui.widgets import MonitoredEntry

class MetadataSave(ManagedWindow.ManagedWindow):
    """
    Media Metadata Saver
    """

    def __init__(self, dbstate, uistate, track, media):

        self.dbstate = dbstate
        self.uistate = uistate
        self.track = track
        self.db = dbstate.db
        
        self.media = media

        ManagedWindow.ManagedWindow.__init__(self, uistate, track, media)

        self.widgets = {}
        top = self.__create_gui()
        self.set_window(top, None, _("Metadata Save") )

    def _set_value(self, KeyTag, KeyValue):
        """
        sets the value for the Exif keys

        @param: KeyTag   -- exif key
        @param: KeyValue -- value to be saved
        """

        # LesserVersion would only be True when pyexiv2-to 0.1.3 is installed
        if not LesserVersion:

            # Exif KeyValue family?
            if "Exif" in KeyTag:
                try:
                    self.plugin_image[KeyTag].value = KeyValue
                except KeyError:
                    self.plugin_image[KeyTag] = pyexiv2.ExifTag(KeyTag, KeyValue)
                except ValueError, AttributeError:
                    pass

            # Iptc KeyValue family?
            else:
                try:
                    self.plugin_image[KeyTag].values = KeyValue
                except KeyError:
                    self.plugin_image[KeyTag] = pyexiv2.IptcTag(KeyTag, KeyValue)
                except ValueError, AttributeError:
                    pass

        else:
            self.plugin_image[KeyTag] = KeyValue 

#------------------------------------------------
#     Writes/ saves metadata to image
#------------------------------------------------
    def save_metadata(self, obj):
        """
        gets the information from the plugin data fields
        and sets the keytag = keyvalue image metadata
        """

        # check write permissions for this image
        if not self._dirty_write:

            # Author data field
            artist = self.exif_widgets["Author"].get_text()
            if (self.artist is not artist):
                self._set_value(ImageArtist, artist)

            # Copyright data field
            copyright = self.exif_widgets["Copyright"].get_text()
            if (self.copyright is not copyright):
                self._set_value(ImageCopyright, copyright)

            # get date from data field for saving
            wdate = self._write_date( self.exif_widgets["NewDate"].get_text(),
                                 self.exif_widgets["NewTime"].get_text() )
            if wdate is not False: 
                self._set_value(ImageDateTime, wdate)

            # get Latitude/ Longitude from this addon...
            latitude  =  self.exif_widgets["Latitude"].get_text()
            longitude = self.exif_widgets["Longitude"].get_text()

            # check to see if Latitude/ Longitude exists?
            if (latitude and longitude):

                # complete some error checking to prevent crashes...
                # if "?" character exist, remove it?
                if ("?" in latitude or "?" in longitude):
                    latitude = latitude.replace("?", "")
                    longitude = longitude.replace("?", "")

                # if "," character exists, remove it?
                if ("," in latitude or "," in longitude): 
                    latitude = latitude.replace(",", "")
                    longitude = longitude.replace(",", "") 

                # if it is in decimal format, convert it to DMS?
                # if not, then do nothing?
                self.convert2dms(self.plugin_image)

                # get Latitude/ Longitude from the data fields
                latitude  =  self.exif_widgets["Latitude"].get_text()
                longitude = self.exif_widgets["Longitude"].get_text()

                # will add (degrees, minutes, seconds) symbols if needed?
                # if not, do nothing...
                latitude, longitude = self.addsymbols2gps(latitude, longitude)

                # set up display
                self.exif_widgets["Latitude"].set_text(latitude)
                self.exif_widgets["Longitude"].set_text(longitude)

                LatitudeRef = " N"
                if "S" in latitude:
                    LatitudeRef = " S"
                latitude = latitude.replace(LatitudeRef, "")
                LatitudeRef = LatitudeRef.replace(" ", "")

                LongitudeRef = " E"
                if "W" in longitude:
                    LongitudeRef = " W"
                longitude = longitude.replace(LongitudeRef, "")
                LongitudeRef = LongitudeRef.replace(" ", "")

                # remove symbols for saving Latitude/ Longitude GPS Coordinates
                latitude, longitude = _removesymbols4saving(latitude, longitude) 

                # convert (degrees, minutes, seconds) to Rational for saving
                self._set_value(ImageLatitude, coords_to_rational(latitude))
                self._set_value(ImageLatitudeRef, LatitudeRef)

                # convert (degrees, minutes, seconds) to Rational for saving
                self._set_value(ImageLongitude, coords_to_rational(longitude))
                self._set_value(ImageLongitudeRef, LongitudeRef)

            # description data field
            start = self.exif_widgets["Description"].get_start_iter()
            end = self.exif_widgets["Description"].get_end_iter()
            meta_descr = self.exif_widgets["Description"].get_text(start, end)
            if (self.description is not meta_descr):
                self._set_value(ImageDescription, meta_descr)

            # writes the metdata KeyTags to the image...  
            # LesserVersion would only be True when pyexiv2-to 0.1.3 is installed
            if not LesserVersion:
                self.plugin_image.write()
            else:
                self.plugin_image.writeMetadata()

            # notify the user of successful write...
            OkDialog(_("Image metadata has been saved."))

        else:
            ErrorDialog(_("There is an error with this image!\n"
                "You may not have write access or privileges for this image?"))

#------------------------------------------------
# Process Date/ Time fields for saving to image
#------------------------------------------------
    def _write_date(self, wdate = False, wtime = False):
        """
        process the date/ time for writing to image

        @param: wdate -- date from the interface
        @param: wtime -- time from the interface
        """

        # set to initial values, so if it is something wrong,
        # so we can catch it...?
        wyear, wmonth, wday = False, False, False
        hour, minutes, seconds = False, False, False

        # if date is in proper format: 1826-Apr-12 or 1826-April-12
        if (wdate and wdate.count("-") == 2):
            wyear, wmonth, wday = _split_values(wdate)

        # if time is in proper format: 14:06:00
        if (wtime and wtime.count(":") == 2):
            hour, minutes, seconds = _split_values(wtime)

        # if any value for date or time is False, then do not save date
        bad_datetime = any(value == False for value in [wyear, wmonth, wday, hour, minutes, seconds] )
        if not bad_datetime:

            # convert each value for date/ time
            try:
                wyear, wday = int(wyear), int(wday)
            except ValueError:
                pass

            try:
                hour, minutes, seconds = int(hour), int(minutes), int(seconds)
            except ValueError:
                pass

            if wdate is not False:

                # do some error trapping...
                if wday == 0:
                    wday = 1
                if hour >= 24:
                    hour = 0
                if minutes > 59:
                    minutes = 59
                if seconds > 59:
                    seconds = 59

                # convert month, and do error trapping
                try:
                    wmonth = int(wmonth)
                except ValueError:
                    wmonth = _return_month(wmonth)
                if wmonth > 12:
                    wmonth = 12

                # get the number of days in wyear of all months
                numdays = [0] + [calendar.monthrange(year, month)[1] for year 
                    in [wyear] for month in range(1, 13) ]

            if wday > numdays[wmonth]:
                wday = numdays[wmonth]

            # ExifImage Year must be greater than 1900
            # if not, we save it as a string
            if wyear < 1900:
                wdate = "%04d-%s-%02d %02d:%02d:%02d" % (
                    wyear, _dd.long_months[wmonth], wday, hour, minutes, seconds)

            # year -> or equal to 1900
            else:
                wdate = datetime(wyear, wmonth, wday, hour, minutes, seconds)

            self.exif_widgets["NewDate"].set_text("%04d-%s-%02d" % (
                wyear, _dd.long_months[wmonth], wday) )
            self.exif_widgets["NewTime"].set_text("%02d:%02d:%02d" % (
                hour, minutes, seconds) )

        else:

            ErrorDialog(_("There was a problem with either the date and/ or time."))

        # return the modified date/ time
        return wdate

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
        self.exif_widgets["NewDate"].set_text(
            "%04d-%s-%02d" % (year, _dd.long_months[month], day) )

        # close this window
        self.app.destroy()

# -------------------------------------------------------------------
#          GPS Coordinates functions
# -------------------------------------------------------------------
    def addsymbols2gps(self, latitude =False, longitude =False):
        """
        converts a degrees, minutes, seconds representation of Latitude/ Longitude
        without their symbols to having them...

        @param: latitude -- Latitude GPS Coordinates
        @param: longitude -- Longitude GPS Coordinates
        """
        LatitudeRef, LongitudeRef = "N", "E"

        # check to see if Latitude/ Longitude exits?
        if (latitude and longitude):

            if (latitude.count(".") == 1 and longitude.count(".") == 1):
                self.convert2dms(self.plugin_image)

                # get Latitude/ Longitude from data fields
                # after the conversion
                latitude  =  self.exif_widgets["Latitude"].get_text()
                longitude = self.exif_widgets["Longitude"].get_text()

            # add DMS symbols if necessary?
            # the conversion to decimal format, require the DMS symbols
            elif ( (latitude.count("°") == 0 and longitude.count("°") == 0) and
                (latitude.count("′") == 0 and longitude.count("′") == 0) and
                (latitude.count('″') == 0 and longitude.count('″') == 0) ):

                # is there a direction element here?
                if (latitude.count("N") == 1 or latitude.count("S") == 1):
                    latdeg, latmin, latsec, LatitudeRef = latitude.split(" ", 3)
                else:
                    atitudeRef = "N"
                    latdeg, latmin, latsec = latitude.split(" ", 2)
                    if latdeg[0] == "-":
                        latdeg = latdeg.replace("-", "")
                        LatitudeRef = "S"

                # is there a direction element here?
                if (longitude.count("E") == 1 or longitude.count("W") == 1):
                    longdeg, longmin, longsec, LongitudeRef = longitude.split(" ", 3)
                else:
                    ongitudeRef = "E"
                    longdeg, longmin, longsec = longitude.split(" ", 2)
                    if longdeg[0] == "-":
                        longdeg = longdeg.replace("-", "")
                        LongitudeRef = "W"

                latitude  = """%s° %s′ %s″ %s""" % (latdeg, latmin, latsec, LatitudeRef)
                longitude = """%s° %s′ %s″ %s""" % (longdeg, longmin, longsec, LongitudeRef)
        return latitude, longitude

    def convert2decimal(self, obj):
        """
        will convert a decimal GPS Coordinates into decimal format
        """

        # get Latitude/ Longitude from the data fields
        latitude  =  self.exif_widgets["Latitude"].get_text()
        longitude = self.exif_widgets["Longitude"].get_text()

        # if latitude and longitude exist?
        if (latitude and longitude):

            # is Latitude/ Longitude are in DMS format?
            if (latitude.count(" ") >= 2 and longitude.count(" ") >= 2): 

                # add DMS symbols if necessary?
                # the conversion to decimal format, require the DMS symbols 
                if ( (latitude.count("°") == 0 and longitude.count("°") == 0) and
                    (latitude.count("′") == 0 and longitude.count("′") == 0) and
                    (latitude.count('″') == 0 and longitude.count('″') == 0) ):

                    latitude, longitude = self.addsymbols2gps(latitude, longitude)

                # convert degrees, minutes, seconds w/ symbols to an 8 point decimal
                latitude, longitude = conv_lat_lon( unicode(latitude),
                                                    unicode(longitude), "D.D8")

                self.exif_widgets["Latitude"].set_text(latitude)
                self.exif_widgets["Longitude"].set_text(longitude)

    def convert2dms(self, obj):
        """
        will convert a decimal GPS Coordinates into degrees, minutes, seconds
        for display only
        """

        # get Latitude/ Longitude from the data fields
        latitude = self.exif_widgets["Latitude"].get_text()
        longitude = self.exif_widgets["Longitude"].get_text()

        # if Latitude/ Longitude exists?
        if (latitude and longitude):

            # if coordinates are in decimal format?
            if (latitude.count(".") == 1 and longitude.count(".") == 1):

                # convert latitude and longitude to a DMS with separator of ":"
                latitude, longitude = conv_lat_lon(latitude, longitude, "DEG-:")
 
                # remove negative symbol if there is one?
                LatitudeRef = "N"
                if latitude[0] == "-":
                    latitude = latitude.replace("-", "")
                    LatitudeRef = "S"
                latdeg, latmin, latsec = latitude.split(":", 2)

               # remove negative symbol if there is one?
                LongitudeRef = "E"
                if longitude[0] == "-":
                    longitude = longitude.replace("-", "")
                    LongitudeRef = "W"
                longdeg, longmin, longsec = longitude.split(":", 2)

                self.exif_widgets["Latitude"].set_text(
                    """%s° %s′ %s″ %s""" % (latdeg, latmin, latsec, LatitudeRef) )

                self.exif_widgets["Longitude"].set_text(
                    """%s° %s′ %s″ %s""" % (longdeg, longmin, longsec, LongitudeRef) )

def string_to_rational(coordinate):
    """
    convert string to rational variable for GPS
    """

    if '.' in coordinate:
        value1, value2 = coordinate.split('.')
        return pyexiv2.Rational(int(float(value1 + value2)), 10**len(value2))
    else:
        return pyexiv2.Rational(int(coordinate), 1)

def _removesymbols4saving(latitude =False, longitude =False):
    """
    will recieve a DMS with symbols and return it without them

    @param: latitude -- Latitude GPS Coordinates
    @param: longitude -- GPS Longitude Coordinates
    """

    # check to see if latitude/ longitude exist?
    if (latitude and longitude):

        # remove degrees symbol if it exist?
        latitude = latitude.replace("°", "")
        longitude = longitude.replace("°", "")

        # remove minutes symbol if it exist?
        latitude = latitude.replace("′", "")
        longitude = longitude.replace("′", "")

        # remove seconds symbol if it exist?
        latitude = latitude.replace('″', "")
        longitude = longitude.replace('″', "")

    return latitude, longitude

def coords_to_rational(Coordinates):
    """
    returns the GPS coordinates to Latitude/ Longitude
    """

    return [string_to_rational(coordinate) for coordinate in Coordinates.split( " ")]

def convert_value(value):
    """
    will take a value from the coordinates and return its value
    """

    return str( ( Decimal(value.numerator) / Decimal(value.denominator) ) )

def rational_to_dms(coords, ValueType = False):
    """
    takes a rational set of coordinates and returns (degrees, minutes, seconds)

    @param: ValueType -- how did the coordinates come into this addon
            0 = [Fraction(40, 1), Fraction(0, 1), Fraction(1079, 20)]
            1 = '105/1 16/1 1396/100 
    """

    deg, min, sec = False, False, False
    if ValueType is not False:

        # coordinates look like: '38/1 38/1 318/100'  
        if ValueType == 1:

            deg, min, sec = coords.split(" ")
            deg, rest = deg.split("/")
            min, rest = min.split("/")
            sec, rest = sec.split("/")

            sec = str( ( Decimal(sec) / Decimal(rest) ) )

        # coordinates look like:
        #     [Rational(38, 1), Rational(38, 1), Rational(150, 50)]
        # or [Fraction(38, 1), Fraction(38, 1), Fraction(318, 100)]   
        elif (ValueType == 0 and isinstance(coords, list) ):
    
            if len(coords) == 3:
                deg, min, sec = coords[0], coords[1], coords[2]
                deg = convert_value(deg)
                min = convert_value(min)
                sec = convert_value(sec)
    return deg, min, sec
