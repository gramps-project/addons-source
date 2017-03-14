#-------------------------------------------------------------------------
#
# Copyright (C) 2017 Mark B. <familynetworkchart@gmail.com>
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, 
# Boston, MA 02110-1301  USA
#
# version 0.0.3
#-------------------------------------------------------------------------
import importlib
from gramps.gen.const import URL_WIKISTRING
module1 = importlib.find_loader("networkx")
module2 = importlib.find_loader("pygraphviz")
if module1 is not None and module2 is not None:
    register(REPORT,
        id = 'networkchart',
        name = _('Network Chart'),
        category = CATEGORY_WEB,
        status = STABLE,
        fname = 'NetworkChart.py',
        reportclass = 'NetworkChartReport',
        optionclass = 'NetworkChartOptions',
        report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI],
        authors = ['Mark B.'],
        authors_email = ['familynetworkchart@gmail.com'],
        #help_url = URL_WIKISTRING+'NetworkChart',
        description = _('Generates a family network chart.'),
        version = '0.0.3',
        gramps_target_version = '4.2',
        include_in_listing = True,
    )
else:
    from gramps.gen.config import logging
    warn_msg = _("Failure to load Family NetworkChart.  Python networkx or pygraphviz module(s) not found.")
    logging.log(logging.WARNING, warn_msg)
