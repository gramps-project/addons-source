#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026      Doug Blank
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

"""Integration tests for ``goql_support.py`` against a real temp SQLite db,
on both the SQL path and the per-record fallback (behind a proxy).

Needs the GOQLFilter addon next to this one, as in addons-source itself.

Run with::

    python3 -m unittest GrampyScript.tests.test_integration_goql_support -v
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

from gramps.gen.db import DbTxn
from gramps.gen.db.utils import make_database
from gramps.gen.lib import Date, Event, EventRef, EventType, Name, Person, Surname
from gramps.gen.proxy import PrivateProxyDb

try:
    import goql_support
    from goql_support import (
        GOQLUnavailableError,
        load_goql,
        make_iterator,
        query_handles,
    )

    load_goql()
except ImportError as err:
    raise unittest.SkipTest("GOQLFilter addon not available: %s" % err)


def _person(given, surname, gender, year=None, private=False):
    name = Name()
    name.set_first_name(given)
    surn = Surname()
    surn.set_surname(surname)
    name.set_surname_list([surn])
    person = Person()
    person.set_primary_name(name)
    person.set_gender(gender)
    person.set_privacy(private)
    return person, year


# ------------------------------------------------------------
#
# QueryHandlesTest
#
# ------------------------------------------------------------
class QueryHandlesTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="grampyscript_goql_")
        self.db = make_database("sqlite")
        self.db.load(self.tmp_dir)
        self.handles = {}
        people = [
            _person("Karl", "Anderson", Person.MALE, 1850),
            _person("Lena", "Baker", Person.FEMALE, 1855),
            _person("Otto", "Anderson", Person.MALE, 1880),
            _person("Greta", "Carlson", Person.FEMALE, None, private=True),
        ]
        with DbTxn("build test db", self.db) as trans:
            for person, year in people:
                if year is not None:
                    event = Event()
                    event.set_type(EventType.BIRTH)
                    event.set_date_object(Date(year))
                    ref = EventRef()
                    ref.set_reference_handle(self.db.add_event(event, trans))
                    person.add_event_ref(ref)
                    person.set_birth_ref(ref)
                handle = self.db.add_person(person, trans)
                self.handles[person.get_primary_name().get_first_name()] = handle

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def names(self, handles):
        by_handle = {handle: name for name, handle in self.handles.items()}
        return [by_handle[handle] for handle in handles]

    def test_where_flat_column(self):
        handles = query_handles(self.db, "person", "gender == Person.MALE")
        self.assertEqual(sorted(self.names(handles)), ["Karl", "Otto"])

    def test_where_across_relationship(self):
        handles = query_handles(
            self.db, "person", "birth.date.sortval >= Date('1855')"
        )
        self.assertEqual(sorted(self.names(handles)), ["Lena", "Otto"])

    def test_order_and_limit(self):
        order = [{"column": "given_name", "direction": "desc"}]
        handles = query_handles(self.db, "person", order=order, limit=2)
        self.assertEqual(self.names(handles), ["Otto", "Lena"])

    def test_blank_where_matches_everything(self):
        self.assertEqual(len(query_handles(self.db, "person", "  ")), 4)

    def test_other_table(self):
        self.assertEqual(len(query_handles(self.db, "event", limit=None)), 3)

    def test_proxied_db_uses_fallback(self):
        proxy = PrivateProxyDb(self.db)
        order = [{"column": "given_name", "direction": "asc"}]
        handles = query_handles(proxy, "person", "gender == Person.FEMALE", order)
        # Greta is private, so the proxy hides her.
        self.assertEqual(self.names(handles), ["Lena"])

    def test_bad_where_raises(self):
        with self.assertRaises(ValueError):
            query_handles(self.db, "person", "no_such_field == 1")


# ------------------------------------------------------------
#
# MakeIteratorTest
#
# ------------------------------------------------------------
class MakeIteratorTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="grampyscript_iter_")
        self.db = make_database("sqlite")
        self.db.load(self.tmp_dir)
        with DbTxn("build test db", self.db) as trans:
            for i in range(55):
                person, _year = _person("P%02d" % i, "Smith", i % 2)
                self.db.add_person(person, trans)
        self.people = make_iterator(self.db, "Person", lambda data: data)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_default_limit_is_50_in_handle_order(self):
        handles = [data["handle"] for data in self.people()]
        self.assertEqual(handles, sorted(self.db.get_person_handles())[:50])

    def test_limit_none_returns_everything(self):
        self.assertEqual(len(list(self.people(limit=None))), 55)

    def test_explicit_limit_without_where(self):
        self.assertEqual(len(list(self.people(limit=5))), 5)

    def test_plain_calls_dont_need_goql(self):
        with mock.patch.object(
            goql_support, "query_handles", side_effect=AssertionError
        ):
            self.assertEqual(len(list(self.people())), 50)
            self.assertEqual(len(list(self.people(limit=None))), 55)

    def test_where_keeps_default_limit(self):
        males = list(self.people(where="gender == Person.MALE"))
        self.assertEqual(len(males), 27)
        self.assertEqual(len(list(self.people(where="surname == 'Smith'"))), 50)


# ------------------------------------------------------------
#
# MissingGOQLFilterTest
#
# ------------------------------------------------------------
class MissingGOQLFilterTest(unittest.TestCase):
    def test_raises_install_message(self):
        loaded = {
            name: module
            for name, module in sys.modules.items()
            if name.startswith(goql_support.GOQL_PACKAGE)
        }
        with mock.patch.object(goql_support, "_goql", None), mock.patch.object(
            goql_support, "_goqlfilter_dirs", return_value=[]
        ), mock.patch.dict(sys.modules):
            for name in loaded:
                del sys.modules[name]
            with self.assertRaises(GOQLUnavailableError) as ctx:
                load_goql()
        self.assertIn("GOQL Filter addon", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
