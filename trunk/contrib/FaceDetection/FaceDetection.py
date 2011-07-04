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
# $Id: MediaPreview.py 17399 2011-05-03 21:32:32Z nick-h $
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
        self.top = gtk.VBox()
        self.photo = Photo()
        self.top.pack_start(self.photo, fill=True, expand=False, padding=5)
        button = gtk.Button(_("Detect Faces"))
        button.connect('button-press-event', self.detect)
        #self.photo.photo.connect("expose-event", self.expose)
        self.top.pack_start(button, fill=True, expand=False)
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
            self.load_image(media)
            self.set_has_data(True)
        else:
            self.photo.set_image(None)
            self.set_has_data(False)
        self.top.show()

    def load_image(self, media):
        """
        Load the primary image if it exists.
        """
        self.full_path = Utils.media_path_full(self.dbstate.db,
                                               media.get_path())
        mime_type = media.get_mime_type()
        self.photo.set_image(self.full_path, mime_type)

    def detect(self, obj, event):
        filename = self.full_path
        if not filename:
            return
        # First, reset image, in case of previous detections:
        active_handle = self.get_active('Media')
        media = self.dbstate.db.get_object_from_handle(active_handle)
        self.load_image(media)
        min_face_size = (50,50) # FIXME: get from setting
        print "Loading..."
        self.cv_image = cv.LoadImage(filename, cv.CV_LOAD_IMAGE_GRAYSCALE)
        print "Equalizing..."
        cv.EqualizeHist(self.cv_image, self.cv_image)
        cascade = cv.Load(HAARCASCADE_PATH)
        print "Detecting faces..."
        faces = cv.HaarDetectObjects(self.cv_image, cascade, cv.CreateMemStorage(0),
                                     1.2, 2, cv.CV_HAAR_DO_CANNY_PRUNING, min_face_size)
        if faces:
            rects = []
            for ((x, y, width, height), neighbors) in faces:
                print '   face detected:', (x, y), (x + width, y + height)
                #self.draw_rectangle(x, y, width, height)
                rects.append( (x, y, width, height) )
            self.draw_rectangles(rects)
        else:
            print '   no face detected'

    def expose(self, area, event):
        print "expose!"
        gc = area.window.new_gc()
        gdk_color = gc.get_colormap().alloc_color("Green")
        gc.set_foreground(gdk_color)
        area.window.draw_rectangle(gc, True, 0, 0, 80, 70)
        return False

    def draw_rectangles(self, rects):
        pixbuf = self.photo.photo.get_pixbuf()
        pixmap, mask = pixbuf.render_pixmap_and_mask()
        cm = pixmap.get_colormap()
        red = cm.alloc_color("red")
        gc = pixmap.new_gc(foreground=red)
        # the thumbnail's actual size:
        t_width, t_height = self.photo.photo.size_request()
        o_width, o_height = self.cv_image.width, self.cv_image.height
        drawable = self.photo.photo.window # gdk.Window
        cm = drawable.get_colormap()
        gc = drawable.new_gc(foreground=cm.alloc_color('#ff0000',True,False))
        x_ratio = float(t_width)/float(o_width)
        y_ratio = float(t_height)/float(o_height)
        for (x, y, width, height) in rects:
            pixmap.draw_rectangle(gc, False, # fill?
                                  int(x * x_ratio), 
                                  int(y * y_ratio), 
                                  int(width * x_ratio), 
                                  int(height * y_ratio))
            print '   rectangle:', int(x * x_ratio), int(y * y_ratio), int(width * x_ratio), int(height * y_ratio)
        #pixmap.draw_line(gc, 0, 0, w, h)
        self.photo.photo.set_from_pixmap(pixmap, mask)
        #cv.Rectangle(cv_image, (x, y),
        #             (x + width, y + height),
        #             cv.CV_RGB(0, 0, 0), 3) # black, 3-pixel border
        #cv.Rectangle(cv_image, (x + 1, y + 1),
        #             (x + width + 1, y + height + 1),
        #             cv.CV_RGB(255, 255, 255), 3) # white, 3-pixel border
        
    def scalepixbuf(self, i):
        width = i.get_width()
        height = i.get_height()
        ratio = float(max(i.get_height(), i.get_width()))
        scale = float(180.0)/ratio
        x = int(scale*(i.get_width()))
        y = int(scale*(i.get_height()))
        i = i.scale_simple(x, y, gtk.gdk.INTERP_BILINEAR)
        return i

    def cv2image(self, cv_image):
        return Image.fromstring("L", cv.GetSize(cv_image), cv_image.tostring())

    def image2cv(self, pil_image):
        cv_image = cv.CreateImageHeader(pil_image.size, cv.IPL_DEPTH_8U, 3)
        cv.SetData(cv_image, pil_image.tostring())
        return cv_image

    def image2pixbuf(self, im):  
        """
        PIL image to Pixbuf.
        """
        file1 = StringIO.StringIO()  
        im.save(file1, "ppm")  
        contents = file1.getvalue()  
        file1.close()  
        loader = gtk.gdk.PixbufLoader("pnm")  
        loader.write(contents, len(contents))  
        pixbuf = loader.get_pixbuf()  
        loader.close()  
        return pixbuf  

    def pixbuf2image(self, pb):
        """
        Pixbuf to PIL image.
        """
        width,height = pb.get_width(), pb.get_height()
        return Image.fromstring("RGB", (width, height), pb.get_pixels())
