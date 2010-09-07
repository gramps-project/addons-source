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
# Register: Image Metadata Gramplet
#------------------------------------------------------------------------
register(                   GRAMPLET,
    id =                    "Image Metadata Gramplet",
    name =                  _("Image Metadata Gramplet"),
    description =           _("Gramplet for editing image EXIF metadata"),
    height =                335,
    expand =                False,
    gramplet =              'ImageMetadataGramplet',
    gramplet_title =        _("Image Metadata Gramplet"),
    detached_width =        450,
    detached_height =       440,
    version = '1.1.4',
    gramps_target_version = "3.3.0",
    status =                STABLE,
    fname =                 "ImageMetadataGramplet.py",
    authors =               ["Rob G. Healey"],
    authors_email =         ["robhealey1@gmail.com"],
    help_url =              "Image Metadata Gramplet",
    )
