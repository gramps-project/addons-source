#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Doug Blank <doug.blank@gmail.com>
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
Tests for the Export Story addon's builder, against a real temporary
database. Run from the addons-source root::

    python3 -m unittest StoryExport.tests.test_storyexport -v
"""

import io
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

from gramps.gen.db import DbTxn
from gramps.gen.db.utils import make_database
from gramps.gen.lib import (
    Date,
    Event,
    EventRef,
    EventRoleType,
    EventType,
    Family,
    Media,
    MediaRef,
    Name,
    Person,
    Place,
    PlaceName,
    Surname,
)
from gramps.gen.proxy import LivingProxyDb, PrivateProxyDb

from storyexport_builder import (
    StoryExportError,
    build_story,
    no_living_in_photo,
    sort_year,
    to_edtf,
)


def tiny_png(color=b"\x80\x40\x20"):
    """A valid 4x3 PNG, without needing Pillow."""

    def chunk(kind, body):
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body))
        )

    rows = b"".join(b"\x00" + color * 4 for _ in range(3))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 3, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def media_ref(handle):
    ref = MediaRef()
    ref.set_reference_handle(handle)
    return ref


def date(
    year,
    modifier=Date.MOD_NONE,
    quality=Date.QUAL_NONE,
    calendar=Date.CAL_GREGORIAN,
    month=0,
    day=0,
    stop=None,
):
    value = (day, month, year, False) + ((0, 0, stop, False) if stop else ())
    result = Date()
    result.set(quality=quality, modifier=modifier, calendar=calendar, value=value)
    return result


class StoryExportTest(unittest.TestCase):
    """Josef Meyer (1850-1920): a dated birth at Zürich with its own photo,
    a private christening, a death, an undated census, and a marriage to
    Anna, who is living. A photo of the two of them is on the marriage and
    the census. He has a portrait."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="storyexport_")
        cls.db = make_database("sqlite")
        os.makedirs(os.path.join(cls.tmp, "db"))
        cls.db.load(os.path.join(cls.tmp, "db"))
        db = cls.db

        def image(name, color):
            path = os.path.join(cls.tmp, name)
            with open(path, "wb") as handle:
                handle.write(tiny_png(color))
            media = Media()
            media.set_path(path)
            media.set_mime_type("image/png")
            return media

        def person(given, surname):
            p = Person()
            name = Name()
            name.set_first_name(given)
            surname_obj = Surname()
            surname_obj.set_surname(surname)
            name.add_surname(surname_obj)
            p.set_primary_name(name)
            return p

        def event(kind, when, place=None, private=False, description=""):
            e = Event()
            e.set_type(kind)
            if when is not None:
                e.set_date_object(when)
            if place is not None:
                e.set_place_handle(place.handle)
            e.set_privacy(private)
            e.set_description(description)
            return e

        with DbTxn("build test tree", db) as txn:
            zurich = Place()
            zurich.set_name(PlaceName(value="Zürich"))
            zurich.set_latitude("47.3769")
            zurich.set_longitude("8.5417")
            db.add_place(zurich, txn)

            portrait = image("portrait.png", b"\x10\x20\x30")
            birth_photo = image("birth.png", b"\x40\x50\x60")
            couple_photo = image("couple.png", b"\x70\x80\x90")
            for media in (portrait, birth_photo, couple_photo):
                db.add_media(media, txn)

            birth = event(
                EventType.BIRTH,
                date(1850, Date.MOD_ABOUT),
                zurich,
                description="Born at home.",
            )
            birth.add_media_reference(media_ref(birth_photo.handle))
            christening = event(
                EventType.CHRISTEN, date(1850, month=3, day=12), private=True
            )
            death = event(EventType.DEATH, date(1920))
            census = event(EventType.CENSUS, None)
            census.add_media_reference(media_ref(couple_photo.handle))
            marriage = event(EventType.MARRIAGE, date(1878))
            marriage.add_media_reference(media_ref(couple_photo.handle))
            anna_birth = event(EventType.BIRTH, date(1990))
            for e in (birth, christening, death, census, marriage, anna_birth):
                db.add_event(e, txn)

            josef = person("Josef", "Meyer")
            for e in (birth, christening, death, census):
                ref = EventRef()
                ref.set_reference_handle(e.handle)
                ref.set_role(EventRoleType.PRIMARY)
                josef.add_event_ref(ref)
            josef.add_media_reference(media_ref(portrait.handle))
            josef.add_media_reference(media_ref(couple_photo.handle))

            anna = person("Anna", "Keller")
            anna_ref = EventRef()
            anna_ref.set_reference_handle(anna_birth.handle)
            anna_ref.set_role(EventRoleType.PRIMARY)
            anna.add_event_ref(anna_ref)
            anna.set_birth_ref(anna_ref)
            anna.add_media_reference(media_ref(couple_photo.handle))
            db.add_person(josef, txn)
            db.add_person(anna, txn)

            family = Family()
            family.set_father_handle(josef.handle)
            family.set_mother_handle(anna.handle)
            marriage_ref = EventRef()
            marriage_ref.set_reference_handle(marriage.handle)
            marriage_ref.set_role(EventRoleType.FAMILY)
            family.add_event_ref(marriage_ref)
            db.add_family(family, txn)
            josef.add_family_handle(family.handle)
            anna.add_family_handle(family.handle)
            db.commit_person(josef, txn)
            db.commit_person(anna, txn)

        cls.josef, cls.anna = josef.handle, anna.handle
        cls.media = {
            "portrait": portrait.handle,
            "birth": birth_photo.handle,
            "couple": couple_photo.handle,
        }

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def written(self, story):
        out = io.BytesIO()
        story.write(out)
        with zipfile.ZipFile(io.BytesIO(out.getvalue())) as archive:
            return json.loads(archive.read("story.json")), set(archive.namelist())

    def test_the_whole_story(self):
        doc, files = self.written(build_story(self.db, self.josef))
        self.assertEqual(doc["format"], "gramps-connect-story")
        self.assertEqual(doc["title"], "The Story of Meyer, Josef")
        titles = [s.get("title") for s in doc["slides"]]
        # Opening slide, then by date (the christening shares the birth's
        # year), then the undated census last.
        self.assertEqual(
            titles,
            [
                "The Story of Meyer, Josef",
                "Birth",
                "Christening",
                "Marriage",
                "Death",
                "Census",
            ],
        )
        self.assertEqual(
            doc["slides"][0]["text"], "5 events from the life of Meyer, Josef."
        )
        self.assertEqual(
            [s["id"] for s in doc["slides"]], ["s0", "s1", "s2", "s3", "s4", "s5"]
        )

        birth = doc["slides"][1]
        self.assertEqual(birth["text"], "Born at home.")
        self.assertEqual(birth["date"]["edtf"], "1850~")
        self.assertEqual(birth["date"]["sortYear"], 1850)
        self.assertTrue(birth["date"]["text"])
        self.assertEqual(birth["place"]["name"], "Zürich")
        self.assertAlmostEqual(birth["place"]["lat"], 47.3769)
        self.assertAlmostEqual(birth["place"]["lon"], 8.5417)
        self.assertEqual(birth["people"], [{"name": "Meyer, Josef"}])
        self.assertEqual(doc["slides"][2]["date"]["edtf"], "1850-03-12")
        self.assertNotIn("date", doc["slides"][5])
        self.assertEqual(
            doc["slides"][3]["people"],
            [{"name": "Meyer, Josef"}, {"name": "Keller, Anna"}],
        )

        # Photos: the birth's own; the portrait on the opening slide and as
        # every other slide's fallback; the couple's on the marriage. Each
        # file stored once.
        refs = [s.get("media", [{}])[0].get("ref") for s in doc["slides"]]
        self.assertEqual(refs[0], refs[2])
        self.assertEqual(refs[0], refs[4])
        self.assertNotEqual(refs[0], refs[1])
        self.assertNotEqual(refs[0], refs[3])
        self.assertEqual(refs[3], refs[5])
        self.assertEqual(len(doc["media"]), 3)
        for item in doc["media"].values():
            self.assertIn(item["src"], files)

    def test_private_records_left_out(self):
        doc, _ = self.written(build_story(PrivateProxyDb(self.db), self.josef))
        self.assertNotIn("Christening", [s.get("title") for s in doc["slides"]])

    def test_living_people_left_out(self):
        db = LivingProxyDb(self.db, LivingProxyDb.MODE_EXCLUDE_ALL)
        doc, _ = self.written(build_story(db, self.josef, no_living_in_photo(self.db)))
        titles = [s.get("title") for s in doc["slides"]]
        # Gramps clears the events of a family with a living parent
        # (LivingProxyDb), so the marriage goes...
        self.assertNotIn("Marriage", titles)
        # ...and the census keeps its slide but not the photo Anna is in:
        # it falls back to Josef's portrait.
        census = doc["slides"][titles.index("Census")]
        self.assertEqual(census["media"], doc["slides"][0]["media"])
        self.assertEqual(len(doc["media"]), 2)
        self.assertTrue(no_living_in_photo(self.db)(self.media["birth"]))
        self.assertFalse(no_living_in_photo(self.db)(self.media["couple"]))

    def test_a_living_subject_is_refused(self):
        db = LivingProxyDb(self.db, LivingProxyDb.MODE_EXCLUDE_ALL)
        with self.assertRaises(StoryExportError):
            build_story(db, self.anna)

    def test_edtf(self):
        self.assertEqual(to_edtf(date(1850)), "1850")
        self.assertEqual(to_edtf(date(1850, month=3)), "1850-03")
        self.assertEqual(to_edtf(date(1850, quality=Date.QUAL_ESTIMATED)), "1850~")
        self.assertEqual(to_edtf(date(1850, Date.MOD_BEFORE)), "../1850")
        self.assertEqual(to_edtf(date(1850, Date.MOD_AFTER)), "1850/..")
        self.assertEqual(to_edtf(date(1850, Date.MOD_SPAN, stop=1860)), "1850/1860")
        self.assertEqual(to_edtf(date(1850, Date.MOD_RANGE, stop=1860)), "[1850..1860]")
        self.assertIsNone(to_edtf(date(1850, calendar=Date.CAL_JULIAN)))
        self.assertIsNone(to_edtf(Date()))
        text_only = Date()
        text_only.set_as_text("spring of that year")
        self.assertIsNone(to_edtf(text_only))

    def test_sort_year_is_gregorian(self):
        self.assertEqual(sort_year(date(1850)), 1850)
        # 1 January 1700 (Julian) is 12 January 1700 (Gregorian); a
        # year-end Julian date crosses into the next Gregorian year.
        self.assertEqual(
            sort_year(date(1699, calendar=Date.CAL_JULIAN, month=12, day=31)), 1700
        )
        self.assertIsNone(sort_year(Date()))


if __name__ == "__main__":
    unittest.main()
