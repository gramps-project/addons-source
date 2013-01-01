#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009 Benny Malengier
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

register(REPORT, 
         id    = 'Repositories Report Options',
         name  = _("Repositories Report Options"),
         description =  _("Produces a textual repositories report"),
         version = '0.3.7',
         gramps_target_version = '4.1',
         status = STABLE, # not yet tested with python 3
         fname = 'RepositoriesReportAlt.py',
         authors = ["Jerome Rapinat"],
         authors_email = ["romjerome@yahoo.fr"],
         category = CATEGORY_TEXT,
         reportclass = 'RepositoryReportAlt',
         optionclass = 'RepositoryOptionsAlt',
         report_modes = [REPORT_MODE_GUI, REPORT_MODE_BKI, REPORT_MODE_CLI],
         require_active = False
         )

register(REPORT, 
         id    = 'Repositories Report',
         name  = _("Repositories Report"),
         description =  _("Produces a textual repositories report"),
         version = '1.1.7',
         gramps_target_version = '4.1',
         status = STABLE, # not yet tested with python 3
         fname = 'RepositoriesReport.py',
         authors = ["Jerome Rapinat"],
         authors_email = ["romjerome@yahoo.fr"],
         category = CATEGORY_TEXT,
         reportclass = 'RepositoryReport',
         optionclass = 'RepositoryOptions',
         report_modes = [REPORT_MODE_GUI, REPORT_MODE_BKI, REPORT_MODE_CLI],
         require_active = False
         )
