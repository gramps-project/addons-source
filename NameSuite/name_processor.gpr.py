#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Dmitry Bryndin
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

# type: ignore

register(
    TOOL,
    id="name_standardization_tool",
    name=_("Audit Given and Patronymic Names"),
    category=TOOL_DBPROC,  # Standard database processing category
    description=_(
        "Tools to rename given name, audit and infer patronymic (East Slavic) names."
    ),
    version = '1.0.1',
    gramps_target_version="6.0",
    status=STABLE,
    fname="names_tool.py",
    authors=["Dmitry Bryndin"],
    authors_email=["1129396+bryndin@users.noreply.github.com"],
    toolclass="NamesTool",
    optionclass="NamesToolOptions",
    help_url="Addon:NameSuite",
)

register(
    GRAMPLET,
    id="patronymic_suggestion_gramplet",
    name=_("Patronymic Suggestion"),
    description=_(
        "Suggests (East Slavic) patronymic names in real-time as you navigate."
    ),
    version = '1.0.1',
    gramps_target_version="6.0",
    status=STABLE,
    fname="patronymics_gramplet.py",
    authors=["Dmitry Bryndin"],
    authors_email=["1129396+bryndin@users.noreply.github.com"],
    gramplet="PatronymicSuggestionGramplet",
    navtypes=["Person", "Relationship"],
    gramplet_title=_("Patronymic Suggestion"),
    help_url="Addon:NameSuite",
)
