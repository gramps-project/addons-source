# encoding: utf-8
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009 Rob G. Healey <robhealey1@gmail.com>
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
# $Id$
#

#------------------------------------------------------------------------
#
# Exif Image Metadata Gramplet
#
#------------------------------------------------------------------------
register(GRAMPLET,
    id = "Image Metadata Gramplet",
    name = _("Image Metadata Gramplet"),
    height = 300,
    expand = False,
    gramplet = 'imageMetadataGramplet',
    gramplet_title = _("Image Metadata Gramplet"),
    detached_width = 450,
    detached_height = 415,
    version = "0.2.r270",
    gramps_target_version = "3.2",
    status = UNSTABLE,
    fname = "ImageMetadataGramplet.py",
    )
