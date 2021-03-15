""" Options """
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021  Manuela Kugel (gramps@ur-ahn.de)
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# TimePedigreeHtml - a plugin for GRAMPS - version 0.1
# Outcome is an HTML file showing a pedigree with time scale

# Version 0.0.2:
# - register() instead of newplugin()

from gramps.gen.plug._pluginreg import (newplugin, STABLE, REPORT,
    CATEGORY_WEB, REPORT_MODE_GUI, REPORT_MODE_CLI)
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext

MODULE_VERSION="5.1"

#------------------------------------------------------------------------
#
# Narrated Web Site
#
#------------------------------------------------------------------------

register(REPORT,
         id = 'TimePedigreeHTML',
         name = _("Timeline Pedigree Report"),
         description = _("This creates a website showing a "
            "pedigree with birthday relation"),
         version = '0.0.2',
         gramps_target_version = MODULE_VERSION,
         status = STABLE,
         fname = 'TimePedigreeHtml.py',
         authors = ["Manuela Kugel"],
         authors_email = ["gramps@ur-ahn.de"],
         category = CATEGORY_WEB,
         reportclass = 'TimePedigreeHtml',
         optionclass = 'TimePedigreeHtmlOptions',
         report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI]
)
