# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Vadim Verenich
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

# ------------------------------------------------------------------------
#
# Circle Tree View
#
# ------------------------------------------------------------------------
register(
    VIEW,
    id="circletreeview",
    name=_("Circle Tree View"),
    category=("Ancestry", _("Charts")),
    description=_(
        "Descendant tree with circular nodes, spouse infinity mark, "
        "auto generation depth (max 6), SVG/PNG export"
    ),
    version="1.4.0",
    gramps_target_version="6.1",
    status=STABLE,
    fname="circletreeview.py",
    authors=["Vadim Verenich"],
    authors_email=["vadimverenich@gmail.com"],
    viewclass="CircleTreeView",
    stock_icon="gramps-pedigree",
)
