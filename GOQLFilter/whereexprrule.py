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

"""Filter rule matching objects against a gramps-object-query-language
where-expression, one subclass per primary object type.

Registering these as ordinary ``RULE`` plugins (see ``whereexprrule.gpr.py``)
lets a GOQL expression be dropped into Gramps' own Custom Filter Editor
(``EditFilter``) as a single rule, so a filter built from one now shows up
everywhere a normal Custom Filter would -- other views' sidebar filters,
reports, exports -- not just in this addon's own gramplet.

When ``prepare()`` sees an unproxied, DB-API-backed ``db``, it pushes the
expression down to SQL (``gramps_object_query_language.query.compile_query``)
instead of evaluating it per-object -- the same fast/slow split
gramps-web-api's ``resources/object_query.py`` makes (``_post_sql`` vs.
``_post_proxied``), just reached from ``Rule.prepare(db, user)`` instead of
a request handler. Re-decided on every ``prepare()`` call, never cached on
the rule instance: a saved Custom Filter can be applied against a different
db, or the same db behind a different proxy, at any later time, and each
application must see its own, current ``db``.
"""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
import logging
from typing import Any, Optional

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules import Rule
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.proxy import CacheProxyDb
from gramps.gen.proxy.proxybase import ProxyDbBase

# -------------------------------------------------------------------------
#
# gramps-object-query-language modules
#
# -------------------------------------------------------------------------
try:
    from gramps_object_query_language.query_lang import (
        QueryLangError,
        compile_expr_for_spec,
    )
    from gramps_object_query_language.evaluator import evaluate_where
    from gramps_object_query_language.query import (
        CITATION,
        EVENT,
        FAMILY,
        MEDIA,
        NOTE,
        PERSON,
        PLACE,
        REPOSITORY,
        SOURCE,
        Dialect,
        Query,
        compile_query,
    )
except ImportError as err:
    raise ImportError(
        "GOQLFilter requires the gramps-object-query-language "
        "package.\nInstall with: pip install gramps-object-query-language"
    ) from err

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

LOG = logging.getLogger(".GOQLFilter.whereexprrule")

# Adapted from gramps-web-api's resources/object_query.py (_DIALECT_BY_NAME /
# _resolve_dialect) -- core DBAPI/SQLite and the SharedPostgreSQL addon
# don't advertise a `.dialect` attribute yet (proposed but unmerged
# core-side: gramps-project/gramps#2178); the single-user PostgreSQL addon
# already does (`dialect = "postgresql"`), so that's read straight off `db`
# when present. Once core grows a real `.dialect` property, this whole
# function collapses to `getattr(db, "dialect", None)` and this copy can be
# deleted.
#
# Diverges from gramps-web-api's version in one deliberate way: that one
# falls back to `isinstance(basedb, SQLite)` for the common case, but a live
# `dbstate.db` here was constructed through Gramps' *plugin* loader, which
# imports `sqlite.py` as a bare top-level module named `sqlite` -- not via
# `gramps.plugins.db.dbapi.sqlite`, the normal package path this file (and
# gramps-web-api) imports `SQLite` through. That makes `type(db)` a
# *different* class object from the `SQLite` imported here even for a real
# SQLite-backed db (confirmed live: `type(make_database("sqlite")).__module__
# == "sqlite"`, not `"gramps.plugins.db.dbapi.sqlite"`) -- `isinstance` never
# matches, and the dialect check would fall through silently. Matching by
# class *name* instead sidesteps the module-identity split. Unrecognized
# class names return `None` (never a guessed dialect) so an unknown backend
# just skips SQL push-down rather than risking wrong-dialect SQL -- the
# caller falls back to per-object eval either way.
_DIALECT_BY_NAME = {
    "sqlite": Dialect.SQLITE,
    "postgres": Dialect.POSTGRESQL,
    "postgresql": Dialect.POSTGRESQL,
}
_DIALECT_BY_CLASS_NAME = {
    "SQLite": Dialect.SQLITE,
    "PostgreSQL": Dialect.POSTGRESQL,
    "SharedPostgreSQL": Dialect.POSTGRESQL,
}


def _resolve_dialect(db: Any) -> Optional[Dialect]:
    name: Optional[str] = getattr(db, "dialect", None)
    if name:
        dialect = _DIALECT_BY_NAME.get(name)
        if dialect is not None:
            return dialect
    return _DIALECT_BY_CLASS_NAME.get(type(db).__name__)


def _unwrap_cache_proxy(db: Any) -> Any:
    """Peel off ``CacheProxyDb`` wrapping to find what SQL-eligibility
    checks should actually look at.

    Every real call into a ``Rule`` from Gramps' own filtering goes through
    ``CacheProxyDb`` -- ``gui/views/treemodels/flatbasemodel.py``'s
    ``_rebuild_filter`` unconditionally does ``cdb = CacheProxyDb(self.db);
    self.search.apply(cdb, ...)`` -- so ``db`` here is *never* the raw
    backend object, even with no privacy proxy in play. ``CacheProxyDb``
    has no privacy relevance (it exists purely to cache fetched objects)
    but, unlike ``PrivateProxyDb``/``LivingProxyDb``/etc., it doesn't
    subclass ``ProxyDbBase`` -- so both ``isinstance(db, ProxyDbBase)`` and
    ``_resolve_dialect(db)``'s class-name lookup silently see straight past
    a real backend/proxy underneath it without this unwrap: the former
    would miss a nested privacy proxy entirely (treating it as
    "unproxied"), the latter would miss the real backend's class name
    entirely (``type(CacheProxyDb(...)).__name__ == "CacheProxyDb"``, never
    a recognized dialect).

    Stops the moment the current layer is anything other than
    ``CacheProxyDb`` -- including a real ``ProxyDbBase`` -- so a privacy
    proxy nested underneath (``CacheProxyDb(PrivateProxyDb(raw_db))``) is
    correctly left in place for the caller's ``isinstance(_, ProxyDbBase)``
    check to catch, not unwrapped past.
    """
    while isinstance(db, CacheProxyDb):
        db = db.db
    return db


def _sql_matched_handles(db: Any, spec: Any, where: Any):
    """Matching handles via SQL push-down, or ``None`` if not possible.

    Only ever called with a ``db`` already confirmed unproxied and
    DB-API-backed (see ``MatchesExpression.prepare``) -- mirrors
    gramps-web-api's ``_post_sql`` dispatch, minus the privacy predicate,
    which is exactly why an unproxied `db` is required before this runs at
    all (see ``query.py``'s ``compile_query`` docstring: "carries no
    privacy predicate"). Never raises: an unrecognized backend (no
    resolvable dialect) is a routine, silent "skip the optimization";
    a genuine compile/execute failure is logged, then also falls back to
    per-object evaluation rather than breaking the filter outright.
    """
    dialect = _resolve_dialect(db)
    if dialect is None:
        return None
    try:
        query = Query(select=["handle"], where=where, limit=None)
        sql, params = compile_query(spec, query, dialect=dialect)
        db.dbapi.execute(sql, params)
        return {row[0] for row in db.dbapi.fetchall()}
    except Exception:
        LOG.exception("GOQL SQL push-down failed; falling back to per-object eval")
        return None


# -------------------------------------------------------------------------
#
# MatchesExpression
#
# -------------------------------------------------------------------------
class MatchesExpression(Rule):
    """Base rule: true for objects a GOQL where-expression evaluates true for.

    Not registered directly -- each object type needs its own registered
    subclass (below) since a ``RULE`` plugin's ``namespace``/``ruleclass``
    pair, and the ``ObjectTypeSpec`` GOQL needs to compile the expression
    against, are fixed per type.
    """

    labels = [_("GOQL expression")]
    description = _(
        "Matches objects for which the given gramps-object-query-language "
        "where-expression evaluates to true"
    )
    category = _("General filters")
    spec: Any = None  # set by each subclass below

    def prepare(self, db, user):
        self._where = None
        # NOT a private name: `gen.filters.optimizer.Optimizer` specifically
        # looks for `selected_handles` (`hasattr(rule, "selected_handles")`)
        # to narrow `possible_handles` in `GenericFilter.apply()` *before*
        # any `get_object()` fetch -- see `apply_logical_op_to_all`. A rule
        # holding its precomputed match set under any other name is
        # invisible to the Optimizer: every candidate still gets fetched
        # and deserialized before `apply_to_one` ever runs, no matter how
        # fast `apply_to_one` itself is. This was set as `_matched_handles`
        # originally and measured ~8s "Apply time" on a real tree as a
        # result -- renaming it to the name the Optimizer actually checks
        # for is the fix, not a cosmetic one.
        self.selected_handles = None
        expr = (self.list[0] or "").strip()
        if not expr:
            return
        try:
            self._where = compile_expr_for_spec(self.spec, expr)
        except QueryLangError:
            # Leave self._where as None -- an invalid/incomplete expression
            # matches nothing rather than raising out of GenericFilter.apply().
            self._where = None
            return
        # SQL push-down only when `db`, past any CacheProxyDb wrapping, is
        # unproxied (no privacy predicate to lose) and DB-API-backed
        # (something to push down to). Re-checked here, every call -- see
        # this module's docstring.
        basedb = _unwrap_cache_proxy(db)
        if not isinstance(basedb, ProxyDbBase) and hasattr(basedb, "dbapi"):
            self.selected_handles = _sql_matched_handles(basedb, self.spec, self._where)

    def apply_to_one(self, db, obj) -> bool:
        if self._where is None or obj is None:
            return False
        if self.selected_handles is not None:
            return obj.handle in self.selected_handles
        return evaluate_where(db, obj, self._where, self.spec)


class PersonMatchesExpression(MatchesExpression):
    name = _("People matching the <GOQL expression>")
    spec = PERSON


class FamilyMatchesExpression(MatchesExpression):
    name = _("Families matching the <GOQL expression>")
    spec = FAMILY


class EventMatchesExpression(MatchesExpression):
    name = _("Events matching the <GOQL expression>")
    spec = EVENT


class PlaceMatchesExpression(MatchesExpression):
    name = _("Places matching the <GOQL expression>")
    spec = PLACE


class RepositoryMatchesExpression(MatchesExpression):
    name = _("Repositories matching the <GOQL expression>")
    spec = REPOSITORY


class SourceMatchesExpression(MatchesExpression):
    name = _("Sources matching the <GOQL expression>")
    spec = SOURCE


class CitationMatchesExpression(MatchesExpression):
    name = _("Citations matching the <GOQL expression>")
    spec = CITATION


class MediaMatchesExpression(MatchesExpression):
    name = _("Media matching the <GOQL expression>")
    spec = MEDIA


class NoteMatchesExpression(MatchesExpression):
    name = _("Notes matching the <GOQL expression>")
    spec = NOTE
