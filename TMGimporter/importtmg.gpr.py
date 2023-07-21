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
grampsversion = "5.2"

register(IMPORT,
         id    = 'im_sqz',
         name  = _('TMG Project Backup'),
         description =  _('Import TMG project files'),
         version = '0.0.78',
         gramps_target_version = grampsversion,
         include_in_listing = False,
         status = STABLE,
         fname = 'importtmg.py',
         import_function = 'importSqzData',
         extension = "sqz", # Only detects lower case extensions (TODO: add SQZ uppercase)
         requires_mod=['dbf'],
)
if direct_tmg_pjc_ver_support:
# Only Load when importer directly supports (tmg/pjc/ver)
    register(IMPORT,
             id    = 'im_pjc',
             name  = _('TMG Unsupported'),
             description =  _('Import TMG project files'),
             version = '0.0.78',
             gramps_target_version = grampsversion,
             include_in_listing = False,
             status = UNSTABLE,
             fname = 'importtmg.py',
             import_function = 'importpjc',
             extension = "pjc",
             requires_mod=['dbf'],
    )

    register(IMPORT,
             id    = 'im_tmg',
             name  = _('TMG Unsupported'),
             description =  _('Import TMG project files'),
             version = '0.0.78',
             gramps_target_version = grampsversion,
             include_in_listing = False,
             status = UNSTABLE,
             fname = 'importtmg.py',
             import_function = 'importtmg',
             extension = "tmg",
             requires_mod=['dbf'],
    )

    register(IMPORT,
             id    = 'im_ver',
             name  = _('TMG Unsupported'),
             description =  _('Import TMG project files'),
             version = '0.0.78',
             gramps_target_version = grampsversion,
             include_in_listing = False,
             status = UNSTABLE,
             fname = 'importtmg.py',
             import_function = 'importver',
             extension = "ver",
             requires_mod=['dbf'],
    )
