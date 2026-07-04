#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009  Jerome Rapinat
# Copyright (C) 2026  Brian McCullough,
#               with assistance from Anthropic Claude and GitHub Copilot
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

"""
Gramps registration file
"""

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.version import major_version, VERSION_TUPLE
# -------------------------------------------------------------------------
#
# Check Associations Data
#
# -------------------------------------------------------------------------

if VERSION_TUPLE >= (6, 0, 0):
    register(
        TOOL,
        id="associationstool",
        name=_("Check Associations data"),
        description=_("Display all person Associations in a sortable, hotlinked table"),
        version = '1.2.1',
        gramps_target_version=major_version,
        include_in_listing=True,
        status=STABLE,
        fname="associationstool.py",
        authors=["Jerome Rapinat", "Brian McCullough"],
        authors_email=["romjerome@yahoo.fr","emyoulation@yahoo.com"],
        maintainers=["Brian McCullough"],
        maintainers_email=["emyoulation@yahoo.com"],
        category=TOOL_UTILS,
        toolclass="AssociationsTool",
        optionclass="AssociationsToolOptions",
        tool_modes=[TOOL_MODE_GUI, TOOL_MODE_CLI],
        help_url="Addon:Check_Associations",
    )
