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
Generate a person's or a family's story -- one slide per event, in date
order, after an opening slide -- as a gramps_connect_story.Story, by the
same rules as Gramps Connect's "Add a story". No GUI imports, so it can be
tested without a display; StoryExport.py is the tool around it.
"""

import base64
import html
import json
import math
import os
from xml.etree import ElementTree

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.datehandler import displayer as date_displayer
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.lib import Date, EventRoleType, EventType
from gramps.gen.utils.alive import probably_alive
from gramps.gen.utils.file import media_path_full
from gramps.gen.utils.place import conv_lat_lon
from gramps.version import VERSION

from gramps_connect_story import OVERLAY_MAX_EDGE, Story

_trans = glocale.get_addon_translator(__file__)
_ = _trans.gettext
ngettext = _trans.ngettext


#: The story player, from the @gramps-connect/story npm package: its
#: latest 0.x release, so pages get each new player (0.x releases only
#: add to the <gramps-connect-story> element this page uses).
PLAYER_URL = "https://cdn.jsdelivr.net/npm/@gramps-connect/story@0/dist/embed.js"

_VIEWER_PAGE = """<!doctype html>
<html lang="%(lang)s"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<link rel="icon" href="data:image/svg+xml,%%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%%3E%%3Crect width='64' height='64' rx='15' fill='%%231866ba'/%%3E%%3Cg transform='translate(9.6 9.6) scale(0.7)'%%3E%%3Cpath d='M25 32h7M32 15v34M32 15h7M32 49h7' fill='none' stroke='%%23fff' stroke-width='5' stroke-linecap='round'/%%3E%%3Cg fill='%%23fff'%%3E%%3Crect x='1' y='24' width='24' height='16' rx='4'/%%3E%%3Crect x='39' y='7' width='24' height='16' rx='4'/%%3E%%3Crect x='39' y='41' width='24' height='16' rx='4'/%%3E%%3C/g%%3E%%3C/g%%3E%%3C/svg%%3E">
<style>html,body{margin:0;height:100%%}
gramps-connect-story{display:block;height:100vh}</style>
<script type="module" src="%(player)s"></script>
</head><body>
<gramps-connect-story brand></gramps-connect-story>
<script id="story" type="application/octet-stream">%(data)s</script>
<script>
const text = atob(document.getElementById("story").textContent);
const bytes = new Uint8Array(text.length);
for (let i = 0; i < text.length; i++) bytes[i] = text.charCodeAt(i);
document.querySelector("gramps-connect-story").setAttribute("src",
  URL.createObjectURL(new Blob([bytes], {type: "application/zip"})));
</script>
</body></html>
"""


def viewer_page(story_zip, title, lang="en"):
    """A web page that plays the .story.zip (bytes) it contains, so a
    browser can open it from disk: a page can't read a local file by its
    path. The player comes from PLAYER_URL, so it needs the internet."""
    return _VIEWER_PAGE % {
        "lang": html.escape(lang or "en"),
        "title": html.escape(title),
        "player": PLAYER_URL,
        "data": base64.b64encode(story_zip).decode("ascii"),
    }


class StoryExportError(Exception):
    """The story can't be built (shown to the user as is)."""


def _edtf_part(part):
    """(day, month, year, slash) -> "1850", "1850-03" or "1850-03-12"."""
    day, month, year, slash = part
    if slash or year <= 0 or year > 9999:
        return None
    if not 1 <= month <= 12:
        return "%04d" % year
    if day < 1:
        return "%04d-%02d" % (year, month)
    return "%04d-%02d-%02d" % (year, month, day)


def to_edtf(date):
    """
    The date in Extended Date/Time Format, or None when it doesn't map
    faithfully: only Gregorian dates with a real year, January new year,
    and no dual dating. (The same rules as Gramps Connect's downloads.)
    """
    if date is None or date.is_empty() or date.get_calendar() != Date.CAL_GREGORIAN:
        return None
    if (
        date.get_new_year() != Date.NEWYEAR_JAN1
        or date.get_modifier() == Date.MOD_TEXTONLY
    ):
        return None
    start = _edtf_part(date.get_start_date())
    if start is None:
        return None
    modifier = date.get_modifier()
    q = (
        "~"
        if date.get_quality() != Date.QUAL_NONE or modifier == Date.MOD_ABOUT
        else ""
    )
    if modifier in (Date.MOD_NONE, Date.MOD_ABOUT):
        return start + q
    if modifier in (Date.MOD_BEFORE, Date.MOD_TO):
        return "../" + start + q
    if modifier in (Date.MOD_AFTER, Date.MOD_FROM):
        return start + q + "/.."
    if modifier in (Date.MOD_RANGE, Date.MOD_SPAN):
        stop = _edtf_part(date.get_stop_date())
        if stop is None:
            return None
        if modifier == Date.MOD_RANGE:
            return "[%s%s..%s%s]" % (start, q, stop, q)
        return "%s%s/%s%s" % (start, q, stop, q)
    return None


def sort_year(date):
    """The date's (start) year in the Gregorian calendar, or None."""
    if date is None or date.is_empty() or date.get_modifier() == Date.MOD_TEXTONLY:
        return None
    if date.get_calendar() != Date.CAL_GREGORIAN:
        date = Date(date)
        date.convert_calendar(Date.CAL_GREGORIAN)
    year = date.get_year()
    return year if year else None


def _image_path(db, media_handle):
    """Full path of an image media object whose file exists, else None."""
    media = db.get_media_from_handle(media_handle)
    if media is None or not (media.get_mime_type() or "").startswith("image/"):
        return None
    path = media_path_full(db, media.get_path())
    return path if os.path.isfile(path) else None


def _first_image(db, media_refs, allowed):
    for ref in media_refs:
        handle = ref.get_reference_handle()
        if not allowed(handle):
            continue
        path = _image_path(db, handle)
        if path:
            return path
    return None


def _event_place(db, event):
    place_handle = event.get_place_handle()
    return db.get_place_from_handle(place_handle) if place_handle else None


# A place's map files, as Gramps Connect draws them: its "Map overlay"
# media (GeoJSON written by Gramps Connect, holding shapes and image
# overlays), or failing those, its KML files (what Gramps' own Geography
# views draw). Not both: an overlay is usually made from a KML file that
# stays attached beside it, and would otherwise be drawn twice.

#: The tag Gramps Connect gives its map overlay media.
OVERLAY_TAG = "Map overlay"
#: Marks a feature in an overlay file as an image overlay: its Polygon is
#: the image's corners (top-left, top-right, bottom-right, bottom-left,
#: closed) and its "image" property the picture's media handle.
IMAGE_OVERLAY_PROPERTY = "gramps:image-overlay"
GEOJSON_MIME = "application/geo+json"
KML_MIME = "application/vnd.google-earth.kml+xml"
#: Map files bigger than this are skipped rather than read.
MAP_FILE_LIMIT = 20 * 1024 * 1024


def _media_file(db, media):
    path = media_path_full(db, media.get_path())
    if not os.path.isfile(path) or os.path.getsize(path) > MAP_FILE_LIMIT:
        return None
    return path


def _has_tag(db, obj, name):
    for handle in obj.get_tag_list():
        tag = db.get_tag_from_handle(handle)
        if tag is not None and tag.get_name() == name:
            return True
    return False


def _is_overlay_file(db, media):
    path = media.get_path().lower()
    return (
        media.get_mime_type() == GEOJSON_MIME or path.endswith(".geojson")
    ) and _has_tag(db, media, OVERLAY_TAG)


def _is_kml_file(media):
    return media.get_mime_type() == KML_MIME or media.get_path().lower().endswith(
        ".kml"
    )


def _simplestyle(feature):
    """A GeoJSON file's own colours (stroke, fill, fill-opacity,
    marker-color) as the color/opacity properties the player reads; an
    explicit color wins."""
    props = dict(feature.get("properties") or {})
    region = (feature.get("geometry") or {}).get("type") in (
        "Polygon",
        "MultiPolygon",
    )
    if props.get("color") is None:
        color = (
            props.get("fill") or props.get("stroke")
            if region
            else props.get("stroke") or props.get("marker-color")
        )
        if color is not None:
            props["color"] = color
    if props.get("opacity") is None and region and "fill-opacity" in props:
        props["opacity"] = props["fill-opacity"]
    return dict(feature, properties=props)


def _geojson_features(doc):
    if not isinstance(doc, dict):
        return []
    if doc.get("type") == "FeatureCollection":
        return [f for f in doc.get("features") or [] if isinstance(f, dict)]
    if doc.get("type") == "Feature":
        return [doc]
    if doc.get("type"):
        return [{"type": "Feature", "geometry": doc, "properties": {}}]
    return []


def _number(value, default):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def read_overlay_file(path):
    """(shapes, image overlays) of a Gramps Connect overlay file: GeoJSON
    features, and (image handle, corners, opacity, order or None) each.
    Anything unreadable gives nothing rather than an error."""
    try:
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle)
    except (OSError, ValueError):
        return [], []
    shapes, images = [], []
    for feature in _geojson_features(doc):
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            continue
        props = feature.get("properties") or {}
        if props.get(IMAGE_OVERLAY_PROPERTY) is True and isinstance(
            props.get("image"), str
        ):
            ring = (geometry.get("coordinates") or [[]])[0]
            if geometry.get("type") != "Polygon" or len(ring) != 5:
                continue
            opacity = _number(props.get("opacity"), 1)
            images.append(
                (
                    props["image"],
                    [[float(x), float(y)] for x, y, *_rest in ring[:4]],
                    opacity if 0 <= opacity <= 1 else 1,
                    _number(props.get("order"), None),
                )
            )
        else:
            shapes.append(_simplestyle(feature))
    return shapes, images


def _local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _kml_coords(element):
    for child in element.iter():
        if _local(child.tag) == "coordinates":
            points = []
            for chunk in (child.text or "").split():
                parts = chunk.split(",")
                try:
                    points.append([float(parts[0]), float(parts[1])])
                except (IndexError, ValueError):
                    continue
            return points
    return []


def _kml_ring(boundary):
    for child in boundary.iter():
        if _local(child.tag) == "LinearRing":
            return _kml_coords(child)
    return []


def _kml_geometry(element):
    kind = _local(element.tag)
    if kind == "Point":
        points = _kml_coords(element)
        return {"type": "Point", "coordinates": points[0]} if points else None
    if kind == "LineString":
        points = _kml_coords(element)
        return {"type": "LineString", "coordinates": points} if points else None
    if kind == "Polygon":
        outer = [c for c in element if _local(c.tag) == "outerBoundaryIs"]
        rings = [_kml_ring(outer[0])] if outer else []
        rings += [_kml_ring(c) for c in element if _local(c.tag) == "innerBoundaryIs"]
        rings = [ring for ring in rings if len(ring) >= 4]
        return {"type": "Polygon", "coordinates": rings} if rings else None
    if kind == "MultiGeometry":
        parts = [_kml_geometry(child) for child in element]
        parts = [part for part in parts if part]
        return {"type": "GeometryCollection", "geometries": parts} if parts else None
    return None


def read_kml_file(path):
    """The shapes (points, lines, polygons) in a KML file's placemarks, as
    GeoJSON features: what Gramps' Geography views draw. Anything
    unreadable gives nothing rather than an error."""
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError):
        return []
    features = []
    for placemark in root.iter():
        if _local(placemark.tag) != "Placemark":
            continue
        for child in placemark:
            geometry = _kml_geometry(child)
            if geometry:
                props = {}
                for name in placemark:
                    if _local(name.tag) == "name" and (name.text or "").strip():
                        props["name"] = name.text.strip()
                features.append(
                    {"type": "Feature", "geometry": geometry, "properties": props}
                )
                break
    return features


def place_maps(db, place):
    """(shapes, image overlays) of a place's map files; see above."""
    overlay_files, kml_files = [], []
    for ref in place.get_media_list():
        media = db.get_media_from_handle(ref.get_reference_handle())
        if media is None:
            continue
        if _is_overlay_file(db, media):
            overlay_files.append(media)
        elif _is_kml_file(media):
            kml_files.append(media)
    shapes, images = [], []
    if overlay_files:
        for media in overlay_files:
            path = _media_file(db, media)
            if path:
                more_shapes, more_images = read_overlay_file(path)
                shapes += more_shapes
                images += more_images
    else:
        for media in kml_files:
            path = _media_file(db, media)
            if path:
                shapes += read_kml_file(path)
    return shapes, images


def no_living_in_photo(db):
    """A photo_allowed for the build functions: refuses a photo any
    probably living person is linked to. ``db`` must be the real database,
    not a LivingProxyDb, which hides exactly the people this looks for."""

    def allowed(media_handle):
        for _class, handle in db.find_backlink_handles(media_handle, ["Person"]):
            person = db.get_person_from_handle(handle)
            if person is not None and probably_alive(person, db):
                return False
        return True

    return allowed


def left_out_reason(db, kind, handle, include_private, include_living):
    """Why the chosen privacy settings leave the story's subject (a
    "person" or a "family") out, saying which option would include them;
    None if they're included. ``db`` must be the real database, as for
    no_living_in_photo()."""
    if kind == "family":
        family = db.get_family_from_handle(handle)
        if family is not None and not include_private and family.get_privacy():
            return _(
                "This family is marked private. To generate its story, check "
                '"Include data marked private".'
            )
        return None
    person = db.get_person_from_handle(handle)
    if person is None:
        return None
    name = person_name(person)
    if not include_private and person.get_privacy():
        return (
            _(
                '%s is marked private. To generate their story, check "Include data '
                'marked private".'
            )
            % name
        )
    if not include_living and probably_alive(person, db):
        return (
            _(
                '%s is probably living. To generate their story, check "Include '
                'living people".'
            )
            % name
        )
    return None


# The sentence each slide starts with, as in Gramps Connect's own story
# builder (app/src/store/storyText.ts): a seed the author can rewrite, so
# no slide is born blank.

#: What one person did, by event type.
PERSON_PHRASES = {
    EventType.BIRTH: _("%(who)s was born"),
    EventType.STILLBIRTH: _("%(who)s was stillborn"),
    EventType.BAPTISM: _("%(who)s was baptized"),
    EventType.CHRISTEN: _("%(who)s was christened"),
    EventType.ADULT_CHRISTEN: _("%(who)s was christened"),
    EventType.BLESS: _("%(who)s was blessed"),
    EventType.CONFIRMATION: _("%(who)s was confirmed"),
    EventType.FIRST_COMMUN: _("%(who)s took First Communion"),
    EventType.BAR_MITZVAH: _("%(who)s celebrated their Bar Mitzvah"),
    EventType.BAS_MITZVAH: _("%(who)s celebrated their Bas Mitzvah"),
    EventType.ADOPT: _("%(who)s was adopted"),
    EventType.GRADUATION: _("%(who)s graduated"),
    EventType.DEGREE: _("%(who)s was awarded a degree"),
    EventType.EMIGRATION: _("%(who)s emigrated"),
    EventType.IMMIGRATION: _("%(who)s immigrated"),
    EventType.NATURALIZATION: _("%(who)s was naturalized"),
    EventType.ORDINATION: _("%(who)s was ordained"),
    EventType.ELECTED: _("%(who)s was elected"),
    EventType.RETIREMENT: _("%(who)s retired"),
    EventType.DEATH: _("%(who)s died"),
    EventType.BURIAL: _("%(who)s was buried"),
    EventType.CREMATION: _("%(who)s was cremated"),
    EventType.PROBATE: _("%(who)s had their estate probated"),
}

#: What a couple did together: used when a moment is about two people.
COUPLE_PHRASES = {
    EventType.MARRIAGE: _("%(who)s were married"),
    EventType.MARR_ALT: _("%(who)s were married"),
    EventType.MARR_BANNS: _("%(who)s had their banns read"),
    EventType.MARR_CONTR: _("%(who)s signed a marriage contract"),
    EventType.MARR_LIC: _("%(who)s took out a marriage license"),
    EventType.MARR_SETTL: _("%(who)s agreed a marriage settlement"),
    EventType.ENGAGEMENT: _("%(who)s were engaged"),
    EventType.DIVORCE: _("%(who)s were divorced"),
    EventType.DIV_FILING: _("%(who)s filed for divorce"),
    EventType.ANNULMENT: _("%(who)s had their marriage annulled"),
    EventType.CENSUS: _("%(who)s were recorded in the census"),
    EventType.RESIDENCE: _("%(who)s lived"),
}

#: A family member's own moments in a family story: the ones that open
#: and close a life, so the household's arc isn't buried under each
#: member's census rows and residences.
VITAL_TYPES = (EventType.BIRTH, EventType.STILLBIRTH, EventType.DEATH)

#: Roles that make an event the subject's own (they were born, married),
#: rather than one they took part in (a witness at a baptism).
SUBJECT_ROLES = (EventRoleType.PRIMARY, EventRoleType.FAMILY, EventRoleType.UNKNOWN)


def person_name(person):
    """ "Josef Meyer": given name(s) then surname, as in prose, whatever
    the tree's display format."""
    name = person.get_primary_name()
    text = " ".join(
        part for part in (name.get_first_name(), name.get_surname()) if part
    )
    return text or name_displayer.display(person)


def join_names(names):
    """ "Hans Meyer & Anna Schmidt", for a title."""
    return " & ".join(name for name in names if name)


def _join_prose(names):
    names = [name for name in names if name]
    if len(names) <= 1:
        return names[0] if names else ""
    return _("%(names)s and %(last)s") % {
        "names": ", ".join(names[:-1]),
        "last": names[-1],
    }


def _sentence(text):
    text = text.strip()
    if not text:
        return ""
    return text if text[-1] in ".!?…" else text + "."


def _is_subject_role(role):
    return role is None or role.value in SUBJECT_ROLES


def _date_text(date):
    """The date as Gramps shows it, and the word to put before it: "on"
    a day, "in" a month or year, nothing for "about 1850" and the like,
    which read as their own phrase."""
    if date is None or date.is_empty():
        return "", ""
    text = date_displayer.display(date)
    if (
        date.get_modifier() != Date.MOD_NONE
        or date.get_quality() != Date.QUAL_NONE
        or not date.get_year()
    ):
        return text, ""
    return text, "on" if date.get_day() else "in"


def moment_title(event, subjects, role=None):
    """ "Birth of Josef Meyer", "Marriage of Hans Meyer & Anna Schmidt",
    or the bare type when there's nobody to name."""
    kind = str(event.get_type())
    if not _is_subject_role(role):
        return _("%(type)s (%(role)s)") % {"type": kind, "role": str(role)}
    names = join_names(subjects)
    return _("%(type)s of %(who)s") % {"type": kind, "who": names} if names else kind


def moment_text(db, event, subjects, role=None):
    """One sentence placing the moment ("Josef Meyer was born about 1850 in
    Zürich."), then the event's own description, if it adds anything."""
    kind = str(event.get_type())
    who = _join_prose(subjects)
    phrases = COUPLE_PHRASES if len(subjects) == 2 else PERSON_PHRASES
    phrase = phrases.get(event.get_type().value)
    if not _is_subject_role(role) and who:
        text = _("%(who)s took part in this %(type)s as %(role)s") % {
            "who": who,
            "type": kind,
            "role": str(role),
        }
    elif phrase and who:
        text = phrase % {"who": who}
    elif who:
        text = _("%(type)s of %(who)s") % {"type": kind, "who": who}
    else:
        text = kind

    date, preposition = _date_text(event.get_date_object())
    if date and preposition == "on":
        text = _("%(moment)s on %(date)s") % {"moment": text, "date": date}
    elif date and preposition == "in":
        text = _("%(moment)s in %(date)s") % {"moment": text, "date": date}
    elif date:
        text = _("%(moment)s %(date)s") % {"moment": text, "date": date}
    place = place_displayer.display_event(db, event) if event.get_place_handle() else ""
    if place:
        text = _("%(moment)s in %(place)s") % {"moment": text, "place": place}
    text = _sentence(text)

    extra = (event.get_description() or "").strip()
    if extra and extra.lower() != kind.lower() and extra not in text:
        text = "%s %s" % (text, _sentence(extra))
    return text or kind


class _Moments:
    """The slides being drafted: each event once, with who it's about and
    where its photo may come from, in the order found."""

    def __init__(self, db, allowed):
        self.db = db
        self.allowed = allowed
        self.drafts = []
        self.seen = set()
        self.maps = {}

    def add(self, event_handle, role, subjects, portraits=()):
        """Draft an event's slide, unless it's already drafted or hidden."""
        if event_handle in self.seen:
            return
        event = self.db.get_event_from_handle(event_handle)
        if event is None:
            return
        self.seen.add(event_handle)
        self.drafts.append((event, role, subjects, portraits))

    def add_vital(self, people):
        """Each person's own births, stillbirths and deaths."""
        for person in people:
            name = person_name(person)
            for ref in person.get_event_ref_list():
                if not _is_subject_role(ref.get_role()):
                    continue
                event = self.db.get_event_from_handle(ref.ref)
                if event is None or event.get_type().value not in VITAL_TYPES:
                    continue
                self.add(ref.ref, ref.get_role(), [name], person.get_media_list())

    def photo(self, event, portraits):
        """The event's own picture, then the face of whoever it's about,
        then the place it happened at."""
        db, allowed = self.db, self.allowed
        found = _first_image(db, event.get_media_list(), allowed)
        found = found or _first_image(db, portraits, allowed)
        place = _event_place(db, event)
        return found or (place and _first_image(db, place.get_media_list(), allowed))

    def place(self, story, event):
        """The slide's place: its name and coordinates, and its map files'
        shapes and image overlays (read once per place)."""
        db = self.db
        place = _event_place(db, event)
        if place is None:
            return None
        result = {"name": place_displayer.display_event(db, event) or None}
        lat, lon = conv_lat_lon(place.get_latitude(), place.get_longitude(), "D.D8")
        if lat is not None and lon is not None:
            result["lat"] = float(lat)
            result["lon"] = float(lon)
        if place.handle not in self.maps:
            self.maps[place.handle] = self.place_maps(story, place)
        result.update(self.maps[place.handle])
        return result

    def place_maps(self, story, place):
        """{"geometry": ..., "overlays": [...]} for a place, or what of it
        there is. An overlay's era is the place's own name date, as in
        Gramps Connect."""
        db = self.db
        shapes, images = place_maps(db, place)
        result = {}
        if shapes:
            result["geometry"] = {"type": "FeatureCollection", "features": shapes}
        name_date = place.get_name().get_date_object()
        date = None
        if not name_date.is_empty():
            date = {"text": date_displayer.display(name_date)}
            edtf = to_edtf(name_date)
            if edtf:
                date["edtf"] = edtf
        overlays = []
        for image_handle, corners, opacity, order in images:
            if not self.allowed(image_handle):
                continue
            path = _image_path(db, image_handle)
            if not path:
                continue
            overlay = {
                "media": story.add_media(path, max_edge=OVERLAY_MAX_EDGE),
                "corners": corners,
                "opacity": opacity,
                "order": int(round(order if order is not None else len(overlays) * 10)),
            }
            if date:
                overlay["date"] = date
            overlays.append(overlay)
        if overlays:
            result["overlays"] = overlays
        return result

    def add_to(self, story, fallback_photo=None):
        """The slides, dated ones in date order and then undated ones in
        the order found."""
        drafts = sorted(
            self.drafts,
            key=lambda d: (
                d[0].get_date_object().get_sort_value() == 0,
                d[0].get_date_object().get_sort_value(),
            ),
        )
        for event, role, subjects, portraits in drafts:
            date = event.get_date_object()
            date_text = date_displayer.display(date) if not date.is_empty() else ""
            story.add_slide(
                title=moment_title(event, subjects, role),
                text=moment_text(self.db, event, subjects, role),
                date=(
                    {
                        "text": date_text,
                        "edtf": to_edtf(date),
                        "sortYear": sort_year(date),
                    }
                    if date_text
                    else None
                ),
                place=self.place(story, event),
                photo=self.photo(event, portraits) or fallback_photo,
                people=subjects,
            )


def _new_story(title):
    return Story(
        title,
        language=glocale.lang,
        generator={
            "name": "Gramps",
            "version": VERSION,
            "url": "https://gramps-project.org",
        },
    )


def _moments_text(count):
    return ngettext("%d moment", "%d moments", count) % count


def _family_members(db, family):
    """(spouses, children) of a family, as Person objects, skipping any
    the database hides."""
    spouses = []
    for handle in (family.get_father_handle(), family.get_mother_handle()):
        person = db.get_person_from_handle(handle) if handle else None
        if person is not None:
            spouses.append(person)
    children = []
    for ref in family.get_child_ref_list():
        person = db.get_person_from_handle(ref.ref)
        if person is not None:
            children.append(person)
    return spouses, children


def _add_family_events(moments, family, spouse_names):
    for ref in family.get_event_ref_list():
        moments.add(ref.ref, ref.get_role(), spouse_names)


def build_person_story(db, person_handle, include_families=False, photo_allowed=None):
    """
    A person's story: their own events in date order, with undated ones
    last, after an opening slide with their portrait. With
    ``include_families``, also each family they belong to, as a parent
    (spouse, children) or as a child (parents, siblings): its own events,
    and its members' births and deaths.

    ``db`` may be a proxy (PrivateProxyDb, LivingProxyDb): whatever it
    hides is left out. ``photo_allowed(media_handle)``, if given, can veto
    individual photos (e.g. ones showing a living person).
    """
    allowed = photo_allowed or (lambda handle: True)
    person = db.get_person_from_handle(person_handle)
    if person is None:
        raise StoryExportError(
            _("This person isn't included with the chosen privacy settings.")
        )
    name = person_name(person)

    moments = _Moments(db, allowed)
    for ref in person.get_event_ref_list():
        moments.add(ref.ref, ref.get_role(), [name])
    if include_families:
        for family_handle in (
            person.get_family_handle_list() + person.get_parent_family_handle_list()
        ):
            family = db.get_family_from_handle(family_handle)
            if family is None:
                continue
            spouses, children = _family_members(db, family)
            _add_family_events(moments, family, [person_name(p) for p in spouses])
            moments.add_vital(
                p for p in spouses + children if p.get_handle() != person_handle
            )
    if not moments.drafts:
        raise StoryExportError(_("%s has no events to build a story from.") % name)

    portrait = _first_image(db, person.get_media_list(), allowed)
    title = _("The Story of %s") % name
    story = _new_story(title)
    story.add_slide(
        title=title,
        text=_("%(moments)s from %(name)s's recorded life.")
        % {"moments": _moments_text(len(moments.drafts)), "name": name},
        photo=portrait,
        people=[name],
    )
    moments.add_to(story, fallback_photo=portrait)
    return story


def build_family_story(db, family_handle, excluded=(), photo_allowed=None):
    """
    A family's story: the couple's own events (marriage, divorce, a shared
    residence) merged by date with the births and deaths of both spouses
    and every child, except the people (handles) in ``excluded``. Each
    member's slide prefers their own portrait; the couple's prefer the
    place's picture.

    ``db`` and ``photo_allowed`` as for build_person_story().
    """
    allowed = photo_allowed or (lambda handle: True)
    family = db.get_family_from_handle(family_handle)
    if family is None:
        raise StoryExportError(
            _("This family isn't included with the chosen privacy settings.")
        )
    spouses, children = _family_members(db, family)
    spouse_names = [person_name(p) for p in spouses]
    couple = join_names(spouse_names) or _("this family")

    moments = _Moments(db, allowed)
    _add_family_events(moments, family, spouse_names)
    moments.add_vital(
        p for p in spouses + children if p.get_handle() not in set(excluded)
    )
    if not moments.drafts:
        raise StoryExportError(
            _(
                "This family has no events to build a story from: not on the "
                "family itself, and no births or deaths recorded for its members."
            )
        )

    photo = _first_image(db, family.get_media_list(), allowed)
    for spouse in spouses:
        photo = photo or _first_image(db, spouse.get_media_list(), allowed)
    title = _("The Story of %s") % couple
    count = _moments_text(len(moments.drafts))
    if children:
        text = _("%(moments)s from the life of %(couple)s and %(children)s.") % {
            "moments": count,
            "couple": couple,
            "children": ngettext(
                "their child", "their %(count)d children", len(children)
            )
            % {"count": len(children)},
        }
    else:
        text = _("%(moments)s from the life of %(couple)s.") % {
            "moments": count,
            "couple": couple,
        }
    story = _new_story(title)
    story.add_slide(title=title, text=text, photo=photo, people=spouse_names)
    moments.add_to(story)
    return story


def family_label(db, family):
    """ "Hans Meyer & Anna Schmidt", or a fallback for a family with
    neither parent set."""
    spouses, _children = _family_members(db, family)
    return join_names(person_name(p) for p in spouses) or _("Family %s") % (
        family.get_gramps_id()
    )
