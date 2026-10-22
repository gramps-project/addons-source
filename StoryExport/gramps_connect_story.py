#
# gramps_connect_story.py -- write .story.zip files
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
Write family-history stories as ``.story.zip`` files, the portable format
specified at https://github.com/dsblank/gramps-connect-stories (spec/1.0).

One file, standard library only, so any program can copy it in. Pillow,
when installed, is used to size photos for viewing and strip their
metadata; without it, photos are stored as they are.

    from gramps_connect_story import Story

    story = Story("The Story of Josef Meyer", language="en")
    story.add_slide(
        title="Birth",
        text="Josef was born *about* 1850.",
        date={"text": "about 1850", "edtf": "1850~", "sortYear": 1850},
        place={"name": "Zürich", "lat": 47.37, "lon": 8.54},
        photo="portrait.jpg",
    )
    story.write("josef.story.zip")

Open the result in the viewer at
https://dsblank.github.io/gramps-connect-stories/.

This file is GPL-2.0-or-later (unlike the rest of gramps-connect-stories,
which is AGPL-3.0-or-later), so that GPL programs such as Gramps addons
can include it.
"""

import io
import json
import mimetypes
import os
import re
import zipfile
from datetime import datetime, timezone

FORMAT_ID = "gramps-connect-story"
FORMAT_VERSION = "1.0"

#: Long edge, in pixels, photos are scaled down to (with Pillow).
PHOTO_MAX_EDGE = 1600

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_LANGUAGE = re.compile(r"^[A-Za-z]{2,8}(-[A-Za-z0-9]{1,8})*$")

try:
    from PIL import Image, ImageOps, features

    _HAVE_PIL = True
except ImportError:
    _HAVE_PIL = False


def bcp47(language):
    """'de_AT' (POSIX/Gramps style) -> 'de-AT'; None if it isn't a tag."""
    if not language:
        return None
    tag = language.split(".")[0].replace("_", "-")
    return tag if _LANGUAGE.match(tag) else None


def optimize_photo(data):
    """
    Size a photo for viewing: EXIF rotation applied, long edge at most
    PHOTO_MAX_EDGE, re-encoded (WebP, else JPEG; PNG if it has
    transparency and WebP isn't available), with all metadata dropped.
    Returns (bytes, mime, extension, width, height). Needs Pillow.
    """
    with Image.open(io.BytesIO(data)) as original:
        image = ImageOps.exif_transpose(original)
        image.thumbnail((PHOTO_MAX_EDGE, PHOTO_MAX_EDGE))
        has_alpha = image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        )
        out = io.BytesIO()
        if features.check("webp"):
            image = image.convert("RGBA" if has_alpha else "RGB")
            image.save(out, "WEBP", quality=82)
            mime, ext = "image/webp", "webp"
        elif has_alpha:
            image.convert("RGBA").save(out, "PNG", optimize=True)
            mime, ext = "image/png", "png"
        else:
            image.convert("RGB").save(out, "JPEG", quality=85, optimize=True)
            mime, ext = "image/jpeg", "jpg"
        return out.getvalue(), mime, ext, image.width, image.height


class Story:
    """A story being built: slides in order, and the media they use."""

    def __init__(
        self, title, language=None, authors=None, generator=None, license=None
    ):
        if not title or not title.strip():
            raise ValueError("a story needs a title")
        self.title = title
        self.language = bcp47(language)
        self.authors = authors or []
        self.generator = generator
        self.license = license
        self.slides = []
        self.extensions = {}
        self._media = {}  # key -> {"item": {...}, "data": bytes}
        self._media_by_source = {}

    def add_media(self, source, mime=None, alt=None):
        """
        Add a photo, from a file path or bytes, and return its media key.
        The same path added twice is stored once. With Pillow the photo is
        optimized (see optimize_photo); without it, stored as is, so
        ``mime`` is needed for bytes.
        """
        if isinstance(source, (str, os.PathLike)):
            path = os.fspath(source)
            if path in self._media_by_source:
                return self._media_by_source[path]
            with open(path, "rb") as handle:
                data = handle.read()
            mime = mime or mimetypes.guess_type(path)[0]
        else:
            path = None
            data = bytes(source)

        key = "m%d" % (len(self._media) + 1)
        item = {}
        if _HAVE_PIL:
            data, mime, ext, width, height = optimize_photo(data)
            item.update(width=width, height=height)
        else:
            if not mime:
                raise ValueError("can't tell the type of this photo; pass mime=")
            ext = (mimetypes.guess_extension(mime) or ".bin").lstrip(".")
        item = {"src": "media/%s.%s" % (key, ext), "mime": mime, **item}
        if alt:
            item["alt"] = alt
        self._media[key] = {"item": item, "data": data}
        if path is not None:
            self._media_by_source[path] = key
        return key

    def add_slide(
        self,
        title=None,
        text=None,
        date=None,
        place=None,
        photo=None,
        caption=None,
        credit=None,
        people=None,
    ):
        """
        Add a slide and return it (a dict, which may be edited further).

        date:   {"text": ..., "edtf": ..., "sortYear": ...}; text required.
        place:  {"name": ..., "lat": ..., "lon": ...}; all optional, but
                lat and lon go together.
        photo:  a path, bytes, or a key from add_media().
        people: names of the people the slide is about.
        """
        slide = {"id": "s%d" % len(self.slides)}
        if title:
            slide["title"] = title
        if text:
            slide["text"] = text
        if date:
            slide["date"] = {k: v for k, v in date.items() if v is not None}
        if place:
            place = {k: v for k, v in place.items() if v is not None}
            if place:
                slide["place"] = place
        if photo is not None:
            key = (
                photo
                if isinstance(photo, str) and photo in self._media
                else self.add_media(photo)
            )
            ref = {"ref": key}
            if caption:
                ref["caption"] = caption
            if credit:
                ref["credit"] = credit
            slide["media"] = [ref]
        if people:
            slide["people"] = [{"name": name} for name in people if name]
        self.slides.append(slide)
        return slide

    def to_dict(self):
        """story.json, as a dict."""
        doc = {
            "format": FORMAT_ID,
            "version": FORMAT_VERSION,
            "title": self.title,
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if self.language:
            doc["language"] = self.language
        if self.generator:
            doc["generator"] = self.generator
        if self.authors:
            doc["authors"] = [{"name": name} for name in self.authors]
        if self.license:
            doc["license"] = self.license
        doc["slides"] = self.slides
        doc["media"] = {key: entry["item"] for key, entry in self._media.items()}
        if self.extensions:
            doc["extensions"] = self.extensions
        return doc

    def validate(self):
        """
        Raise ValueError for what would make an invalid story: the checks
        a writer can get wrong (ids, references, coordinates, empty
        text). The full JSON Schema is in the format's spec/.
        """
        if not self.slides:
            raise ValueError("a story needs at least one slide")
        seen = set()
        for slide in self.slides:
            sid = slide.get("id")
            if not isinstance(sid, str) or not _ID.match(sid):
                raise ValueError("bad slide id %r" % (sid,))
            if sid in seen:
                raise ValueError("duplicate slide id %r" % sid)
            seen.add(sid)
            date = slide.get("date")
            if date is not None:
                if not str(date.get("text", "")).strip():
                    raise ValueError("slide %s: a date needs its text" % sid)
                year = date.get("sortYear")
                if year is not None and (
                    isinstance(year, bool) or not isinstance(year, int)
                ):
                    raise ValueError("slide %s: sortYear must be a whole year" % sid)
            place = slide.get("place") or {}
            if ("lat" in place) != ("lon" in place):
                raise ValueError("slide %s: lat and lon go together" % sid)
            if "lat" in place and not (
                -90 <= place["lat"] <= 90 and -180 <= place["lon"] <= 180
            ):
                raise ValueError("slide %s: coordinates out of range" % sid)
            refs = [m["ref"] for m in slide.get("media", [])]
            refs += [o["media"] for o in place.get("overlays", [])]
            for ref in refs:
                if ref not in self._media:
                    raise ValueError("slide %s: unknown media %r" % (sid, ref))

    def write(self, path_or_file):
        """Validate, then write the .story.zip to a path or a binary file."""
        self.validate()
        doc = self.to_dict()
        with zipfile.ZipFile(path_or_file, "w") as archive:
            archive.writestr(
                "story.json",
                json.dumps(doc, ensure_ascii=False, indent=2),
                compress_type=zipfile.ZIP_DEFLATED,
            )
            for entry in self._media.values():
                # Photos are already compressed: store them as they are.
                archive.writestr(
                    entry["item"]["src"],
                    entry["data"],
                    compress_type=zipfile.ZIP_STORED,
                )
