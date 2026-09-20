# -*- coding: utf-8 -*-
#
# KinshipSort - biological kinship sorting for Gramps
# Copyright (C) 2026 Jacek Kuznia <jacek.kuznia@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <https://www.gnu.org/licenses/>.
#

register(
    VIEW,
    id="KinshipSortListView",
    name=_("People by kinship degree"),
    description=_(
        "People with biological kinship degrees relative to the Home Person "
        "and sortable columns."
    ),
    version="0.2.8",
    gramps_target_version="6.0",
    status=EXPERIMENTAL,
    fname="kinshipsort.py",
    authors=["Jacek Kuznia"],
    authors_email=["jacek.kuznia@gmail.com"],
    maintainers=["Jacek Kuznia"],
    maintainers_email=["jacek.kuznia@gmail.com"],
    requires_gi=[("Gtk", "3.0")],
    category=("People", _("People")),
    viewclass="KinshipSortListView",
    stock_icon="gramps-tree-list",
)

register(
    VIEW,
    id="KinshipSortTreeView",
    name=_("People by kinship, grouped"),
    description=_(
        "People grouped by surname, with biological kinship degrees "
        "relative to the Home Person."
    ),
    version="0.2.8",
    gramps_target_version="6.0",
    status=EXPERIMENTAL,
    fname="kinshipsort.py",
    authors=["Jacek Kuznia"],
    authors_email=["jacek.kuznia@gmail.com"],
    maintainers=["Jacek Kuznia"],
    maintainers_email=["jacek.kuznia@gmail.com"],
    requires_gi=[("Gtk", "3.0")],
    category=("People", _("People")),
    viewclass="KinshipSortTreeView",
    stock_icon="gramps-tree-group",
)
