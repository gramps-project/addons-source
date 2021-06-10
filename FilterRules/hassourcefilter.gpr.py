#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2017       Dave Scheipers
# Copyright (C) 2017       Paul Culley
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

"""
Filter rule to match source with a particular value.
"""
register(RULE,
  id    = 'HasSourceParameter',
  name  = _("Source matching parameters"),
  description = _("Matches Sources with values containing the chosen parameters"),
  version = '0.0.15',
  authors = ["Dave Scheipers", "Paul Culley"],
  authors_email = ["paulr2787@gmail.com"],
  gramps_target_version = '5.1',
  status = STABLE,
  fname = "hassourcefilter.py",
  ruleclass = 'HasSourceParameter',  # must be rule class name
  namespace = 'Source',  # one of the primary object classes
  )