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
#
#------------------------------------------------------------------------
# Image Metadata Gramplet
#------------------------------------------------------------------------
register(GRAMPLET, 
        id                    = "Image Metadata Gramplet", 
        name                  = _("Image Metadata Gramplet"), 
        description           = _("Gramplet to view, edit, and save image Exif metadata."),
        height                = 550,
        expand                = False,
        gramplet              = 'imageMetadataGramplet',
        gramplet_title        = _("Image Metadata"),
        detached_width        = 510,
        detached_height       = 550,
        version = '2.0.1',
        gramps_target_version = '3.4',
        status                = UNSTABLE,
        fname                 = "ImageMetadataGramplet.py",
        help_url              = "Image Metadata Gramplet",
        authors               = ['Rob G. Healey'],
        authors_email         = ['robhealey1@gmail.com'],
        navtypes              = ["Media"],
    )
