#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021-2024 David Straub
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
# from gramps.gen.plug._pluginreg import *
# from gramps.gen.const import GRAMPS_LOCALE as glocale
# _ = glocale.translation.gettext

"""GRAMPS registration file."""

register(
    TOOL,
    id="gramps_web_sync",
    name=_("Gramps Web Sync"),
    description=_("Synchronizes a local database with a Gramps Web instance."),
    version = '1.3.0',
    gramps_target_version="6.0",
    status=STABLE,
    fname="grampswebsync.py",
    authors=["David Straub"],
    authors_email=["straub@protonmail.com"],
    category=TOOL_DBPROC,
    toolclass="GrampsWebSyncTool",
    optionclass="GrampsWebSyncOptions",
    tool_modes=[TOOL_MODE_GUI],
    help_url="Addon:Gramps_Web_Sync",
)
