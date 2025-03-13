#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2012
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
    id="BirthIndex",
    name=_("BirthIndex"),
    description=_("BirthIndex"),
    version = '0.0.38',
    gramps_target_version="6.0",
    include_in_listing=False,
    status=UNSTABLE,  # not yet tested with python 3, toplevel + signals + managedwindow
    fname="birth.py",
    category=TOOL_UTILS,
    toolclass="BirthIndex",
    optionclass="BirthIndexOptions",
    tool_modes=[TOOL_MODE_GUI],
)

register(
    TOOL,
    id="MarriageIndex",
    name=_("MarriageIndex"),
    description=_("MarriageIndex"),
    version = '0.0.36',
    gramps_target_version="6.0",
    include_in_listing=False,
    status=STABLE,  # not yet tested with python 3,
    fname="marriage.py",
    category=TOOL_UTILS,
    toolclass="MarriageIndex",
    optionclass="MarriageIndexOptions",
    tool_modes=[TOOL_MODE_GUI],
)

register(
    TOOL,
    id="DeathIndex",
    name=_("DeathIndex"),
    description=_("DeathIndex"),
    version = '0.0.36',
    gramps_target_version="6.0",
    include_in_listing=False,
    status=UNSTABLE,  # not yet tested with python 3, toplevel + signals + managedwindow
    fname="death.py",
    category=TOOL_UTILS,
    toolclass="DeathIndex",
    optionclass="DeathIndexOptions",
    tool_modes=[TOOL_MODE_GUI],
)

register(
    TOOL,
    id="CensusIndex",
    name=_("CensusIndex"),
    description=_("CensusIndex"),
    version = '0.0.36',
    gramps_target_version="6.0",
    include_in_listing=False,
    status=UNSTABLE,  # not yet tested with python 3, toplevel + signals + managedwindow
    fname="census.py",
    category=TOOL_UTILS,
    toolclass="CensusIndex",
    optionclass="CensusIndexOptions",
    tool_modes=[TOOL_MODE_GUI],
)

register(
    TOOL,
    id="Witness",
    name=_("Witness"),
    description=_("Witness"),
    version = '0.0.36',
    gramps_target_version="6.0",
    include_in_listing=False,
    status=UNSTABLE,  # not yet tested with python 3, toplevel + signals + managedwindow
    fname="witness.py",
    category=TOOL_UTILS,
    toolclass="Witness",
    optionclass="WitnessOptions",
    tool_modes=[TOOL_MODE_GUI],
)

register(
    TOOL,
    id="Index",
    name=_("SourceIndex"),
    description=_("SourceIndex"),
    version = '0.0.40',
    gramps_target_version="6.0",
    include_in_listing=False,
    status=STABLE,  # not yet tested with python 3, see feature 5552
    fname="index.py",
    category=TOOL_UTILS,
    toolclass="Index",
    optionclass="IndexOptions",
    tool_modes=[TOOL_MODE_GUI],
)
