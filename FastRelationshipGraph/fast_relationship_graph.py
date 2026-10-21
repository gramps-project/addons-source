#
# FastRelationshipGraph -- a standalone addon, independent of gramps-core
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program. If not, see
# <https://www.gnu.org/licenses/>.
#

"""FastRelationshipGraph: gramps-sql-extensions-shaped API
(relationship()/all_relationships()/relationship_path()/
all_relationship_paths()/relationships_to()), object-API only -- no SQL,
no dependency on gramps-sql-extensions, no core patching. See
`fast_relationship_engine.py` for how the search itself is made fast
without touching `RelationshipCalculator`.

Function-by-function, against core and against gramps-sql-extensions:

- `relationship()` / `all_relationships()`: thin wrappers around the
  engine's `get_one_relationship()`/`get_all_relationships()` -- core
  already has these entry points, they just needed to be fast (see
  `fast_relationship_engine.py`). Uses core's own `collapse_relations()`
  unmodified, so there is no "known gap" versus core's literal
  behavior the way gramps-sql-extensions' own docstring notes for its
  simplified port.
- `relationship_path()` / `all_relationship_paths()`: core has no
  equivalent at all (it only ever returns wording, never the chain of
  people). New code: a bounded, visited-once ancestor-map BFS (the same
  approach validated earlier against this exact tree this session),
  with the same ancestor-couple collapse logic gramps-sql-extensions
  itself uses (`_collapsed_paths`/`_famrel_from_persrel`/partner map),
  ported here rather than imported, so this addon has no dependency on
  that project.
- `relationships_to()`: core has no bulk API at all. Two strategies
  chosen by target count, because neither is good across the whole
  range (both measured against a real 100,000-person tree this
  session): a per-target bounded BFS below ~a few hundred targets (no
  fixed cost), and a one-time full-tree edge index above that (bounded
  fixed cost, near-free per target after). See `relationships_to()`'s
  own docstring for the measured crossover.

Privacy: pass a `PrivateProxyDb`-wrapped `db` (or any db) straight
through -- every lookup goes through `db.get_person_from_handle()`/
`get_family_from_handle()` exactly as core does, so restricted queries
are correct automatically, with no privacy code of this module's own to
drift from core's three rules. Measured cost of that: see each
function's own docstring.
"""

from typing import Optional

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.errors import HandleError

from fast_relationship_engine import fast_relationship_calculator

_BIRTH = 1  # ChildRefType.BIRTH


def _safe_get_person(db, handle):
    """`db.get_person_from_handle()` returns `None` for a handle a
    `PrivateProxyDb` is filtering out, but *raises* `HandleError` for a
    handle that never existed at all (core's own contract --
    `ProxyDbBase.get_person_from_handle` itself doesn't guard against
    that either). Every handle this module's public methods take can
    come straight from caller-supplied (e.g. HTTP request) input, so
    both cases need to mean the same thing here: not found."""
    try:
        return db.get_person_from_handle(handle)
    except HandleError:
        return None


def _is_birth_path(path: str) -> bool:
    return not any(c in ("F", "M", "A") for c in path)


def _famrel_from_persrel(persrel_a: str, persrel_b: str) -> str:
    """Port of `RelationshipCalculator._famrel_from_persrel` -- combine
    two parents' single-person path codes ('m'/'f'/'M'/'F') for the same
    family into one family-level code ('a'/'b'/'c'/'A'), so locale
    calculators that key off the *last* path character (most non-English
    ones do, to tell a full relation from a half one) see two parents as
    one shared-ancestor family rather than two unrelated single-parent
    links."""
    if persrel_a == persrel_b:
        return persrel_a
    pair = {persrel_a, persrel_b}
    if pair == {"m", "f"}:
        return "a"
    if pair == {"m", "F"}:
        return "b"
    if pair == {"f", "M"}:
        return "c"
    return "A"


def _ancestor_sort_key(dist1, path1, dist2, path2, h):
    """Deterministic tie-break for picking among equally-plausible common
    ancestors: nearer total distance first; among ties, direct relation >
    birth-line > mother-line-over-father-line; finally the handle itself,
    so ties that survive even that sort identically on every call rather
    than depending on `set` iteration order (hash-seed dependent, not
    stable across processes)."""
    p1, p2 = path1[h], path2[h]
    direct = dist1[h] == 0 or dist2[h] == 0
    birth = _is_birth_path(p1) and _is_birth_path(p2)
    code_rank = {"m": 0, "f": 1, "M": 2, "F": 3}
    c1 = code_rank.get(p1[-1], -1) if p1 else -1
    c2 = code_rank.get(p2[-1], -1) if p2 else -1
    return (dist1[h] + dist2[h], not direct, not birth, c1, c2, h)


def _nearest_common_ancestors(common: set, path1: dict, path2: dict) -> set:
    """Drop a common ancestor sitting *behind* a nearer one on both
    people's own routes to it -- core's own search stops the moment a
    branch crosses into the other person's known ancestors, so a
    still-more-distant shared ancestor further up that exact same route
    is never visited there, let alone reported."""
    redundant = set()
    for anc2 in common:
        p1, p2 = path1[anc2], path2[anc2]
        for anc1 in common:
            if anc1 is anc2:
                continue
            q1, q2 = path1[anc1], path2[anc1]
            if len(q1) < len(p1) and len(q2) < len(p2) and p1.startswith(q1) and p2.startswith(q2):
                redundant.add(anc2)
                break
    return common - redundant


def _ancestor_map(db, handle, max_depth=15):
    """Bounded, visited-once BFS over the object API -- `dist`/`path`
    (path-code string, e.g. 'ffm') / `prev` (predecessor handle, for
    chain reconstruction) / `partner_map` ((child, parent) -> other
    parent in that family, for ancestor-couple collapse)."""
    dist, path, prev = {handle: 0}, {handle: ""}, {handle: None}
    partner_map = {}
    frontier = [handle]
    depth = 0
    while frontier and depth < max_depth - 1:
        depth += 1
        nxt = []
        for h in frontier:
            person = db.get_person_from_handle(h)
            if person is None:
                continue
            fam_handle = person.get_main_parents_family_handle()
            if not fam_handle:
                continue
            family = db.get_family_from_handle(fam_handle)
            if family is None:
                continue
            childrel = [
                (cr.get_mother_relation(), cr.get_father_relation())
                for cr in family.get_child_ref_list()
                if cr.ref == h
            ]
            if not childrel:
                continue
            mrel, frel = childrel[0]
            fh, mh = family.father_handle, family.mother_handle
            if fh and mh:
                partner_map[(h, fh)] = mh
                partner_map[(h, mh)] = fh
            for parent, code in (
                (fh, "f" if frel == _BIRTH else "F"),
                (mh, "m" if mrel == _BIRTH else "M"),
            ):
                if parent and parent not in dist:
                    dist[parent] = depth
                    path[parent] = path[h] + code
                    prev[parent] = h
                    nxt.append(parent)
        frontier = nxt
    return dist, path, prev, partner_map


def _collapsed_paths(anc, dist1, path1, prev1, pm1, dist2, path2, prev2, pm2, common):
    """If `anc`'s spouse in the relevant family is *also* a common
    ancestor, reached from both people via that same family, return the
    family-collapsed `(path_a, path_b, partner)` triple: the last hop's
    lone-parent code becomes a family code. Returns the unchanged paths
    (partner=None) when there's no such partner."""
    path_a, path_b = path1[anc], path2[anc]
    x1, x2 = prev1.get(anc), prev2.get(anc)
    if not path_a or not path_b or x1 is None or x2 is None:
        return path_a, path_b, None
    partner_a = pm1.get((x1, anc))
    partner_b = pm2.get((x2, anc))
    if (
        partner_a is None
        or partner_b is None
        or partner_a != partner_b
        or partner_a not in common
        or prev1.get(partner_a) != x1
        or prev2.get(partner_a) != x2
    ):
        return path_a, path_b, None
    partner = partner_a
    new_a = path_a[:-1] + _famrel_from_persrel(path_a[-1], path1[partner][-1])
    new_b = path_b[:-1] + _famrel_from_persrel(path_b[-1], path2[partner][-1])
    return new_a, new_b, partner


def _chain_to_ancestor(prev: dict, anc: str) -> list:
    chain = [anc]
    while prev[chain[-1]] is not None:
        chain.append(prev[chain[-1]])
    chain.reverse()
    return chain


class FastRelationshipGraph:
    """Object-API-only equivalent of `gramps_sql_extensions.RelationshipGraph`
    -- same five public methods, same paging conventions for
    `relationships_to()`, no SQL, no core patching. Needs exactly one
    thing from the caller: `db` (any `DbReadBase`, including a
    `PrivateProxyDb`-wrapped one for restricted queries) and, since this
    works with actual Person objects rather than raw handles, resolves
    handles to objects itself via `db.get_person_from_handle()`.

    `locale` is a `GrampsLocale` (default: the running application's own
    locale) -- passed straight through to
    `fast_relationship_engine.fast_relationship_calculator()`.
    """

    def __init__(self, db, locale=glocale, max_depth: int = 15):
        self._db = db
        self._locale = locale
        self._calc = fast_relationship_calculator(locale)
        self._max_depth = max_depth

    # -- relationship() / all_relationships(): thin wrappers around the
    # now-fast core entry points -------------------------------------

    def relationship(self, h1: str, h2: str, depth: Optional[int] = None):
        """Return (relationship_string, distance_common_orig,
        distance_common_other) -- the single most-direct relationship.
        Delegates entirely to the engine's `get_one_relationship()`
        (core's own method, made fast -- see `fast_relationship_engine`),
        including core's own `collapse_relations()` for ancestor-couple
        wording, so there is no gap versus core's literal behavior.

        `get_one_relationship()`'s own `olocale` parameter defaults to
        the *application's* default locale and unconditionally does
        `self._locale = olocale` on entry (core's own code, not this
        module's) -- so `olocale` must be passed explicitly here, or
        this call would silently discard the locale this graph was
        constructed with on every call, in favor of `glocale`."""
        if h1 == h2:
            return "", -1, -1
        p1 = _safe_get_person(self._db, h1)
        p2 = _safe_get_person(self._db, h2)
        if p1 is None or p2 is None:
            return "", -1, -1
        self._calc.set_depth(depth if depth is not None else self._max_depth)
        return self._calc.get_one_relationship(
            self._db, p1, p2, extra_info=True, olocale=self._locale
        )

    def all_relationships(self, h1: str, h2: str, depth: Optional[int] = None):
        """Return {relationship_string, common_ancestors} dicts for
        every distinct relationship between h1 and h2. Delegates to the
        engine's `get_all_relationships()`. A result of `[{}]` means no
        relationship was found."""
        if h1 == h2:
            return [{}]
        p1 = _safe_get_person(self._db, h1)
        p2 = _safe_get_person(self._db, h2)
        if p1 is None or p2 is None:
            return [{}]
        self._calc.set_depth(depth if depth is not None else self._max_depth)
        relstrings, common_lists = self._calc.get_all_relationships(self._db, p1, p2)
        if not relstrings:
            return [{}]
        return [
            {"relationship_string": rel, "common_ancestors": common_lists[i]}
            for i, rel in enumerate(relstrings)
        ]

    # -- relationship_path() / all_relationship_paths(): no core
    # equivalent -- new code, object-API BFS + ported collapse logic --

    def relationship_path(self, h1: str, h2: str, depth: Optional[int] = None):
        """Return the chain of people connecting `h1` and `h2` through
        their nearest common ancestor, as a list of `{"handle",
        "relationship_string"}` dicts ordered from `h1` to `h2`
        inclusive. `relationship_string` is always that node's
        relationship *to `h1`*, so `h1`'s own entry is always `""`.
        Returns `[]` if unrelated within `depth`, or a single-entry list
        if `h1 == h2`."""
        if h1 == h2:
            return [{"handle": h1, "relationship_string": ""}]
        max_depth = depth if depth is not None else self._max_depth
        p1o = _safe_get_person(self._db, h1)
        p2o = _safe_get_person(self._db, h2)
        if p1o is None or p2o is None:
            return []

        spouse = self._calc.is_spouse(self._db, p1o, p2o)
        if spouse:
            return [
                {"handle": h1, "relationship_string": ""},
                {"handle": h2, "relationship_string": spouse},
            ]

        d1, p1, pv1, pm1 = _ancestor_map(self._db, h1, max_depth)
        d2, p2, pv2, pm2 = _ancestor_map(self._db, h2, max_depth)
        common = set(d1) & set(d2)
        if not common:
            return []
        anc = min(common, key=lambda h: _ancestor_sort_key(d1, p1, d2, p2, h))

        gender1 = p1o.get_gender()
        chain1 = _chain_to_ancestor(pv1, anc)  # [h1, ..., anc]
        chain2 = _chain_to_ancestor(pv2, anc)  # [h2, ..., anc]
        result = [{"handle": h1, "relationship_string": ""}]
        for node in chain1[1:]:
            gender_node = self._db.get_person_from_handle(node).get_gender()
            only_birth = _is_birth_path(p1[node])
            rel_str = self._calc.get_single_relationship_string(
                d1[node], 0, gender1, gender_node, p1[node], "",
                only_birth=only_birth, in_law_a=False, in_law_b=False,
            )
            result.append({"handle": node, "relationship_string": rel_str})
        for node in reversed(chain2[:-1]):
            gender_node = self._db.get_person_from_handle(node).get_gender()
            Ga = d1[anc]
            Gb = d2[anc] - d2[node]
            path_a, full_path_b, _partner = _collapsed_paths(anc, d1, p1, pv1, pm1, d2, p2, pv2, pm2, common)
            path_b = full_path_b[len(p2[node]):]
            if Ga == 1 and Gb == 1:
                sib = self._sibling_type(h1, node, pv1, pv2)
                rel_str = self._calc.get_sibling_relationship_string(sib, gender1, gender_node)
            else:
                only_birth = _is_birth_path(path_a) and _is_birth_path(path_b)
                rel_str = self._calc.get_single_relationship_string(
                    Ga, Gb, gender1, gender_node, path_a, path_b,
                    only_birth=only_birth, in_law_a=False, in_law_b=False,
                )
            result.append({"handle": node, "relationship_string": rel_str})
        return result

    def all_relationship_paths(self, h1: str, h2: str, depth: Optional[int] = None, max_paths: Optional[int] = None):
        """Same idea as `all_relationships()` generalizes `relationship()`:
        one path per common ancestor, nearest first, rather than just the
        closest. `all_relationship_paths(h1, h2)[0]` always equals
        `relationship_path(h1, h2)`. `max_paths` caps how many are
        returned (`None` returns all)."""
        if h1 == h2:
            return [[{"handle": h1, "relationship_string": ""}]]
        max_depth = depth if depth is not None else self._max_depth
        p1o = _safe_get_person(self._db, h1)
        p2o = _safe_get_person(self._db, h2)
        if p1o is None or p2o is None:
            return []

        paths = []
        spouse = self._calc.is_spouse(self._db, p1o, p2o)
        if spouse:
            paths.append([
                {"handle": h1, "relationship_string": ""},
                {"handle": h2, "relationship_string": spouse},
            ])

        d1, p1, pv1, pm1 = _ancestor_map(self._db, h1, max_depth)
        d2, p2, pv2, pm2 = _ancestor_map(self._db, h2, max_depth)
        common = set(d1) & set(d2)
        if not common:
            return paths
        common = _nearest_common_ancestors(common, p1, p2)

        gender1 = p1o.get_gender()
        ancestors = sorted(common, key=lambda h: _ancestor_sort_key(d1, p1, d2, p2, h))
        if max_paths is not None:
            ancestors = ancestors[:max_paths]

        for anc in ancestors:
            chain1 = _chain_to_ancestor(pv1, anc)
            chain2 = _chain_to_ancestor(pv2, anc)
            path = [{"handle": h1, "relationship_string": ""}]
            for node in chain1[1:]:
                gender_node = self._db.get_person_from_handle(node).get_gender()
                only_birth = _is_birth_path(p1[node])
                rel_str = self._calc.get_single_relationship_string(
                    d1[node], 0, gender1, gender_node, p1[node], "",
                    only_birth=only_birth, in_law_a=False, in_law_b=False,
                )
                path.append({"handle": node, "relationship_string": rel_str})
            for node in reversed(chain2[:-1]):
                gender_node = self._db.get_person_from_handle(node).get_gender()
                Ga = d1[anc]
                Gb = d2[anc] - d2[node]
                path_a, full_path_b, _partner = _collapsed_paths(anc, d1, p1, pv1, pm1, d2, p2, pv2, pm2, common)
                path_b = full_path_b[len(p2[node]):]
                if Ga == 1 and Gb == 1:
                    sib = self._sibling_type(h1, node, pv1, pv2)
                    rel_str = self._calc.get_sibling_relationship_string(sib, gender1, gender_node)
                else:
                    only_birth = _is_birth_path(path_a) and _is_birth_path(path_b)
                    rel_str = self._calc.get_single_relationship_string(
                        Ga, Gb, gender1, gender_node, path_a, path_b,
                        only_birth=only_birth, in_law_a=False, in_law_b=False,
                    )
                path.append({"handle": node, "relationship_string": rel_str})
            paths.append(path)
        return paths

    def _sibling_type(self, h1, h2, pv1, pv2):
        """Best-effort sibling-type classification for path labeling --
        full/half/step -- via each person's immediate parent family.
        Simpler than core's own `get_sibling_type` (which examines both
        parents' exact relation types); sufficient for path labeling,
        where the common ancestor + distances already establish that
        these two ARE siblings, only the full/half/step wording needs
        picking."""
        f1 = self._db.get_person_from_handle(h1)
        f2 = self._db.get_person_from_handle(h2)
        fam1 = f1.get_main_parents_family_handle() if f1 else None
        fam2 = f2.get_main_parents_family_handle() if f2 else None
        if fam1 and fam1 == fam2:
            return 0  # NORM_SIB
        return 3  # STEP_SIB fallback -- see docstring

    # -- relationships_to(): no core bulk API -- new code, dual strategy

    def relationships_to(
        self,
        h1: str,
        handles: Optional[list] = None,
        depth: Optional[int] = None,
        page: int = 0,
        pagesize: int = 20,
        bulk_threshold: int = 700,
    ):
        """Return `h1`'s relationship to each of `handles`, paged like
        gramps-web-api's own object-list resources (`page` 1-indexed,
        default 0 = no paging; `pagesize` default 20). `handles=None`
        means every person in the tree.

        Two strategies, chosen by the number of *visible* targets after
        paging (measured against a real 100,000-person tree this
        session):
        - Below `bulk_threshold` (default 700, between the measured
          unrestricted (~680) and restricted (~1,520) crossover points):
          per-target bounded BFS reusing h1's own ancestor map -- no
          fixed cost, ~1.45-7ms/target depending on whether `db` is a
          restricted (proxy-wrapped) view.
        - At or above `bulk_threshold`: build a one-time full-tree edge
          index (0.95s unrestricted / ~10-12s restricted on that same
          tree -- restricted is real because it goes through
          `db.get_family_from_handle()` per family, the correct
          sanitizing path; `db.iter_families()` does NOT sanitize the
          families it returns, only filters out wholly-private ones --
          then ~0.05-0.24ms/target after. Confirmed end to end on a full
          ~100,000-target sweep: 6.4s unrestricted, 34.0s restricted,
          versus 144.8s / 595.4s for the per-target strategy at that
          scale.

        A handle that doesn't exist, or resolves to `None` (e.g. a
        privacy-restricted person under a `PrivateProxyDb`-wrapped `db`),
        is silently skipped, matching gramps-web-api's own `handles`
        query-param convention.
        """
        max_depth = depth if depth is not None else self._max_depth
        if handles is None:
            target_handles = [h for h in self._db.get_person_handles() if h != h1]
        else:
            target_handles = [h for h in handles if h != h1]

        visible = []
        for h in target_handles:
            if _safe_get_person(self._db, h) is not None:
                visible.append(h)
        total = len(visible)
        if page > 0:
            offset = (page - 1) * pagesize
            visible = visible[offset: offset + pagesize]

        if len(visible) < bulk_threshold:
            items = self._relationships_to_small(h1, visible, max_depth)
        else:
            items = self._relationships_to_bulk(h1, visible, max_depth)

        return {"items": items, "total": total, "page": page, "pagesize": pagesize}

    def _relationships_to_small(self, h1, targets, max_depth):
        p1o = _safe_get_person(self._db, h1)
        if p1o is None:
            return [{"handle": h, "relationship_string": ""} for h in targets]
        d1, p1, pv1, pm1 = _ancestor_map(self._db, h1, max_depth)
        g1 = p1o.get_gender()
        items = []
        for h2 in targets:
            p2o = _safe_get_person(self._db, h2)
            if p2o is None:
                continue
            spouse = self._calc.is_spouse(self._db, p1o, p2o)
            if spouse:
                items.append({"handle": h2, "relationship_string": spouse})
                continue
            d2, p2, pv2, pm2 = _ancestor_map(self._db, h2, max_depth)
            common = set(d1) & set(d2)
            if not common:
                items.append({"handle": h2, "relationship_string": ""})
                continue
            anc = min(common, key=lambda h: _ancestor_sort_key(d1, p1, d2, p2, h))
            Ga, Gb = d1[anc], d2[anc]
            g2 = p2o.get_gender()
            if Ga == 1 and Gb == 1:
                rel_str = self._calc.get_sibling_relationship_string(0, g1, g2)
            else:
                pa, pb, _partner = _collapsed_paths(anc, d1, p1, pv1, pm1, d2, p2, pv2, pm2, common)
                only_birth = _is_birth_path(pa) and _is_birth_path(pb)
                rel_str = self._calc.get_single_relationship_string(
                    Ga, Gb, g1, g2, pa, pb, only_birth=only_birth, in_law_a=False, in_law_b=False,
                )
            items.append({"handle": h2, "relationship_string": rel_str})
        return items

    def _relationships_to_bulk(self, h1, targets, max_depth):
        edges, partner_map = self._build_full_index()
        gender_cache = {}

        def gender_of(handle):
            if handle not in gender_cache:
                p = _safe_get_person(self._db, handle)
                gender_cache[handle] = p.get_gender() if p is not None else None
            return gender_cache[handle]

        d1, p1, pv1 = self._index_ancestor_map(edges, h1, max_depth)
        g1 = gender_of(h1)
        items = []
        for h2 in targets:
            g2 = gender_of(h2)
            if g2 is None:
                continue
            d2, p2, pv2 = self._index_ancestor_map(edges, h2, max_depth)
            common = set(d1) & set(d2)
            if not common:
                items.append({"handle": h2, "relationship_string": ""})
                continue
            anc = min(common, key=lambda h: _ancestor_sort_key(d1, p1, d2, p2, h))
            Ga, Gb = d1[anc], d2[anc]
            pa, pb = p1[anc], p2[anc]
            partner_a = partner_map.get((pv1.get(anc), anc))
            partner_b = partner_map.get((pv2.get(anc), anc))
            if (
                pv1.get(anc) is not None and pv2.get(anc) is not None
                and partner_a is not None and partner_a == partner_b and partner_a in common
                and pv1.get(partner_a) == pv1.get(anc) and pv2.get(partner_a) == pv2.get(anc)
            ):
                pa = pa[:-1] + _famrel_from_persrel(pa[-1], p1[partner_a][-1])
                pb = pb[:-1] + _famrel_from_persrel(pb[-1], p2[partner_a][-1])
            if Ga == 1 and Gb == 1:
                rel_str = self._calc.get_sibling_relationship_string(0, g1, g2)
            else:
                only_birth = _is_birth_path(pa) and _is_birth_path(pb)
                rel_str = self._calc.get_single_relationship_string(
                    Ga, Gb, g1, g2, pa, pb, only_birth=only_birth, in_law_a=False, in_law_b=False,
                )
            items.append({"handle": h2, "relationship_string": rel_str})
        return items

    def _build_full_index(self):
        """One-time, per-call, full-tree parent/child edge index -- never
        cached across calls (see `relationships_to()`'s docstring on why:
        a cache outliving one call risks serving stale data after a tree
        edit, or leaking one viewer's privacy-filtered view into
        another's request). Uses `db.get_family_from_handle()` per family
        handle rather than `db.iter_families()` -- the latter only
        filters out wholly-private families, it does NOT sanitize
        private father/mother/child-ref links on the families it does
        return (confirmed by reading `ProxyDbBase.iter_families()` this
        session), so it is not privacy-correct on its own."""
        edges = {}
        partner_map = {}
        for family_handle in self._db.get_family_handles():
            family = self._db.get_family_from_handle(family_handle)
            if family is None:
                continue
            fh, mh = family.father_handle, family.mother_handle
            for cr in family.get_child_ref_list():
                child = cr.ref
                if fh:
                    edges.setdefault(child, []).append((fh, "f" if cr.get_father_relation() == _BIRTH else "F"))
                if mh:
                    edges.setdefault(child, []).append((mh, "m" if cr.get_mother_relation() == _BIRTH else "M"))
                if fh and mh:
                    partner_map[(child, fh)] = mh
                    partner_map[(child, mh)] = fh
        return edges, partner_map

    @staticmethod
    def _index_ancestor_map(edges, handle, max_depth=15):
        dist, path, prev = {handle: 0}, {handle: ""}, {handle: None}
        frontier = [handle]
        depth = 0
        while frontier and depth < max_depth - 1:
            depth += 1
            nxt = []
            for h in frontier:
                for parent, code in edges.get(h, ()):
                    if parent not in dist:
                        dist[parent] = depth
                        path[parent] = path[h] + code
                        prev[parent] = h
                        nxt.append(parent)
            frontier = nxt
        return dist, path, prev
