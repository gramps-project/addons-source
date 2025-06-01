#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Yurii Liubymyi <jurchello@gmail.com>
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

# ----------------------------------------------------------------------------

"""
Module providing a lightweight chainable query interface for in-memory records.

The RecordQuery class enables basic filtering and querying of lists of dictionaries
using chainable `.where()` conditions. Supports retrieving all matching records or
just the first one.

Example usage:
    query = RecordQuery(records)
    result = query.where("name", "John").get()
    result = query.where(name="John").first()
"""


class RecordQuery:
    """Chainable query builder for filtering in-memory list of record dictionaries."""

    def __init__(self, records: list, dbtable):
        """Initialize the RecordQuery with a list of record dictionaries."""
        self._records = records
        self._conditions = []
        self._order_by_key = None
        self._reverse = False
        self._dbtable = dbtable

    def where(self, *args, **kwargs):
        """Add one or more filtering conditions to the query."""
        if args and len(args) == 2:
            field_name, value = args
            self._conditions.append((field_name, value))
        for field_name, value in kwargs.items():
            self._conditions.append((field_name, value))
        return self

    def sort_by(self, key, direction="asc"):
        """Set the sorting key and direction ('asc' or 'desc') for the query results."""
        self._order_by_key = key
        self._reverse = direction.lower() == "desc"
        return self

    def count(self):
        """Return the number of matching records."""
        return len(self.get())

    def exists(self):
        """Return True if at least one record matches the query conditions."""
        return bool(self.get())

    def get(self):
        """Execute the query and return all matching records."""
        result = self._records
        for field, value in self._conditions:
            result = [r for r in result if r.get(field) == value]
        if self._order_by_key:
            result = sorted(
                result, key=lambda x: x.get(self._order_by_key), reverse=self._reverse
            )
        return result

    def first(self):
        """Return the first matching record from the query"""
        results = self.get()
        return results[0] if results else None

    def values_list(self, field):
        """Return a list of values for a single field from filtered records."""
        return [r[field] for r in self.get() if field in r]

    def all_values_list(self, field):
        """Return a list of values for a single field from filtered records (respects where())."""
        return [r[field] for r in self.get() if field in r]

    def delete(self):
        """Remove matching records from the original record list and save changes."""
        to_delete = set(id(r) for r in self.get())
        self._records[:] = [r for r in self._records if id(r) not in to_delete]
        if self._dbtable:
            self._dbtable.save_data(self._records)
        return self
