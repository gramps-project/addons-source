#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026 Perplexity AI Assistant
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
# Generated: January 17, 2026 - Perplexity AI Assistant v1.0
# virtualkeyboard.gpr.py
# Virtual Keyboard Gramplet plug-in registration generated for Gramps
# Touch-friendly on-screen keyboard for clipboarded data entry
# Default: Special (accented) layout

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gui import plug
from gramps.version import major_version, VERSION_TUPLE

if VERSION_TUPLE < (5, 2, 0):
    additional_args = {
        "status": UNSTABLE,
    }
else:
    additional_args = {
        "audience": EXPERT,
        "status": EXPERIMENTAL,
        "maintainers": "Brian McCullough",
        "maintainers_email": "Emyoulation@yahoo.com",
    }

register(
    GRAMPLET,
    id="VirtualKeyboard",
    name=_("Virtual Keyboard"),
    description=_("Touch-friendly on-screen keyboard for clipboarding characters"),
    authors = ["Perplexity AI Assistant"],
    fname="virtualkeyboard.py",
    height=280,
    expand=False,
    gramplet="VirtualKeyboard",
    gramplet_title=_("Virtual Keyboard"),
    version="1.0.0",
    gramps_target_version=major_version,
    navtypes=["Dashboard", "Person", "Family", "Event", "Place", "Source", "Citation", "Repository", "Media", "Note"],
#    help_url="Addon:Virtual_Keyboard",
    help_url="https://gramps.discourse.group/t/python-virtual-keyboard-with-diacritical-marks/3006/10",
    include_in_listing=True,
    **additional_args,
)
