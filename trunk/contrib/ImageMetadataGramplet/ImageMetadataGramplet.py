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

# abilty to escape certain characters from html output...
from xml.sax.saxutils import escape as _html_escape

from itertools import chain

from decimal import *
getcontext().prec = 4
from fractions import Fraction

import subprocess
#------------------------------------------------
# Internaturilation
#------------------------------------------------
from TransUtils import get_addon_translator
_ = get_addon_translator().ugettext

# -----------------------------------------------------------------------------
# GTK modules
# -----------------------------------------------------------------------------
import gtk

# -----------------------------------------------------------------------------
# GRAMPS modules
# -----------------------------------------------------------------------------
import GrampsDisplay
from QuestionDialog import OkDialog, WarningDialog, QuestionDialog

from gen.plug import Gramplet
from DateHandler import displayer as _dd

import gen.lib
import Utils
from PlaceUtils import conv_lat_lon

#####################################################################
#               Check for pyexiv2 library...
#####################################################################
# pyexiv2 download page (C) Olivier Tilloy
_DOWNLOAD_LINK = "http://tilloy.net/dev/pyexiv2/download.html"

# make sure the pyexiv2 library is installed and at least a minimum version
software_version = False
Min_VERSION = (0, 1, 3)
Min_VERSION_str = "pyexiv2-%d.%d.%d" % Min_VERSION
Pref_VERSION_str = "pyexiv2-%d.%d.%d" % (0, 3, 0)

# to be able for people that have pyexiv2-0.1.3 to be able to use this addon also...
LesserVersion = False

try:
    import pyexiv2
    software_version = pyexiv2.version_info

except ImportError, msg:
    WarningDialog(_("You need to install, %s or greater, for this addon to work...\n"
                    "I would recommend installing, %s, and it may be downloaded from here: \n%s") % (
                        Min_VERSION_str, Pref_VERSION_str, _DOWNLOAD_LINK), str(msg))
    raise Exception(_("Failed to load 'Image Metadata Gramplet'..."))
               
# This only happends if the user has pyexiv2-0.1.3 installed on their computer...
except AttributeError:
    LesserVersion = True

# the library is either not installed or does not meet minimum required version for this addon....
if (software_version and (software_version < Min_VERSION)):
    msg = _("The minimum required version for pyexiv2 must be %s \n"
        "or greater.  Or you do not have the python library installed yet.  "
        "You may download it from here: %s\n\n  I recommend getting, %s") % (
         Min_VERSION_str, _DOWNLOAD_LINK, Pref_VERSION_str)
    WarningDialog(msg)
    raise Exception(msg)

# *******************************************************************
#         Determine if we have access to outside Programs
#
# The programs are ImageMagick, and jhead
# * ImageMagick -- Convert and Delete all Exif metadata...
# * jhead       -- re-initialize a jpeg image...
# * del         -- delete the image after converting to Jpeg...
#********************************************************************
system_platform = os.sys.platform
# Windows 32bit systems
if system_platform == "win32":
    _MAGICK_FOUND = Utils.search_for("convert.exe")
    _JHEAD_FOUND = Utils.search_for("jhead.exe")
    _DEL_FOUND = Utils.search_for("del.exe")
    __del_command = "del.exe"

# all Linux systems
elif system_platform == "Linux2":
    _MAGICK_FOUND = Utils.search_for("convert")
    _JHEAD_FOUND = Utils.search_for("jhead")
    _DEL_FOUND = Utils.search_for("rm")
    __del_command = "rm"

# Windows 64bit systems
else:
    _MAGICK_FOUND = Utils.search_for("convert")
    _JHEAD_FOUND = Utils.search_for("jhead")
    _DEL_FOUND = Utils.search_for("del")
    __del_command = "del"

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
# available image types for exiv2 and pyexiv2
# [".jpeg", ".jpg", ".jfif", ".exv", ".tiff", ".dng", ".nef", ".pef", ".pgf", ".png", ".psd", ".jp2"]

def _help_page(obj):
    """
    will bring up a Wiki help page.
    """

    GrampsDisplay.help(webpage = 'Image Metadata Gramplet')

_allmonths = list([_dd.short_months[i], _dd.long_months[i], i] for i in range(1, 13))

def _return_month(month):
    """
    returns either an integer of the month number or the abbreviated month name

    @param: rmonth -- can be one of:
        10, "10", "Oct", or "October"
    """

    try:
        month = int(month)

    except ValueError:
        for sm, lm, index in _allmonths:
            if month == sm or month == lm:
                month = int(index)
                break
            elif str(month) == index:
                    month = lm
                    break
    return month

def _split_values(text):
    """
    splits a variable into its pieces
    """

    # a hypen
    if "-" in text:
        separator = "-"

    # a period
    elif "." in text:
        separator = "."

    # a colon
    elif ":" in text:
        separator = ":"

    # a space
    else:
        separator = " "

    return [value for value in text.split(separator)]

_BUTTONTIPS = {

    # Clear Display Area button... 
    "Clear"             : _("Clears the Exif metadata from the Display area."),

    # Edit Exif metadata button...
    "Edit"              : _("A pop-up window will allow you to Edit the image Exif metadata"),

    # Convert to .Jpeg button...
    "Convert"           : _("If your image is not a jpeg image, convert it to jpeg?"),

    # Wiki Help button...
    "Help"              : _("Displays the Gramps Wiki Help page for 'Image Metadata Gramplet' "
        "in your web bvboxer."),

    # Save Exif Metadata button...
    "Save"              : _("Saves/ writes the Exif metadata to this image.\n"
        "WARNING: Exif metadata will be erased if you save a blank entry field..."),

    # Delete/Erase/ Wipe Exif metadata button...
    "Delete"            : _("WARNING:  This will completely delete/ erase all Exif metadata "
        "from this image?") }.items()

#************************************************
#
# This class will handle all the common
# ground work for all the classes into this
# addon/ gramplet
#
#************************************************
class BasePage(object):

    def init(self):

        # set up Exif keys for Image.exif_keys
        self._DATAMAP = {
            "Exif.Image.ImageDescription"  : "Description",
            "Exif.Image.DateTime"          : "ModDateTime",
            "Exif.Image.Artist"            : "Artist",
            "Exif.Image.Copyright"         : "Copyright",
            "Exif.Photo.DateTimeOriginal"  : "DateTime",
            "Exif.GPSInfo.GPSLatitudeRef"  : "LatitudeRef",
            "Exif.GPSInfo.GPSLatitude"     : "Latitude",
            "Exif.GPSInfo.GPSLongitudeRef" : "LongitudeRef",
            "Exif.GPSInfo.GPSLongitude"    : "Longitude"}
        self._DATAMAP  = dict( (key, val) for key, val in self._DATAMAP.items())
        self._DATAMAP.update( (val, key) for key, val in self._DATAMAP.items())

    def create_column(self, name, colnum, fixed =True):
        """
        will create the column for the column row...
        """

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(name, renderer, text =colnum)

        if fixed:
            column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
            column.set_expand(True)

        else:
            column.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
            column.set_expand(False)

        column.set_alignment(0.0)
        column.set_sort_column_id(colnum)

        return column

    def create_button(self, pos, text, callback, icon =False, sensitive = True):
        """
        creates and returns a button for display
        """

        if (icon and not text):
            button = gtk.Button(stock=icon)
        else:
            button = gtk.Button(text)

        button.connect("clicked", callback)

        if not sensitive:
            button.set_sensitive(False)
        self.exif_widgets[pos] = button

        return button

#********************************************************************
#
#                    image Metadata Gramplet class
#
#         This is the meat and potatoes for the Gramplet...
#********************************************************************
class imageMetadataGramplet(BasePage, Gramplet):

    def init(self):
        BasePage.init(self)

        self.exif_widgets = {}

        # set all dirty variables to False to begin this addon...
        self._dirty = False

        self.orig_image    = False
        self.image_path    = False
        self.plugin_image  = False
        self.MediaDataTags = False

        vbox = gtk.VBox()

        medialabel = gtk.HBox(False)
        self.exif_widgets["Media:Label"] = gtk.Label()
        self.exif_widgets["Media:Label"].set_alignment(0.0, 0.0)
        medialabel.pack_start(self.exif_widgets["Media:Label"], expand =False)

        mimetype = gtk.HBox(False)
        self.exif_widgets["Mime:Type"] = gtk.Label()
        self.exif_widgets["Mime:Type"].set_alignment(0.0, 0.0)
        mimetype.pack_start(self.exif_widgets["Mime:Type"], expand =False)

        messagearea = gtk.HBox(False)
        self.exif_widgets["Message:Area"] = gtk.Label(_("Click an image to begin..."))
        self.exif_widgets["Message:Area"].set_alignment(0.5, 0.0)
        messagearea.pack_start(self.exif_widgets["Message:Area"], expand =False)

        self.model = gtk.ListStore(object, str, str)
        view = gtk.TreeView(self.model)

        # Key Column
        view.append_column( self.create_column(_("Key"), 1) )

        # Value Column
        view.append_column( self.create_column(_("Value"), 2) )

        # bring all items together above the data fields
        vbox.pack_start(medialabel, expand =False)
        vbox.pack_start(mimetype, expand =False)
        vbox.pack_start(messagearea, expand =False)

        # Clear, Edit, Convert horizontal box...
        cec_box = gtk.HButtonBox()
        cec_box.set_layout(gtk.BUTTONBOX_START)

        # Clear button...
        cec_box.add( self.create_button(
            "Clear", False, self.clear_metadata, gtk.STOCK_CLEAR, False) )

        # Edit Exif metadata button
        cec_box.add( self.create_button(
            "Edit", False, self.__edit_metadata, gtk.STOCK_EDIT, False) )

        # Convert to Jpeg button...
        cec_box.add( self.create_button(
            "Convert", False, self.convert2Jpeg, gtk.STOCK_CONVERT, False) )
        vbox.pack_start(cec_box, expand =False, fill =False, padding =10)

        # Help, Save, Delete horizontal box...
        hsd_box = gtk.HButtonBox()
        hsd_box.set_layout(gtk.BUTTONBOX_START)

        # Help button...
        hsd_box.add( self.create_button(
            "Help", False, _help_page, gtk.STOCK_HELP) )

        # Save button...
        hsd_box.add( self.create_button(
            "Save", False, self.__save_dialog, gtk.STOCK_SAVE, False) )

        # Delete All Exif metadata button...
        hsd_box.add( self.create_button(
            "Delete", False, self.__delete_dialog, gtk.STOCK_DELETE, False) )

        # adds Exif Viewing Area
        vbox.pack_start(view, padding =10)
        vbox.pack_start(hsd_box, expand =False, fill =False, padding =10)

        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(vbox)
        vbox.show_all()

        # Setup Tooltips for all buttons...
        for widget, tooltip in _BUTTONTIPS:
            self.exif_widgets[widget].set_tooltip_text(tooltip)

    def main(self): # return false finishes
        """
        get the active media, mime type, and reads the image metadata
        """
        db = self.dbstate.db

        # clear Display and Edit Areas
        self.model.clear()

        # De-activate the buttons except for Help...
        self.deactivate_buttons(["Clear", "Convert", "Save", "Delete"])

        # Re-post initial image message...
        self.exif_widgets["Message:Area"].set_text(_("Select an image to begin..."))

        active_handle = self.get_active("Media")
        if not active_handle:
            return

        self.orig_image = db.get_object_from_handle(active_handle)
        self.image_path = Utils.media_path_full(db, self.orig_image.get_path() )
        if (not self.orig_image or not os.path.isfile(self.image_path)):
            self.exif_widgets["Message:Area"].set_text(_("Image is either missing or deleted,\n"
                "Choose a different image..."))
            return

        # check image read privileges...
        _readable = os.access(self.image_path, os.R_OK)
        if not _readable:
            self.exif_widgets["Message:Area"].set_text(_("Image is NOT readable,\n"
                "Choose a different image..."))
            return

        # check image write privileges...
        _writable = os.access(self.image_path, os.W_OK)
        if not _writable:
            self.exif_widgets["Message:Area"].set_text(_("Image is NOT writable,\n"
                "You will NOT be able to save Exif metadata...."))

        # Mime type information...
        mime_type = self.orig_image.get_mime_type()
        _mtype = gen.mime.get_description(mime_type)
        self.exif_widgets["Mime:Type"].set_text(_mtype)

        # determine if it is a mime image object?
        if (mime_type and mime_type.startswith("image") ):

            # display file description/ title...
            self.exif_widgets["Media:Label"].set_text( _html_escape(
                self.orig_image.get_description() ) )

            # will create the image and read it...
            self.setup_image(self.image_path, True)

            # Checks to make sure that ImageMagick is installed on this computer and
            # the image is NOT a jpeg image...
            if _MAGICK_FOUND:
                basename, extension = os.path.splitext(self.image_path)
                if extension not in [".jpeg", ".jpg", ".jfif"]:
                    self.activate_buttons(["Convert"])

            # displays the imge Exif metadata
            self.display_exif_tags(self.image_path)

        else:
            self.exif_widgets["Message:Area"].set_text(_("Choose a different image..."))
            return

    def __edit_metadata(self, obj):
        """
        Gandles the Edit button...
        """

        MetadataEditor(self.gui.dbstate, self.gui.uistate, self.plugin_image, self.MediaDataTags)

    def __save_dialog(self, obj):
        """
        Handles the Save question Dialog...
        """

        QuestionDialog(_("Image Metadata Gramplet"), _("Save Exif metadata to this image?"),
                _("Save"), self.save_metadata)

    def __delete_dialog(self, obj):
        """
        Handles the Delete Dialog...
        """

        QuestionDialog(_("Image Metadata Gramplet"), _("WARNING!  You are about to completely "
            "delete the Exif metadata from this image?"), _("Delete"),
                self.strip_metadata)

    def setup_image(self, full_path, createimage =False):
        """
        will return an image instance and read the Exif metadata.

        if createimage is True, it will create the pyexiv2 image instance...

        LesserVersion -- prior to pyexiv2-0.2.0
                      -- pyexiv2-0.2.0 and above...
        """

        if createimage:
            if LesserVersion:
                self.plugin_image = pyexiv2.Image(full_path)
            else:
                self.plugin_image = pyexiv2.ImageMetadata(full_path)

        if LesserVersion:
            self.plugin_image.readMetadata()

            # get all KeyTags for this image for diplay only...
            self.MediaDataTags = [KeyTag for KeyTag in chain(
                                self.plugin_image.exifKeys(),
                                self.plugin_image.xmpKeys(),
                                self.plugin_image.iptcKeys() ) ]
        else:
            self.plugin_image.read()

            # get all KeyTags for this image for diplay only...
            self.MediaDataTags = [KeyTag for KeyTag in chain(
                                self.plugin_image.exif_keys,
                                self.plugin_image.xmp_keys,
                                self.plugin_image.iptc_keys) ]

    def _get_exif_KeyTag(self, KeyTag):
        """
        gets the value from the Exif Key, and returns it...

        @param: KeyTag -- image metadata key
        """

        KeyValue = ""
        if LesserVersion:
            KeyValue = self.plugin_image[KeyTag]
        else:
            try:
                KeyValue = self.plugin_image[KeyTag].value

            except (KeyError, ValueError, AttributeError):
                pass

        return KeyValue

    def display_exif_tags(self, full_path):
        """
        once the pyexiv2.Image has been created, we display
            all of the image Exif metadata...
        """

        # check to see if we got metadata from the media object?
        if self.MediaDataTags:

            # clears all Message Area labels...
            self.exif_widgets["Message:Area"].set_text("")

            # activates necessary buttons...
            self.activate_buttons(["Edit", "Save", "Delete"])

            for KeyTag in self.MediaDataTags:
                tagValue = self._get_exif_KeyTag(KeyTag)
                if tagValue:
                    if LesserVersion:
                        label = self.plugin_image.tagDetails(KeyTag)[0]
                        human_value = self.plugin_image.interpretedExifValue(KeyTag)
                    else:
                        try:
                            tag = self.plugin_image[KeyTag]
                            label = tag.label
                            human_value = tag.human_value
                        except AttributeError:
                            human_value = False

                    if human_value is not False:
                        if KeyTag in ("Exif.Image.DateTime", "Exif.Photo.DateTimeOriginal",
                            "Exif.Photo.DateTimeDigitized"):
                            human_value = _process_date( self._get_exif_KeyTag(KeyTag) )

                        self.model.append( (self.plugin_image, label, human_value) )
        else:
            # display "No Exif metadata" message...
            self.exif_widgets["Message:Area"].set_text(_("No Exif metadata for this image..."))

        # Activate Clear and Save buttons..
        self.activate_buttons(["Clear"])

    def activate_buttons(self, ButtonList):
        """
        Enable/ activate the buttons that are in ButtonList
        """

        for ButtonName in ButtonList:
            self.exif_widgets[ButtonName].set_sensitive(True)

    def deactivate_buttons(self, ButtonList):
        """
        disable/ de-activate buttons in ButtonList
        """
        for ButtonName in ButtonList:
            self.exif_widgets[ButtonName].set_sensitive(False)

    def clear_metadata(self, obj, cleartype = "All"):
        """
        clears all data fields to nothing

        @param: cleartype -- 
            "Date" = clears only Date entry fields
            "All" = clears all data fields
        """

        self.model.clear()

    def convert2Jpeg(self, obj):
        """
        Will attempt to convert an image to jpeg if it is not?
        """

        # if ImageMagick's convert is installed...
        if _MAGICK_FOUND:
            self.exif_widgets["Message:Area"].set_text(_("Converting image to a jpeg image..."))

            filepath, basename = os.path.split(self.image_path)
            basename, oldext = os.path.splitext(self.image_path)
            newextension = ".jpeg"

            change = subprocess.check_call( ["convert", self.image_path, 
                    os.path.join(filepath, basename + newextension) ] )
            if str(change):
                self.disable_button(["Convert"])

                if _DEL_FOUND:
                    deleted = subprocess.check_call( [_del_command, self.image_path] )
                    if str(deleted):
                        self.exif_widgets["Message:Area"].set_text(_("Original image has "
                            "been deleted!"))

    def _set_exif_KeyTag(self, KeyTag, KeyValue):
        """
        sets the value for the metadata KeyTags
        """

        if LesserVersion:
            self.plugin_image[KeyTag] = KeyValue

        else:
            try:  # tag is being modified...
                self.plugin_image[KeyTag] = KeyValue

            except KeyError:  # tag has not been set...
                self.plugin_image[KeyTag] = pyexiv2.ExifTag(KeyTag, KeyValue)

            except (ValueError, AttributeError):  # there is an issue with either KeyTag or KeyValue
                pass

    def write_metadata(self, imageinstance):
        """
        writes the Exif metadata to the image.

        LesserVersion -- prior to pyexiv2-0.2.0
                      -- pyexiv2-0.2.0 and above... 
        """
        if LesserVersion:
            imageinstance.writeMetadata()

        else:
            imageinstance.write()

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
        will convert a decimal GPS Coordinates into decimal format.

        @param: latitude  -- GPS Latitude Coordinates from data field...
        @param: longitude -- GPS Longitude Coordinates from data field...
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

#------------------------------------------------
#        Saves Exif metadata to image
#------------------------------------------------
    def save_metadata(self):
        """
        gets the information from the plugin data fields
        and sets the KeyTag = keyvalue image metadata
        """

        # set Message Area for saving...
        self.exif_widgets["Message:Area"].set_text(_("Saving Exif metadata to image..."))

        # Description data field
        self._set_exif_KeyTag(self._DATAMAP["Description"], self.exif_widgets["Description"].get_text() )

        # Modify Date/ Time... not a data field, but saved anyway...
        ModDateTime = _format_datetime(datetime.now() )
        self._set_exif_KeyTag(self._DATAMAP["ModDateTime"], _write_date(ModDateTime) )
 
        # Artist/ Author data field
        self._set_exif_KeyTag(self._DATAMAP["Artist"], self.exif_widgets["Artist"].get_text() )

        # Copyright data field
        self._set_exif_KeyTag(self._DATAMAP["Copyright"], self.exif_widgets["Copyright"].get_text() )

        # Original Date/ Time data field
        DateTime = self.exif_widgets["DateTime"].get_text()
        if DateTime:
            if type(DateTime) is not datetime:
                DateTime = _process_date(DateTime)
                
            if type(DateTime) == datetime:
                self.exif_widgets["DateTime"].set_text(_format_datetime(DateTime) )
        self._set_exif_KeyTag(self._DATAMAP["DateTime"], _write_date(DateTime) )

        # Latitude/ Longitude data fields
        latitude  =  self.exif_widgets["Latitude"].get_text()
        longitude = self.exif_widgets["Longitude"].get_text()

        # check to see if Latitude/ Longitude exists?
        if (latitude and longitude):

            # complete some error checking to prevent crashes...
            # if "?" character exist, remove it?
            if "?" in latitude:
                latitude = latitude.replace("?", "")
            if "?" in longitude:
                longitude = longitude.replace("?", "")

            # if "," character exists, remove it?
            if "," in latitude: 
                latitude = latitude.replace(",", "")
            if "," in longitude:
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
            self._set_exif_KeyTag(self._DATAMAP["LatitudeRef"], LatitudeRef)
            self._set_exif_KeyTag(self._DATAMAP["Latitude"], coords_to_rational(latitude))

            # convert (degrees, minutes, seconds) to Rational for saving
            self._set_exif_KeyTag(self._DATAMAP["LongitudeRef"], LongitudeRef)
            self._set_exif_KeyTag(self._DATAMAP["Longitude"], coords_to_rational(longitude))

        # notify the user of successful write...
        OkDialog(_("Image Exif metadata has been saved."))

        # writes all Exif Metadata to image...
        self.write_metadata(self.plugin_image)

        # Activate Delete button...
        self.activate_buttons(["Delete"])

        # clears message area...
        self.exif_widgets["Message:Area"].set_text("")

    def strip_metadata(self):
        """
        Will completely and irrevocably erase all Exif metadata from this image.
        """

        if _MAGICK_FOUND:
            erase = subprocess.check_call( ["convert", self.image_path, "-strip", self.image_path] )
            erase_results = str(erase)

        else:
            if self.MediaDataTags: 
                for KeyTag in self.MediaDataTags:
                    del self.plugin_image[KeyTag]
                erase_results = True

                # write wiped metadata to image...
                self.write_metadata(self.plugin_image)

        if erase_results:

            # set Message Area for deleting...
            self.exif_widgets["Message:Area"].set_text(_("Deleting all Exif metadata..."))

            # Clear the Display and Edit Areas
            self.clear_metadata(self.plugin_image)
            self.model.clear()

            # Notify the User...
            self.exif_widgets["Message:Area"].set_text(_("All Exif metadata has been "
                    "deleted from this image..."))

            self.update()

            # re- initialize the image...
            if _JHEAD_FOUND:
                reinit = subprocess.check_call( ["jhead", "-purejpg", self.image_path] )

#------------------------------------------------
#     Database functions
#------------------------------------------------
    def post_init(self):
        self.connect_signal("Media", self.update)
        
    def db_changed(self):
        self.dbstate.db.connect('media-update', self.update)
        self.update()

def string_to_rational(coordinate):
    """
    convert string to rational variable for GPS
    """

    if '.' in coordinate:
        value1, value2 = coordinate.split('.')
        return pyexiv2.Rational(int(float(value1 + value2)), 10**len(value2))
    else:
        return pyexiv2.Rational(int(coordinate), 1)

def coords_to_rational(Coordinates):
    """
    returns the GPS coordinates to Latitude/ Longitude
    """

    return [string_to_rational(coordinate) for coordinate in Coordinates.split(" ")]

def convert_value(value):
    """
    will take a value from the coordinates and return its value
    """

    if isinstance(value, (Fraction, pyexiv2.Rational)):

        return str( ( Decimal(value.numerator) / Decimal(value.denominator) ) )

def _removesymbols4saving(latitude, longitude):
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

def rational_to_dms(coords):
    """
    takes a rational set of coordinates and returns (degrees, minutes, seconds)

    [Fraction(40, 1), Fraction(0, 1), Fraction(1079, 20)]
    """

    deg, min, sec =     False, False, False
    # coordinates look like:
    #     [Rational(38, 1), Rational(38, 1), Rational(150, 50)]
    # or [Fraction(38, 1), Fraction(38, 1), Fraction(318, 100)]   
    if isinstance(coords, list):
    
        if len(coords) == 3:
            return [convert_value(coordinate) for coordinate in coords]

    return deg, min, sec

def _format_datetime(exif_dt):
    """
    Convert a python datetime object into a string for display, using the
    standard Gramps date format.
    """
    if type(exif_dt) is not datetime:
        return ''

    date_part = gen.lib.Date()
    date_part.set_yr_mon_day(exif_dt.year, exif_dt.month, exif_dt.day)
    date_str = _dd.display(date_part)
    time_str = exif_dt.strftime('%H:%M:%S')

    return _('%(date)s %(time)s') % {'date': date_str, 'time': time_str}

def _get_date_format(datestr):
    """
    attempt to retrieve date format from date string
    """

    # attempt to determine the dateformat of the variable passed to it...
    for dateformat in ["%Y-%m-%d %H:%M:%S", "%Y %m %d %H:%M:%S",
                       "%Y-%b-%d %H:%M:%S", "%Y %b %d %H:%M:%S",
                       "%Y-%B-%d %H:%M:%S", "%Y %B %d %H:%M:%S",
                       "%d-%m-%Y %H:%M:%S", "%d %m %Y %H:%M:%S",
                       "%d-%b-%Y %H:%M:%S", "%d %b %Y %H:%M:%S",
                       "%d-%B-%Y %H:%M:%S", "%d %B %Y %H:%M:%S",
                       "%m-%d-%Y %H:%M:%S", "%m %d %Y %H:%M:%S",
                       "%b-%d-%Y %H:%M:%S", "%b %d %Y %H:%M:%S",
                       "%B-%d-%Y %H:%M:%S", "%B %d %Y %H:%M:%S"]:

        # find date string format
        try:
            tmpDate = time.strptime(datestr, dateformat)
            break

        # datestring format  not found...
        except ValueError:
            tmpDate = False

    return tmpDate

def _write_date(wdatetime):
    """
    handle thes Original Date/ Time field for saving
    """

    datestr = _get_date_format(wdatetime)
    if datestr is not False:
        wyear, wmonth, day, hour, minutes, seconds = datestr[0:6]

        # do some error trapping...
        if wmonth > 12: wmonth = 12
        if day == 0: day = 1
        if hour >= 24: hour = 0
        if minutes > 59: minutes = 59
        if seconds > 59: seconds = 59

        # get the number of days in year for all months
        numdays = [0] + [calendar.monthrange(year, month)[1] for year
                        in [wyear] for month in range(1, 13) ]

        # Make sure that day number is not greater than number of days in that month...
        if day > numdays[wmonth]: day = numdays[wmonth]

        if wyear < 1900:
            try:
                tmpDate = "%04d-%s-%02d %02d:%02d:%02d" % (wyear, _dd.long_months[wmonth], day,
                                                    hour, minutes, seconds)
            except ValueError:
                tmpDate = ""
        else:
            try:
                tmpDate = datetime(wyear, wmonth, day, hour, minutes, seconds)
            except ValueError:
                tmpDate = ""

        return tmpDate
    else:
        return ""
    
def _process_date(tmpDate):
    """
    will attempt to parse the date/ time Exif metadata entry into its pieces...
        (year, month, day, hour, minutes, seconds)
    """

    if not tmpDate:
        return ""

    datetype = type(tmpDate)

    # if variable is already in datetime.datetime() format, return it?
    if datetype == datetime:
        return _format_datetime(tmpDate)

    elif datetype in [date, gen.lib.date.Date, list]:
        hour, minutes, seconds = time.localtime()[3:6]

        # ImageDateTime is in datetime.date format
        if datetype == date:
            pyear, pmonth, day = tmpDate.year, tmpDate.month, tmpDate.day

        # ImageDateTime is in gen.lib.date.Date format
        elif datetype == gen.lib.date.Date:
            pyear, pmonth, day = tmpDate.get_year(), tmpDate.get_month(), tmpDate.get_day()

        # ImageDateTime is in list format
        else:
            pyear, pmonth, day = tmpDate[0].year, tmpDate[0].month, tmpDate[0].day

    # datetime is in string format...
    elif datetype == str:

        datestr = _get_date_format(tmpDate)
        if datestr is not False:
            pyear, pmonth, day, hour, minutes, seconds = datestr[0:6]

        else:
            pyear, pmonth, day, hour, minutes, seconds = [False]*6

        # do some error trapping...
        if pmonth > 12: pmonth = 12
        if day == 0: day = 1
        if hour >= 24: hour = 0
        if minutes > 59: minutes = 59
        if seconds > 59: seconds = 59

        # get the number of days in year for all months
        numdays = [0] + [calendar.monthrange(year, month)[1] for year
                        in [pyear] for month in range(1, 13) ]

        if day > numdays[pmonth]:
            day = numdays[pmonth]

    if pyear < 1900:
        try:
            tmpDate = "%04d-%s-%02d %02d:%02d:%02d" % (pyear, _dd.long_months[pmonth], day,
                                                hour, minutes, seconds)
        except ValueError:
            tmpDate = ""
    else:
        try:
            tmpDate = datetime(pyear, pmonth, day, hour, minutes, seconds)

        except ValueError:
            tmpDate = False

    if tmpDate is not False:
        if type(tmpDate) == datetime:
            return _format_datetime(tmpDate)
        else:
            try:
                return "%04d-%s-%02d %02d:%02d:%02d" % (pyear, _dd.long_months[pmonth], day,
                                                hour, minutes, seconds)
            except ValueError:
                return ""
    else:
        return ""

import pygtk
pygtk.require("2.0")

#************************************************
#                                               #
#          Edit Exif metadata class             #
#                                               #
#************************************************

# define tooltips for all entries and buttons...
_TOOLTIPS = {

    # Description...
    "Description"       : _("Provide a short descripion for this image."),

    # Artist 
    "Artist"            : _("Enter the Artist/ Author of this image.  The person's name or "
        "the company who is responsible for the creation of this image."),

    # Copyright
    "Copyright"         : _("Enter the copyright information for this image. \n"
        "Example: (C) 2010 Smith and Wesson"),

    # Original Date/ Time... 
    "DateTime"      : _("Original Date/ Time of this image.\n"
        "Example: 1826-Apr-12 14:30:00, 1826-April-12, 1998-01-31 13:30:00"),

    # GPS Latitude...
    "Latitude"          : _("Enter the GPS Latitude Coordinates for your image,\n"
        "Example: 43.722965, 43 43 22 N, 38° 38′ 03″ N, 38 38 3"),

    # GPS Longitude...
    "Longitude"         : _("Enter the GPS Longitude Coordinates for your image,\n"
        "Example: 10.396378, 10 23 46 E, 105° 6′ 6″ W, -105 6 6") }.items()

class MetadataEditor(BasePage):

    def __init__(self, dbstate, uistate, media, mediadatatags):    
        BasePage.init(self)

        self.dbstate = dbstate
        self.uistate = uistate

        self.plugin_image = media
        self.MediaDataTags = mediadatatags

        self.exif_widgets = {}
        _tip = _("This window will allow you to Edit and Save the Image Eif metadata...")

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.tooltip = _tip
        self.window.set_title(_("Exif Metadata Editor"))
        self.window.set_default_size(400, 350)
        self.window.set_border_width(10)
        self.window.connect("delete_event", self.delete_event)

        table = self.__create_table(9, 6)
        self.exif_widgets["Table"] = table
        self.window.add(self.exif_widgets["Table"])

        self.exif_widgets["Table"].show()
        self.window.show()

    def delete_event(self):
        """
        Handles closing this window.
        """

        self.window.destroy()

    def __create_table(self, rows, cols, homogeneous =False):
        """
        Creates a table with xrows and ycolumns...
        """

        table = gtk.Table(rows, cols, homogeneous)
        table.set_row_spacings(4)
        table.set_col_spacings(4)

        # Row 0
        label = gtk.Label(_("Description"))
        widget = gtk.EventBox()
        table.attach(label, 0, 1, 0, 1, xoptions=SHRINK, yoptions=SHRINK)
        table.attach(widget, 1, 6, 0, 1, xoptions=SHRINK, yoptions=SHRINK)

        # Row 1
        label = gtk.Label(_("Artist"))
        widget = gtk.EventBox()
        table.attach(label, 0, 1, 1, 2, xoptions=SHRINK, yoptions=SHRINK)
        table.attach(widget, 1, 6, 1, 2, xoptions=SHRINK, yoptions=SHRINK)

        return table

    def CopyTo(self):
        """
        reads the image metadata after the pyexiv2.Image has been created
        """

        if LesserVersion:
            imageKeyTags = [KeyTag for KeyTag in self.plugin_image.exifKeys() if KeyTag in self._DATAMAP]

        else:
            imageKeyTags = [KeyTag for KeyTag in self.plugin_image.exif_keys if KeyTag in self._DATAMAP]

        if imageKeyTags:
            self.exif_widgets["Message:Area"].set_text(_("Copying Exif metadata to the Edit Area..."))

        for KeyTag in imageKeyTags:

            # name for matching to exif_widgets 
            widgetsName = self._DATAMAP[KeyTag]

            tagValue = self._get_exif_KeyTag(KeyTag)
            if tagValue:

                if widgetsName in ["Description", "Artist", "Copyright"]:
                    self.exif_widgets[widgetsName].set_text(tagValue)

                # Original Date of the image...
                elif widgetsName == "DateTime":
                    use_date = self._get_exif_KeyTag(KeyTag)
                    use_date = _process_date(use_date) if use_date else False
                    if use_date is not False:
                        self.exif_widgets[widgetsName].set_text(use_date)

                # LatitudeRef, Latitude, LongitudeRef, Longitude...
                elif widgetsName == "Latitude":

                    latitude  =  self._get_exif_KeyTag(KeyTag)
                    longitude = self._get_exif_KeyTag(self._DATAMAP["Longitude"] )

                    # if latitude and longitude exist, display them?
                    if (latitude and longitude):

                        # split latitude metadata into (degrees, minutes, and seconds) from Rational
                        latdeg, latmin, latsec = rational_to_dms(latitude)

                        # split longitude metadata into degrees, minutes, and seconds
                        longdeg, longmin, longsec = rational_to_dms(longitude)

                        # check to see if we have valid GPS Coordinates?
                        latfail = any(coords == False for coords in [latdeg, latmin, latsec])
                        longfail = any(coords == False for coords in [longdeg, longmin, longsec])
                        if (not latfail and not longfail):

                            # Latitude Direction Reference
                            LatitudeRef = self._get_exif_KeyTag(self._DATAMAP["LatitudeRef"] )

                            # Longitude Direction Reference
                            LongitudeRef = self._get_exif_KeyTag(self._DATAMAP["LongitudeRef"] )

                            # set display for Latitude GPS Coordinates
                            self.exif_widgets["Latitude"].set_text(
                                """%s° %s′ %s″ %s""" % (latdeg, latmin, latsec, LatitudeRef) )

                            # set display for Longitude GPS Coordinates
                            self.exif_widgets["Longitude"].set_text(
                                """%s° %s′ %s″ %s""" % (longdeg, longmin, longsec, LongitudeRef) )

        # enable Save button after metadata has been "Copied to Edit Area"...
        self.activate_buttons(["Save", "Delete"])

        # Clear the Message Area...
        self.exif_widgets["Message:Area"].set_text("")

def _setup_widget_tooltips():
    """
    setup tooltips for each entry field and button.
    """

    for widget, tooltip in _TOOLTIPS:
        self.exif_widgets[widget].set_tooltip_text(tooltip)
