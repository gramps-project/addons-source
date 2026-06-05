#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2015 Douglas Blank <doug.blank@gmail.com>
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#
from gramps.gen.plug._pluginreg import register, STABLE, DATABASE
from gramps.gen.const import GRAMPS_LOCALE as glocale

_ = glocale.translation.gettext

register(
    DATABASE,
    id="sqlite-with-select",
    name=_("SQLite with Select"),
    name_accell=_("_SQLite with Select Database"),
    description=_("SQLite with Select Database"),
    version="1.0.0",
    gramps_target_version="6.0",
    status=STABLE,
    fname="sqlite_with_select.py",
    databaseclass="SQLiteWithSelect",
    authors=["Doug Blank"],
    authors_email=["doug.blank@gmail.com"],
)
