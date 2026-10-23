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
Tests for the Generate Story addon's builder, against a real temporary
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
    ChildRef,
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
    Tag,
)
from gramps.gen.proxy import LivingProxyDb, PrivateProxyDb

from storyexport_builder import (
    StoryExportError,
    build_family_story,
    build_person_story,
    left_out_reason,
    no_living_in_photo,
    sort_year,
    to_edtf,
    viewer_page,
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


KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<Placemark><name>Old town</name><MultiGeometry>
  <Polygon><outerBoundaryIs><LinearRing><coordinates>
    7.4,46.9 7.5,46.9 7.5,47.0 7.4,46.9
  </coordinates></LinearRing></outerBoundaryIs></Polygon>
  <LineString><coordinates>7.4,46.9,0 7.5,47.0,0</coordinates></LineString>
</MultiGeometry></Placemark>
<Placemark><Point><coordinates>7.45,46.95</coordinates></Point></Placemark>
</Document></kml>
"""


class StoryExportTest(unittest.TestCase):
    """Josef Meyer (1850-1920): a dated birth at Zürich with its own photo,
    a private christening, a death, an undated census, and a marriage to
    Anna, who is living. A photo of the two of them is on the marriage and
    the census. He has a portrait. Their son Karl (1880-1950) has a
    portrait, and a baptism besides his birth and death.

    Zürich (so named 1800-1900) has a Gramps Connect map overlay (a shape
    and an old map) and a KML file, which the overlay supersedes. Bern,
    where Josef died, has only a KML file."""

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

        def map_file(name, text, mime, tags=()):
            path = os.path.join(cls.tmp, name)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            media = Media()
            media.set_path(path)
            media.set_mime_type(mime)
            for tag in tags:
                media.add_tag(tag)
            return media

        with DbTxn("build test tree", db) as txn:
            overlay_tag = Tag()
            overlay_tag.set_name("Map overlay")
            db.add_tag(overlay_tag, txn)
            old_map = image("old-map.png", b"\xd0\xc0\xb0")
            db.add_media(old_map, txn)
            overlay = map_file(
                "zurich.geojson",
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "Polygon",
                                    "coordinates": [
                                        [
                                            [8.5, 47.3],
                                            [8.6, 47.3],
                                            [8.6, 47.4],
                                            [8.5, 47.3],
                                        ]
                                    ],
                                },
                                "properties": {"fill": "#aa0000"},
                            },
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "Polygon",
                                    "coordinates": [
                                        [
                                            [8.5, 47.4],
                                            [8.6, 47.4],
                                            [8.6, 47.3],
                                            [8.5, 47.3],
                                            [8.5, 47.4],
                                        ]
                                    ],
                                },
                                "properties": {
                                    "gramps:image-overlay": True,
                                    "image": old_map.handle,
                                    "opacity": 0.6,
                                    "order": 3,
                                },
                            },
                        ],
                    }
                ),
                "application/geo+json",
                [overlay_tag.handle],
            )
            zurich_kml = map_file(
                "zurich.kml", KML, "application/vnd.google-earth.kml+xml"
            )
            bern_kml = map_file("bern.kml", KML, "application/vnd.google-earth.kml+xml")
            for media in (overlay, zurich_kml, bern_kml):
                db.add_media(media, txn)

            zurich = Place()
            name = PlaceName(value="Zürich")
            name.set_date_object(date(1800, Date.MOD_SPAN, stop=1900))
            zurich.set_name(name)
            zurich.set_latitude("47.3769")
            zurich.set_longitude("8.5417")
            zurich.add_media_reference(media_ref(overlay.handle))
            zurich.add_media_reference(media_ref(zurich_kml.handle))
            db.add_place(zurich, txn)
            bern = Place()
            bern.set_name(PlaceName(value="Bern"))
            bern.add_media_reference(media_ref(bern_kml.handle))
            db.add_place(bern, txn)

            portrait = image("portrait.png", b"\x10\x20\x30")
            birth_photo = image("birth.png", b"\x40\x50\x60")
            couple_photo = image("couple.png", b"\x70\x80\x90")
            karl_photo = image("karl.png", b"\xa0\xb0\xc0")
            for media in (portrait, birth_photo, couple_photo, karl_photo):
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
            death = event(EventType.DEATH, date(1920), bern)
            census = event(EventType.CENSUS, None)
            census.add_media_reference(media_ref(couple_photo.handle))
            marriage = event(EventType.MARRIAGE, date(1878))
            marriage.add_media_reference(media_ref(couple_photo.handle))
            anna_birth = event(EventType.BIRTH, date(1990))
            karl_events = [
                event(EventType.BIRTH, date(1880)),
                event(EventType.BAPTISM, date(1880, month=6)),
                event(EventType.DEATH, date(1950)),
            ]
            for e in [birth, christening, death, census, marriage, anna_birth]:
                db.add_event(e, txn)
            for e in karl_events:
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

            karl = person("Karl", "Meyer")
            for e in karl_events:
                ref = EventRef()
                ref.set_reference_handle(e.handle)
                ref.set_role(EventRoleType.PRIMARY)
                karl.add_event_ref(ref)
            karl.add_media_reference(media_ref(karl_photo.handle))
            db.add_person(karl, txn)

            family = Family()
            family.set_father_handle(josef.handle)
            family.set_mother_handle(anna.handle)
            marriage_ref = EventRef()
            marriage_ref.set_reference_handle(marriage.handle)
            marriage_ref.set_role(EventRoleType.FAMILY)
            family.add_event_ref(marriage_ref)
            child_ref = ChildRef()
            child_ref.set_reference_handle(karl.handle)
            family.add_child_ref(child_ref)
            db.add_family(family, txn)
            josef.add_family_handle(family.handle)
            anna.add_family_handle(family.handle)
            karl.add_parent_family_handle(family.handle)
            db.commit_person(josef, txn)
            db.commit_person(anna, txn)
            db.commit_person(karl, txn)

        cls.josef, cls.anna, cls.karl = josef.handle, anna.handle, karl.handle
        cls.family = family.handle
        cls.media = {
            "portrait": portrait.handle,
            "birth": birth_photo.handle,
            "couple": couple_photo.handle,
            "karl": karl_photo.handle,
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

    def titles(self, doc):
        return [s.get("title") for s in doc["slides"]]

    def test_a_person_story(self):
        doc, files = self.written(build_person_story(self.db, self.josef))
        self.assertEqual(doc["format"], "gramps-connect-story")
        self.assertEqual(doc["title"], "The Story of Josef Meyer")
        # His own events: by date (the christening shares the birth's
        # year), then the undated census last. No family events.
        self.assertEqual(
            self.titles(doc),
            [
                "The Story of Josef Meyer",
                "Birth of Josef Meyer",
                "Christening of Josef Meyer",
                "Death of Josef Meyer",
                "Census of Josef Meyer",
            ],
        )
        self.assertEqual(
            doc["slides"][0]["text"], "4 moments from Josef Meyer's recorded life."
        )
        self.assertEqual(
            [s["id"] for s in doc["slides"]], ["s0", "s1", "s2", "s3", "s4"]
        )

        birth = doc["slides"][1]
        self.assertEqual(
            birth["text"], "Josef Meyer was born about 1850 in Zürich. Born at home."
        )
        self.assertEqual(birth["date"]["edtf"], "1850~")
        self.assertEqual(birth["date"]["sortYear"], 1850)
        self.assertEqual(birth["place"]["name"], "Zürich")
        self.assertAlmostEqual(birth["place"]["lat"], 47.3769)
        self.assertAlmostEqual(birth["place"]["lon"], 8.5417)
        self.assertEqual(birth["people"], [{"name": "Josef Meyer"}])
        self.assertTrue(
            doc["slides"][2]["text"].startswith("Josef Meyer was christened on ")
        )
        self.assertEqual(doc["slides"][2]["date"]["edtf"], "1850-03-12")
        self.assertEqual(doc["slides"][3]["text"], "Josef Meyer died in 1920 in Bern.")
        self.assertEqual(doc["slides"][4]["text"], "Census of Josef Meyer.")
        self.assertNotIn("date", doc["slides"][4])

        # Photos: the birth's own; the portrait on the opening slide and as
        # the fallback; the couple's on the census. Each file stored once.
        refs = [s.get("media", [{}])[0].get("ref") for s in doc["slides"]]
        self.assertNotEqual(refs[0], refs[1])
        self.assertEqual(refs[0], refs[2])
        self.assertEqual(refs[0], refs[3])
        self.assertNotIn(refs[4], (refs[0], refs[1]))
        self.assertEqual(len(doc["media"]), 4)  # and the old map
        for item in doc["media"].values():
            self.assertIn(item["src"], files)

    def test_map_overlays(self):
        doc, files = self.written(build_person_story(self.db, self.josef))
        zurich = doc["slides"][1]["place"]
        # The overlay file's shape (its fill as the color the player
        # reads), not the KML beside it.
        self.assertEqual(
            [f["geometry"]["type"] for f in zurich["geometry"]["features"]],
            ["Polygon"],
        )
        self.assertEqual(
            zurich["geometry"]["features"][0]["properties"]["color"], "#aa0000"
        )
        (overlay,) = zurich["overlays"]
        self.assertEqual(
            overlay["corners"], [[8.5, 47.4], [8.6, 47.4], [8.6, 47.3], [8.5, 47.3]]
        )
        self.assertEqual((overlay["opacity"], overlay["order"]), (0.6, 3))
        self.assertEqual(overlay["date"]["edtf"], "1800/1900")
        self.assertIn(doc["media"][overlay["media"]]["src"], files)

        # Bern has no coordinates, just its KML: two placemarks, the
        # first a polygon and a line together.
        bern = doc["slides"][3]["place"]
        self.assertEqual(bern["name"], "Bern")
        self.assertNotIn("lat", bern)
        self.assertNotIn("overlays", bern)
        features = bern["geometry"]["features"]
        self.assertEqual(
            [f["geometry"]["type"] for f in features], ["GeometryCollection", "Point"]
        )
        self.assertEqual(
            [g["type"] for g in features[0]["geometry"]["geometries"]],
            ["Polygon", "LineString"],
        )
        self.assertEqual(features[0]["properties"], {"name": "Old town"})
        self.assertEqual(features[1]["geometry"]["coordinates"], [7.45, 46.95])

    def test_a_person_story_with_families(self):
        doc, _ = self.written(
            build_person_story(self.db, self.josef, include_families=True)
        )
        self.assertEqual(
            self.titles(doc),
            [
                "The Story of Josef Meyer",
                "Birth of Josef Meyer",
                "Christening of Josef Meyer",
                "Marriage of Josef Meyer & Anna Keller",
                "Birth of Karl Meyer",
                "Death of Josef Meyer",
                "Death of Karl Meyer",
                "Birth of Anna Keller",
                "Census of Josef Meyer",
            ],
        )
        marriage = doc["slides"][3]
        self.assertEqual(
            marriage["text"], "Josef Meyer and Anna Keller were married in 1878."
        )
        self.assertEqual(
            marriage["people"], [{"name": "Josef Meyer"}, {"name": "Anna Keller"}]
        )

    def test_a_family_story(self):
        doc, _ = self.written(build_family_story(self.db, self.family))
        self.assertEqual(doc["title"], "The Story of Josef Meyer & Anna Keller")
        # The couple's events and everyone's births and deaths; not Karl's
        # baptism or Josef's christening and census.
        self.assertEqual(
            self.titles(doc),
            [
                "The Story of Josef Meyer & Anna Keller",
                "Birth of Josef Meyer",
                "Marriage of Josef Meyer & Anna Keller",
                "Birth of Karl Meyer",
                "Death of Josef Meyer",
                "Death of Karl Meyer",
                "Birth of Anna Keller",
            ],
        )
        self.assertEqual(
            doc["slides"][0]["text"],
            "6 moments from the life of Josef Meyer & Anna Keller and their child.",
        )
        refs = {s["title"]: s.get("media", [{}])[0].get("ref") for s in doc["slides"]}
        # Karl's slides show Karl; the opening slide a parent's portrait.
        self.assertEqual(refs["Birth of Karl Meyer"], refs["Death of Karl Meyer"])
        self.assertNotEqual(refs["Birth of Karl Meyer"], refs[doc["title"]])
        self.assertEqual(refs[doc["title"]], refs["Death of Josef Meyer"])

    def test_a_family_story_leaves_out_who_isnt_wanted(self):
        doc, _ = self.written(
            build_family_story(self.db, self.family, excluded={self.anna})
        )
        self.assertNotIn("Birth of Anna Keller", self.titles(doc))
        self.assertIn("Marriage of Josef Meyer & Anna Keller", self.titles(doc))

    def test_private_records_left_out(self):
        doc, _ = self.written(build_person_story(PrivateProxyDb(self.db), self.josef))
        self.assertNotIn("Christening of Josef Meyer", self.titles(doc))

    def test_living_people_left_out(self):
        db = LivingProxyDb(self.db, LivingProxyDb.MODE_EXCLUDE_ALL)
        allowed = no_living_in_photo(self.db)
        doc, _ = self.written(
            build_person_story(db, self.josef, True, photo_allowed=allowed)
        )
        titles = self.titles(doc)
        # Gramps clears the events of a family with a living parent
        # (LivingProxyDb), and hides Anna herself...
        self.assertNotIn("Marriage of Josef Meyer & Anna Keller", titles)
        self.assertNotIn("Birth of Anna Keller", titles)
        # ...and the census keeps its slide but not the photo Anna is in:
        # it falls back to Josef's portrait.
        census = doc["slides"][titles.index("Census of Josef Meyer")]
        self.assertEqual(census["media"], doc["slides"][0]["media"])
        self.assertTrue(allowed(self.media["birth"]))
        self.assertFalse(allowed(self.media["couple"]))

    def test_a_living_subject_is_refused(self):
        db = LivingProxyDb(self.db, LivingProxyDb.MODE_EXCLUDE_ALL)
        with self.assertRaises(StoryExportError):
            build_person_story(db, self.anna)

    def test_left_out_reason_names_the_option(self):
        self.assertIn(
            "Include living people",
            left_out_reason(self.db, "person", self.anna, True, False),
        )
        self.assertIsNone(left_out_reason(self.db, "person", self.anna, False, True))
        self.assertIsNone(left_out_reason(self.db, "person", self.josef, False, False))
        self.assertIsNone(left_out_reason(self.db, "family", self.family, False, False))

    def test_viewer_page_holds_the_story(self):
        import base64
        import re

        out = io.BytesIO()
        build_person_story(self.db, self.josef).write(out)
        page = viewer_page(out.getvalue(), "Josef <Meyer>", "de")
        self.assertIn("Josef &lt;Meyer&gt;", page)
        self.assertIn('<html lang="de">', page)
        self.assertIn("@gramps-connect/story@0.1/dist/embed.js", page)
        data = re.search(r'<script id="story"[^>]*>([^<]*)</script>', page)
        self.assertEqual(base64.b64decode(data.group(1)), out.getvalue())

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
