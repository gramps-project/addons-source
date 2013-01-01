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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

# $Id: $

#------------------------------------------------------------------------
#
# Extensions to the GEDCOM format (GED2)
#
#------------------------------------------------------------------------

plg = newplugin()
plg.id    = 'Export Gedcom Extensions'
plg.name  = _("Export Gedcom Extensions (GED2)")
plg.name_accell  = _("Gedcom Extensions (GED2)")
plg.description =  _("Extensions to the common GEDCOM format.")
plg.version = '1.0'
plg.gramps_target_version = '4.1'
plg.status = UNSTABLE # not yet tested with python 3, see bug 6092
plg.fname = 'GedcomExtensions.py'
plg.ptype = EXPORT
plg.export_function = 'export_data'
plg.export_options = 'GedcomWriterOptionBox'
plg.export_options_title = _('Gedcom Extensions options')
plg.extension = "ged2"

