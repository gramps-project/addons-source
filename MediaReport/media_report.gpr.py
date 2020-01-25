#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2019  Matthias Kemmer <matt.familienforschung@gmail.com>
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

register(REPORT,
         id = 'MediaReport',
         name = _("Media Report"),
         description = _("Generates report including images, image data"
                         " and notes."),
         version = '1.2.0',
         gramps_target_version = "5.1",
         status = STABLE,
         fname = "media_report.py",
         authors = ["Matthias Kemmer"],
         authors_email = ["matt.familienforschung@gmail.com"],
         category = CATEGORY_TEXT,
         reportclass = 'MediaReport',
         optionclass = 'ReportOptions',
         report_modes = [REPORT_MODE_CLI, REPORT_MODE_GUI],
         )
