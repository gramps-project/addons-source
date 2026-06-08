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
Regression test for Mantis issue 8653 -- the Deep Connections Gramplet must not
route a connection path back through the Home (start) person.  The Home person
is the search origin and may appear in a produced path only as its terminal
"self" root; it must never be named as the anchor of an intermediate
relationship step (the reporter's "... / sibling of <Home>" chain).

PRODUCTION-PATH NOTE (brief.md PRODUCTION-PATH REQUIREMENT / principles §3.4):
this test drives ``DeepConnectionsGramplet.main()`` itself -- the *actual*
breadth-first search generator the gramplet runs in production -- not a copy of
its loop.  A lightweight harness subclass overrides only the GUI surface
(``append_text``/``link``/``pretty_print``/progress widgets/``pause``...), so
``main`` runs the real queue/cache/``get_relatives`` path-construction code
against a tiny in-memory database.  The produced path is captured at the point
``main`` hands it to ``pretty_print``.  Because the harness drives ``main``
*outside* the broad ``try/except`` in production, any error in the search
surfaces as a test failure rather than being swallowed into "Error during
search".

The gramplet module imports ``gi``/Gtk at load time; the addon C4 gate runs
under ``xvfb`` with the GI-version bootstrap, so importing it here is safe (the
same pattern SurnameMappingGramplet's import test uses).  No display-bound
widget is ever constructed: the harness skips ``Gramplet.__init__``.
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
    production implementations.
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

    # -- capture the produced path instead of rendering it -----------------
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


def _nibling_db():
    """
    Home person ``D`` and sibling ``S`` are children of family ``Fp`` (parents
    ``P1``/``P2``).  ``S`` has their own family ``Fs`` with spouse ``W`` and
    child ``A`` (the active person).  So ``A`` connects to Home ``D`` as
    "child of D's sibling S" -- a two-hop path that, before the fix, named
    ``D`` (Home) as an intermediate "sibling of <Home>" step.
    """
    families = {
        "Fp": _Family("Fp", father="P1", mother="P2", children=["D", "S"]),
        "Fs": _Family("Fs", father="S", mother="W", children=["A"]),
    }
    people = {
        "D": _Person("D", parent_families=["Fp"]),
        "S": _Person("S", families=["Fs"], parent_families=["Fp"]),
        "A": _Person("A", parent_families=["Fs"]),
        "W": _Person("W", families=["Fs"]),
        "P1": _Person("P1", families=["Fp"]),
        "P2": _Person("P2", families=["Fp"]),
    }
    return _DB(people, families, default="D")


class TestStartPersonNotIntermediate(unittest.TestCase):
    """The Home (start) person must never be an intermediate path step (8653)."""

    def _first_path_steps(self, db, active_handle):
        """
        Run the production ``main`` generator until it produces the first
        connection path; return its flattened steps (outermost -> root).
        """
        harness = _Harness(db, active_handle)
        # Patch the module-level name displayer so main() needs no real Name.
        original_displayer = dcg_mod.name_displayer
        dcg_mod.name_displayer = _StubNameDisplayer()
        try:
            for _signal in harness.main():
                if harness.captured_paths:
                    break
        finally:
            dcg_mod.name_displayer = original_displayer
        self.assertTrue(
            harness.captured_paths,
            "main() produced no connection path to %r" % (active_handle,),
        )
        return _flatten(harness.captured_paths[0])

    def test_home_not_an_intermediate_step_on_multi_hop_path(self):
        """A two-hop connection must not name the Home person mid-path."""
        steps = self._first_path_steps(_nibling_db(), "A")

        root = steps[-1]
        non_root = steps[:-1]
        intermediate_handles = [anchor for (_relation, anchor) in non_root]

        # Not vacuous: the connection genuinely routes through the intermediate
        # relative S (active A is "child of S") -- the multi-hop case the bug
        # needs, not a direct relative of Home.
        self.assertIn(
            "S",
            intermediate_handles,
            "scenario does not route through the intermediate S; steps=%r" % (steps,),
        )

        # The bug (issue 8653): D (Home) appears as a non-root anchor.
        self.assertNotIn(
            "D",
            intermediate_handles,
            "Home person re-entered as an intermediate step; steps=%r" % (steps,),
        )

        # The chain is not broken: it still terminates at the Home person as the
        # "self" root, so A is connected to Home (A -> child of S -> root D).
        self.assertEqual(
            root[1],
            "D",
            "path must terminate at the Home person as its root; steps=%r" % (steps,),
        )
        self.assertEqual(
            [anchor for (_relation, anchor) in steps].count("D"),
            1,
            "Home person must appear exactly once (as the root); steps=%r" % (steps,),
        )

    def test_direct_relative_of_home_only_at_root(self):
        """A direct sibling of Home still connects, with Home only as root."""
        steps = self._first_path_steps(_nibling_db(), "S")  # S is Home's sibling
        intermediate_handles = [anchor for (_relation, anchor) in steps[:-1]]
        self.assertNotIn(
            "D",
            intermediate_handles,
            "Home person re-entered as an intermediate step; steps=%r" % (steps,),
        )
        self.assertEqual(
            steps[-1][1],
            "D",
            "path must terminate at the Home person as its root; steps=%r" % (steps,),
        )


if __name__ == "__main__":
    unittest.main()
