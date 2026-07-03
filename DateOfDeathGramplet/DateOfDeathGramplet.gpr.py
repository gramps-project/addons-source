#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Javad Razavian <javadr@gmail.com>
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
    id="DateOfDeath",
    name=_("Date of Death"),
    description=_("a gramplet that displays dates of death sorted by month and day"),
    status=STABLE,
    version = '1.0.2',
    fname="DateOfDeathGramplet.py",
    height=200,
    gramplet="DateOfDeathGramplet",
    gramps_target_version="6.0",
    gramplet_title=_("Date of Death"),
    help_url="DateOfDeathGramplet",
)
