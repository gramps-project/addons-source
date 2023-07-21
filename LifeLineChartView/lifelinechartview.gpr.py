# encoding:utf-8
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020 Christian Schulze
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
         id='lifelinechartancestorview',
         name=_("Life Line Ancestor Chart"),
         category=("Ancestry", _("Charts")),
         description=_("Persons and their relation in a time based chart"),
         version = '1.3.21',
         gramps_target_version="5.2",
         status=STABLE,
         fname='lifelinechartview.py',
         authors=["Christian Schulze"],
         authors_email=["c.w.schulze@gmail.com"],
         viewclass='LifeLineChartAncestorView',
         icons = [('gramps-lifelineancestorchart-bw', _('Life Line Chart'))],
         stock_icon='gramps-lifelineancestorchart-bw',
         requires_mod=['life_line_chart', 'svgwrite'],
         )
register(VIEW,
         id='lifelinechartdescendantview',
         name=_("Life Line Descendant Chart"),
         category=("Ancestry", _("Charts")),
         description=_("Persons and their relation in a time based chart"),
         version = '1.3.21',
         gramps_target_version="5.2",
         status=STABLE,
         fname='lifelinechartview.py',
         authors=["Christian Schulze"],
         authors_email=["c.w.schulze@gmail.com"],
         viewclass='LifeLineChartDescendantView',
         icons = [('gramps-lifelineancestorchart-bw', _('Life Line Chart'))],
         stock_icon='gramps-lifelinedescendantchart-bw',
         requires_mod=['life_line_chart', 'svgwrite'],
         )
