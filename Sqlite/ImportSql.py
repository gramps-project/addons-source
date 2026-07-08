#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009 Douglas S. Blank <doug.blank@gmail.com>
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

"Import from SQLite Database"

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
import json
import sqlite3 as sqlite
import time
from collections import abc

# -------------------------------------------------------------------------
#
# Set up logging
#
# -------------------------------------------------------------------------
import logging

LOG = logging.getLogger(__name__)

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.db import DbTxn
from gramps.gen.lib.json_utils import data_to_object
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    trans = glocale.get_addon_translator(__file__)
except ValueError:
    trans = glocale.translation
_ = trans.gettext
ngettext = trans.ngettext


# -------------------------------------------------------------------------
#
# Helper
#
# -------------------------------------------------------------------------
def _gtype(class_name: str, value: int, string: str) -> dict:
    """Return a GrampsType DataDict."""
    return {"_class": class_name, "value": value, "string": string}


def lookup(handle: str | None, event_ref_list: list) -> int:
    """
    Find the handle in a DataDict event_ref_list and return its index, or -1.
    """
    if handle is None:
        return -1
    for count, event_ref in enumerate(event_ref_list):
        if handle == event_ref["ref"]:
            return count
    return -1


# -------------------------------------------------------------------------
#
# Database
#
# -------------------------------------------------------------------------
class Database(object):
    """
    The SQLite db connection wrapper.
    """

    def __init__(self, database: str) -> None:
        """Open the SQLite database file."""
        self.database = database
        self.db = sqlite.connect(self.database)
        self.cursor = self.db.cursor()

    def query(self, q: str, *args):
        """Execute a query and return all results."""
        if q.strip().upper().startswith("DROP"):
            try:
                self.cursor.execute(q, args)
                self.db.commit()
            except Exception:
                LOG.warning("no such table to drop: '%s'", q)
        else:
            try:
                self.cursor.execute(q, args)
                self.db.commit()
            except Exception:
                LOG.error("query: %s", q)
                LOG.error("values: %s", args)
                raise
            return self.cursor.fetchall()

    def close(self) -> None:
        """Close and write out tables."""
        self.cursor.close()
        self.db.close()


# -------------------------------------------------------------------------
#
# SQLReader
#
# -------------------------------------------------------------------------
class SQLReader(object):
    """
    Reads a Gramps SQLite export file and populates a Gramps database.

    All sub-object helpers return DataDicts (named-key dicts) compatible with
    ``data_to_object()`` from ``gramps.gen.lib.json_utils``.  This avoids
    positional tuple unpacking, making the import forward-compatible with
    any future schema additions in Gramps core.
    """

    def __init__(self, db, filename: str, user) -> None:
        """Initialise the reader with a target database and source file."""
        if isinstance(user.callback, abc.Callable):
            callback = user.callback
        else:
            callback = self.dummy_callback
        self.db = db
        self.filename = filename
        self.callback = callback

    def dummy_callback(self, *args) -> None:
        """No-op progress callback."""

    def openSQL(self):
        """Open the SQLite source file and return a Database connection."""
        try:
            from gramps.gui.dialog import ErrorDialog
        except Exception:
            ErrorDialog = LOG.error
        sql = None
        try:
            sql = Database(self.filename)
        except IOError as msg:
            errmsg = _("%s could not be opened\n") % self.filename
            ErrorDialog(errmsg, msg)
            return None
        return sql

    # -----------------------------------------------
    # Link helpers
    # -----------------------------------------------

    def get_link(self, sql, from_type: str, from_handle: str, to_link: str) -> str | None:
        """Return a single linked handle, or None."""
        if from_handle is None:
            return None
        rows = self.get_links(sql, from_type, from_handle, to_link)
        if len(rows) == 1:
            return rows[0]
        elif len(rows) > 1:
            LOG.error(
                "too many links %s:%s -> %s (%d)",
                from_type, from_handle, to_link, len(rows),
            )
        return None

    def get_links(self, sql, from_type: str, from_handle: str, to_link: str) -> list:
        """Return all linked handles (possibly empty)."""
        results = sql.query(
            "select to_handle from link where from_type = ? "
            "and from_handle = ? and to_type = ?;",
            from_type, from_handle, to_link,
        )
        return [r[0] for r in results]

    # -----------------------------------------------
    # DataDict builders for sub-objects
    # -----------------------------------------------

    def get_date(self, sql, handle: str | None) -> dict | None:
        """Return a Date DataDict for *handle*, or None."""
        if not handle:
            return None
        rows = sql.query("select * from date where handle = ?;", handle)
        if not rows:
            return None
        (
            _handle, calendar, modifier, quality,
            day1, month1, year1, slash1,
            day2, month2, year2, slash2,
            text, sortval, newyear,
        ) = rows[0]
        if day2 == month2 == year2 == 0 and not slash2:
            dateval = [day1, month1, year1, bool(slash1)]
        else:
            dateval = [day1, month1, year1, bool(slash1),
                       day2, month2, year2, bool(slash2)]
        return {
            "_class": "Date",
            "calendar": calendar,
            "modifier": modifier,
            "quality": quality,
            "dateval": dateval,
            "text": text,
            "sortval": sortval,
            "newyear": newyear,
        }

    def get_attribute_list(self, sql, from_type: str, from_handle: str) -> list:
        """Return a list of Attribute DataDicts for *from_handle*."""
        result = []
        for handle in self.get_links(sql, from_type, from_handle, "attribute"):
            rows = sql.query("select * from attribute where handle = ?;", handle)
            for row in rows:
                (handle, the_type0, the_type1, value, private) = row
                result.append({
                    "_class": "Attribute",
                    "private": bool(private),
                    "citation_list": self.get_links(sql, "attribute", handle, "citation"),
                    "note_list": self.get_links(sql, "attribute", handle, "note"),
                    "type": _gtype("AttributeType", the_type0, the_type1),
                    "value": value,
                })
        return result

    def get_src_attribute_list(self, sql, from_handle: str) -> list:
        """Return a list of SrcAttribute DataDicts from the datamap table."""
        result = []
        rows = sql.query(
            "select from_handle, the_type0, the_type1, value_field, private "
            "from datamap where from_handle = ?;", from_handle
        )
        for (_fh, the_type0, the_type1, value_field, private) in (rows or []):
            result.append({
                "_class": "SrcAttribute",
                "private": bool(private),
                "type": _gtype("SrcAttributeType", the_type0, the_type1),
                "value": value_field,
            })
        return result

    def get_child_ref_list(self, sql, from_type: str, from_handle: str) -> list:
        """Return a list of ChildRef DataDicts for *from_handle*."""
        result = []
        for handle in self.get_links(sql, from_type, from_handle, "child_ref"):
            rows = sql.query("select * from child_ref where handle = ?;", handle)
            for row in rows:
                (handle, ref, frel0, frel1, mrel0, mrel1, private) = row
                result.append({
                    "_class": "ChildRef",
                    "private": bool(private),
                    "citation_list": self.get_links(sql, "child_ref", handle, "citation"),
                    "note_list": self.get_links(sql, "child_ref", handle, "note"),
                    "ref": ref,
                    "frel": _gtype("ChildRefType", frel0, frel1),
                    "mrel": _gtype("ChildRefType", mrel0, mrel1),
                })
        return result

    def get_event_ref_list(self, sql, from_type: str, from_handle: str) -> list:
        """Return a list of EventRef DataDicts for *from_handle*."""
        result = []
        for handle in self.get_links(sql, from_type, from_handle, "event_ref"):
            rows = sql.query("select * from event_ref where handle = ?;", handle)
            for row in rows:
                (handle, ref, role0, role1, private) = row
                result.append({
                    "_class": "EventRef",
                    "private": bool(private),
                    "citation_list": self.get_links(sql, "event_ref", handle, "citation"),
                    "note_list": self.get_links(sql, "event_ref", handle, "note"),
                    "attribute_list": self.get_attribute_list(sql, "event_ref", handle),
                    "ref": ref,
                    "role": _gtype("EventRoleType", role0, role1),
                })
        return result

    def get_person_ref_list(self, sql, from_type: str, from_handle: str) -> list:
        """Return a list of PersonRef DataDicts for *from_handle*."""
        result = []
        for handle in self.get_links(sql, from_type, from_handle, "person_ref"):
            rows = sql.query("select * from person_ref where handle = ?;", handle)
            for row in rows:
                (handle, ref, description, private) = row
                result.append({
                    "_class": "PersonRef",
                    "private": bool(private),
                    "citation_list": self.get_links(sql, "person_ref", handle, "citation"),
                    "note_list": self.get_links(sql, "person_ref", handle, "note"),
                    "ref": ref,
                    "rel": description,
                })
        return result

    def get_media_list(self, sql, from_type: str, from_handle: str) -> list:
        """Return a list of MediaRef DataDicts for *from_handle*."""
        result = []
        for handle in self.get_links(sql, from_type, from_handle, "media_ref"):
            rows = sql.query("select * from media_ref where handle = ?;", handle)
            for row in rows:
                (handle, ref, role0, role1, role2, role3, private) = row
                rect = None if role0 == role1 == role2 == role3 == -1 \
                    else [role0, role1, role2, role3]
                result.append({
                    "_class": "MediaRef",
                    "private": bool(private),
                    "citation_list": self.get_links(sql, "media_ref", handle, "citation"),
                    "note_list": self.get_links(sql, "media_ref", handle, "note"),
                    "attribute_list": self.get_attribute_list(sql, "media_ref", handle),
                    "ref": ref,
                    "rect": rect,
                })
        return result

    def get_url_list(self, sql, from_type: str, from_handle: str) -> list:
        """Return a list of Url DataDicts for *from_handle*."""
        result = []
        for handle in self.get_links(sql, from_type, from_handle, "url"):
            rows = sql.query("select * from url where handle = ?;", handle)
            for row in rows:
                (_handle, path, desc, type0, type1, private) = row
                result.append({
                    "_class": "Url",
                    "private": bool(private),
                    "path": path,
                    "desc": desc,
                    "type": _gtype("UrlType", type0, type1),
                })
        return result

    def get_repository_ref_list(self, sql, from_type: str, from_handle: str) -> list:
        """Return a list of RepoRef DataDicts for *from_handle*."""
        result = []
        for handle in self.get_links(sql, from_type, from_handle, "repository_ref"):
            rows = sql.query(
                "select * from repository_ref where handle = ?;", handle
            )
            for row in rows:
                (handle, ref, call_number, smt0, smt1, private) = row
                result.append({
                    "_class": "RepoRef",
                    "private": bool(private),
                    "note_list": self.get_links(sql, "repository_ref", handle, "note"),
                    "ref": ref,
                    "call_number": call_number,
                    "media_type": _gtype("SourceMediaType", smt0, smt1),
                })
        return result

    def get_lds_list(self, sql, from_type: str, from_handle: str) -> list:
        """Return a list of LdsOrd DataDicts for *from_handle*."""
        result = []
        for handle in self.get_links(sql, from_type, from_handle, "lds"):
            rows = sql.query("select * from lds where handle = ?;", handle)
            for row in rows:
                (handle, type_, place, famc, temple, status, private) = row
                date_handle = self.get_link(sql, "lds", handle, "date")
                result.append({
                    "_class": "LdsOrd",
                    "citation_list": self.get_links(sql, "lds", handle, "citation"),
                    "note_list": self.get_links(sql, "lds", handle, "note"),
                    "date": self.get_date(sql, date_handle),
                    # type_ is stored as a plain int in the SQLite schema
                    "type": type_,
                    "place": place,
                    "famc": famc,
                    "temple": temple,
                    "status": status,
                    "private": bool(private),
                })
        return result

    def get_location(self, sql, handle: str) -> dict | None:
        """Return a Location DataDict for *handle*, or None."""
        rows = sql.query("select * from location where handle = ?;", handle)
        if not rows:
            return None
        (_handle, street, locality, city, county, state, country, postal, phone, parish) = rows[0]
        return {
            "_class": "Location",
            "street": street or "",
            "locality": locality or "",
            "city": city or "",
            "county": county or "",
            "state": state or "",
            "country": country or "",
            "postal": postal or "",
            "phone": phone or "",
            "parish": parish or "",
        }

    def get_address_list(self, sql, from_type: str, from_handle: str) -> list:
        """Return a list of Address DataDicts for *from_handle*.

        In Gramps 6.1, Address carries location fields directly.  These are
        stored in the linked location row and merged back into the Address dict
        on import.
        """
        result = []
        for handle in self.get_links(sql, from_type, from_handle, "address"):
            rows = sql.query("select * from address where handle = ?;", handle)
            for row in rows:
                (handle, private) = row
                date_handle = self.get_link(sql, "address", handle, "date")
                loc_handle = self.get_link(sql, "address", handle, "location")
                loc = self.get_location(sql, loc_handle) if loc_handle else {}
                addr = {
                    "_class": "Address",
                    "private": bool(private),
                    "citation_list": self.get_links(sql, "address", handle, "citation"),
                    "note_list": self.get_links(sql, "address", handle, "note"),
                    "date": self.get_date(sql, date_handle),
                    "street": (loc or {}).get("street", ""),
                    "locality": (loc or {}).get("locality", ""),
                    "city": (loc or {}).get("city", ""),
                    "county": (loc or {}).get("county", ""),
                    "state": (loc or {}).get("state", ""),
                    "country": (loc or {}).get("country", ""),
                    "postal": (loc or {}).get("postal", ""),
                    "phone": (loc or {}).get("phone", ""),
                }
                result.append(addr)
        return result

    def get_alt_location_list(self, sql, from_type: str, from_handle: str) -> list:
        """Return a list of Location DataDicts for Place alt_loc."""
        result = []
        for handle in self.get_links(sql, from_type, from_handle, "location"):
            loc = self.get_location(sql, handle)
            if loc:
                result.append(loc)
        return result

    def get_surname_list(self, sql, name_handle: str) -> list:
        """Return a list of Surname DataDicts for *name_handle*."""
        rows = sql.query(
            "select s.* from surname s inner join link l "
            "ON l.to_handle = s.handle where l.from_handle = ?;",
            name_handle,
        )
        result = []
        for row in rows:
            (_handle, surname, prefix, primary_surname, ot0, ot1, connector) = row
            result.append({
                "_class": "Surname",
                "surname": surname,
                "prefix": prefix,
                "primary": bool(primary_surname),
                "origintype": _gtype("NameOriginType", ot0, ot1),
                "connector": connector,
            })
        return result

    def get_names(self, sql, from_type: str, from_handle: str, primary: bool):
        """
        Return the primary Name DataDict or a list of alternate Name DataDicts.
        """
        handles = self.get_links(sql, from_type, from_handle, "name")
        result = []
        for handle in handles:
            rows = sql.query(
                "select * from name where handle = ? and primary_name = ?;",
                handle, primary,
            )
            for row in rows:
                (
                    handle, _primary_flag, priv, first_name, suffix, title,
                    name_type0, name_type1, group_as, sort_as, display_as,
                    call, nick, famnick,
                ) = row
                date_handle = self.get_link(sql, "name", handle, "date")
                result.append({
                    "_class": "Name",
                    "private": bool(priv),
                    "citation_list": self.get_links(sql, "name", handle, "citation"),
                    "note_list": self.get_links(sql, "name", handle, "note"),
                    "date": self.get_date(sql, date_handle),
                    "first_name": first_name,
                    "surname_list": self.get_surname_list(sql, handle),
                    "suffix": suffix,
                    "title": title,
                    "type": _gtype("NameType", name_type0, name_type1),
                    "group_as": group_as,
                    "sort_as": sort_as,
                    "display_as": display_as,
                    "call": call,
                    "nick": nick,
                    "famnick": famnick,
                })
        if primary:
            return result[0] if result else data_to_object({"_class": "Name"})
        return result

    def get_alt_place_name_list(self, sql, handle: str) -> list:
        """Return a list of PlaceName DataDicts for alternate place names."""
        rows = sql.query(
            "select * from place_name where from_handle = ?;", handle
        )
        result = []
        for row in rows:
            (ref_handle, _from_handle, value, lang) = row
            date_handle = self.get_link(sql, "place_name", ref_handle, "date")
            result.append({
                "_class": "PlaceName",
                "value": value,
                "date": self.get_date(sql, date_handle),
                "lang": lang,
            })
        return result

    def get_place_ref_list(self, sql, handle: str) -> list:
        """Return a list of PlaceRef DataDicts for a place."""
        rows = sql.query(
            "select * from place_ref where from_place_handle = ?;", handle
        )
        result = []
        for row in rows:
            (ref_handle, _from_handle, to_place_handle) = row
            date_handle = self.get_link(sql, "place_ref", ref_handle, "date")
            result.append({
                "_class": "PlaceRef",
                "ref": to_place_handle,
                "date": self.get_date(sql, date_handle),
            })
        return result

    # -----------------------------------------------
    # Main import loop
    # -----------------------------------------------

    def process(self) -> None:
        """Process the SQL file and import all objects into the Gramps database."""
        sql = self.openSQL()
        total = (
            sql.query("select count(*) from note;")[0][0]
            + sql.query("select count(*) from person;")[0][0]
            + sql.query("select count(*) from event;")[0][0]
            + sql.query("select count(*) from family;")[0][0]
            + sql.query("select count(*) from repository;")[0][0]
            + sql.query("select count(*) from place;")[0][0]
            + sql.query("select count(*) from media;")[0][0]
            + sql.query("select count(*) from tag;")[0][0]
            + sql.query("select count(*) from citation;")[0][0]
            + sql.query("select count(*) from source;")[0][0]
        )
        with DbTxn(_("CSV import"), self.db, batch=True) as self.trans:
            self.db.disable_signals()
            self.t = time.time()
            self._process(0.0, total, sql)
        sql.db.commit()
        sql.db.close()

    def _process(self, count: float, total: int, sql) -> None:
        """Import all object types from the SQL database into Gramps."""

        # ---------------------------------
        # Notes
        # ---------------------------------
        for note in sql.query("select * from note;"):
            (handle, gid, text, format_, note_type1, note_type2, change, private) = note

            markup_rows = sql.query(
                "select to_handle from link where from_handle = ? "
                "and to_type = 'markup';", handle,
            )
            tags_list = []
            for (to_handle,) in (markup_rows or []):
                markup_detail = sql.query(
                    "select * from markup where handle = ?;", to_handle
                )
                for (_mh, markup0, markup1, value, start_stop_list) in (markup_detail or []):
                    ss_list = eval(start_stop_list)
                    tags_list.append({
                        "_class": "StyledTextTag",
                        "name": _gtype("StyledTextTagType", markup0, markup1),
                        "value": value,
                        "ranges": ss_list,
                    })

            raw = {
                "_class": "Note",
                "handle": handle,
                "gramps_id": gid,
                "text": {
                    "_class": "StyledText",
                    "string": text,
                    "tags": tags_list,
                },
                "format": format_,
                "type": _gtype("NoteType", note_type1, note_type2),
                "change": change,
                "tag_list": self.get_links(sql, "note", handle, "tag"),
                "private": bool(private),
            }
            self.db.add_note(data_to_object(raw), self.trans)
            count += 1
            self.callback(100 * count / total)

        # ---------------------------------
        # Events
        # ---------------------------------
        for event in sql.query("select * from event;"):
            (handle, gid, the_type0, the_type1, description, change, private) = event
            date_handle = self.get_link(sql, "event", handle, "date")
            place_handle = self.get_link(sql, "event", handle, "place")

            raw = {
                "_class": "Event",
                "handle": handle,
                "gramps_id": gid,
                "type": _gtype("EventType", the_type0, the_type1),
                "date": self.get_date(sql, date_handle),
                "description": description,
                "place": place_handle or "",
                "citation_list": self.get_links(sql, "event", handle, "citation"),
                "note_list": self.get_links(sql, "event", handle, "note"),
                "media_list": self.get_media_list(sql, "event", handle),
                "attribute_list": self.get_attribute_list(sql, "event", handle),
                "change": change,
                "tag_list": self.get_links(sql, "event", handle, "tag"),
                "private": bool(private),
            }
            self.db.add_event(data_to_object(raw), self.trans)
            count += 1
            self.callback(100 * count / total)

        # ---------------------------------
        # Persons
        # ---------------------------------
        people = sql.query(
            "select handle, gid, gender, death_ref_handle, birth_ref_handle, "
            "change, private, familysearch_sync from person;"
        )
        for person_row in (people or []):
            if person_row is None:
                continue
            if len(person_row) == 8:
                (handle, gid, gender, death_ref_handle, birth_ref_handle,
                 change, private, familysearch_sync_json) = person_row
            else:
                (handle, gid, gender, death_ref_handle, birth_ref_handle,
                 change, private) = person_row
                familysearch_sync_json = None

            event_ref_list = self.get_event_ref_list(sql, "person", handle)

            raw = {
                "_class": "Person",
                "handle": handle,
                "gramps_id": gid,
                "gender": int(gender),
                "primary_name": self.get_names(sql, "person", handle, True),
                "alternate_names": self.get_names(sql, "person", handle, False),
                "death_ref_index": lookup(death_ref_handle, event_ref_list),
                "birth_ref_index": lookup(birth_ref_handle, event_ref_list),
                "event_ref_list": event_ref_list,
                "family_list": self.get_links(sql, "person", handle, "family"),
                "parent_family_list": self.get_links(sql, "person", handle, "parent_family"),
                "media_list": self.get_media_list(sql, "person", handle),
                "address_list": self.get_address_list(sql, "person", handle),
                "attribute_list": self.get_attribute_list(sql, "person", handle),
                "urls": self.get_url_list(sql, "person", handle),
                "lds_ord_list": self.get_lds_list(sql, "person", handle),
                "citation_list": self.get_links(sql, "person", handle, "citation"),
                "note_list": self.get_links(sql, "person", handle, "note"),
                "change": int(change),
                "tag_list": self.get_links(sql, "person", handle, "tag"),
                "private": bool(private),
                "person_ref_list": self.get_person_ref_list(sql, "person", handle),
                # familysearch_sync: use stored JSON or default empty state
                "familysearch_sync": (
                    json.loads(familysearch_sync_json) if familysearch_sync_json
                    else {
                        "_class": "FamilySearchSync",
                        "fsid": None, "is_root": False,
                        "status_ts": None, "confirmed_ts": None,
                        "gramps_modified_ts": None, "fs_modified_ts": None,
                        "essential_conflict": False, "conflict": False,
                    }
                ),
            }
            g_pers = data_to_object(raw)

            self.db.add_person(g_pers, self.trans)
            count += 1
            self.callback(100 * count / total)

        # ---------------------------------
        # Families
        # ---------------------------------
        for family in sql.query("select * from family;"):
            (handle, gid, father_handle, mother_handle,
             the_type0, the_type1, change, private) = family

            raw = {
                "_class": "Family",
                "handle": handle,
                "gramps_id": gid,
                "father_handle": father_handle,
                "mother_handle": mother_handle,
                "child_ref_list": self.get_child_ref_list(sql, "family", handle),
                "type": _gtype("FamilyRelType", the_type0, the_type1),
                "event_ref_list": self.get_event_ref_list(sql, "family", handle),
                "media_list": self.get_media_list(sql, "family", handle),
                "attribute_list": self.get_attribute_list(sql, "family", handle),
                "lds_ord_list": self.get_lds_list(sql, "family", handle),
                "citation_list": self.get_links(sql, "family", handle, "citation"),
                "note_list": self.get_links(sql, "family", handle, "note"),
                "change": change,
                "tag_list": self.get_links(sql, "family", handle, "tag"),
                "private": bool(private),
            }
            self.db.add_family(data_to_object(raw), self.trans)
            count += 1
            self.callback(100 * count / total)

        # ---------------------------------
        # Repositories
        # ---------------------------------
        for repo in sql.query("select * from repository;"):
            (handle, gid, the_type0, the_type1, name, change, private) = repo

            raw = {
                "_class": "Repository",
                "handle": handle,
                "gramps_id": gid,
                "type": _gtype("RepositoryType", the_type0, the_type1),
                "name": name,
                "note_list": self.get_links(sql, "repository", handle, "note"),
                "address_list": self.get_address_list(sql, "repository", handle),
                "urls": self.get_url_list(sql, "repository", handle),
                "change": change,
                "tag_list": self.get_links(sql, "repository", handle, "tag"),
                "private": bool(private),
            }
            self.db.add_repository(data_to_object(raw), self.trans)
            count += 1
            self.callback(100 * count / total)

        # ---------------------------------
        # Places
        # ---------------------------------
        for place in sql.query("select * from place;"):
            count += 1
            (handle, gid, title, value, the_type0, the_type1,
             code, long_, lat, lang, change, private) = place

            raw = {
                "_class": "Place",
                "handle": handle,
                "gramps_id": gid,
                "title": title,
                "long": long_,
                "lat": lat,
                "placeref_list": self.get_place_ref_list(sql, handle),
                "name": {
                    "_class": "PlaceName",
                    "value": value,
                    "date": None,
                    "lang": lang,
                },
                "alt_names": self.get_alt_place_name_list(sql, handle),
                "place_type": _gtype("PlaceType", the_type0, the_type1),
                "code": code,
                "alt_loc": self.get_alt_location_list(sql, "place_alt", handle),
                "urls": self.get_url_list(sql, "place", handle),
                "media_list": self.get_media_list(sql, "place", handle),
                "citation_list": self.get_links(sql, "place", handle, "citation"),
                "note_list": self.get_links(sql, "place", handle, "note"),
                "change": change,
                "tag_list": self.get_links(sql, "place", handle, "tag"),
                "private": bool(private),
            }
            self.db.commit_place(data_to_object(raw), self.trans)
            self.callback(100 * count / total)

        # ---------------------------------
        # Citations
        # ---------------------------------
        for citation in sql.query("select * from citation;"):
            (handle, gid, confidence, page, source_handle, change, private) = citation
            date_handle = self.get_link(sql, "citation", handle, "date")

            raw = {
                "_class": "Citation",
                "handle": handle,
                "gramps_id": gid,
                "date": self.get_date(sql, date_handle),
                "page": page,
                "confidence": confidence,
                "source_handle": source_handle,
                "note_list": self.get_links(sql, "citation", handle, "note"),
                "media_list": self.get_media_list(sql, "citation", handle),
                "attribute_list": self.get_src_attribute_list(sql, handle),
                "change": change,
                "tag_list": self.get_links(sql, "citation", handle, "tag"),
                "private": bool(private),
            }
            self.db.commit_citation(data_to_object(raw), self.trans)
            count += 1
            self.callback(100 * count / total)

        # ---------------------------------
        # Sources
        # ---------------------------------
        for source in sql.query("select * from source;"):
            (handle, gid, title, author, pubinfo, abbrev, change, private) = source

            raw = {
                "_class": "Source",
                "handle": handle,
                "gramps_id": gid,
                "title": title,
                "author": author,
                "pubinfo": pubinfo,
                "note_list": self.get_links(sql, "source", handle, "note"),
                "media_list": self.get_media_list(sql, "source", handle),
                "abbrev": abbrev,
                "change": change,
                "attribute_list": self.get_src_attribute_list(sql, handle),
                "reporef_list": self.get_repository_ref_list(sql, "source", handle),
                "tag_list": self.get_links(sql, "source", handle, "tag"),
                "private": bool(private),
            }
            self.db.commit_source(data_to_object(raw), self.trans)
            count += 1
            self.callback(100 * count / total)

        # ---------------------------------
        # Media
        # ---------------------------------
        for med in sql.query("select * from media;"):
            (handle, gid, path, mime, desc, checksum, change, private) = med
            date_handle = self.get_link(sql, "media", handle, "date")

            raw = {
                "_class": "Media",
                "handle": handle,
                "gramps_id": gid,
                "path": path,
                "mime": mime,
                "desc": desc,
                "checksum": checksum,
                "attribute_list": self.get_attribute_list(sql, "media", handle),
                "citation_list": self.get_links(sql, "media", handle, "citation"),
                "note_list": self.get_links(sql, "media", handle, "note"),
                "change": change,
                "date": self.get_date(sql, date_handle),
                "tag_list": self.get_links(sql, "media", handle, "tag"),
                "private": bool(private),
            }
            self.db.commit_media(data_to_object(raw), self.trans)
            count += 1
            self.callback(100 * count / total)

        # ---------------------------------
        # Tags
        # ---------------------------------
        for tag in sql.query("select * from tag;"):
            (handle, name, color, priority, change) = tag
            raw = {
                "_class": "Tag",
                "handle": handle,
                "name": name,
                "color": color,
                "priority": priority,
                "change": change,
            }
            self.db.commit_tag(data_to_object(raw), self.trans)
            count += 1
            self.callback(100 * count / total)

        # ---------------------------------
        # Name group (surname groupings)
        # ---------------------------------
        for name, grouping in sql.query("select * from name_group;") or []:
            self.db.set_name_group_mapping(name, grouping)

    def cleanup(self) -> None:
        """Finalize import: re-enable signals and report elapsed time."""
        self.t = round(time.time() - self.t)
        msg = (
            ngettext("Import Complete: %d second", "Import Complete: %d seconds", self.t)
            % self.t
        )
        self.db.enable_signals()
        self.db.request_rebuild()
        LOG.info(msg)


# -------------------------------------------------------------------------
#
# Entry point
#
# -------------------------------------------------------------------------
def importData(db, filename: str, user) -> None:
    """Import a Gramps SQLite export file into the given database."""
    g = SQLReader(db, filename, user)
    g.process()
    g.cleanup()
