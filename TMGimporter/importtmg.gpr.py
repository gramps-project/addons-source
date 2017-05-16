#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2017 Sam Manzi
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
# Set up logging
#
#------------------------------------------------------------------------
import logging
LOG = logging.getLogger(".TMGImport")

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------
from gramps.gui.dialog import ErrorDialog
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.sgettext

#------------------------------------------------------------------------
#
# Register TMG Importer
#
#------------------------------------------------------------------------
dbfavailable = False
addonversion = '0.0.63'
grampsversion = "5.0"

try:
    # External Library: dbf.pypi
    # https://pypi.python.org/pypi/dbf
    import dbf
    print("DBF version = ", dbf.version)
    dbfavailable = True
except ImportError:
    '''
    ErrorDialog(_('DBF could not be found'),
                _('TMG Import Addon requires DBF 0.96.8 or greater to function.'),
                _('Please install DBF from https://pypi.python.org/pypi/dbf '))
    '''
    print("DBF could not be found")
    dbfavailable = False

if dbfavailable:
    register(IMPORT,
             id    = 'im_sqz',
             name  = _('TMG Project Backup'),
             description =  _('Import TMG project files'),
             version = addonversion,
             gramps_target_version = grampsversion,
             include_in_listing = False,
             status = STABLE,
             fname = 'importtmg.py',
             import_function = 'importSqzData',
             extension = "sqz"
    )

    register(IMPORT,
             id    = 'im_pjc',
             name  = _('TMG Unsupported'),
             description =  _('Import TMG project files'),
             version = addonversion,
             gramps_target_version = grampsversion,
             include_in_listing = False,
             status = UNSTABLE,
             fname = 'importtmgunsupported.py',
             import_function = 'importpjc',
             extension = "pjc"
    )

    register(IMPORT,
             id    = 'im_tmg',
             name  = _('TMG Unsupported'),
             description =  _('Import TMG project files'),
             version = addonversion,
             gramps_target_version = grampsversion,
             include_in_listing = False,
             status = UNSTABLE,
             fname = 'importtmgunsupported.py',
             import_function = 'importtmg',
             extension = "tmg"
    )

    register(IMPORT,
             id    = 'im_ver',
             name  = _('TMG Unsupported'),
             description =  _('Import TMG project files'),
             version = addonversion,
             gramps_target_version = grampsversion,
             include_in_listing = False,
             status = UNSTABLE,
             fname = 'importtmgunsupported.py',
             import_function = 'importver',
             extension = "ver"
    )

