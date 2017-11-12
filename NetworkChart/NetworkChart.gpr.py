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
# version 0.0.6
#-------------------------------------------------------------------------
import importlib
from gramps.gen.const import URL_WIKISTRING
from gramps.gen.utils.file import search_for
module1 = importlib.find_loader("networkx") is not None
module2 = importlib.find_loader("pydotplus") is not None
module3 = importlib.find_loader("pydot") is not None
module4 = importlib.find_loader("pygraphviz") is not None
module5 = bool(search_for('dot'))
module6 = bool(search_for('dot.exe'))
conditions_met = (module1) and (module2 or module3 or module4 or module5 or module6)
if conditions_met:
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
        version = '0.0.8',
        gramps_target_version = '5.0',
        include_in_listing = True,
    )
elif uistate:  # don't start GUI if in CLI mode, just ignore
    from gramps.gen.config import config
    from gramps.gui.dialog import QuestionDialog2
    from gramps.gen.config import logging
    if not module1:
        warn_msg = _("NetworkChart Warning:  Python networkx module not found.")
        logging.log(logging.WARNING, warn_msg)
    if not (module2 or module3 or module4 or module5 or module6):
        warn_msg = _("NetworkChart Warning:  NetworkChart needs one of the following to work: \n"
                     "     Python module  pydotplus            OR\n"
                     "     Python module  pydot                OR\n"
                     "     Python module  pygraphviz           OR\n"
                     "     Package        dot (from graphviz)  OR\n"
                     "     Executable     dot.exe (from graphviz or Gramps)")
        logging.log(logging.WARNING, warn_msg)
    inifile = config.register_manager("networkchartwarn")
    inifile.load()
    sects = inifile.get_sections()
    if 'networkchartwarn' not in sects:
        yes_no = QuestionDialog2(_("NetworkChart Failed to Load"),
            _("\n\nNetworkChart is missing python modules or programs.  Networkx AND at\n"
              "least one of (pydotplus OR pydot OR pygraphviz OR dot OR dot.exe) must be\n"
              "installed.  For now, it may be possible to install the files manually. See\n\n"
              "https://gramps-project.org/wiki/index.php?title=NetworkChart \n\n"
              "To dismiss all future NetworkChart warnings click Dismiss."),
            _(" Dismiss "),
            _("Continue"), parent=uistate.window)
        prompt = yes_no.run()
        if prompt is True:
            inifile.register('networkchartwarn.MissingModules', "")
            inifile.set('networkchartwarn.MissingModules', "True")
            inifile.save()
