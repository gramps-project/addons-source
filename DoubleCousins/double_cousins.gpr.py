#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020  Matthias Kemmer
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
"""A text report listing double cousins."""

register(REPORT,
         id = 'double_cousins',
         name = _("Double Cousins"),
         description = _("A text report listing double cousins."),
         version = '1.0.4',
         gramps_target_version = "5.1",
         status = STABLE,
         fname = "double_cousins.py",
         authors = ["Matthias Kemmer"],
         authors_email = ["matt.familienforschung@gmail.com"],
         category = CATEGORY_TEXT,
         reportclass = 'DoubleCousins',
         optionclass = 'ReportOptions',
         report_modes = [REPORT_MODE_CLI, REPORT_MODE_GUI],
         )
