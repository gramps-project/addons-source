# encoding:utf-8
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026 Adrian Baugh
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
# `_` is injected into this file's namespace by the plugin registrar, and is
# already the addon's own translator; it must not be defined here.
#
from gramps.gen.plug._pluginreg import *

MODULE_VERSION = "6.0"

register(
    VIEW,
    id="contextview",
    name=_("Context"),
    description=_(
        "A chart placing a person in the context of their immediate family: "
        "the couple in the centre, each partner's parents above them, their "
        "children below, and each partner's siblings in a column to their "
        "own side, eldest at the top. Click any box to re-centre the chart "
        "on that person; the name in bold marks the way back to the home "
        "person."
    ),
    version = '1.0.1',
    gramps_target_version=MODULE_VERSION,
    status=STABLE,
    audience=EVERYONE,
    fname="ContextView.py",
    authors=["Adrian Baugh"],
    authors_email=["aje.baugh@gmail.com"],
    category=("Ancestry", _("Charts")),
    viewclass="ContextView",
    order=END,
    stock_icon="gramps-relation",
    help_url="Addon:Context_View",
)
