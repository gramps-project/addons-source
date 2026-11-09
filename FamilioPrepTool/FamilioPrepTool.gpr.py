# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 Alexander Aganichev <aaganichev@gmail.com>
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

register(TOOL,
    id='familiopreptool',
    name=_("Prepare for Familio export"),
    description=_(
        "Adds a missing _UID attribute to persons (without overwriting "
        "existing ones) and adds missing 'Marriage' events to families, "
        "so that GEDCOM export produces the tags Familio expects."
    ),
    version = '1.0.1',
    gramps_target_version="6.0",
    status=STABLE,
    fname='FamilioPrepTool.py',
    authors=["Alexander Aganichev", "Claude", "Gemini"],
    authors_email=["aaganichev@gmail.com"],
    category=TOOL_DBPROC,
    toolclass='FamilioPrepTool',
    optionclass='FamilioPrepOptions',
    tool_modes=[TOOL_MODE_GUI],
    help_url="Addon:FamilioPrepTool",
    )
