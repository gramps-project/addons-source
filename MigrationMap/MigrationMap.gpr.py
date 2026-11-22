#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Brian Caudill
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

# ------------------------------------------------------------------------
#
# Register the Migration Map tool
#
# ------------------------------------------------------------------------
register(
    TOOL,
    id="MigrationMap",
    name=_("Migration Map"),
    description=_(
        "Generate an animated, interactive map of how people and families "
        "moved over time, built from dated events whose places have "
        "coordinates. Opens in your web browser with a timeline you can play."
    ),
    version="0.0.1",
    gramps_target_version="6.0",
    status=STABLE,
    audience=EXPERT,
    fname="MigrationMap.py",
    category=TOOL_ANAL,
    toolclass="MigrationMapWindow",
    optionclass="MigrationMapOptions",
    tool_modes=[TOOL_MODE_GUI],
    authors=["Brian Caudill"],
    authors_email=["brian.m.caudill@gmail.com"],
    maintainers=["Brian Caudill"],
    maintainers_email=["brian.m.caudill@gmail.com"],
    help_url="Addon:MigrationMap",
)
