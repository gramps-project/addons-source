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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
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
version = '1.0.19',
gramps_target_version = '4.1',
status = STABLE, # not yet tested with python 3
fname = 'libaccess.py',
authors = ["Doug Blank"],
authors_email = ["doug.blank@gmail.com"],
load_on_reg = True
  )
