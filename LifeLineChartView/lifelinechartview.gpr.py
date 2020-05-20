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
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext


life_line_chart_version_required = (1, 2, 28)
try:
    import life_line_chart
    life_line_chart_is_missing = False
    original_version = life_line_chart.__version__
    version_tuple = tuple([int(i) if i.isnumeric() else i for i in original_version.split('.')])
    wrong_life_line_chart_version = life_line_chart_version_required != version_tuple

    # load icon
    import os
    from gi.repository import Gtk, GdkPixbuf
    from gramps.gen.const import USER_PLUGINS
    fname = os.path.join(USER_PLUGINS, 'LifeLineChartView')
    icons = Gtk.IconTheme().get_default()
    icons.append_search_path(fname)
    unknown_import_error = False
    import_error_message = None
except ImportError as e:
    wrong_life_line_chart_version = False
    life_line_chart_is_missing = True
    unknown_import_error = False
    import_error_message = str(e)
except Exception as e:
    wrong_life_line_chart_version = False
    life_line_chart_is_missing = False
    unknown_import_error = True
    import_error_message = str(e)

if not wrong_life_line_chart_version and not life_line_chart_is_missing:
    register(VIEW,
            id='lifelinechartview',
            name=_("Life Line Chart"),
            category=("Ancestry", _("Charts")),
            description=_("A view showing parents through a lifelinechart"),
            version = '1.0.13',
            gramps_target_version="5.1",
            status=STABLE,
            fname='lifelinechartview.py',
            authors=["Christian Schulze"],
            authors_email=["c.w.schulze@gmail.com"],
            viewclass='LifeLineChartView',
            stock_icon='gramps-lifelinechart-bw',
            )

from gramps.gen.config import logging
ui_message = ""
if life_line_chart_is_missing or wrong_life_line_chart_version or unknown_import_error:
    ui_message = _("\n\nLife Line Chart failed to import life_line_chart module")
    if wrong_life_line_chart_version:
        what_to_do = _('Please upgrade the module life_line_chart')
        pip_command = 'pip install --upgrade life_line_chart=={}.{}.{}'.format(*life_line_chart_version_required)
        ui_message += ". The installed verison {original_version} is not compatible.".format(**locals())
    elif unknown_import_error:
        what_to_do = _('Failed to import life_line_chart module')
        pip_command = 'pip install life_line_chart=={}.{}.{}'.format(*life_line_chart_version_required)
        ui_message += ":\n<i>{import_error_message}</i>".format(**locals())
    else:
        what_to_do = _('Please install life_line_chart module')
        pip_command = 'pip install life_line_chart=={}.{}.{}'.format(*life_line_chart_version_required)
        ui_message += ":\n<i>{import_error_message}</i>".format(**locals())

    ui_message += "\n\n{what_to_do}:\n<i>{pip_command}</i>".format(**locals())
    logging.log(logging.WARNING, ui_message)



from gramps.gen.config import config
inifile = config.register_manager("lifelinechart_warn")
inifile.load()
sects = inifile.get_sections()
if (life_line_chart_is_missing or wrong_life_line_chart_version) and locals().get('uistate'):
    from gramps.gui.dialog import QuestionDialog2
    if 'lifelinechart_warn' not in sects or not inifile.get('lifelinechart_warn.missingmodules')!='False':
        yes_no = QuestionDialog2(
            _("Life Line Chart View Failed to Load"),
            ui_message +
            "\n\nTo dismiss all future Life Line Chart View warnings click Dismiss.",
            _(" Dismiss "),
            _("Continue"), parent=uistate.window)
        prompt = yes_no.run()
        if prompt is True:
            inifile.register('lifelinechart_warn.missingmodules', "")
            inifile.set('lifelinechart_warn.missingmodules', "True")
            inifile.save()
else:
    inifile.register('lifelinechart_warn.missingmodules', "")
    inifile.set('lifelinechart_warn.missingmodules', "False")
    inifile.save()
