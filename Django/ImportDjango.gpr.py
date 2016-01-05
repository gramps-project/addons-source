# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2008 - 2009  Douglas S. Blank <doug.blank@gmail.com>
# Copyright (C) 2009         B. Malengier <benny.malengier@gmail.com>
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
#

#------------------------------------------------------------------------
#
# Set up logging
#
#------------------------------------------------------------------------
import logging
LOG = logging.getLogger(".ImportDjango")

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------

from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.sgettext

#------------------------------------------------------------------------
#
# Register Addon if prerequisite is present.
#
#------------------------------------------------------------------------

available = False

try:
    from django.conf import settings
    available = True
except ImportError:
    pass

if available:
    # Load the Addon only if the prerequisite is present.
    register(IMPORT,
             id                   = "import_django",
             name                 = _('Django Import'),
             description          = _('Django is a web framework working on a '
                                      'configured database'),
             version = '1.0.30',
             gramps_target_version= '5.0',
             status               = STABLE,
             import_function      = 'import_data',
             extension            = "django",
             fname                = "ImportDjango.py",
             )
    LOG.info("ImportDjango Addon loaded successfully")
else:
    LOG.warn("Prerequiste: Django not installed. ImportDjango function disabled")
    from gramps.gen.config import config
    if not config.is_set('importdjango.ignore-django'):
        from gramps.gen.constfunc import has_display
        if has_display():
            from gramps.gui.dialog import MessageHideDialog
            title = _("django.conf could not be found")
            message = _("Django Import Addon requires Django 1.7 or greater")
            #MessageHideDialog(title, message, 'importdjango.ignore-django') # fails with
            ####################### AttributeError: No such config section name: 'importdjango'
            ##########################################################
            from gramps.gui.dialog import ErrorDialog
            #ErrorDialog(_(title),
            #            _(message))

