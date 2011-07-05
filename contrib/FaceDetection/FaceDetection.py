# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2011 Nick Hall
#           (c) 2011 Doug Blank <doug.blank@gmail.com>
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
#
# $Id: $
#

from gen.plug import Gramplet
from gui.widgets import Photo
import Utils
import gtk
import os
import cv
import Image
import ImageDraw
import StringIO

from TransUtils import get_addon_translator
_ = get_addon_translator(__file__).ugettext

path, filename = os.path.split(__file__)
HAARCASCADE_PATH = os.path.join(path, 'haarcascade_frontalface_alt.xml')

class FaceDetection(Gramplet):
    """
    Interface for detecting and assigning facial areas to a person.
    """
    def init(self):
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(self.gui.WIDGET)

    def build_gui(self):
        """
        Build the GUI interface.
        """
        self.top = gtk.HBox()
        # first column:
        vbox = gtk.VBox()
        self.top.pack_start(vbox, fill=False, expand=False)
        self.photo = Photo()
        vbox.pack_start(self.photo, fill=False, expand=False, padding=5)
        self.detect_button = gtk.Button(_("Detect New Faces"))
        self.detect_button.connect('button-press-event', self.detect)
        vbox.pack_start(self.detect_button, fill=False, expand=False)
        # second column
        vbox = gtk.VBox()
        vbox.pack_start(gtk.Label("Image:"), fill=False, expand=False)
        self.top.pack_start(vbox, fill=False, expand=False)
        # show and return:
        self.top.show_all()
        return self.top

    def db_changed(self):
        self.dbstate.db.connect('media-update', self.update)
        self.connect_signal('Media', self.update)
        self.update()

    def update_has_data(self): 
        active_handle = self.get_active('Media')
        active_media = self.dbstate.db.get_object_from_handle(active_handle)
        self.set_has_data(active_media is not None)

    def main(self):
        active_handle = self.get_active('Media')
        media = self.dbstate.db.get_object_from_handle(active_handle)
        self.top.hide()
        if media:
            self.detect_button.set_sensitive(True)
            self.load_image(media)
            self.set_has_data(True)
        else:
            self.detect_button.set_sensitive(False)
            self.photo.set_image(None)
            self.set_has_data(False)
        self.top.show()

    def load_image(self, media):
        """
        Load the primary image if it exists.
        """
        self.full_path = Utils.media_path_full(self.dbstate.db,
                                               media.get_path())
        self.mime_type = media.get_mime_type()
        self.photo.set_image(self.full_path, self.mime_type)
        # show where image parts are used by people:
        rects = self.find_references()
        self.draw_rectangles([], rects)

    def find_references(self):
        """
        Find backref people
        """
        active_handle = self.get_active('Media')
        rects = []
        for (classname, handle) in \
                self.dbstate.db.find_backlink_handles(active_handle):
            if classname == "Person":
                person = self.dbstate.db.get_person_from_handle(handle)
                if person:
                    media_list = person.get_media_list()
                    for media_ref in media_list:
                        # get the rect for this image:
                        if media_ref.ref != active_handle: continue
                        rect = media_ref.get_rectangle()
                        if rect:
                            x1, y1, x2, y2 = rect
                            # make percentages
                            rects.append((x1/100.0, y1/100.0, 
                                          (x2 - x1)/100.0, (y2 - y1)/100.0))
        return rects

    def detect(self, obj, event):
        # First, reset image, in case of previous detections:
        active_handle = self.get_active('Media')
        media = self.dbstate.db.get_object_from_handle(active_handle)
        self.load_image(media)
        min_face_size = (50,50) # FIXME: get from setting
        self.cv_image = cv.LoadImage(self.full_path, cv.CV_LOAD_IMAGE_GRAYSCALE)
        o_width, o_height = self.cv_image.width, self.cv_image.height
        cv.EqualizeHist(self.cv_image, self.cv_image)
        cascade = cv.Load(HAARCASCADE_PATH)
        faces = cv.HaarDetectObjects(self.cv_image, cascade, 
                                     cv.CreateMemStorage(0),
                                     1.2, 2, cv.CV_HAAR_DO_CANNY_PRUNING, 
                                     min_face_size)
        references = self.find_references()
        rects = []
        o_width, o_height = [float(t) for t in (self.cv_image.width, self.cv_image.height)]
        for ((x, y, width, height), neighbors) in faces:
            # percentages:
            rects.append((x/o_width, y/o_height, width/o_width, height/o_height))
        self.draw_rectangles(rects, references)

    def draw_rectangles(self, faces, references):
        # reset image:
        self.photo.set_image(self.full_path, self.mime_type)
        # draw on it
        pixbuf = self.photo.photo.get_pixbuf()
        pixmap, mask = pixbuf.render_pixmap_and_mask()
        cm = pixmap.get_colormap()
        # the thumbnail's actual size:
        t_width, t_height = [float(t) for t in self.photo.photo.size_request()]
        # percents:
        for (x, y, width, height) in references:
            self.draw_rectangle(cm, pixmap, t_width, t_height,
                                x, y, width, height, "blue")
        for (x, y, width, height) in faces:
            self.draw_rectangle(cm, pixmap, t_width, t_height,
                                x, y, width, height, "red")
        self.photo.photo.set_from_pixmap(pixmap, mask)

    def draw_rectangle(self, cm, pixmap, t_width, t_height, 
                       x, y, width, height, color):
        cmcolor = cm.alloc_color("white")
        gc = pixmap.new_gc(foreground=cmcolor)
        pixmap.draw_rectangle(gc, False, # fill it?
                              int(x * t_width) + 1, 
                              int(y * t_height) + 1, 
                              int(width * t_width), 
                              int(height * t_height))
        cmcolor = cm.alloc_color(color)
        gc = pixmap.new_gc(foreground=cmcolor)
        pixmap.draw_rectangle(gc, False, # fill it?
                              int(x * t_width), 
                              int(y * t_height), 
                              int(width * t_width), 
                              int(height * t_height))
