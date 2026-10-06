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
# Register the Agent Bridge gramplet
#
# ------------------------------------------------------------------------
register(
    GRAMPLET,
    id="Agent Bridge",
    name=_("Agent Bridge"),
    description=_(
        "Embeds a control bridge in Gramps so an AI agent can drive the live "
        "application through a watched directory or an MCP server. Executes "
        "submitted Python on the GTK main thread. For developers and power "
        "users; runs arbitrary code at your privileges."
    ),
    version="0.0.1",
    gramps_target_version="6.0",
    status=STABLE,
    audience=DEVELOPER,
    fname="AgentBridge.py",
    gramplet="AgentBridge",
    gramplet_title=_("Agent Bridge"),
    height=140,
    expand=True,
    detached_width=520,
    detached_height=300,
    navtypes=["Dashboard"],
    authors=["Brian Caudill"],
    authors_email=["brian.m.caudill@gmail.com"],
    maintainers=["Brian Caudill"],
    maintainers_email=["brian.m.caudill@gmail.com"],
    help_url="Addon:AgentBridge",
)
