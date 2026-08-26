#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
# Plugin registration for Expanded Ancestor Tree addon
#
# Copyright (C) 2026  Bartok Szabolcs <bartokszabi2005@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <https://www.gnu.org/licenses/>.

from gramps.version import major_version, VERSION_TUPLE

if (5, 2, 0) <= VERSION_TUPLE <= (6, 2, 0):
    register(
        REPORT,
        id="ExpandedAncestorTree",
        name=_("Ancestor Tree Expanded"),
        description=_("Expanded Ancestor Graph showing direct ancestors, siblings, cousins and spouses."),
        version="1.0.1",
        gramps_target_version=major_version,
        status=STABLE,
        fname="ExpandedAncestorTree.py",
        category=CATEGORY_DRAW,
        authors=["Bartok Szabolcs"],
        authors_email=["bartokszabi2005@gmail.com"],
        reportclass="ExpandedAncestorTree",
        optionclass="ExpandedAncestorTreeOptions",
        report_modes=[REPORT_MODE_GUI, REPORT_MODE_CLI, REPORT_MODE_BKI],
        help_url="https://gramps.discourse.group/t/9891",
    )