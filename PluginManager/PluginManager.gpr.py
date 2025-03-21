#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2017      Paul Culley
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
# $Id$

# ------------------------------------------------------------------------
#
# Plugin Manager Enhanced
#
# ------------------------------------------------------------------------
register(
    GENERAL,
    id="PluginManager",
    name=_("Plugin Manager Enhanced"),
    description=_("An Addon/Plugin Manager with several additional " "capabilities"),
    version = '1.2.7',
    gramps_target_version="6.0",
    fname="PluginManagerLoad.py",
    authors=["Paul Culley"],
    authors_email=["paulr2787@gmail.com"],
    category=TOOL_UTILS,
    load_on_reg=True,
    help_url="Addon:Plugin_ManagerV2",
    status=STABLE,
)
