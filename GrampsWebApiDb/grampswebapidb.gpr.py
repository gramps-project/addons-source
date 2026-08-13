#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026 Douglas S. Blank <doug.blank@gmail.com>
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
register(
    DATABASE,
    id="grampswebapidb",
    status=BETA,
    name=_("GrampsWebApiDb"),
    name_accell=_("Gramps _Web API Database"),
    description=_(
        "Use a Gramps Web API server (e.g. gramps-connect or Gramps Web) "
        "as a live database, mirrored locally for speed."
    ),
    version = '0.1.3',
    gramps_target_version="6.1",
    fname="grampswebapidb.py",
    databaseclass="WebApiDB",
    authors=["Doug Blank"],
    authors_email=["doug.blank@gmail.com"],
    help_url="Addon:GrampsWebApiDb",
)
