#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025      Doug Blank
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

"""
Builds the runtime completion namespace: real live objects for the DSL
names whose fields are safe and useful to introspect directly.

active_person/active_family/etc. are deliberately NOT included here --
see stub_generator.ACTIVE_VARIABLES. They're handled as static
annotations instead, because completing through them would otherwise
require jedi to actually call DataDict2's computed @property methods
(father, birth, ...) to see what they return, executing real
SimpleAccess lookups for no benefit (a blank template has nothing to
find anyway).

Kept free of GTK imports so it can be developed and tested without a
running Gramps/GTK environment.
"""

import datetime
from collections import defaultdict

from gramps.gen.lib import Date


def build_namespace(database=None):
    """
    Return a namespace dict for get_completions(), covering the
    directly-bound DSL names in execute_code() that are safe to
    introspect as live objects: today, counter, and database.

    `database` is the real Gramps database (self.dbstate.db). Passing it
    enables completion of its real methods (database.get_person_from_handle,
    ...); it's optional since dir() on it never executes anything.
    """
    today = datetime.date.today()
    namespace = {
        "today": Date(today.year, today.month, today.day),
        "counter": lambda: defaultdict(int),
    }
    if database is not None:
        namespace["database"] = database
    return namespace
