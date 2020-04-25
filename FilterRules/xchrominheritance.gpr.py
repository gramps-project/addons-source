#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020    Matthias Kemmer
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
"""X-chromosomal inheritance of <person>."""

register(RULE,
  id = 'xchrominheritance',
  name = _("X-chromosomal inheritance of <person>"),
  description = _("Matches people contributing to X-chromosomal inheritance of <person>."),
  version = '1.0.0',
  authors = ["Matthias Kemmer"],
  authors_email = ["matt.familienforschung@gmail.com"],
  gramps_target_version = '5.1',
  status = STABLE,
  fname = "xchrominheritance.py",
  ruleclass = 'XChromInheritance',  # must be rule class name
  namespace = 'Person',  # one of the primary object classes
  )
