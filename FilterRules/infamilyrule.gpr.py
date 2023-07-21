#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020  Paul Culley
# Copyright (C) 2020  Matthias Kemmer
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
"""Filter rule that matches people who are matched by a family filter."""

register(RULE,
  id = 'PersonsInFamilyFilterMatch',
  name = _('People who are part of families matching <filter>'),
  description = _('People who are part of families matching <filter>'),
  version = '1.0.17',
  authors = ["Matthias Kemmer", "Paul Culley"],
  authors_email = ["matt.familienforschung@gmail.com", "paulr2787@gmail.com"],
  gramps_target_version = '5.2',
  status = STABLE,
  fname = "infamilyrule.py",
  ruleclass = 'PersonsInFamilyFilterMatch',  # must be rule class name
  namespace = 'Person',  # one of the primary object classes
  )
