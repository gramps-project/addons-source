#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026       stolpee
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
    GENERAL,
    id="DarkModePrefs",
    name=_("Dark mode preferences"),
    description=_(
        "Adds robust dark mode controls with Linux-friendly defaults "
        "(Auto/Dark/Light) for Gramps desktop."
    ),
    version="0.1.2",
    gramps_target_version="6.0",
    fname="darkmode_load.py",
    authors=["stolpee"],
    authors_email=["slashmad@users.noreply.github.com"],
    maintainers=["stolpee"],
    maintainers_email=["slashmad@users.noreply.github.com"],
    category=TOOL_UTILS,
    load_on_reg=True,
    status=STABLE,
)
