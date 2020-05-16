#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2018       Paul Culley
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
Filter rule to match an Event Role with a particular value.
"""
register(RULE,
  id    = 'HasPersonEventRole',
  name  = _("People with events with a selected role"),
  description = _("Matches people with an event with a selected role"),
  version = '0.0.10',
  authors = ["Paul Culley"],
  authors_email = ["paulr2787@gmail.com"],
  gramps_target_version = '5.1',
  status = STABLE,
  fname = "hasrolerule.py",
  ruleclass = 'HasPersonEventRole',  # must be rule class name
  namespace = 'Person',  # one of the primary object classes
  )

register(RULE,
  id    = 'HasFamilyEventRole',
  name  = _("Families with events with a selected role"),
  description = _("Matches families with an event with a selected role"),
  version = '0.0.10',
  authors = ["Paul Culley"],
  authors_email = ["paulr2787@gmail.com"],
  gramps_target_version = '5.1',
  status = STABLE,
  fname = "hasrolerule.py",
  ruleclass = 'HasFamilyEventRole',  # must be rule class name
  namespace = 'Family',  # one of the primary object classes
  )
