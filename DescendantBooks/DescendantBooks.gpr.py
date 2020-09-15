#
# Copyright (C) 2011 Matt Keenan <matt.keenan@gmail.com>
# Copyright (C) 2019 Giansalvo Gusinu <giansalvo.gusinu@gmail.com>
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
register(REPORT,
    id   = 'DescendantBook',
    name = _('Descendant Book'),
    description = _("Produces one or more descendant reports based on a supplied query."),
    version = '1.1.24',
    gramps_target_version = "5.2",
    status = STABLE,
    fname = 'DescendantBookReport.py',
    authors = ["Matt Keenan", "Giansalvo Gusinu"],
    authors_email = ["matt.keenan@gmail.com", "giansalvo.gusinu@gmail.com"],
    category = CATEGORY_TEXT,
    reportclass = 'DescendantBookReport',
    optionclass = 'DescendantBookOptions',
    report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI],
    require_active = True
    )

register(REPORT,
    id   = 'DetailedDescendantBook',
    name = _('Detailed Descendant Book'),
    description = _("Produces one or more detailed descendant reports based on a supplied query."),
    version = '1.1.24',
    gramps_target_version = "5.2",
    status = STABLE,
    fname = 'DetailedDescendantBookReport.py',
    authors = ["Matt Keenan", "Giansalvo Gusinu"],
    authors_email = ["matt.keenan@gmail.com", "giansalvo.gusinu@gmail.com"],
    category = CATEGORY_TEXT,
    reportclass = 'DetailedDescendantBookReport',
    optionclass = 'DetailedDescendantBookOptions',
    report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI],
    require_active = True
    )

__author__ = "mattman"
