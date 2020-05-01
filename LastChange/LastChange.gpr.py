#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010      Jakim Friant
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
# $Id$
#
register(GRAMPLET,
         id="LastChangeGramplet",
         name=_("Last Change"),
         description=_("List the last ten person records that have been changed"),
         status=STABLE,
         version = '0.1.7',
         fname="LastChangeGramplet.py",
         authors=['Jakim Friant'],
         authors_email=["jmodule@friant.org"],
         height=170,
         gramplet='LastChangeGramplet',
         gramps_target_version="5.1",
         gramplet_title=_("Latest Changes"),
         help_url = "LastChange",
         )

register(REPORT,
         id="LastChangeReport",
         name=_("Last Change Report"),
         description=_("Report of the last records that have been changed"),
         status=STABLE,
         version = '0.1.7',
         fname="LastChangeReport.py",
         gramps_target_version="5.1",
         authors=['Jakim Friant'],
         authors_email=["jmodule@friant.org"],
         category=CATEGORY_TEXT,
         reportclass='LastChangeReport',
         optionclass='LastChangeOptions',
         report_modes=[REPORT_MODE_GUI, REPORT_MODE_BKI, REPORT_MODE_CLI],
         require_active=False
         )
