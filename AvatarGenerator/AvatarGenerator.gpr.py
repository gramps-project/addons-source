#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2019 Matthias Kemmer <matt.familienforschung@gmail.com>
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
    TOOL,
    id="AvatarGenerator",
    name=_("Avatar Generator Tool"),
    description=_("A tool to add avatar pictures to your family tree"),
    version = '1.0.18',
    gramps_target_version="6.0",
    status=STABLE,
    fname="AvatarGenerator.py",
    authors=["Matthias Kemmer"],
    authors_email=["matt.familienforschung@gmail.com"],
    category=TOOL_DBPROC,
    toolclass="AvatarGeneratorWindow",
    optionclass="AvatarGeneratorOptions",
    tool_modes=[TOOL_MODE_GUI],
    help_url="Addon:AvatarGenerator",
)
