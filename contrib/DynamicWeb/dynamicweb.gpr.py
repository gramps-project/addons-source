# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2014 Pierre Bélissent
#
# This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with this program; if not, write to the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# $Id: $

register(REPORT,
id = 'DynamicWeb',
name = _("Dynamic Web Report"),
description =  _("Produces dynamic web pages for the database"),
version = '0.0.16',
gramps_target_version = '4.2',
status = UNSTABLE,
fname = 'dynamicweb.py',
authors = ["Pierre Bélissent"],
authors_email = ["pierre.belissent@gmail.com"],
category = CATEGORY_WEB,
reportclass = 'DynamicWebReport',
optionclass = 'DynamicWebOptions',
report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI]
)
