#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2024      Nick Hall
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

#------------------------------------------------------------------------
#
# GraphML
#
#------------------------------------------------------------------------

register(EXPORT,
         id = "ex_person_gexf",
         name = _('Person GEXF'),
         name_accell = _('_Person GEXF'),
         description = _('GEXF is used in many network graph applications.'),
         version = '1.0.1',
         gramps_target_version = '5.2',
         status = BETA,
         audience = EXPERT,
         fname = 'exportpersongexf.py',
         export_function = 'exportData',
         export_options = 'WriterOptionBox',
         export_options_title = _('GEXF export options'),
         extension = 'gexf',
         include_in_listing = True,
        )
