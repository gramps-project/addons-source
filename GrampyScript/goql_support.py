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

"""people(), families(), and the other record iterators, and the GOQL
support behind their where= and order= arguments.

Uses the copy of gramps-object-query-language bundled with the GOQLFilter
addon (gramps_object_query_language_copy), so the same where string means
the same thing here as in GOQLFilter, in Gramps Web, and in Gramps
Connect's Gramplets. GOQLFilter must be installed; it's only needed once a
script actually passes where= or order=.

Like GOQLFilter's rules, a query runs as SQL when the database is an
unproxied DB-API backend, and falls back to evaluating each record in
Python otherwise.
"""

# ------------------------------------------------------------------------
#
# Standard Python modules
#
# ------------------------------------------------------------------------
import importlib
import logging
import os
import sys

# ------------------------------------------------------------------------
#
# Gramps modules
#
# ------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.plug import PluginRegister
from gramps.gen.proxy import CacheProxyDb
from gramps.gen.proxy.proxybase import ProxyDbBase

_ = glocale.translation.gettext

LOG = logging.getLogger(".GrampyScript.goql_support")

GOQL_PACKAGE = "gramps_object_query_language_copy"
# Any plugin registered from GOQLFilter's folder will do; this one is a
# rule, so it's registered whether or not its gramplets are shown.
GOQLFILTER_PLUGIN_ID = "PersonMatchesExpression"
GOQLFILTER_FOLDER = "GOQLFilter"

_SUBMODULES = ("query", "query_lang", "proxied_query")
_goql = None


class GOQLUnavailableError(ImportError):
    """The GOQLFilter addon, which bundles GOQL, isn't installed."""


def _goqlfilter_dirs():
    pdata = PluginRegister.get_instance().get_plugin(GOQLFILTER_PLUGIN_ID)
    if pdata is not None:
        yield pdata.fpath
    # Installed addons are sibling folders, so this also finds GOQLFilter
    # when the registry hasn't scanned it (e.g. under unittest).
    yield os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        GOQLFILTER_FOLDER,
    )


def _import_goql():
    return {
        name: importlib.import_module("%s.%s" % (GOQL_PACKAGE, name))
        for name in _SUBMODULES
    }


def load_goql():
    """GOQL's submodules (query, query_lang, proxied_query) as a dict.

    Already imported if GOQLFilter has been used this session. Otherwise
    GOQLFilter's folder goes on sys.path only for the import: the package
    uses relative imports throughout, so nothing needs it there afterwards.
    """
    global _goql
    if _goql is not None:
        return _goql
    if GOQL_PACKAGE in sys.modules:
        _goql = _import_goql()
        return _goql
    for path in _goqlfilter_dirs():
        if not os.path.isdir(os.path.join(path, GOQL_PACKAGE)):
            continue
        sys.path.insert(0, path)
        try:
            _goql = _import_goql()
            return _goql
        finally:
            sys.path.remove(path)
    raise GOQLUnavailableError(
        _(
            "where= and order= need the GOQL Filter addon; "
            "install it from the Addon Manager."
        )
    )


def _dialect(db, query):
    # Same lookup as GOQLFilter's whereexprrule._resolve_dialect().
    by_name = {
        "sqlite": query.Dialect.SQLITE,
        "postgres": query.Dialect.POSTGRESQL,
        "postgresql": query.Dialect.POSTGRESQL,
    }
    by_class_name = {
        "SQLite": query.Dialect.SQLITE,
        "PostgreSQL": query.Dialect.POSTGRESQL,
        "SharedPostgreSQL": query.Dialect.POSTGRESQL,
    }
    name = getattr(db, "dialect", None)
    if name and name in by_name:
        return by_name[name]
    return by_class_name.get(type(db).__name__)


def _order_by(query, order):
    """order is a list of {"column": ..., "direction": "asc"|"desc"}, the
    same shape Gramps Connect's people(order=...) takes."""
    if not order:
        return ()
    return tuple(
        query.OrderBy(item["column"], item.get("direction", "asc"))
        for item in order
    )


def query_handles(db, table, where=None, order=None, limit=None):
    """Handles of the table's records matching the GOQL where string, in
    order, at most limit of them (None for all).

    table is the lowercase table name: "person", "family", "event", ...
    """
    goql = load_goql()
    query = goql["query"]
    spec = getattr(query, table.upper())
    where_ast = None
    if where is not None and where.strip():
        where_ast = goql["query_lang"].compile_expr_for_spec(spec, where)
    order_by = _order_by(query, order)

    basedb = db
    while isinstance(basedb, CacheProxyDb):
        basedb = basedb.db
    dialect = None
    if not isinstance(basedb, ProxyDbBase) and hasattr(basedb, "dbapi"):
        dialect = _dialect(basedb, query)
    if dialect is not None:
        sql, params = query.compile_query(
            spec,
            query.Query(
                select=["handle"], where=where_ast, order_by=order_by, limit=limit
            ),
            dialect=dialect,
        )
        basedb.dbapi.execute(sql, params)
        return [row[0] for row in basedb.dbapi.fetchall()]

    rows = goql["proxied_query"].run_query(
        db, spec, where_ast, order_by=order_by, limit=limit, select=["handle"]
    )
    return [row[0] for row in rows]


def make_iterator(db, class_name, wrap):
    """One of the script's record iterators, e.g. people() for "Person".

    iterator(where=None, order=None, limit=50) yields wrap(raw_data) for
    each matching record -- the same arguments and default as Gramps
    Connect's Gramplets, so the first 50 by default and limit=None for all.
    Without where/order, records come in handle order, which is also the
    order Gramps Connect's server returns them in, and GOQL isn't needed.
    """
    table = class_name.lower()
    iter_raw = getattr(db, "_iter_raw_%s_data" % table)
    get_handles = getattr(db, "get_%s_handles" % table)
    get_raw = db._get_table_func(class_name, "raw_func")

    def iterator(where=None, order=None, limit=50):
        if where is None and order is None:
            if limit is None:
                for handle, data in iter_raw():
                    yield wrap(data)
                return
            handles = sorted(get_handles())[:limit]
        else:
            handles = query_handles(db, table, where, order, limit)
        for handle in handles:
            data = get_raw(handle)
            if data is not None:
                yield wrap(data)

    return iterator
