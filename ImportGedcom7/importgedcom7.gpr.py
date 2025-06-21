# Copyright (C) 2025 David Straub
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

"""Import a Gedcom 7 file into Gramps."""

register(
    IMPORT,
    id="im_ged7",
    name=_("GEDCOM 7"),
    description=_("Import GEDCOM 7 files"),
    version = "0.1.0",
    gramps_target_version="6.0",
    status=BETA,
    fname="import_gedcom7.py",
    import_function="import_data",
    extension="ged7",
    requires_mod=["gramps_gedcom7"],
)
