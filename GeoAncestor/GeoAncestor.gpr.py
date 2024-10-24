# encoding:utf-8
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2016-     Serge Noiraud
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
# Geography view for the ancestor view
#
#------------------------------------------------------------------------

register(VIEW,
         id='geoancestor',
         name=_("Ancestors map"),
         description=_("A view showing ancestors places on the map."),
         version = '1.0.10',
         gramps_target_version='5.2',
         status=STABLE,
         fname='GeoAncestor.py',
         authors=["Serge Noiraud"],
         authors_email=[""],
         category=("Geography", _("Geography")),
         viewclass='GeoAncestor',
         icons = [('geo-ancestor', _('Ancestors map'))],
         stock_icon='geo-ancestor',
         requires_gi=[('OsmGpsMap', '1.0')],
         )
