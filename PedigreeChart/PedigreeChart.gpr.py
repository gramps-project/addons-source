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
from gramps.version import major_version, VERSION_TUPLE

if VERSION_TUPLE < (5, 2, 0):
    additional_args = {}
else:
    additional_args = {"help_url": "Addon:PedigreeChart"}

register(
    REPORT,
    id="PedigreeChart",
    name=_("Pedigree Chart"),
    description=_("Alternate version of the traditional pedigree chart."),
    status = STABLE,
    version = '1.0.42',
    fname="PedigreeChart.py",
    gramps_target_version=major_version,
    authors=["Jakim Friant"],
    authors_email=["jakim@friant.org"],
    category=CATEGORY_DRAW,
    reportclass="PedigreeChart",
    optionclass="PedigreeChartOptions",
    report_modes=[REPORT_MODE_GUI, REPORT_MODE_BKI, REPORT_MODE_CLI],
    require_active=False,
    **additional_args
)

__author__ = "jfriant"
__date__ = "$May 13, 2010 10:48:00 AM$"
