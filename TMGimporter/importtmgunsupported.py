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

"Import from an Whollygenes - The Master Genealogist (TMG) Project backup file"

#-------------------------------------------------------------------------
#
# Standard Python Modules
#
#-------------------------------------------------------------------------
import logging
LOG = logging.getLogger(".TMGImport")

#-------------------------------------------------------------------------
#
# Gramps Modules
#
#-------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext
from gramps.gen.const import URL_WIKISTRING

#-------------------------------------------------------------------------
#
# Unsupported direct formats for importing data must be tmg sqz backup file
#
#-------------------------------------------------------------------------
def importpjc(database, filename, user):
    '''
    *.PJC - Project Configuration File for TMG 5.0 to TMG 9.05
    '''
    import_dict = { 'gramps_wiki_import_pjc_direct_url' :
                         URL_WIKISTRING +
                             "Addon:TMGimporter#"
                             "Unsupported_formats" }
    user.notify_error(_("%s could not be opened") % filename,
                      _("Directly importing from TMG files is not supported\n"
                        "by the TMG Importer Addon.\n\n"
                        "You need to use an backup copy of the TMG project(*.sqz)\n\n"
                        "Ensure that your TMG project was created by:\n"
                        "TMG version 5.x or greater.\n\n"
                        "Your file:\n"
                        "*.PJC - Project Configuration File for TMG 5.0 to TMG 9.05\n\n"
                        "Please refer to:\n"
                        "%(gramps_wiki_import_pjc_direct_url)s" ) %
                                import_dict )
    return

def importtmg(database, filename, user):
    '''
    *.TMG - Version Control File for TMG 2.0 to TMG 4.0d
    '''
    import_dict = { 'gramps_wiki_import_pjc_direct_url' :
                         URL_WIKISTRING +
                             "Addon:TMGimporter#"
                             "Unsupported_formats" }
    user.notify_error(_("%s could not be opened") % filename,
                      _("Directly importing from TMG files is not supported"
                        "by the TMG Importer Addon."
                        "You need to use an backup copy of TMG project(*.sqz)"
                        "Ensure that your TMG project was created by:"
                        "TMG version 5.x or greater."
                        "Your file:"
                        "*.TMG - Version Control File for TMG 2.0 to TMG 4.0d"
                        "Please refer to:"
                        "%(gramps_wiki_import_pjc_direct_url)s" ) %
                                import_dict )
    return

def importver(database, filename, user):
    '''
    *.VER - Version Control File for TMG 1.2 and earlier
    '''
    import_dict = { 'gramps_wiki_import_pjc_direct_url' :
                         URL_WIKISTRING +
                             "Addon:TMGimporter#"
                             "Unsupported_formats" }
    user.notify_error(_("%s could not be opened") % filename,
                      _("Directly importing from TMG files is not supported"
                        "by the TMG Importer Addon."
                        "You need to use an backup copy of TMG project(*.sqz)"
                        "Ensure that your TMG project was created by:"
                        "TMG version 5.x or greater."
                        "Your file:"
                        "*.VER - Version Control File for TMG 1.2 and earlier"
                        "Please refer to:"
                        "%(gramps_wiki_import_pjc_direct_url)s" ) %
                                import_dict )
    return
