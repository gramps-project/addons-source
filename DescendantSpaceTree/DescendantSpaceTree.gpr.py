# -------------------------------------------------------------------------
#
# Copyright 2018-2025  Thomas S. Poindexter <tpoindex@gmail.com>
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
# ------------------------------------------------------------------------
# See LICENSE.txt for the full text of the license.
# ------------------------------------------------------------------------

register(
    REPORT,
    id="descendantspacetree",
    name=_("Descendant Space Tree"),
    category=CATEGORY_WEB,
    status=STABLE,
    fname="DescendantSpaceTree.py",
    reportclass="DescendantSpaceTreeReport",
    optionclass="DescendantSpaceTreeOptions",
    report_modes=[REPORT_MODE_GUI, REPORT_MODE_CLI],
    authors=["Tom Poindexter"],
    authors_email=["tpoindex@gmail.com"],
    description=_(
        "Generates a web page with an interactive "
        "graph of descendants represented "
        "as a Space Tree for efficient viewing, even "
        "with many descendants or generations."
    ),
    version="1.0.0",
    gramps_target_version="6.0",
)
