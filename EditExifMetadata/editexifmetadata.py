# -*- coding: utf-8 -*-
#!/usr/bin/env python

#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009-2011 Rob G. Healey <robhealey1@gmail.com>
#               2019      Paul Culley <paulr2787@gmail.com>
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


# *****************************************************************************
# Python Modules
# *****************************************************************************
import os
import datetime
import time
from PIL import Image

# abilty to escape certain characters from output
from xml.sax.saxutils import escape as _html_escape

from decimal import Decimal, getcontext
getcontext().prec = 6

# -----------------------------------------------------------------------------
# GTK modules
# -----------------------------------------------------------------------------
from gi.repository import Gtk, GdkPixbuf
import gi
gi.require_version('GExiv2', '0.10')
from gi.repository import GExiv2
# -----------------------------------------------------------------------------
# GRAMPS modules
# -----------------------------------------------------------------------------
from gramps.gui.display import display_help

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.const import IMAGE_DIR, GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.sgettext

from gramps.gen.datehandler import displayer as _dd
from gramps.gen.datehandler import parser as _dp

from gramps.gen.plug import Gramplet

from gramps.plugins.lib.libmetadata import MetadataView, format_datetime
from gramps.gui.widgets import ValidatableMaskedEntry
from gramps.gen.errors import ValidationError
from gramps.gui.dialog import QuestionDialog, QuestionDialog3

from gramps.gen.lib import Date

from gramps.gen.mime import get_description, get_type
from gramps.gen.utils.file import media_path_full
from gramps.gen.utils.place import conv_lat_lon

from gramps.gen.db import DbTxn


#------------------------------------------------
# support functions
#------------------------------------------------
def _parse_datetime(value):
    """
    Parse date and time and return a datetime object.
    """
    value = value.rstrip()
    if not value:
        return None

    if value.find(':') >= 0:
        # Time part present
        if value.find(' ') >= 0:
            # Both date and time part
            date_text, time_text = value.rsplit(' ', 1)
        else:
            # Time only
            date_text = ''
            time_text = value
    else:
        # Date only
        date_text = value
        time_text = '00:00:00'

    date_part = _dp.parse(date_text)
    try:
        time_part = time.strptime(time_text, '%H:%M:%S')

    except ValueError:
        time_part = None

    if (date_part.get_modifier() == Date.MOD_NONE and time_part is not None):
        return datetime.datetime(
            date_part.get_year(),
            date_part.get_month(),
            date_part.get_day(),
            time_part.tm_hour,
            time_part.tm_min,
            time_part.tm_sec)
    else:
        return None

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
# available image types for exiv2
_vtypes = [".bmp", ".dng", ".exv", ".jp2", ".jpeg", ".jpg", ".nef", ".pef",
           ".pgf", ".png", ".psd", ".srw", ".tiff"]

# valid converting types for PIL.Image
# there are more image formats that PIL.Image can convert to,
# but they are not usable in exiv2/ pyexiv2
_validconvert = [_("<-- Image Types -->"), ".bmp", ".jpg", ".png", ".tiff"]

# set up Exif keys for Image Exif metadata keypairs
_DATAMAP = {
    None                           : "MediaTitle",
    "Exif.Image.ImageDescription"  : "Description",
    "Exif.Photo.DateTimeOriginal"  : "Original",
    "Exif.Image.DateTime"          : "Modified",
    "Exif.Photo.DateTimeDigitized" : "Digitized",
    "Exif.Image.Artist"            : "Artist",
    "Exif.Image.Copyright"         : "Copyright",
    "Exif.GPSInfo.GPSLatitudeRef"  : "LatitudeRef",
    "Exif.GPSInfo.GPSLatitude"     : "Latitude",
    "Exif.GPSInfo.GPSLongitudeRef" : "LongitudeRef",
    "Exif.GPSInfo.GPSLongitude"    : "Longitude",
    "Exif.GPSInfo.GPSAltitudeRef"  : "AltitudeRef",
    "Exif.GPSInfo.GPSAltitude"     : "Altitude",
    "Exif.Photo.DateTimeDigitized" : "Digitized"}
#_DATAMAP  = dict( (key, val) for key, val in list(_DATAMAP.items()))
_DATAMAP.update((val, key) for key, val in list(_DATAMAP.items()))

# define tooltips for all data entry fields
_TOOLTIPS = {
    "MediaTitle" : _("Warning:  Changing this entry will update the Media "
                     "object title field in Gramps not Exiv2 metadata."),

    "Description" : _("Provide a short description for this image."),

    "Artist" : _("Enter the Artist/ Author of this image.  The person's name "
                 "or the company who is responsible for the creation of this "
                 "image."),

    "Copyright" : _("Enter the copyright information for this image. \n"),

    "Original" : _("The original date/ time when the image was first created/"
                   " taken as in a photograph.\n"
                   "Example: 1830-01-1 09:30:59"),

    "Modified" : _("This is the date/ time that the image was last changed/ "
                   "modified.\nExample: 2011-05-24 14:30:00"),

    "Latitude" : _("Enter the Latitude GPS coordinates for this image,\n"
                   "Example: -43.722965, -43:43:22, 38° 38′ 03″ N"),

    "Longitude" : _("Enter the Longitude GPS coordinates for this image,\n"
                    "Example: -10.396378, -10:23:46, 105° 6′ 6″ W"),

    "Altitude" : _("This is the measurement of Above or Below Sea Level.  It "
                   "is measured in meters.  Example: 200.558, -200.558")
}
_TOOLTIPS = dict(
    (key, tooltip) for key, tooltip in list(_TOOLTIPS.items()))

# define tooltips for all buttons
# common buttons for all images
_BUTTONTIPS = {
    "Help" : _("Displays the Gramps Wiki Help page for 'Edit Image Exif "
               "Metadata' in your web browser."),

    "Edit" : _("This will open up a new window to allow you to edit/ modify "
               "this image's Exif metadata.\n  It will also allow you to be "
               "able to Save the modified metadata."),

    "Thumbnail" : _("Will produce a Popup window showing a Thumbnail Viewing "
                    "Area"),

    "ImageTypes" : _("Select from a drop- down box the image file type that "
                     "you would like to convert your non- Exiv2 compatible "
                     "media object to."),

    "Convert" : _("If your image is not of an image type that can have "
                  "Exif metadata read/ written to/from, convert it to a type "
                  "that can?"),

    "Delete" : _("WARNING:  This will completely erase all Exif metadata "
                 "from this image!  Are you sure that you want to do this?")
}
# Words needed for translation and creating a template.pot
_CLEAR_GPS = _("Clear GPS")
_THUMBNAIL = _("Thumbnail")
_COPY = _("Copy")
_CONVERT = _("Convert")
_CLEAR = _("Clear")

# ----------------------------------------------------


class EditExifMetadata(Gramplet):
    """
    Edit Image Exif Metadata

    This gramplet/ add-on allows the adding, editting, and manipulating of
    an image's exif metadata.  These metadata items are being used and
    added by most modern cameras today.

    Most modern graphic software is also able to add, edit, and manipulate
    these  items.

    This add- on brings this ability/ functionality to Gramps...

        Special symbols...
            degrees symbol = [Ctrl] [Shift] u \00b0
            minutes symbol =                  \2032
            seconds symbol =                  \2033
    """
    def init(self):
        """
        create variables, and build display
        """
        self.exif_widgets = {}

        self.orig_image, self.plugin_image, self.image_path = [False] * 3

        vbox = self.__build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(vbox)

    def active_changed(self, handle):
        """
        handles when a media object has changed
        """
        self.update()

    def db_changed(self):
        """
        connects the media signals to self.update; which updates the display...
        """
        self.connect(self.dbstate.db, 'media-add', self.update)
        self.connect(self.dbstate.db, 'media-update', self.update)
        self.connect(self.dbstate.db, 'media-delete', self.update)
        self.connect(self.dbstate.db, 'media-rebuild', self.update)

        self.connect_signal('Media', self.update)

    def __build_gui(self):
        """
        will display all exif metadata and all buttons.
        """
        main_vbox = Gtk.VBox(homogeneous=False, spacing=0)
        main_vbox.set_border_width(10)

        # Displays the file name
        medialabel = Gtk.HBox(homogeneous=False, spacing=0)
        label = self.__create_label("MediaLabel", False, False, False)
        medialabel.pack_start(label, expand=False, fill=True, padding=0)
        main_vbox.pack_start(medialabel, expand=False, fill=True, padding=0)

        # Displays mime type information
        mimetype = Gtk.HBox(homogeneous=False, spacing=0)
        label = self.__create_label("MimeType", False, False, False)
        mimetype.pack_start(label, expand=False, fill=True, padding=0)
        main_vbox.pack_start(mimetype, expand=False, fill=True, padding=0)

        # image dimensions
        imagesize = Gtk.HBox(homogeneous=False, spacing=0)
        label = self.__create_label("ImageSize", False, False, False)
        imagesize.pack_start(label, expand=False, fill=False, padding=0)
        main_vbox.pack_start(imagesize, expand=False, fill=True, padding=0)

        # Displays all plugin messages
        messagearea = Gtk.HBox(homogeneous=False, spacing=0)
        label = self.__create_label("MessageArea", False, False, False)
        messagearea.pack_start(label, expand=False, fill=True, padding=0)
        main_vbox.pack_start(messagearea, expand=False, fill=True, padding=0)

        # Separator line before the buttons
        main_vbox.pack_start(Gtk.HSeparator(), expand=False, fill=False,
                             padding=0)

        # Thumbnail, ImageType, and Convert buttons
        new_hbox = Gtk.HBox(homogeneous=False, spacing=0)
        main_vbox.pack_start(new_hbox, expand=False, fill=False, padding=0)
        new_hbox.show()

        # Thumbnail button
        event_box = Gtk.EventBox()
        new_hbox.pack_start(event_box, expand=False, fill=False, padding=0)
        event_box.show()

        button = self.__create_button("Thumbnail", [self.thumbnail_view], )
        event_box.add(button)

        # Image Types
        event_box = Gtk.EventBox()
        new_hbox.pack_start(event_box, expand=False, fill=False, padding=0)
        event_box.show()

        combo_box = Gtk.ComboBoxText()
        combo_box.append_text(_validconvert[0])
        combo_box.set_active(0)
        combo_box.set_sensitive(False)
        event_box.add(combo_box)
        self.exif_widgets["ImageTypes"] = combo_box
        combo_box.show()

        # Convert button
        event_box = Gtk.EventBox()
        new_hbox.pack_start(event_box, expand=False, fill=False, padding=0)
        event_box.show()

        button = self.__create_button("Convert", [self.__convert_dialog], )
        event_box.add(button)

        # Connect the changed signal to ImageType
        self.exif_widgets["ImageTypes"].connect("changed", self.changed_cb)

        # Help, Edit, and Delete buttons
        new_hbox = Gtk.HBox(homogeneous=False, spacing=0)
        main_vbox.pack_start(new_hbox, expand=False, fill=False, padding=0)
        new_hbox.show()

        for (widget, callback, is_sensitive) in [
                ("Help",   [self.__help_page],  True),
                ("Edit",   [self.display_edit], False),
                ("Clear GPS", [self.clear_gps], False),
                ("Delete", [self._wipe_dialog], False)]:

            event_box = Gtk.EventBox()
            new_hbox.pack_start(event_box, expand=False, fill=False, padding=0)
            event_box.show()

            button = self.__create_button(widget, callback, is_sensitive)
            event_box.add(button)

        # add viewing model
        self.view = MetadataView()
        main_vbox.pack_start(self.view, expand=False, fill=True, padding=5)

        # Separator line before the Total
        main_vbox.pack_start(Gtk.HSeparator(), expand=False, fill=True,
                             padding=5)

        # number of key/ value pairs shown
        label = self.__create_label("Total", False, False, False)
        main_vbox.pack_start(label, expand=False, fill=True, padding=5)

        main_vbox.show_all()
        return main_vbox

    def main(self):  # return false finishes
        """
        get the active media, mime type, and reads the image metadata

        *** disable all buttons at first, then activate as needed
            # Help will never be disabled
        """
        db = self.dbstate.db

        # deactivate all buttons except Help
        self.deactivate_buttons(["Convert", "Edit", "ImageTypes", "Delete",
                                 "Clear GPS"])
        imgtype_format = []

        # display all button tooltips only
        # 1st argument is for Fields, 2nd argument is for Buttons
        self._setup_widget_tips(fields=False, buttons=True)

        # clears all labels and display area
        for widget in ["MediaLabel", "MimeType", "ImageSize", "MessageArea",
                       "Total"]:
            self.exif_widgets[widget].set_text("")

        active_handle = self.get_active("Media")
        if not active_handle:
            self.set_has_data(False)
            # set Message Ares to Select
            self.exif_widgets["MessageArea"].set_text(_(
                "Select an image to begin..."))
            return

        # get image from database
        self.orig_image = db.get_media_from_handle(active_handle)
        if not self.orig_image:
            self.set_has_data(False)
            return

        # get file path and attempt to find it?
        self.image_path = media_path_full(db, self.orig_image.get_path())
        if not os.path.isfile(self.image_path):
            self.set_has_data(False)
            return

        # check image read privileges
        _readable = os.access(self.image_path, os.R_OK)
        if not _readable:
            self.exif_widgets["MessageArea"].set_text(_(
                "Image is NOT readable,\nPlease choose a different image..."))
            return

        # display file description/ title
        self.exif_widgets["MediaLabel"].set_text(_html_escape(
            self.orig_image.get_description()))

        # Mime type information
        mime_type = self.orig_image.get_mime_type()
        self.exif_widgets["MimeType"].set_text(get_description(mime_type))

        # get dirpath/ basename, and extension
        self.basename, self.extension = os.path.splitext(self.image_path)

        if (mime_type and mime_type.startswith("image/")):

            if self.extension.lower() not in _vtypes:

                # Convert message
                self.exif_widgets["MessageArea"].set_text(_(
                    "Please convert this "
                    "image to an Exiv2- compatible image type..."))

                imgtype_format = _validconvert

                self.exif_widgets["ImageTypes"].remove_all()
                for index in range(1, len(imgtype_format)):
                    self.exif_widgets["ImageTypes"].append_text(
                        imgtype_format[index])
                self.exif_widgets["ImageTypes"].set_active(0)

                self.activate_buttons(["ImageTypes"])
            else:
                # creates, and reads the plugin image instance
                self.plugin_image = self.setup_image(self.image_path)

                # activate Edit button
                self.activate_buttons(["Edit"])

                # get image width and height
                self.exif_widgets["ImageSize"].show()
                width = self.plugin_image.get_pixel_width()
                height = self.plugin_image.get_pixel_height()
                self.exif_widgets["ImageSize"].set_text(_(
                    "Image Size : {width} x {height} pixels").format(
                    width=width, height=height))

                # check for thumbnails
                has_thumb = self.__check4thumbnails()
                if has_thumb:
                    self.activate_buttons(["Thumbnail"])

        # display all Exif tags for this image,
        # XmpTag and IptcTag has been purposefully excluded
        self.__display_exif_tags()

        # check image write privileges
        _writable = os.access(self.image_path, os.W_OK)
        if not _writable:
            self.exif_widgets["MessageArea"].set_text(_(
                "Image is NOT writable,\n"
                "You will NOT be able to save Exif metadata...."))
            self.deactivate_buttons(["Edit", "Delete", "Clear GPS"])

    def __check4thumbnails(self):
        """
        check for thumbnails and activate Thumbnail button if found?
        """
        previews = self.plugin_image.get_preview_properties()
        return bool(previews)

    def __display_exif_tags(self, *_object):
        """
        Display the exif tags.
        """
#         self.exif_widgets["MessageArea"].set_text(
#             _("Displaying Exif metadata..."))

        # display exif tags in the treeview
        has_data = self.view.display_exif_tags(self.image_path)

        # update set_has_data functionality
        self.set_has_data(has_data)

        if has_data:
            self.activate_buttons(["Delete", "Clear GPS"])

    def changed_cb(self, ext_value=None):
        """
        will show the Convert Button once an Image Type has been selected, and
        if image extension is not an Exiv2- compatible image?
        """
        # get convert image type and check it from ImageTypes drop- down
        ext_value = self.exif_widgets["ImageTypes"].get_active()
        if ext_value >= 1:

            # if Convert button is not active, set it to active?
            # so that the user may convert this image?
            if not self.exif_widgets["Convert"].get_sensitive():
                self.activate_buttons(["Convert"])

    def _setup_widget_tips(self, fields=None, buttons=None):
        """
        set up widget tooltips
            * data fields
            * buttons
        """
        # if True, setup tooltips for all Data Entry Fields
        if fields:
            for widget, tooltip in list(_TOOLTIPS.items()):
                self.exif_widgets[widget].set_tooltip_text(tooltip)

        # if True, setup tooltips for all Buttons
        if buttons:
            for widget, tooltip in list(_BUTTONTIPS.items()):
                self.exif_widgets[widget].set_tooltip_text(tooltip)

    def setup_image(self, full_path):
        """
        This will:
            * create the plugin image instance if needed,
            * setup the tooltips for the data fields,
            * setup the tooltips for the buttons,
        """
        metadata = GExiv2.Metadata(full_path)

        return metadata

    def update_has_data(self):
        """
        updates the has_data functionality to show on the sidebar/ bottombar
            highlighted tab if there is any data to show...
        """
        active_handle = self.get_active('Media')
        if active_handle:
            active = self.dbstate.db.get_media_from_handle(active_handle)
            self.set_has_data(self.get_has_data(active))
        else:
            self.set_has_data(False)

    def get_has_data(self, media):
        """
        Return True if the gramplet has data, else return False.
        """
        if media is None:
            return False

        full_path = media_path_full(self.dbstate.db, media.get_path())
        return self.view.get_has_data(full_path)

    def __create_button(self, text, callback=[], sensitive=False):
        """
        creates and returns a button for display
        """
        button = Gtk.Button(label=_(text))

        if callback is not []:
            for call_ in callback:
                button.connect("clicked", call_)

        # attach a addon widget to the button for later manipulation
        self.exif_widgets[text] = button

        if not sensitive:
            button.set_sensitive(False)

        button.show()
        return button

    def __create_label(self, widget, text, width, height, wrap=True):
        """
        creates a label for this addon.
        """
        label = Gtk.Label()

        if text:
            label.set_text(text)

        if wrap:
            label.set_line_wrap(True)

        if (width and height):
            label.set_size_request(width, height)

        if widget:
            self.exif_widgets[widget] = label

        label.show()
        return label

    def __create_event_entry(self, pos, width, height, length_, type_,
                             cb_list):
        """
        handles the creation of an event_box and entry containers and returns
        them...
        """
        evt_box = Gtk.EventBox()

        if (width and height):
            evt_box.set_size_request(width, height)
        self.exif_widgets[pos + "Box"] = evt_box
        evt_box.show()

        if type_ == "Validate":
            entry = ValidatableMaskedEntry()

            if cb_list:
                for call_ in cb_list:
                    entry.connect('validate', call_, pos)

        elif type_ == "Entry":
            entry = Gtk.Entry(max_length=length_)

            if cb_list:
                for call_ in cb_list:
                    entry.connect('validate', call_)

        evt_box.add(entry)
        self.exif_widgets[pos] = entry

        entry.show()
        return evt_box

    def thumbnail_view(self, _object):
        """
        will allow a display area for a thumbnail pop-up window.
        """
        tip = _("Click Close to close this Thumbnail View Area.")

        parent = self.gui.get_container_widget().get_toplevel()
        self.tbarea = Gtk.Window(type=Gtk.WindowType.TOPLEVEL,
                                 transient_for=parent)
        self.tbarea.tooltip = tip
        self.tbarea.set_title(_("Thumbnail View Area"))

        pbloader, width, height = self.__get_thumbnail_data()
        if pbloader:
            self.tbarea.set_default_size((width + 40), (height + 40))

            self.tbarea.set_border_width(10)
            self.tbarea.connect('destroy', lambda w: self.tbarea.destroy())

            new_vbox = self.build_thumbnail_gui(pbloader, width, height)
            self.tbarea.add(new_vbox)
            self.tbarea.show()
        else:
            self.deactivate_buttons(["Thumbnail"])
            lambda w: self.tbarea.destroy()

    def __get_thumbnail_data(self):
        """
        returns the thumbnail width and height from the active media object if
        there is any?
        """
        pbloader, width, height = [False] * 3

        previews = self.plugin_image.get_preview_properties()
        if not previews:
            return pbloader, width, height

        # Get the largest preview available
        preview = previews[-1]
        width = preview.get_width()
        height = preview.get_height()

        # Create a GTK pixbuf loader to read the thumbnail data
        pv_img = self.plugin_image.get_preview_image(preview)
        pbloader = GdkPixbuf.PixbufLoader()
        pbloader.write(pv_img.get_data())

        return pbloader, width, height

    def build_thumbnail_gui(self, pbloader, width, height):
        """
        builds the thumbnail viewing area.
        """
        main_vbox = Gtk.VBox()
        main_vbox.set_size_request((width - 30), (height - 30))

        hbox = Gtk.HBox(homogeneous=False, spacing=0)
        main_vbox.pack_start(hbox, expand=False, fill=False, padding=5)
        hbox.show()

        # Get the resulting pixbuf and build an image to be displayed
        pixbuf = pbloader.get_pixbuf()
        pbloader.close()

        imgwidget = Gtk.Image()
        imgwidget.set_from_pixbuf(pixbuf)
        hbox.pack_start(imgwidget, expand=False, fill=True, padding=0)
        imgwidget.show()

        main_vbox.show_all()
        return main_vbox

    def __convert_dialog(self, _object):
        """
        Handles the Convert question Dialog
        """
        # Convert and delete original file or just convert
        parent = self.gui.get_container_widget().get_toplevel()
        res = QuestionDialog3(
            _("Edit Image Exif Metadata"),
            _("WARNING: You are about to convert this image into a "
              ".jpeg image.  Are you sure that you want to do this?"),
            _("Convert and Delete"), _("Convert"),
            parent=parent).run()
        if res == -1:
            return
        if res:
            self.__convert_delete()
        else:
            self.__convert_only()
        self.update()
        return

    def __convert_copy(self, full_path=None):
        """
        Will attempt to convert an image to jpeg if it is not?
        """
        if full_path is None:
            full_path = self.image_path

        # get image filepath and its filename
        filepath, basename = os.path.split(self.basename)

        # get extension selected for converting this image
        ext_type = self.exif_widgets["ImageTypes"].get_active()
        if ext_type == 0:
            return False

        basename += _validconvert[ext_type + 1]

        # new file name and dirpath
        dest_file = os.path.join(filepath, basename)

        # open source image file
        im = Image.open(full_path)
        im.save(dest_file)

        # pyexiv2 source image file
        src_meta = GExiv2.Metadata(full_path)

        # check to see if source image file has any Exif metadata?
        if _get_exif_keypairs(src_meta):

            # Identify the destination image file
            dest_meta = GExiv2.Metadata(dest_file)

            # copy source metadata to destination file
            for tag in src_meta.get_exif_tags():
                dest_meta[tag] = src_meta[tag]
                print(dest_meta[tag])

            # writes all Exif Metadata to image even if the fields are all
            # empty so as to remove the value
            dest_meta.save_file(dest_file)
        return dest_file

    def __convert_delete(self, full_path=None):
        """
        will convert an image file and delete original non-jpeg image.
        """
        if full_path is None:
            full_path = self.image_path

        # Convert image and copy over it's Exif metadata (if any?)
        newfilepath = self.__convert_copy(full_path)
        if newfilepath:

            # delete original file from this computer and set new filepath
            try:
                os.remove(full_path)
                delete_results = True
            except (IOError, OSError):
                delete_results = False
            if delete_results:

                # check for new destination and if source image file is
                # removed?
                if(os.path.isfile(newfilepath) and not
                   os.path.isfile(full_path)):
                    self.__update_media_path(newfilepath)

                    # notify user about the convert, delete, and new filepath
                    self.exif_widgets["MessageArea"].set_text(_(
                        "Your image has been converted and the original file "
                        "has been deleted, and "
                        "the full path has been updated!"))
                else:
                    self.exif_widgets["MessageArea"].set_text(_(
                        "There has been an error, Please check your source and"
                        " destination file paths..."))
        else:
            self.exif_widgets["MessageArea"].set_text(_(
                "There was an error in deleting the original file.  "
                "You will need to delete it yourself!"))

    def __convert_only(self, full_path=None):
        """
        This will only convert the file and update the media object path.
        """
        if full_path is None:
            full_path = self.image_path

        # the convert was sucessful, then update media path?
        newfilepath = self.__convert_copy(full_path)
        if newfilepath:

            # update the media object path
            self.__update_media_path(newfilepath)
        else:
            self.exif_widgets["MessageArea"].set_text(_(
                "There was an error in converting your image file."))

    def __update_media_path(self, newfilepath=None):
        """
        update the media object's media path.
        """
        if newfilepath:
            db = self.dbstate.db

            # begin database tranaction to save media object new path
            with DbTxn(_("Media Path Update"), db) as trans:
                self.orig_image.set_path(newfilepath)
                mtype = get_type(newfilepath)
                self.orig_image.set_mime_type(mtype)

                db.commit_media(self.orig_image, trans)
                #db.request_rebuild()
        else:
            self.exif_widgets["MessageArea"].set_text(_(
                "There has been an error in updating the image file's path!"))

    def __help_page(self, addonwiki=None):
        """
        will bring up a Wiki help page.
        """
        addonwiki = 'Edit Image Exif Metadata'
        display_help(webpage=addonwiki)

    def activate_buttons(self, buttonlist):
        """
        Enable/ activate the buttons that are in buttonlist
        """
        for widget in buttonlist:
            self.exif_widgets[widget].set_sensitive(True)

    def deactivate_buttons(self, buttonlist):
        """
        disable/ de-activate buttons in buttonlist

        *** if All, then disable ALL buttons in the current display
        """
        if buttonlist == ["All"]:
            buttonlist = [(buttonname) for buttonname in
                          list(_BUTTONTIPS.keys()) if buttonname is not "Help"]

        for widget in buttonlist:
            self.exif_widgets[widget].set_sensitive(False)

    def display_edit(self, _object):
        """
        creates the editing area fields.
        """
        tip = _("Click the close button when you are finished modifying this "
                "image's Exif metadata.")

        # on a screen of 1024 x 768, width = 614, height will always remain at
        # 600 for netbooks with a screen height of 600 maximum...
        width_ = 550

        parent = self.gui.get_container_widget().get_toplevel()
        edtarea = Gtk.Window(
            window_position=Gtk.WindowPosition.CENTER_ON_PARENT,
            transient_for=parent, modal=True)
        edtarea.tooltip = tip
        edtarea.set_title(self.orig_image.get_description())
        edtarea.set_size_request((width_ + 45), 540)
        #edtarea.set_border_width(10)
        width_ -= 10  # width = 604
        edtarea.connect("destroy", lambda w: edtarea.destroy())

        # create a new scrolled window.
        scrollwindow = Gtk.ScrolledWindow()
        width_ -= 10  # width = 594

        # will show scrollbars only when necessary
        scrollwindow.set_policy(Gtk.PolicyType.AUTOMATIC,
                                Gtk.PolicyType.AUTOMATIC)
        edtarea.add(scrollwindow)
        scrollwindow.show()

        vbox = self.__build_edit_gui(width_, edtarea)
        scrollwindow.add(vbox)
        vbox.show_all()
        edtarea.show()

        # display all fields and button tooltips...
        # need to add Save, Clear, and Close over here...
        _BUTTONTIPS.update((key, tip) for key, tip in list({

            # Add the Save button...
            "Save" : _("Saves a copy of the data fields into the image's "
                       "Exif metadata."),

            # Re- display the data fields button...
            "Copy" : _("Re -display the data fields that were cleared from "
                       "the Edit Area."),

            # Add the Clear button...
            "Clear" : _("This button will clear all of the data fields shown "
                        "here."),

            # Add the Clear GPS button...
            "Clear GPS" : _("This button will clear all of the GPS fields "
                            "shown here."),

            # Add the Close button...
            "Close" : _("Closes this popup Edit window.\n"
                        "WARNING: This action will NOT Save any changes/ "
                        "modification made to this "
                        "image's Exif metadata.")}.items()))

        # True, True - all data fields and button tooltips will be displayed...
        self._setup_widget_tips(fields=True, buttons=True)

        # display all data fields and their values...
        self.edit_area()

    def __build_edit_gui(self, width_, edtarea):
        """
        creates the content for the edit window...
        """
        main_vbox = Gtk.VBox()
        main_vbox.set_border_width(10)
        width_ -= 10  # width = 584

        # 520 is the normal height of this vertical box...
        #main_vbox.set_size_request(width_, 500)

        # Notification Area for the Edit Area window...
        label = self.__create_label("EditMessage", False, width=(width_ - 62),
                                    height=25)
        main_vbox.pack_start(label, expand=False, fill=True, padding=0)

        # Media Title Frame...
        width_ -= 10  # 574 on a screen width of 1024
        title_frame = Gtk.Frame(label=_("Media Object Title"))
        title_frame.set_size_request(width_, 60)  # width = 574
        main_vbox.pack_start(title_frame, expand=False, fill=True, padding=10)
        title_frame.show()

        new_vbox = Gtk.VBox(homogeneous=False, spacing=0)
        title_frame.add(new_vbox)
        new_vbox.show()

        for widget, text in [("MediaTitle", _("media Title: "))]:

            new_hbox = Gtk.HBox(homogeneous=False, spacing=0)
            new_vbox.pack_start(new_hbox, expand=False, fill=False, padding=5)
            new_hbox.show()

            label = self.__create_label(False, text, width=90, height=25)
            new_hbox.pack_start(label, expand=False, fill=False, padding=0)

            event_box = self.__create_event_entry(widget, 464, 30, 100,
                                                  "Entry", [])
            new_hbox.pack_start(event_box, expand=False, fill=False, padding=0)

        # create the data fields...
        # ***Description, Artist, and Copyright
        gen_frame = Gtk.Frame(label=_("General Data"))
        gen_frame.set_size_request(width_, 155)  # width = 574
        main_vbox.pack_start(gen_frame, expand=False, fill=True, padding=10)
        gen_frame.show()

        new_vbox = Gtk.VBox(homogeneous=False, spacing=0)
        gen_frame.add(new_vbox)
        new_vbox.show()

        for widget, text in [
                ("Description", _("Description: ")),
                ("Artist",      _("Artist: ")),
                ("Copyright",   _("Copyright: "))]:

            new_hbox = Gtk.HBox(homogeneous=False, spacing=0)
            new_vbox.pack_start(new_hbox, expand=False, fill=False, padding=5)
            new_hbox.show()

            label = self.__create_label(False, text, width=90, height=25)
            new_hbox.pack_start(label, expand=False, fill=False, padding=0)

            event_box = self.__create_event_entry(widget, 464, 30, 200,
                                                  "Entry", [])
            new_hbox.pack_start(event_box, expand=False, fill=False, padding=0)

        # iso format: Year, Month, Day spinners...
        datetime_frame = Gtk.Frame(label=_("Date/ Time"))
        datetime_frame.set_size_request(width_, 90)  # width = 574
        main_vbox.pack_start(datetime_frame, expand=False, fill=False,
                             padding=10)
        datetime_frame.show()

        new_vbox = Gtk.VBox(homogeneous=False, spacing=0)
        datetime_frame.add(new_vbox)
        new_vbox.show()

        new_hbox = Gtk.HBox(homogeneous=False, spacing=0)
        new_vbox.pack_start(new_hbox, expand=False, fill=False, padding=0)
        new_hbox.show()

        for widget, text in [
                ("Original", _("Original: ")),
                ("Modified", _("Modified: "))]:

            vbox2 = Gtk.VBox(homogeneous=False, spacing=0)
            new_hbox.pack_start(vbox2, expand=False, fill=False, padding=5)
            vbox2.show()

            label = self.__create_label(widget, text, width=90, height=25)
            vbox2.pack_start(label, expand=False, fill=False, padding=0)
            label.show()

            # each box width = 157
            event_box = self.__create_event_entry(
                widget, 272, 30, 0, "Validate", [self.validate_datetime])
            vbox2.pack_start(event_box, expand=False, fill=False, padding=0)

            #self.dates[widget] = None

        # GPS coordinates...
        latlong_frame = Gtk.Frame(label=_(
            "Latitude/ Longitude/ Altitude GPS coordinates"))
        latlong_frame.set_size_request(width_, 80)  # width = 574
        main_vbox.pack_start(latlong_frame, expand=False, fill=False,
                             padding=0)
        latlong_frame.show()

        new_vbox = Gtk.VBox(homogeneous=False, spacing=0)
        latlong_frame.add(new_vbox)
        new_vbox.show()

        new_hbox = Gtk.HBox(homogeneous=False, spacing=0)
        new_vbox.pack_start(new_hbox, expand=False, fill=False, padding=0)
        new_hbox.show()

        for widget, text in [
                ("Latitude",  _("Latitude :")),
                ("Longitude", _("Longitude :")),
                ("Altitude",  _("Altitude :"))]:

            vbox2 = Gtk.VBox(homogeneous=False, spacing=0)
            new_hbox.pack_start(vbox2, expand=False, fill=False, padding=5)
            vbox2.show()

            label = self.__create_label(widget, text, width=90, height=25)
            vbox2.pack_start(label, expand=False, fill=False, padding=0)
            label.show()

            event_box = self.__create_event_entry(
                widget, 178, 30, 0, "Validate", [self.validate_coordinate])
            vbox2.pack_start(event_box, expand=False, fill=False, padding=0)

        # Help, Save, Clear, Copy, and Close buttons...
        new_hbox = Gtk.HBox(homogeneous=False, spacing=0)
        main_vbox.pack_start(new_hbox, expand=False, fill=True, padding=5)
        new_hbox.show()

        w_list = [
            ("Help",  [self.__help_page],                True),
            ("Save",  [self.save_metadata, self.update], True),
            ("Clear", [self.clear_metadata],             True),
            ("Copy",  [self.edit_area],                  True),
            ("Close", [lambda w: edtarea.destroy()],     True)]

        for (widget, callback, is_sensitive) in w_list:

            event_box = Gtk.EventBox()
            event_box.set_size_request(112, 30)
            new_hbox.pack_start(event_box, expand=False, fill=True, padding=1)
            event_box.show()

            event_box.add(self.__create_button(widget, callback, is_sensitive))
        return main_vbox

    def validate_datetime(self, widget, data, field):
        """
        Validate current date and time in text entry
        """
        value = _parse_datetime(widget.get_text())
        #if self.dates[field] is None:
        if value is None:
            return ValidationError(_('Bad Date/Time'))

    def validate_coordinate(self, widget, data, field):
        """
        Validate current latitude or longitude in text entry
        """
        # validate the Latitude field...
        if field == "Latitude" and not conv_lat_lon(data, "0", "ISO-D"):
            return ValidationError(_("Invalid latitude (syntax: 18\u00b09'") +
                                   _('48.21"S, -18.2412 or -18:9:48.21)'))

        # validate the Longitude field...
        if field == "Longitude" and not conv_lat_lon("0", data, "ISO-D"):
            return ValidationError(_("Invalid longitude (syntax: 18\u00b09'") +
                                   _('48.21"E, -18.2412 or -18:9:48.21)'))

    def _wipe_dialog(self, _object):
        """
        Handles the Delete Dialog...
        """
        parent = self.gui.get_container_widget().get_toplevel()
        QuestionDialog(_("Edit Image Exif Metadata"),
                       _("WARNING!  You are about to completely "
                         "delete the Exif metadata from this image?"),
                       _("Delete"), self.strip_metadata,
                       parent=parent)
        self.update()

    def clear_gps(self, _object):
        """
        clears all GPS data fields to nothing after dialog
        """
        parent = self.gui.get_container_widget().get_toplevel()
        QuestionDialog(_("Edit Image Exif Metadata"),
                       _("WARNING!  You are about to completely "
                         "delete the GPS metadata from this image?"),
                       _("Delete"), self.strip_gps,
                       parent=parent)
        self.update()

    def strip_gps(self):
        """
        clears all gps data fields to nothing
        """
        self.plugin_image.delete_gps_info()
        self.write_metadata(self.plugin_image, "MessageArea")

    def clear_metadata(self, _object):
        """
        clears all data fields to nothing
        """
        for widget in list(_TOOLTIPS.keys()):
            self.exif_widgets[widget].set_text("")

    def edit_area(self, *_object):
        """
        displays the image Exif metadata in the Edit Area...
        """
        mediadatatags = _get_exif_keypairs(self.plugin_image)
        if mediadatatags:
            mediadatatags = [key for key in mediadatatags if key in _DATAMAP]

            for key in mediadatatags:
                widget = _DATAMAP[key]
                tag_value = _get_value(self.plugin_image, key)

                if widget in ["Description", "Artist", "Copyright"]:
                    if tag_value:
                        self.exif_widgets[widget].set_text(tag_value)

                # Original Date...
                elif widget == "Original":
                    use_date = format_datetime(tag_value)
                    if use_date:
                        self.exif_widgets[widget].set_text(use_date)

                # Last Modified date
                elif widget == "Modified":
                    use_date = format_datetime(tag_value)
                    if use_date:
                        self.exif_widgets["Modified"].set_text(use_date)

                        # set Modified Datetime to non-editable...
                        self.exif_widgets[widget].set_editable(False)

                # LatitudeRef, Latitude, LongitudeRef, Longitude...
                elif widget == "Latitude":

                    latitude = tag_value
                    longitude = _get_value(self.plugin_image,
                                           "Exif.GPSInfo.GPSLongitude")

                    # if latitude and longitude exist, display them?
                    if (latitude is not None and longitude is not None):

                        # split latitude into (degrees, minutes, and seconds)
                        latdeg, latmin, latsec = rational_to_dms(latitude)

                        # split longitude into degrees, minutes, and seconds
                        longdeg, longmin, longsec = rational_to_dms(longitude)

                        # check to see if we have valid GPS coordinates?
                        latfail = any(coords is None for coords in
                                      [latdeg, latmin, latsec])
                        longfail = any(coords is None for coords in
                                       [longdeg, longmin, longsec])
                        if (not latfail and not longfail):

                            # Latitude Direction Reference
                            latref = _get_value(
                                self.plugin_image,
                                "Exif.GPSInfo.GPSLatitudeRef")

                            # Longitude Direction Reference
                            longref = _get_value(
                                self.plugin_image,
                                "Exif.GPSInfo.GPSLongitudeRef")

                            # set display for Latitude GPS coordinates
                            latitude = """%s° %s′ %s″ %s""" % (
                                latdeg, latmin, latsec, latref)
                            self.exif_widgets["Latitude"].set_text(latitude)

                            # set display for Longitude GPS coordinates
                            longitude = """%s° %s′ %s″ %s""" % (
                                longdeg, longmin, longsec, longref)
                            self.exif_widgets["Longitude"].set_text(longitude)

                            self.exif_widgets["Latitude"].validate()
                            self.exif_widgets["Longitude"].validate()

                elif widget == "Altitude":
                    altitude = tag_value
                    altref = self.plugin_image.get_tag_string(
                        "Exif.GPSInfo.GPSAltitudeRef")

                    if altitude:
                        altitude = str(convert_value(altitude))
                        if altitude:
                            if altref == "1":
                                altitude = "-" + altitude
                            self.exif_widgets[widget].set_text(altitude)

        # no Exif metadata, but there is a media object date available
        else:
            media_date = self.orig_image.get_date_object()
            if media_date:
                self.exif_widgets["Original"].set_text(_dd.display(media_date))

        # Media Object Title...
        self.media_title = self.orig_image.get_description()
        self.exif_widgets["MediaTitle"].set_text(self.media_title)

    def convert_format(self, latitude, longitude, format_):
        """
        Convert GPS coordinates into a specified format.
        """
        if (not latitude and not longitude):
            return [False] * 2

        latitude, longitude = conv_lat_lon(latitude, longitude, format_)
        return latitude, longitude

    def convert2dms(self, latitude=None, longitude=None):
        """
        will convert a decimal GPS coordinates into degrees, minutes, seconds
        for display only
        """
        if (not latitude or not longitude):
            return [False] * 2

        latitude, longitude = self.convert_format(latitude, longitude, "DEG-:")

        return latitude, longitude

    def save_metadata(self, _object):
        """
        gets the information from the plugin data fields
        and sets the key = widgetvaluee image metadata
        """
        # set up default variables...
        db = self.dbstate.db
        valid = True
        latref, longref, altref = [False] * 3

        # get all data field values...
        mediatitle = self.exif_widgets["MediaTitle"].get_text()
        description = self.exif_widgets["Description"].get_text()
        artist = self.exif_widgets["Artist"].get_text()
        copyright_ = self.exif_widgets["Copyright"].get_text()

        # special variables have been set up for the dates...
        original = self.exif_widgets["Original"].get_text()
#         if original:
#             self.set_datetime(self.exif_widgets["Original"], "Original")

        # update dynamically set Modified date...
        modified = datetime.datetime.now().strftime('%Y:%m:%d %H:%M:%S')

        latitude = self.exif_widgets["Latitude"].get_text()
        longitude = self.exif_widgets["Longitude"].get_text()
        altitude = self.exif_widgets["Altitude"].get_text()

        widgets = ["MediaTitle", "Description", "Artist", "Copyright",
                   "Original", "Modified", "Latitude", "Longitude", "Altitude"]
        values = [mediatitle, description, artist, copyright_, original,
                  modified, latitude, longitude, altitude]

        namevalues = list(zip(widgets, values))
        namevalues = [(w, v) for w, v in namevalues if v]
        if namevalues:
            for widgetname, widgetvalue in namevalues:
                key = _DATAMAP[widgetname]

                # Media Object's Title...
                # this will only affect the Media object wthin the database...
                if widgetname == "MediaTitle":
                    if(self.media_title and
                       self.media_title is not mediatitle):
                        with DbTxn(_("Media Title Update"), db) as trans:
                            self.orig_image.set_description(mediatitle)

                            db.commit_media(self.orig_image, trans)
                            #db.request_rebuild()

                # original date of image...
                elif widgetname == "Original":
                    if original:
                        media_date = self.orig_image.get_date_object()
                        if media_date.is_empty():
                            media_date = Date()

                        original = _parse_datetime(original)
                        if original:
                            try:

                                media_date.set_yr_mon_day(original.year,
                                                          original.month,
                                                          original.day)
                            except ValueError:
                                media_date = None

                            if media_date:
                                with DbTxn(_("Media Object Date Created"),
                                           db) as trans:
                                    self.orig_image.set_date_object(media_date)

                                    db.commit_media(self.orig_image, trans)
                                    # db.request_rebuild()
                            # put original back into exif valid string
                            original = original.strftime('%Y:%m:%d %H:%M:%S')

                # Latitude Ref, Latitude, Longitude Ref, and Longitude...
                # if equal to None, then convert failed?
                elif widgetname == "Latitude":
                    latitude = self.exif_widgets["Latitude"].get_text()
                    longitude = self.exif_widgets["Longitude"].get_text()
                    if (latitude and longitude):

                        latitude, longitude = self.convert2dms(latitude,
                                                               longitude)
                        if (latitude and longitude):

                            latref = 'N'
                            if "-" in latitude:
                                latref = "S"
                                latitude = latitude.replace("-", "")

                            longref = 'E'
                            if "-" in longitude:
                                longref = "W"
                                longitude = longitude.replace("-", "")

                            # convert Latitude/ Longitude into Rational()...
                            latitude = coords_to_rational(latitude)
                            longitude = coords_to_rational(longitude)

                # Altitude Reference, and Altitude...
                elif widgetname == "Altitude":
                    altref = '0'
                    if "-" in widgetvalue:
                        widgetvalue = widgetvalue.replace("-", "")
                        altref = "1"

                    # convert altitude to pyexiv2.Rational for saving...
                    altitude = altitude2rational(widgetvalue)

            # get all values for fields to be saved...
            # except for MediaTitle which is handled above...
            widgets = ["Description", "Artist", "Copyright", "Original",
                       "Modified", "Latitude", "Longitude", "Altitude",
                       "LatitudeRef", "LongitudeRef", "AltitudeRef"]
            values = [description, artist, copyright_, original, modified,
                      latitude, longitude, altitude, latref, longref, altref]

            namevalues = list(zip(widgets, values))
            namevalues = [(w, v) for w, v in namevalues if v]
            if namevalues:
                for widgetname, widgetvalue in namevalues:
                    key = _DATAMAP[widgetname]
                    valid &= _set_value(self.plugin_image, key, widgetvalue)

        if valid:
            # Update dynamically created Modified date...
            self.exif_widgets["Modified"].set_text(format_datetime(modified))

            # set Edit Message to Saved...
            self.exif_widgets["EditMessage"].set_text(
                _("Saving Exif metadata to this image..."))

            # writes/ saves only the fields that have values...
            self.write_metadata(self.plugin_image, "EditMessage")

            # update the display...
            self.update()

    def write_metadata(self, plugininstance, msg_area):
        """
        writes the Exif metadata to the image.

        """
        try:
            plugininstance.save_file(self.image_path)
            return True
        except:
            self.exif_widgets[msg_area].set_text(_(
                "Image is NOT writable,\n"
                "You will NOT be able to save Exif metadata...."))
            return False

    def strip_metadata(self, mediadatatags=None):
        """
        Will completely and irrevocably erase Exif metadata from this image.
        """
        # make sure the image has Exif metadata...
        mediadatatags = _get_exif_keypairs(self.plugin_image)
        if mediadatatags:

            for key in mediadatatags:
                del self.plugin_image[key]
            erase_results = True

            if erase_results and self.write_metadata(self.plugin_image,
                                                     "MessageArea"):
                # write wiped metadata to image...

                for widget in ["MediaLabel", "MimeType", "ImageSize",
                               "MessageArea", "Total"]:
                    self.exif_widgets[widget].set_text("")

                self.exif_widgets["MessageArea"].set_text(_(
                    "All Exif metadata has been deleted from this image..."))
                self.update()

            else:
                self.exif_widgets["MessageArea"].set_text(_(
                    "There was an error "
                    "in stripping the Exif metadata from this image..."))


def string_to_rational(coordinate):
    """
    convert string to rational variable for GPS
    """
    if '.' in coordinate:
        value1, value2 = coordinate.split('.')
        return value1 + value2 + '/' + str(10**len(value2))
    else:
        return coordinate + '/1'


def coords_to_rational(coordinates):
    """
    returns the rational equivalent for (degrees, minutes, seconds)...
    """
    return ' '.join([string_to_rational(coordinate) for coordinate in
                     coordinates.split(":")])


def altitude2rational(meters_):
    """
    convert Altitude to pyexiv2.Rational
    """
    return string_to_rational(meters_)


def convert_value(value):
    """
    will take a value from the coordinates and return its value
    """
    if '/' in value:
        value = value.split('/')
        return (Decimal(value[0]) / Decimal(value[1]))
    return Decimal(value)


def rational_to_dms(coordinates):
    """
    takes a rational set of coordinates and returns (degrees, minutes, seconds)

    [Fraction(40, 1), Fraction(0, 1), Fraction(1079, 20)]
    """
    # coordinates look like:
    #     [Rational(38, 1), Rational(38, 1), Rational(150, 50)]
    # or [Fraction(38, 1), Fraction(38, 1), Fraction(318, 100)]
    coordinates = coordinates.split(' ')
    deg = convert_value(coordinates[0])
    min_ = convert_value(coordinates[1])
    if min_ % 1:
        sec = (min_ % 1) * 60
    else:
        sec = convert_value(coordinates[2])
    return [str(deg), str(int(min_)), str(sec)]


def _get_exif_keypairs(plugin_image):
    """
    Will be used to retrieve and update the Exif metadata from the image.
    """
    if plugin_image:
        return plugin_image.get_exif_tags()
    else:
        return False


#------------------------------------------------
#      Exiv2 support functions
#          * gets from and sets to the image...
#          * it will still need to be saved...
#------------------------------------------------
def _get_value(plugininstance, exif2_key):
    """
    gets the value from the Exif Key, and returns it...

    @param: exif2_key -- image metadata key
    """
    return plugininstance.get_tag_string(exif2_key)


def _set_value(plugininstance, key, widget_value):
    """
    sets the value for the metadata keys
    """
    try:
        plugininstance[key] = widget_value
        return True
    except:
        return False
