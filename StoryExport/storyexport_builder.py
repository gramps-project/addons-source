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
Build a person's story -- one slide per event, in date order, after an
opening slide -- as a gramps_connect_story.Story. No GUI imports, so it
can be tested without a display; StoryExport.py is the tool around it.
"""

import os

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.datehandler import displayer as date_displayer
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.lib import Date, EventRoleType
from gramps.gen.utils.alive import probably_alive
from gramps.gen.utils.file import media_path_full
from gramps.gen.utils.place import conv_lat_lon
from gramps.version import VERSION

from gramps_connect_story import Story

_trans = glocale.get_addon_translator(__file__)
_ = _trans.gettext
ngettext = _trans.ngettext


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


def _place(db, event):
    place_handle = event.get_place_handle()
    place = db.get_place_from_handle(place_handle) if place_handle else None
    if place is None:
        return None
    result = {"name": place_displayer.display_event(db, event) or None}
    lat, lon = conv_lat_lon(place.get_latitude(), place.get_longitude(), "D.D8")
    if lat is not None and lon is not None:
        result["lat"] = float(lat)
        result["lon"] = float(lon)
    return result


def no_living_in_photo(db):
    """A photo_allowed for build_story(): refuses a photo any probably
    living person is linked to. ``db`` must be the real database, not a
    LivingProxyDb, which hides exactly the people this looks for."""

    def allowed(media_handle):
        for _class, handle in db.find_backlink_handles(media_handle, ["Person"]):
            person = db.get_person_from_handle(handle)
            if person is not None and probably_alive(person, db):
                return False
        return True

    return allowed


def left_out_reason(db, person_handle, include_private, include_living):
    """Why the chosen privacy settings leave this person out, saying which
    option would include them; None if they're included. ``db`` must be
    the real database, as for no_living_in_photo()."""
    person = db.get_person_from_handle(person_handle)
    if person is None:
        return None
    name = name_displayer.display(person)
    if not include_private and person.get_privacy():
        return (
            _(
                '%s is marked private. To export their story, check "Include data '
                'marked private".'
            )
            % name
        )
    if not include_living and probably_alive(person, db):
        return (
            _(
                '%s is probably living. To export their story, check "Include '
                'living people".'
            )
            % name
        )
    return None


def build_story(db, person_handle, photo_allowed=None):
    """
    The story of one person: their own events (where they're the primary
    participant) and their families' events, in date order with undated
    events last, after an opening slide with their portrait.

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
    name = name_displayer.display(person)

    # (event, names of who it's about), each event once.
    events = []
    seen = set()
    for ref in person.get_event_ref_list():
        if ref.get_role() != EventRoleType.PRIMARY or ref.ref in seen:
            continue
        event = db.get_event_from_handle(ref.ref)
        if event is not None:
            seen.add(ref.ref)
            events.append((event, [name]))
    for family_handle in person.get_family_handle_list():
        family = db.get_family_from_handle(family_handle)
        if family is None:
            continue
        spouses = []
        for handle in (family.get_father_handle(), family.get_mother_handle()):
            spouse = db.get_person_from_handle(handle) if handle else None
            if spouse is not None:
                spouses.append(name_displayer.display(spouse))
        for ref in family.get_event_ref_list():
            if ref.get_role() != EventRoleType.FAMILY or ref.ref in seen:
                continue
            event = db.get_event_from_handle(ref.ref)
            if event is not None:
                seen.add(ref.ref)
                events.append((event, spouses))

    if not events:
        raise StoryExportError(_("%s has no events to make a story from.") % name)
    # Dated events by date, then undated ones in the order found.
    events.sort(
        key=lambda item: (
            item[0].get_date_object().get_sort_value() == 0,
            item[0].get_date_object().get_sort_value(),
        )
    )

    portrait = _first_image(db, person.get_media_list(), allowed)
    title = _("The Story of %s") % name
    story = Story(
        title,
        language=glocale.lang,
        generator={
            "name": "Gramps",
            "version": VERSION,
            "url": "https://gramps-project.org",
        },
    )
    story.add_slide(
        title=title,
        text=ngettext(
            "%(count)d event from the life of %(name)s.",
            "%(count)d events from the life of %(name)s.",
            len(events),
        )
        % {"count": len(events), "name": name},
        photo=portrait,
        people=[name],
    )

    for event, people in events:
        date = event.get_date_object()
        date_text = date_displayer.display(date) if not date.is_empty() else ""
        photo = _first_image(db, event.get_media_list(), allowed) or portrait
        story.add_slide(
            title=str(event.get_type()),
            text=event.get_description() or None,
            date=(
                {"text": date_text, "edtf": to_edtf(date), "sortYear": sort_year(date)}
                if date_text
                else None
            ),
            place=_place(db, event),
            photo=photo,
            people=people,
        )
    return story
