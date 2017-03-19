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
# version 0.0.4
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
        version = '0.0.4',
        gramps_target_version = '4.2',
        include_in_listing = True,
    )
else:
    from gramps.gen.config import config
    from gramps.gui.dialog import QuestionDialog2
    from gramps.gen.config import logging
    if module1 is None:
        warn_msg = _("NetworkChart Warning:  Python networkx module not found.")
        logging.log(logging.WARNING, warn_msg)
    if module2 is None:
        warn_msg = _("NetworkChart Warning:  Python pygraphviz module not found.")
        logging.log(logging.WARNING, warn_msg)
    inifile = config.register_manager("networkchartwarn")
    inifile.load()
    sects = inifile.get_sections()
    if 'networkchartwarn' not in sects:
        yes_no = QuestionDialog2(_("NetworkChart Failed to Load"),
            _("\n\nNetworkChart is missing python modules.  Both networkx \n" 
              "and pygraphviz must be installed.  For now, you can install \n"
              "the files manually.  See \n\n"
              "https://gramps-project.org/wiki/index.php?title=NetworkChart \n\n"
              "To dismiss all future NetworkChart warnings click Dismiss."),
            _(" Dismiss "),
            _("Continue"))
        prompt = yes_no.run()
        if prompt is True:
            inifile.register('networkchartwarn.MissingModules', "")
            inifile.set('networkchartwarn.MissingModules', "True")
            inifile.save()
