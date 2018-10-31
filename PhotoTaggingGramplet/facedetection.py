#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2011 Nick Hall
#           (C) 2011 Doug Blank <doug.blank@gmail.com>
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

#-------------------------------------------------------------------------
#
# Standard python modules
#
#-------------------------------------------------------------------------

import os

#-------------------------------------------------------------------------
#
# computer vision modules
#
#-------------------------------------------------------------------------

try:
    import cv2
    computer_vision_available = True
except ImportError:
    computer_vision_available = False

#-------------------------------------------------------------------------
#
# constants
#
#-------------------------------------------------------------------------

path, filename = os.path.split(__file__)
HAARCASCADE_PATH = os.path.join(path, 'haarcascade_frontalface_alt.xml')

#-------------------------------------------------------------------------
#
# face detection functions
#
#-------------------------------------------------------------------------

def detect_faces(image_path, min_face_size, sensitivity):
    cv_image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    img_size = (cv_image.shape[0], cv_image.shape[1])
    cv2.equalizeHist(cv_image, cv_image)
    cascade = cv2.CascadeClassifier(HAARCASCADE_PATH)
    # calculate values for sensitivity (scaleFactor, minNeighbors)
    scale_factor = 1.0 + (0.21 - sensitivity/100)       # 1.01 .. 1.2
    min_neighbors = round(3 + (2 - 2*sensitivity/10))   # 1 .. 5

    faces = cascade.detectMultiScale(cv_image, minSize=min_face_size,
                                     scaleFactor=scale_factor,
                                     minNeighbors=min_neighbors)

    return faces, img_size
