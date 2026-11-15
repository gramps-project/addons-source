#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Kevin White
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""Extended tests for GWizardMediaFix planning, hash tokens, and reference resolution."""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
from __future__ import annotations
import itertools
import pathlib
import shutil
import tempfile
import unittest
from typing import Any

# -------------------------------------------------------------------------
#
# GTK test doubles: installed before any GWizard module is imported, so the
# dialog classes subclass the fakes.
#
# -------------------------------------------------------------------------
from . import gwizard_gtk_fakes as fakes

fakes.install()

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
import gwizardmediafix as m


def setUpModule() -> None:
    """Install the GTK fakes for this module's tests."""
    fakes.install()


def tearDownModule() -> None:
    """Restore the real GTK classes for other test modules."""
    fakes.uninstall()


# ------------------------------------------------------------
#
# Mock / Lightweight Data Model Helpers for Deterministic Tests
#
# ------------------------------------------------------------
class _Date:
    def __init__(self, y: int = 0) -> None:
        self.y = y

    def get_year(self) -> int:
        return self.y

    def is_empty(self) -> bool:
        return self.y == 0


class _Name:
    def __init__(self, sur: str, giv: str) -> None:
        self.s = sur
        self.g = giv

    def get_surname(self) -> str:
        return self.s

    def get_first_name(self) -> str:
        return self.g


class _Person:
    def __init__(self, h: str, gid: str, sur: str, giv: str) -> None:
        self.h = h
        self.gid = gid
        self.n = _Name(sur, giv)

    def get_handle(self) -> str:
        return self.h

    def get_gramps_id(self) -> str:
        return self.gid

    def get_primary_name(self) -> _Name:
        return self.n

    def get_event_ref_list(self) -> list[Any]:
        return []

    def get_birth_ref(self) -> Any:
        return None


class _Event:
    def __init__(self, h: str, gid: str, typ: str, y: int) -> None:
        self.h = h
        self.gid = gid
        self.t = typ
        self.d = _Date(y)

    def get_handle(self) -> str:
        return self.h

    def get_gramps_id(self) -> str:
        return self.gid

    def get_type(self) -> str:
        return self.t

    def get_date_object(self) -> _Date:
        return self.d


class _Source:
    def get_title(self) -> str:
        return "familysearch.org"

    def get_gramps_id(self) -> str:
        return "S1"


class _Citation:
    def __init__(self, h: str, gid: str) -> None:
        self.h = h
        self.gid = gid

    def get_handle(self) -> str:
        return self.h

    def get_gramps_id(self) -> str:
        return self.gid

    def get_reference_handle(self) -> str:
        return "src"

    def get_page(self) -> str:
        return ""


class _Media:
    def __init__(
        self,
        h: str,
        gid: str,
        desc: str,
        path: str,
        notes: tuple[str, ...] = (),
    ) -> None:
        self.h = h
        self.gid = gid
        self.desc = desc
        self.path = path
        self.notes = list(notes)

    def get_handle(self) -> str:
        return self.h

    def get_gramps_id(self) -> str:
        return self.gid

    def get_description(self) -> str:
        return self.desc

    def get_path(self) -> str:
        return self.path

    def set_path(self, p: str) -> None:
        self.path = p

    def get_date_object(self) -> _Date:
        return _Date()

    def get_note_list(self) -> list[str]:
        return self.notes

    def remove_note(self, h: str) -> None:
        self.notes.remove(h)

    def get_attribute_list(self) -> list[Any]:
        return []

    def get_tag_list(self) -> list[Any]:
        return []

    def get_citation_list(self) -> list[Any]:
        return []


class _Note:
    def __init__(self, h: str, gid: str, text: str) -> None:
        self.h = h
        self.gid = gid
        self.t = text

    def get(self) -> str:
        return self.t

    def get_gramps_id(self) -> str:
        return self.gid


class _MockDB:
    def __init__(
        self,
        mp: str,
        medias: list[_Media],
        back: dict[str, list[tuple[str, str]]],
        **objs: Any,
    ) -> None:
        self.mp = mp
        self.medias = {x.h: x for x in medias}
        self.back = back
        self.o = objs
        self.commits = 0

    def get_mediapath(self) -> str:
        return self.mp

    def get_undodb(self) -> Any:
        return []

    def transaction_begin(self, _txn: Any) -> None:
        pass

    def transaction_commit(self, _txn: Any) -> None:
        pass

    def transaction_abort(self, _txn: Any) -> None:
        pass

    def iter_media(self) -> Any:
        return iter(list(self.medias.values()))

    def get_media_from_handle(self, h: str) -> _Media | None:
        return self.medias.get(h)

    def commit_media(self, _mm: Any, _t: Any) -> None:
        self.commits += 1

    def remove_media(self, h: str, _t: Any) -> None:
        del self.medias[h]

    def find_backlink_handles(
        self, h: str, include_classes: tuple[str, ...] | None = None
    ) -> list[tuple[str, str]]:
        r = list(self.back.get(h, []))
        return [b for b in r if not include_classes or b[0] in include_classes]

    def get_person_from_handle(self, h: str) -> Any:
        return self.o.get("P", {}).get(h)

    def get_event_from_handle(self, h: str) -> Any:
        return self.o.get("E", {}).get(h)

    def get_citation_from_handle(self, h: str) -> Any:
        return self.o.get("C", {}).get(h)

    def get_source_from_handle(self, _h: str) -> Any:
        return _Source()

    def get_family_from_handle(self, _h: str) -> Any:
        return None

    def get_note_from_handle(self, h: str) -> Any:
        return self.o.get("N", {}).get(h)

    def remove_note(self, h: str, _t: Any) -> None:
        self.o["N"].pop(h, None)


# ------------------------------------------------------------
#
# GWizardMediaFixExTest
#
# ------------------------------------------------------------
class GWizardMediaFixExTest(unittest.TestCase):
    """Extended test suite verifying edge cases, deterministic resolution, and planning."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.p_map = {
            "p450": _Person("p450", "I00450", "Fuller", "Harry Jay"),
            "pE": _Person("pE", "M25S-XWS", "Fuller", "Edward C"),
            "pL": _Person("pL", "I00054", "Fuller", "Lilly"),
            "p451": _Person("p451", "I00451", "Devault", "Nettie"),
        }
        self.e_map = {
            "e1": _Event("e1", "E1", "Census", 1910),
            "e2": _Event("e2", "E2", "Birth", 1856),
        }
        self.c_map = {
            "c1": _Citation("c1", "C00859"),
            "c2": _Citation("c2", "C01169"),
            "c3": _Citation("c3", "C00109"),
        }
        self.base_back = {
            "c1": [("Event", "e1")],
            "e1": [("Person", "p450")],
            "c2": [("Event", "e2")],
            "e2": [("Person", "pE")],
            "c3": [("Person", "pL")],
            "m3": [("Person", "p451")],
        }

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_deterministic_ref_id_backlink_order(self) -> None:
        """resolve_media_reference_context resolves the described person regardless of backlink order."""
        refs: set[tuple[str, str, str]] = set()
        citations = [("Citation", "c1"), ("Citation", "c2"), ("Citation", "c3")]
        for perm in itertools.permutations(citations):
            back = dict(self.base_back)
            back["m0"] = list(perm)
            med = _Media(
                "m0",
                "O00000",
                "Fuller, Harry Jay - 1910Census",
                "/x/Fuller, Harry Jay - 1910Census.jpg",
            )
            db: Any = _MockDB(
                "/b",
                [med],
                back,
                P=self.p_map,
                E=self.e_map,
                C=self.c_map,
            )
            ctx = m.resolve_media_reference_context(db, med)
            refs.add((ctx["ref_id"], ctx["surname"], ctx["given"]))

        self.assertEqual(refs, {("I00450", "Fuller", "Harry Jay")})

    def test_stable_ref_id_for_undescribed_media(self) -> None:
        """Undescribed media yields a single stable ref_id across all backlink permutations."""
        refs: set[str] = set()
        citations = [("Citation", "c1"), ("Citation", "c2"), ("Citation", "c3")]
        for perm in itertools.permutations(citations):
            back = dict(self.base_back)
            back["m0"] = list(perm)
            med = _Media("m0", "O00000", "scan", "/x/scan.jpg")
            db: Any = _MockDB(
                "/b",
                [med],
                back,
                P=self.p_map,
                E=self.e_map,
                C=self.c_map,
            )
            refs.add(m.resolve_media_reference_context(db, med)["ref_id"])

        self.assertEqual(len(refs), 1)

    def test_find_name_mismatches(self) -> None:
        """find_name_mismatches flags media whose description name differs slightly from linked person."""
        tmp = pathlib.Path(self.temp_dir)
        base = tmp / "Tree"
        (base / "sub").mkdir(parents=True)
        other = tmp / "old"
        other.mkdir()
        (other / "Fuller, Harry Jay - 1910Census.jpg").write_text("HARRY CENSUS")
        (base / "sub" / "Duvault, Nettie - 1900Census.jpg").write_text("NETTIE CENSUS")

        m0 = _Media(
            "m0",
            "O00000",
            "Fuller, Harry Jay - 1910Census",
            str(other / "Fuller, Harry Jay - 1910Census.jpg"),
        )
        m3 = _Media(
            "m3",
            "O00003",
            "Duvault, Nettie - 1900Census",
            "Duvault, Nettie - 1900Census.jpg",
        )
        back = dict(self.base_back)
        back["m0"] = [("Citation", "c3"), ("Citation", "c1"), ("Citation", "c2")]
        db: Any = _MockDB(
            str(base),
            [m0, m3],
            back,
            P=self.p_map,
            E=self.e_map,
            C=self.c_map,
        )

        mismatches = m.find_name_mismatches(db)
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0][0], "O00003")
        self.assertEqual(mismatches[0][4], "probable spelling variant")

    def test_build_accept_all_plan_dry_run(self) -> None:
        """build_accept_all_plan creates a non-mutating preview plan of all automated changes."""
        tmp = pathlib.Path(self.temp_dir)
        base = tmp / "Tree"
        (base / "sub").mkdir(parents=True)
        other = tmp / "old"
        other.mkdir()
        (other / "Fuller, Harry Jay - 1910Census.jpg").write_text("HARRY CENSUS")
        (base / "sub" / "Duvault, Nettie - 1900Census.jpg").write_text("NETTIE CENSUS")
        (other / "orphan.jpg").write_text("o")
        (other / "kept.jpg").write_text("k")

        m0 = _Media(
            "m0",
            "O00000",
            "Fuller, Harry Jay - 1910Census",
            str(other / "Fuller, Harry Jay - 1910Census.jpg"),
        )
        m3 = _Media(
            "m3",
            "O00003",
            "Duvault, Nettie - 1900Census",
            "Duvault, Nettie - 1900Census.jpg",
        )
        m4 = _Media("m4", "O00004", "Orphan - 1900Census", str(other / "orphan.jpg"))
        m5 = _Media(
            "m5",
            "O00005",
            "Kept - note",
            str(other / "kept.jpg"),
            notes=("n1",),
        )
        back = dict(self.base_back)
        back["m0"] = [("Citation", "c3"), ("Citation", "c1"), ("Citation", "c2")]
        notes = {
            "n1": _Note(
                "n1",
                "N1",
                "Records not imported into OBJE (multi-media object) Could not import C:\\x",
            )
        }
        db: Any = _MockDB(
            str(base),
            [m0, m3, m4, m5],
            back,
            P=self.p_map,
            E=self.e_map,
            C=self.c_map,
            N=notes,
        )

        snap = [(x.h, x.path) for x in db.medias.values()]
        plan = m.build_accept_all_plan(db, str(base), True)

        # Plan must not mutate state
        self.assertEqual(snap, [(x.h, x.path) for x in db.medias.values()])
        self.assertEqual(db.commits, 0)
        self.assertEqual(len(db.medias), 4)

        # Verify plan contents
        self.assertEqual([f[0] for f in plan["find"]], ["O00003"])
        self.assertEqual(
            plan["find"][0][2].replace("\\", "/"),
            "sub/Duvault, Nettie - 1900Census.jpg",
        )
        self.assertEqual([d[0] for d in plan["delete"]], ["O00004"])
        self.assertEqual([k[0] for k in plan["keep_unref"]], ["O00005"])

        formatted = m.format_plan(plan)
        self.assertIn("O00003", formatted)
        self.assertIn("O00004", formatted)

        # When no base path is set, consolidation step must be halted
        halted_plan = m.build_accept_all_plan(db, str(base), False)
        self.assertTrue(halted_plan["halted"])
        self.assertEqual(halted_plan["moves"], [])

    def test_content_hash_token_uniqueness(self) -> None:
        """The {hash} token generates distinct filenames for different content and identical for same."""
        tmp = pathlib.Path(self.temp_dir)
        (tmp / "a.jpg").write_text("CONTENT_AAA")
        (tmp / "b.jpg").write_text("CONTENT_BBB")

        ma = _Media("ma", "O1", "Smith, J - 1900Census", str(tmp / "a.jpg"))
        mb = _Media("mb", "O2", "Smith, J - 1900Census", str(tmp / "b.jpg"))
        db: Any = _MockDB(str(tmp), [ma, mb], {})

        template = "{surname}_{given}-{doc_type}-{year}-{hash}.{ext}"
        name_a = m.sanitize_standard_filename(
            ma.path, db=db, media=ma, template=template
        )
        name_b = m.sanitize_standard_filename(
            mb.path, db=db, media=mb, template=template
        )

        self.assertNotEqual(name_a, name_b)
        self.assertTrue(name_a.endswith(".jpg"))
        self.assertTrue(name_b.endswith(".jpg"))

        # Re-evaluating the same file produces identical name
        self.assertEqual(
            name_a,
            m.sanitize_standard_filename(ma.path, db=db, media=ma, template=template),
        )

    def test_stale_import_notes_detection_and_removal(self) -> None:
        """find_stale_import_notes finds notes on readable files and remove_import_notes cleans them."""
        tmp = pathlib.Path(self.temp_dir)
        kept_file = tmp / "kept.jpg"
        kept_file.write_text("file content")

        m5 = _Media("m5", "O00005", "Kept - note", str(kept_file), notes=("n1",))
        notes = {
            "n1": _Note(
                "n1",
                "N1",
                "Records not imported into OBJE (multi-media object) Could not import C:\\test.jpg",
            )
        }
        db: Any = _MockDB(str(tmp), [m5], {"n1": [("Media", "m5")]}, N=notes)

        stale = m.find_stale_import_notes(db)
        self.assertEqual([i[1] for i in stale], ["O00005"])

        removed_count = m.remove_import_notes(db, stale)
        self.assertEqual(removed_count, 1)
        self.assertNotIn("n1", db.o["N"])
        self.assertEqual(m5.notes, [])
        self.assertEqual(m.find_stale_import_notes(db), [])

    def test_reference_context_caching(self) -> None:
        """resolve_media_reference_context with cache parameter avoids repeated computation."""
        med = _Media("m0", "O00000", "test photo", "/path/photo.jpg")
        db: Any = _MockDB("/b", [med], {})

        calls: list[int] = []
        orig = m._resolve_media_reference_context_uncached

        def mock_uncached(d: Any, x: Any) -> dict[str, str]:
            calls.append(1)
            return orig(d, x)

        with unittest.mock.patch.object(
            m, "_resolve_media_reference_context_uncached", side_effect=mock_uncached
        ):
            cache: dict[str, dict[str, str]] = {}
            for _ in range(3):
                m.resolve_media_reference_context(db, med, cache)
            self.assertEqual(len(calls), 1)


# Test discovery imports every test module before running any, so take the
# fakes off Gtk again now that the GWizard modules are imported; other Gramps
# tests need the real widgets.  setUpModule puts them back for this module.
fakes.uninstall()


if __name__ == "__main__":
    unittest.main()
