# encoding:utf-8
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009 Benny Malengier
# Copyright (C) 2009 Douglas S. Blank
# Copyright (C) 2009 Nick Hall
# Copyright (C) 2011 Tim G L Lyons
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
import traceback
import os
import sys
import html

from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext
from gi.repository import Gtk, GdkPixbuf
from gramps.gen.const import USER_PLUGINS
from gramps.gen.config import logging
from gramps.gen.config import config
inifile = config.register_manager("lifelinechartview_warn")
inifile.load()
sects = inifile.get_sections()

import importlib


module_provider_file = os.path.join(
        USER_PLUGINS,
        'LifeLineChartView',
        'ModuleProvider.py')
if os.path.isfile(module_provider_file):
    spec = importlib.util.spec_from_file_location(
        'ModuleProvider',
        module_provider_file
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    ModuleProvider = module.ModuleProvider

life_line_chart_version_required = (1, 6, 1)
life_line_chart_version_required_str = '.'.join([str(i) for i in life_line_chart_version_required])

try:
    if 'lifelinechartview_warn' not in sects or not inifile.get('lifelinechartview_warn.missingmodules') != 'False':
        _uistate = locals().get('uistate')
    else:
        _uistate = None
    mp=ModuleProvider('LifeLineChartView', _uistate)
    svgwrite = mp.request(
        'svgwrite',
        '1.4',
        'https://pypi.python.org/packages/source/s/svgwrite/svgwrite-1.4.zip'
    )
    life_line_chart = mp.request(
        'life_line_chart',
        life_line_chart_version_required_str,
        'https://pypi.python.org/packages/source/l/life_line_chart/life_line_chart-'+life_line_chart_version_required_str+'.tar.gz'
    )

    fname = os.path.join(USER_PLUGINS, 'LifeLineChartView')
    icons = Gtk.IconTheme().get_default()
    icons.append_search_path(fname)
    some_import_error = life_line_chart is None or svgwrite is None

except Exception as e:
    some_import_error = True
    import_error_message = traceback.format_exc()
    logging.log(logging.ERROR, 'Failed to load LifeLineChartView plugin.\n' + import_error_message)

if locals().get('uistate') is None or not some_import_error:
    # Right after the download the plugin is loaded without uistate
    # If the gui is available, then the error message is shown anyway
    # so here we can import to avoid additional messages.
    register(VIEW,
             id='lifelinechartancestorview',
             name=_("Life Line Ancestor Chart"),
             category=("Ancestry", _("Charts")),
             description=_("Persons and their relation in a time based chart"),
             version = '1.3.3',
             gramps_target_version="5.1",
             status=STABLE,
             fname='lifelinechartview.py',
             authors=["Christian Schulze"],
             authors_email=["c.w.schulze@gmail.com"],
             viewclass='LifeLineChartAncestorView',
             stock_icon='gramps-lifelineancestorchart-bw',
             )
    register(VIEW,
             id='lifelinechartdescendantview',
             name=_("Life Line Descendant Chart"),
             category=("Ancestry", _("Charts")),
             description=_("Persons and their relation in a time based chart"),
             version = '1.3.3',
             gramps_target_version="5.1",
             status=STABLE,
             fname='lifelinechartview.py',
             authors=["Christian Schulze"],
             authors_email=["c.w.schulze@gmail.com"],
             viewclass='LifeLineChartDescendantView',
             stock_icon='gramps-lifelinedescendantchart-bw',
             )

if not some_import_error:
    inifile.register('lifelinechart_warn.missingmodules', "")
    inifile.set('lifelinechart_warn.missingmodules', "True")
    inifile.save()
