#
# Gramps - a GTK+/GNOME based genealogy program - What Next Gramplet plugin
#
# Copyright (C) 2010  Peter Potrowl <peter017@gmail.com>
# Copyright (C) 2019  Matthias Kemmer <matt.familienforschung@gmail.com>
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

register(GRAMPLET,
    id = 'Birthdays',
    name = _("Birthdays"),
    description = _("a gramplet that displays the birthdays of the living people"),
    status = STABLE,
    version = '1.1.12',
    fname="BirthdaysGramplet.py",
    height = 200,
    gramplet = 'BirthdaysGramplet',
    gramps_target_version = "5.2",
    gramplet_title = _("Birthdays"),
    help_url = "BirthdaysGramplet",
    )
