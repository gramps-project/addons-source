#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Yurii Liubymyi <jurchello@gmail.com>
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

# ----------------------------------------------------------------------------

"""
This module handles the initialization of the translator for the current file.

If the translator initialization through GRAMPS_LOCALE is successful,
the appropriate translation is used.
Otherwise, the default translation is applied.

The variable _ contains the gettext function for retrieving translated strings.
"""

try:
    from gramps.gen.const import GRAMPS_LOCALE as glocale

    # Ініціалізація перекладача
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation

_ = _trans.gettext
