# -*- python -*-
# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2011-2016  Serge Noiraud
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
register(VIEW,
         id='geotimelines',
         name=_("TimeLines Map"),
         description=_("A view showing all the places visited by a person or persons on various date."),
         version = '1.0.1',
         gramps_target_version='5.2',
         status=BETA,
         audience = EXPERT,
         help_url="https://gramps.discourse.group/t/timelines-map-addon-beta-testing/6130",
         fname='GeoTimeLines.py',
         authors=["Thomas B"],
         authors_email=[""],
         category=("Geography", _("Geography")),
         viewclass='GeoTimeLines',
         icons = [('geo-timelines', _('TimeLines map'))],
         stock_icon='geo-timelines',
         requires_gi=[('OsmGpsMap', '1.0')],
         )
