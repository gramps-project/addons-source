#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# TMG Importer addon for Gramps genealogy program
#
# Copyright (C) 2017-2018 Sam Manzi
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

'''
Import from an Whollygenes - The Master Genealogist (TMG) Project backup file
(*.SQZ)
'''

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.sgettext

#------------------------------------------------------------------------
#
# Register TMG Importer
#
#------------------------------------------------------------------------
dbfavailable = False
direct_tmg_pjc_ver_support = False
grampsversion = "5.1"

try:
    # External Library: dbf.pypi
    # https://pypi.python.org/pypi/dbf
    import dbf
    dbfavailable = True
except (ImportError, ValueError):
    dbfavailable = False

if not dbfavailable:
    from gramps.gen.config import config
    inifile = config.register_manager("tmgimporterwarn")
    inifile.load()
    sects = inifile.get_sections()

# Don't register if not runnable, but have to 'Make build' anyway
if(dbfavailable or locals().get('build_script')):
    register(IMPORT,
             id    = 'im_sqz',
             name  = _('TMG Project Backup'),
             description =  _('Import TMG project files'),
             version = '0.0.75',
             gramps_target_version = grampsversion,
             include_in_listing = False,
             status = STABLE,
             fname = 'importtmg.py',
             import_function = 'importSqzData',
             extension = "sqz" # Only detects lower case extensions (TODO: add SQZ uppercase)
    )
    if direct_tmg_pjc_ver_support:
    # Only Load when importer directly supports (tmg/pjc/ver)
        register(IMPORT,
                 id    = 'im_pjc',
                 name  = _('TMG Unsupported'),
                 description =  _('Import TMG project files'),
                 version = '0.0.75',
                 gramps_target_version = grampsversion,
                 include_in_listing = False,
                 status = UNSTABLE,
                 fname = 'importtmg.py',
                 import_function = 'importpjc',
                 extension = "pjc"
        )

        register(IMPORT,
                 id    = 'im_tmg',
                 name  = _('TMG Unsupported'),
                 description =  _('Import TMG project files'),
                 version = '0.0.75',
                 gramps_target_version = grampsversion,
                 include_in_listing = False,
                 status = UNSTABLE,
                 fname = 'importtmg.py',
                 import_function = 'importtmg',
                 extension = "tmg"
        )

        register(IMPORT,
                 id    = 'im_ver',
                 name  = _('TMG Unsupported'),
                 description =  _('Import TMG project files'),
                 version = '0.0.75',
                 gramps_target_version = grampsversion,
                 include_in_listing = False,
                 status = UNSTABLE,
                 fname = 'importtmg.py',
                 import_function = 'importver',
                 extension = "ver"
        )

from gramps.gen.config import logging
if not dbfavailable:
    warn_msg = _("TMG Importer Warning: DBF "
                 "(https://pypi.python.org/pypi/dbf)"
                 " is required for this importer to work")
    logging.log(logging.WARNING, warn_msg)

# don't start GUI if in CLI mode, just ignore
if not dbfavailable and locals().get('uistate'):
    from gramps.gui.dialog import QuestionDialog2
    if 'tmgimporterwarn' not in sects:
        yes_no = QuestionDialog2(
            _("TMG Importer Failed to Load"),
            _("\n\nTMG Importer is missing the DBF python module.\n"
              "DBF must be installed ( https://pypi.python.org/pypi/dbf ).\n\n"
              "For more information see\n<a href=\"https://gramps-project.org/wiki/index.php?"
              "title=Addon:TMGimporter\" "
              "title=\"https://gramps-project.org/wiki/index.php?"
              "title=Addon:TMGimporter\">https://gramps-project.org/wiki/index.php?"
              "title=Addon:TMGimporter</a> \n\n"
              "To dismiss all future TMG Importer warnings click Dismiss."),
            _(" Dismiss "),
            _("Continue"), parent=uistate.window)
        prompt = yes_no.run()
        if prompt is True:
            inifile.register('tmgimporterwarn.MissingModules', "")
            inifile.set('tmgimporterwarn.MissingModules', "True")
            inifile.save()
