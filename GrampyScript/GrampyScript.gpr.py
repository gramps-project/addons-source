#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025      Doug Blank
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
    id="Grampy Script",
    name=_("Gram.py Script"),
    description=_("Run a special Gramps Python script"),
    status=STABLE,
    version="0.0.1",
    fname="GrampyScript.py",
    authors=["Doug Blank"],
    authors_email=["doug.blank@gmail.com"],
    gramps_target_version="6.0",
    gramplet="GrampyScript",
    gramplet_title=_("Gram.py Script"),
    help_url="Addon:GrampyScript",
    height=800,
)
