#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Doug Blank
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
from gramps.gen.const import GRAMPS_LOCALE as glocale

_ = glocale.translation.gettext

register(
    TOOL,
    id="grampsassistant",
    name=_("Gramps Assistant"),
    description=_("AI assistant for querying your Gramps family tree"),
    version = '1.0.1',
    gramps_target_version="6.1",
    status=STABLE,
    fname="grampsassistant.py",
    authors=["Douglas S. Blank"],
    authors_email=["dsblank@gmail.com"],
    category=TOOL_UTILS,
    toolclass="GrampsAssistantTool",
    optionclass="GrampsAssistantOptions",
    tool_modes=[TOOL_MODE_GUI],
    depends_on=["Grampy Script"],
    help_url="Addon:GrampsAssistant",
)
