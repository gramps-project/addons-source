#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Yurii Liubymyi <jurchello@gmail.com>
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

# ----------------------------------------------------------------------------

"""
Registers the WebSearch Gramplet with Gramps.

This module contains metadata and configuration used by Gramps to integrate
the WebSearch Gramplet, including supported navigation types and display settings.
"""

# pylint: disable=E0602
register(
    GRAMPLET,
    id="WebSearch",
    name=_("WebSearch"),
    description=_(
        "Customized queries for online services based on the active "
        "Person, Place, Family, or Source record"
    ),
    status=STABLE,
    version="0.81.67",
    fname="WebSearch.py",
    height=20,
    detached_width=400,
    detached_height=300,
    expand=True,
    gramplet="WebSearch",
    gramplet_title=_("WebSearch"),
    gramps_target_version="6.0",
    navtypes=[
        "Person",
        "Place",
        "Source",
        "Family",
        "Event",
        "Citation",
        "Media",
        "Note",
        "Repository",
    ],
    include_in_listing=True,
    help_url="Addon:WebSearch",
)
