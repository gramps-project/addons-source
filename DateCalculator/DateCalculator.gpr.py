# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (c) 2015 Douglas S. Blank <doug.blank@gmail.com>
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

register(GRAMPLET,
         id="DateCalculator",
         name=_("Date Calculator"),
         description=_("Useful for date math calculations"),
         status=STABLE,
         version = '0.0.10',
         fname="DateCalculator.py",
         authors=['Doug Blank'],
         authors_email=["doug.blank@gmail.com"],
         height=250,
         gramplet='DateCalculator',
         gramps_target_version="5.1",
         gramplet_title=_("Date Calculator"),
         help_url = "DateCalculator",
         )

