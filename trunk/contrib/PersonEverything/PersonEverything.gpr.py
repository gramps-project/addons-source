#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2014       Tim G L Lyons
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

# $Id$

#------------------------------------------------------------------------
#
# PersonEverything Report
#
#------------------------------------------------------------------------

register(REPORT,
        id    = 'PersonEverythingReport',
        name  = _("PersonEverything Report"),
        description =  _("Produces a report containing everything about the active person"),
        version = '1.0.1',
        gramps_target_version = '4.2',
        status = STABLE, # not yet tested with python 3
        fname = 'PersonEverything.py',
        category = CATEGORY_TEXT,
        reportclass = 'PersonEverythingReport',
        optionclass = 'PersonEverthingOptions',
        report_modes = [REPORT_MODE_GUI, REPORT_MODE_BKI, REPORT_MODE_CLI],
        authors = ["Tim G L Lyons"],
        authors_email = ["gramps-project.org"]
        )

