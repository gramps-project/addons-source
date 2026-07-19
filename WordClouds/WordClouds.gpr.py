#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Douglas S. Blank <doug.blank@gmail.com>
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

register(
    GRAMPLET,
    id="Given Name Word Cloud",
    name=_("Given Name Word Cloud"),
    description=_("Gramplet showing all given names as a word cloud"),
    status=STABLE,
    version="1.0.0",
    fname="givennamewordcloudgramplet.py",
    height=300,
    expand=True,
    gramplet="GivenNameWordCloudGramplet",
    gramplet_title=_("Given Name Word Cloud"),
    gramps_target_version="6.1",
    help_url="WordClouds",
)

register(
    GRAMPLET,
    id="Surname Word Cloud",
    name=_("Surname Word Cloud"),
    description=_("Gramplet showing all surnames as a word cloud"),
    status=STABLE,
    version="1.0.0",
    fname="surnamewordcloudgramplet.py",
    height=300,
    expand=True,
    gramplet="SurnameWordCloudGramplet",
    gramplet_title=_("Surname Word Cloud"),
    gramps_target_version="6.1",
    help_url="WordClouds",
)

register(
    GRAMPLET,
    id="Place Word Cloud",
    name=_("Place Word Cloud"),
    description=_("Gramplet showing all places as a word cloud"),
    status=STABLE,
    version="1.0.0",
    fname="placewordcloudgramplet.py",
    height=300,
    expand=True,
    gramplet="PlaceWordCloudGramplet",
    gramplet_title=_("Place Word Cloud"),
    gramps_target_version="6.1",
    help_url="WordClouds",
)
