#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2015      Nick Hall
# Copyright (C) 2024      Paul Womack (BugBear)
# Copyright (C) 2026      Doug Blank
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

register(
    GRAMPLET,
    id="Person Relationship Filter",
    name=_("Person Relationship Filter"),
    description=_("Gramplet providing a person filter on relationships"),
    version="1.0.0",
    gramps_target_version="6.1",
    status=STABLE,
    fname="PersonRelationshipFilter.py",
    height=200,
    gramplet="PersonRelationshipFilter",
    gramplet_title=_("Relationship Filter"),
    navtypes=["Person"],
    authors=["Paul Womack", "Doug Blank"],
    authors_email=["doug.blank@gmail.com"],
    help_url="Addon:PersonRelationshipFilter",
)
