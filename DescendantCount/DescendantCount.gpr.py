#
# Copyright (C) 2009  Douglas S. Blank <doug.blank@gmail.com>
# Copyright (C) 2016  Serge Noiraud <serge.noiraud@free.fr>
# Copyright (C) 2017  Paul Culley <paulr2787@gmail.com>
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

register(GRAMPLET,
         id="Descendant Count Gramplet",
         name=_("Descendant Count"),
         description = _("Gramplet for showing people and descendant counts"),
         status= STABLE,
         fname="DescendantCount.py",
         authors=["Douglas S. Blank, Paul Culley"],
         authors_email=["doug.blank@gmail.com, paulr2787@gmail.com"],
         height=300,
         expand=True,
         gramplet = "DescendantCountGramplet",
         gramplet_title=_("Descendant Count"),
         detached_width = 600,
         detached_height = 400,
         version = '2.0.9',
         gramps_target_version = "5.1",
         help_url="Descendant_Count_Gramplet",
         )

