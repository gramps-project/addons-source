#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2008, 2009 Reinhard Mueller
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
register(REPORT,
    id   = 'FamilySheet',
    name = _('Family Sheet'),
    description = _("Produces a family sheet showing full information "
                    "about a person and his/her partners and children."),
    version = '2.0',
    gramps_target_version = '3.3',
    status = STABLE,
    fname = 'FamilySheet.py',
    authors = ["Reinhard Mueller"],
    authors_email = ["reinhard.mueller@bytewise.at"],
    category = CATEGORY_TEXT,
    reportclass = 'FamilySheet',
    optionclass = 'FamilySheetOptions',
    report_modes = [REPORT_MODE_GUI],
    require_active = True
    )
