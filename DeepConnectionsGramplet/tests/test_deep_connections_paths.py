#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  The Gramps Development Team
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
Regression test for Mantis issue 10628 -- the Deep Connections Gramplet must
advance to a genuinely different connection each time the user presses
"Continue to search for additional relations", instead of returning the *same*
path repeatedly.

Root cause: when ``main`` finds the active (target) person it reports the path,
pauses, and -- on resume -- used to fall through and *expand the target itself*,
queuing the target's own relatives.  Those relatives then re-reach the target,
so the search re-emits the connection it just reported (a path that re-enters
the target as an interior step).  Genuinely distinct connections that were
already queued before the target was first found are still reachable.

PRODUCTION-PATH NOTE (brief.md / principles.md §3.4): this test drives
``DeepConnectionsGramplet.main()`` itself -- the *actual* breadth-first search
generator the gramplet runs in production -- not a copy of its loop.  A
lightweight harness subclass overrides only the GUI surface
(``append_text``/``link``/``pretty_print``/progress widgets/``pause``...), so
``main`` runs the real queue/cache/``get_relatives`` path-construction code
against a tiny in-memory database.  Because the harness's ``pause`` is a no-op,
iterating the generator to exhaustion runs the whole search and captures every
connection path it would hand the user across successive "Continue" presses.

The gramplet module imports ``gi``/Gtk at load time; the addon C4 gate runs
under ``xvfb`` with the GI-version bootstrap, so importing it here is safe (the
same pattern test_deep_connections.py uses).  No display-bound widget is ever
constructed: the harness skips ``Gramplet.__init__``.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The addon directory and its implementation module share a name; use the
# explicit submodule path (same trap noted in libaccess / gramps bug 0012691).
from DeepConnectionsGramplet import DeepConnectionsGramplet as dcg_mod


# ---------------------------------------------------------------------------
# Minimal in-memory stand-ins for the Gramps person/family/db objects, exposing
# only the accessors get_relatives / main touch.
# ---------------------------------------------------------------------------
class _ChildRef:
    def __init__(self, ref):
        self.ref = ref


class _Person:
    def __init__(self, handle, families=(), parent_families=()):
        self.handle = handle
        self._families = list(families)
        self._parent_families = list(parent_families)

    def get_family_handle_list(self):
        return self._families

    def get_parent_family_handle_list(self):
        return self._parent_families

    def get_person_ref_list(self):
        return []

    def get_note_list(self):
        return []

    def get_primary_name(self):
        return self.handle


class _Family:
    def __init__(self, handle, father=None, mother=None, children=()):
        self.handle = handle
        self._father = father
        self._mother = mother
        self._children = list(children)

    def get_child_ref_list(self):
        return [_ChildRef(c) for c in self._children]

    def get_father_handle(self):
        return self._father

    def get_mother_handle(self):
        return self._mother

    def get_note_list(self):
        return []


class _DB:
    def __init__(self, people, families, default):
        self._people = people
        self._families = families
        self._default = default

    def get_default_person(self):
        return self._people.get(self._default)

    def get_person_from_handle(self, handle):
        return self._people.get(handle)

    def get_family_from_handle(self, handle):
        return self._families.get(handle)

    def get_note_from_handle(self, handle):  # no notes in these fixtures
        return None


class _DBState:
    def __init__(self, db):
        self.db = db


class _StubRelCalc:
    """Relationship calculator stub; main() only needs a falsy/str result."""

    def get_one_relationship(self, db, person1, person2):
        return ""


class _StubNameDisplayer:
    """Avoid needing a real gramps Name object for display."""

    def display_name(self, name):
        return str(name)


class _Widget:
    """No-op stand-in for the Gtk widgets main() toggles."""

    def set_visible(self, *args, **kwargs):
        pass

    def set_sensitive(self, *args, **kwargs):
        pass


class _Harness(dcg_mod.DeepConnectionsGramplet):
    """
    Drives the real ``DeepConnectionsGramplet.main`` generator without a GTK
    context.  Only the GUI surface is overridden; ``main``, ``get_relatives``,
    ``get_links_from_notes`` and ``_calculate_path_depth`` are the inherited
    production implementations.  ``pause`` is a no-op so iterating the generator
    to exhaustion walks every "Continue" step and captures every path produced.
    """

    def __init__(self, db, active_handle):
        # Deliberately do NOT call Gramplet.__init__ (no GUI / GTK).
        self.dbstate = _DBState(db)
        self._active_handle = active_handle
        self.selected_handles = set()
        self.captured_paths = []
        self.relationship_calc = _StubRelCalc()
        self.progress_bar = _Widget()
        self.pause_button = _Widget()
        self.continue_button = _Widget()
        self.copy_button = _Widget()

    # -- GUI surface stubbed out -------------------------------------------
    def get_active_object(self, _kind):
        return self.dbstate.db.get_person_from_handle(self._active_handle)

    def set_text(self, *args, **kwargs):
        pass

    def render_text(self, *args, **kwargs):
        pass

    def update_status(self, *args, **kwargs):
        pass

    def update_progress(self, *args, **kwargs):
        pass

    def update_search_info(self, *args, **kwargs):
        pass

    def append_text(self, *args, **kwargs):
        pass

    def link(self, *args, **kwargs):
        pass

    def pause(self, *args, **kwargs):
        pass

    # -- capture each produced path instead of rendering it ----------------
    def pretty_print(self, path):
        self.captured_paths.append(path)


def _flatten(path):
    """
    Flatten a connection path's linked list into ``[(relation, anchor), ...]``
    ordered from the outermost step down to the terminal "self" root.

    Node shape (unchanged from the gramplet)::

        (more_path, (relation_text, anchor_handle, [parents...]))
    """
    steps = []
    node = path
    while node is not None:
        steps.append((node[1][0], node[1][1]))
        node = node[0]
    return steps


def _two_independent_paths_db():
    """
    Two node-disjoint connections between Home ``D`` and active ``A``:

        D -> child X -> child A          (via X)
        D -> child Y -> child A          (via Y)

    ``A`` additionally has a private child ``C`` reachable *only* through ``A``.
    Before the fix, finding ``A`` and continuing expanded ``A`` itself, queuing
    ``C``; ``C`` then re-reached ``A`` and the search re-emitted the connection
    with ``A`` re-entered as an interior step -- the repeated path of 10628.
    """
    families = {
        "FDX": _Family("FDX", father="D", children=["X"]),
        "FDY": _Family("FDY", father="D", children=["Y"]),
        "FX": _Family("FX", father="X", children=["A"]),
        "FY": _Family("FY", father="Y", children=["A"]),
        "FC": _Family("FC", father="A", children=["C"]),
    }
    people = {
        "D": _Person("D", families=["FDX", "FDY"]),
        "X": _Person("X", families=["FX"], parent_families=["FDX"]),
        "Y": _Person("Y", families=["FY"], parent_families=["FDY"]),
        "A": _Person("A", families=["FC"], parent_families=["FX", "FY"]),
        "C": _Person("C", parent_families=["FC"]),
    }
    return _DB(people, families, default="D")


class TestSuccessiveConnectionsAreDistinct(unittest.TestCase):
    """Issue 10628: Continue must not re-emit an already-reported path."""

    def _all_paths(self, db, active_handle):
        """
        Run the production ``main`` generator to exhaustion and return every
        connection path it produces, each flattened to ``[(relation, anchor)]``.
        """
        harness = _Harness(db, active_handle)
        original_displayer = dcg_mod.name_displayer
        dcg_mod.name_displayer = _StubNameDisplayer()
        try:
            for _signal in harness.main():
                pass
        finally:
            dcg_mod.name_displayer = original_displayer
        self.assertTrue(
            harness.captured_paths,
            "main() produced no connection path to %r" % (active_handle,),
        )
        return [_flatten(p) for p in harness.captured_paths]

    def test_continue_does_not_repeat_path_through_target(self):
        """
        No produced connection may route *through* the active/target person:
        that re-entry is exactly how the search re-reported the same connection
        on every Continue.
        """
        paths = self._all_paths(_two_independent_paths_db(), "A")

        for steps in paths:
            anchors = [anchor for (_relation, anchor) in steps]
            self.assertNotIn(
                "A",
                anchors,
                "active/target person re-entered as an interior step -- the "
                "search re-emitted an already-reported connection; steps=%r" % (steps,),
            )

    def test_both_independent_paths_remain_reachable(self):
        """
        The fix must not silence genuinely distinct connections: both the
        via-X and the via-Y path are still produced.
        """
        paths = self._all_paths(_two_independent_paths_db(), "A")
        anchor_sets = [{anchor for (_relation, anchor) in steps} for steps in paths]

        via_x = any("X" in s and "Y" not in s for s in anchor_sets)
        via_y = any("Y" in s and "X" not in s for s in anchor_sets)
        self.assertTrue(
            via_x and via_y,
            "both independent connections must be reachable (via X and via Y); "
            "found anchor sets %r" % (anchor_sets,),
        )

    def test_no_immediate_repeat_of_a_reported_path(self):
        """
        Successive connections must differ: no two consecutive reported paths
        may be identical.
        """
        paths = self._all_paths(_two_independent_paths_db(), "A")
        for earlier, later in zip(paths, paths[1:]):
            self.assertNotEqual(
                earlier,
                later,
                "Continue returned the same path twice in a row; paths=%r" % (paths,),
            )


if __name__ == "__main__":
    unittest.main()
