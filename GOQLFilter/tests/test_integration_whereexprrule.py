#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026       Douglas Blank
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

"""Integration tests for ``whereexprrule.py``.

Drives the rule the same way ``GenericFilter.apply()`` does -- through a
real ``GenericFilter``/``CacheProxyDb`` against a real temp SQLite db, since
that composition (Rule -> GenericFilter -> what a gramplet hands to
``view.generic_filter``) is the thing actually being tested, not the GOQL
compiler in isolation (already covered by gramps-object-query-language's
own test suite). DB-backed, so this is Linux-only in CI (``test_integration_``
prefix) rather than the plain ``test_`` prefix.

Run with::

    python3 -m unittest GOQLFilter.tests.test_integration_whereexprrule -v
"""

import os
import shutil
import sys
import tempfile
import unittest

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    import gi
except ImportError as err:
    raise unittest.SkipTest("PyGObject not available: %s" % err)

try:
    from whereexprrule import (
        FamilyMatchesExpression,
        PersonMatchesExpression,
        _resolve_dialect,
        _unwrap_cache_proxy,
    )
except ImportError as exc:
    raise unittest.SkipTest(
        "whereexprrule import failed (likely missing "
        "gramps-object-query-language): %s" % exc
    )

from gramps.gen.db import DbTxn
from gramps.gen.db.utils import make_database
from gramps.gen.filters import GenericFilterFactory
from gramps.gen.lib import Family, Name, Person, Surname
from gramps.gen.proxy import CacheProxyDb, PrivateProxyDb
from gramps_object_query_language.query import Dialect


def _name(given, surname):
    name = Name()
    name.set_first_name(given)
    surn = Surname()
    surn.set_surname(surname)
    name.set_surname_list([surn])
    return name


# ------------------------------------------------------------
#
# WhereExprRuleTest
#
# ------------------------------------------------------------
class WhereExprRuleTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="goql_addon_")
        self.db = make_database("sqlite")
        self.db.load(self.tmp_dir)

        self.handles = {}
        with DbTxn("build test db", self.db) as trans:
            father = Person()
            father.set_primary_name(_name("Karl", "Anderson"))
            father.set_gender(Person.MALE)
            self.handles["father"] = self.db.add_person(father, trans)

            mother = Person()
            mother.set_primary_name(_name("Lena", "Baker"))
            mother.set_gender(Person.FEMALE)
            self.handles["mother"] = self.db.add_person(mother, trans)

            son = Person()
            son.set_primary_name(_name("Otto", "Anderson"))
            son.set_gender(Person.MALE)
            self.handles["son"] = self.db.add_person(son, trans)

            family = Family()
            family.set_father_handle(self.handles["father"])
            family.set_mother_handle(self.handles["mother"])
            self.handles["family"] = self.db.add_family(family, trans)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _apply_person_filter(self, expr):
        gfilter = GenericFilterFactory("Person")()
        gfilter.add_rule(PersonMatchesExpression([expr]))
        cdb = CacheProxyDb(self.db)
        return set(gfilter.apply(cdb, self.db.get_person_handles()))

    def test_flat_column_match(self):
        matched = self._apply_person_filter("gender == Person.MALE")
        self.assertEqual(matched, {self.handles["father"], self.handles["son"]})

    def test_json_path_and_boolean_combination(self):
        matched = self._apply_person_filter(
            "gender == Person.MALE and "
            "'Anderson' in primary_name.surname_list[0].surname"
        )
        self.assertEqual(matched, {self.handles["father"], self.handles["son"]})

    def test_no_match(self):
        matched = self._apply_person_filter("gender == Person.UNKNOWN")
        self.assertEqual(matched, set())

    def test_empty_expression_matches_nothing(self):
        matched = self._apply_person_filter("")
        self.assertEqual(matched, set())

    def test_invalid_expression_matches_nothing_rather_than_raising(self):
        matched = self._apply_person_filter("this is not valid GOQL !!")
        self.assertEqual(matched, set())

    def test_family_related_object_path(self):
        gfilter = GenericFilterFactory("Family")()
        gfilter.add_rule(FamilyMatchesExpression(["father.surname == 'Anderson'"]))
        cdb = CacheProxyDb(self.db)
        matched = set(gfilter.apply(cdb, self.db.get_family_handles()))
        self.assertEqual(matched, {self.handles["family"]})


# ------------------------------------------------------------
#
# SqlPushDownTest
#
# ------------------------------------------------------------
class SqlPushDownTest(unittest.TestCase):
    """Regression coverage for two bugs found wiring up SQL push-down:

    1. ``_resolve_dialect`` used to do ``isinstance(db, SQLite)``, but
       Gramps' plugin loader imports ``sqlite.py`` as a bare top-level
       module named ``sqlite``, not via ``gramps.plugins.db.dbapi.sqlite``
       -- so a live ``dbstate.db``'s class is never ``isinstance``-
       compatible with a normally-imported ``SQLite``, and dialect
       resolution silently fell through every time. Fixed by matching
       ``type(db).__name__`` instead of ``isinstance``.
    2. Every real filter application wraps ``db`` in ``CacheProxyDb``
       (``gui/views/treemodels/flatbasemodel.py``'s ``_rebuild_filter``:
       ``cdb = CacheProxyDb(self.db); self.search.apply(cdb, ...)``), which
       is not a ``ProxyDbBase`` subclass and forwards attribute access via
       ``__getattr__``. Left unpeeled, that defeats the
       ``isinstance(db, ProxyDbBase)`` privacy check whenever a real
       privacy proxy is nested *underneath* it
       (``CacheProxyDb(PrivateProxyDb(db))``) -- SQL would run straight
       past privacy filtering. Fixed with ``_unwrap_cache_proxy``.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="goql_sql_pushdown_")
        self.db = make_database("sqlite")
        self.db.load(self.tmp_dir)
        with DbTxn("build test db", self.db) as trans:
            father = Person()
            father.set_primary_name(_name("Karl", "Anderson"))
            father.set_gender(Person.MALE)
            self.father_handle = self.db.add_person(father, trans)

            mother = Person()
            mother.set_primary_name(_name("Lena", "Baker"))
            mother.set_gender(Person.FEMALE)
            self.mother_handle = self.db.add_person(mother, trans)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_resolve_dialect_matches_live_sqlite_db_by_class_name(self):
        self.assertEqual(_resolve_dialect(self.db), Dialect.SQLITE)

    def test_resolve_dialect_is_none_for_an_unrecognized_backend(self):
        self.assertIsNone(_resolve_dialect(object()))

    def test_unwrap_cache_proxy_peels_to_the_raw_db(self):
        cdb = CacheProxyDb(self.db)
        self.assertIs(_unwrap_cache_proxy(cdb), self.db)

    def test_unwrap_cache_proxy_stops_at_a_nested_privacy_proxy(self):
        pdb = PrivateProxyDb(self.db)
        cdb = CacheProxyDb(pdb)
        self.assertIs(_unwrap_cache_proxy(cdb), pdb)

    def test_sql_push_down_engages_through_the_cache_proxy_wrapping(self):
        """The exact wrapping every real GenericFilter.apply() call uses."""
        cdb = CacheProxyDb(self.db)
        rule = PersonMatchesExpression(["gender == Person.MALE"])

        rule.prepare(cdb, None)

        self.assertEqual(rule.selected_handles, {self.father_handle})

    def test_privacy_proxy_nested_under_cache_proxy_disables_sql_push_down(self):
        cdb = CacheProxyDb(PrivateProxyDb(self.db))
        rule = PersonMatchesExpression(["gender == Person.MALE"])

        rule.prepare(cdb, None)

        self.assertIsNone(rule.selected_handles)
        # Still correct via the per-object eval fallback:
        father = cdb.get_person_from_handle(self.father_handle)
        mother = cdb.get_person_from_handle(self.mother_handle)
        self.assertTrue(rule.apply_to_one(cdb, father))
        self.assertFalse(rule.apply_to_one(cdb, mother))

    def test_optimizer_recognizes_selected_handles(self):
        """Regression test for the actual ~8s "Apply time" bug: the
        precomputed match set used to be stored as ``_matched_handles``,
        a name ``gen.filters.optimizer.Optimizer`` doesn't look for.
        ``compute_potential_handles_for_rule`` only checks
        ``hasattr(rule, "selected_handles")`` -- anything else is
        invisible to it, so ``GenericFilter.apply()`` fetched and
        deserialized every candidate via ``get_object()`` before
        ``apply_to_one`` ever ran, no matter how fast ``apply_to_one``
        itself was. Renaming the attribute to what the Optimizer actually
        checks for is the fix; this asserts that contract directly rather
        than just re-checking ``apply_to_one``'s own behavior.
        """
        from gramps.gen.filters.optimizer import Optimizer

        cdb = CacheProxyDb(self.db)
        rule = PersonMatchesExpression(["gender == Person.MALE"])
        rule.prepare(cdb, None)

        optimizer = Optimizer(GenericFilterFactory("Person")())
        handles_in, handles_out = optimizer.compute_potential_handles_for_rule(rule)

        self.assertEqual(handles_in, {self.father_handle})
        self.assertIsNone(handles_out)


if __name__ == "__main__":
    unittest.main()
