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

"""
Internationalization (i18n) module for the NameSuite addon.
Provides translation binding anchored at the addon root directory.
"""

import os
from gramps.gen.const import GRAMPS_LOCALE as glocale

# This file is at name_processor/views/i18n.py
# The addon root (which holds locale/) is three directories up
_ADDON_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
try:
    _trans = glocale.get_addon_translator(
        os.path.join(_ADDON_ROOT, "name_processor.gpr.py")
    )
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
