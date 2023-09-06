# encoding:utf-8
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010 Doug Blank <doug.blank@gmail.com>
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
#

# $Id $

#------------------------------------------------------------------------
#
# libaccess
#
#------------------------------------------------------------------------
register(GENERAL,
id    = 'libaccess',
name  = "Generic DB Access lib",
description =  _("Provides a library for generic access to "
                 "the database and gen.lib."),
version = '1.0.32',
gramps_target_version = "5.2",
status = STABLE,
audience = DEVELOPER,
fname = 'libaccess.py',
authors = ["Doug Blank"],
authors_email = ["doug.blank@gmail.com"],
load_on_reg = True
  )
