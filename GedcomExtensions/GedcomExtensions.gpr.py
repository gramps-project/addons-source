#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2012 Doug Blank <doug.blank@gmail.com>
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

# $Id: $

# ------------------------------------------------------------------------
#
# Extensions to the GEDCOM format (GED2)
#
# ------------------------------------------------------------------------

register(
    EXPORT,
    id="Export GEDCOM Extensions",
    name=_("Export GEDCOM Extensions (GED2)"),
    name_accell=_("GEDCOM Extensions (GED2)"),
    description=_("Extensions to the common GEDCOM format."),
    version = '1.0.40',
    gramps_target_version="6.0",
    status=STABLE,
    audience=EXPERT,
    fname="GedcomExtensions.py",
    export_function="export_data",
    export_options="GedcomWriterOptionBox",
    export_options_title=_("GEDCOM Extensions options"),
    extension="ged2",
    help_url="Addon:GEDCOM_Extensions",
)
