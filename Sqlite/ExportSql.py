#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2008 Douglas S. Blank <doug.blank@gmail.com>
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

"Export to SQLite Database"

# Future ideas
# Also include meta:
#   Bookmarks
#   Header - researcher info
#   Name formats
#   Namemaps?
#   GRAMPS Version #, date, exporter

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
from gramps.gen.utils.id import create_id
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gui.plug.export import WriterOptionBox  # don't remove, used!!!
from gramps.gen.lib.attrtype import AttributeType
from gramps.gen.lib.childreftype import ChildRefType
from gramps.gen.lib.citation import Citation
from gramps.gen.lib.date import Date
from gramps.gen.lib.eventroletype import EventRoleType
from gramps.gen.lib.eventtype import EventType
from gramps.gen.lib.familyreltype import FamilyRelType
from gramps.gen.lib.ldsord import LdsOrd
from gramps.gen.lib.nameorigintype import NameOriginType
from gramps.gen.lib.nametype import NameType
from gramps.gen.lib.note import Note
from gramps.gen.lib.notetype import NoteType
from gramps.gen.lib.person import Person
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.lib.placetype import PlaceType
from gramps.gen.lib.repotype import RepositoryType
from gramps.gen.lib.srcattrtype import SrcAttributeType
from gramps.gen.lib.srcmediatype import SourceMediaType
from gramps.gen.lib.styledtexttagtype import StyledTextTagType
from gramps.gen.lib.urltype import UrlType

try:
    trans = glocale.get_addon_translator(__file__)
except ValueError:
    trans = glocale.translation
_ = trans.gettext
ngettext = trans.ngettext


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
        self.batch = False
        self.database = database
        self.db = sqlite.connect(self.database)
        self.cursor = self.db.cursor()
        # Per (from_type, from_handle, to_type) counters, so each link
        # written to the `link` table records its position within its
        # list -- preserving any GUI-driven reordering on round trip.
        self.link_seq: dict[tuple[str, str, str], int] = {}

    def query(self, q: str, *args):
        """Execute a query and return all results."""
        args = list(args)
        if q.strip().upper().startswith("DROP"):
            self.cursor.execute(q, args)
            self.db.commit()
        else:
            try:
                self.cursor.execute(q, args)
                if not self.batch:
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
# Schema creation
#
# -------------------------------------------------------------------------
def makeDB(db: Database, callback) -> None:
    """Create all SQLite tables needed by the Sqlite export."""
    count = 0
    total = 30

    db.query("""drop table if exists note;""")
    db.query(
        """CREATE TABLE note (
                  handle CHARACTER(25) PRIMARY KEY,
                  gid    CHARACTER(25),
                  text   TEXT,
                  format INTEGER,
                  note_type1   INTEGER,
                  note_type2   TEXT,
                  change INTEGER,
                  private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists name;""")
    db.query(
        """CREATE TABLE name (
                  handle CHARACTER(25) PRIMARY KEY,
                  primary_name BOOLEAN,
                  private BOOLEAN,
                  first_name TEXT,
                  suffix TEXT,
                  title TEXT,
                  name_type0 INTEGER,
                  name_type1 TEXT,
                  group_as TEXT,
                  sort_as INTEGER,
                  display_as INTEGER,
                  call TEXT,
                  nick TEXT,
                  famnick TEXT);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists surname;""")
    db.query(
        """CREATE TABLE surname (
                  handle CHARACTER(25),
                  surname TEXT,
                  prefix TEXT,
                  primary_surname BOOLEAN,
                  origin_type0 INTEGER,
                  origin_type1 TEXT,
                  connector TEXT);"""
    )
    count += 1
    callback(100 * count / total)

    db.query(
        """CREATE INDEX idx_surname_handle ON
                  surname(handle);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists date;""")
    db.query(
        """CREATE TABLE date (
                  handle CHARACTER(25) PRIMARY KEY,
                  calendar INTEGER,
                  modifier INTEGER,
                  quality INTEGER,
                  day1 INTEGER,
                  month1 INTEGER,
                  year1 INTEGER,
                  slash1 BOOLEAN,
                  day2 INTEGER,
                  month2 INTEGER,
                  year2 INTEGER,
                  slash2 BOOLEAN,
                  text TEXT,
                  sortval INTEGER,
                  newyear INTEGER);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists person;""")
    db.query(
        """CREATE TABLE person (
                  handle CHARACTER(25) PRIMARY KEY,
                  gid CHARACTER(25),
                  gender INTEGER,
                  death_ref_handle TEXT,
                  birth_ref_handle TEXT,
                  change INTEGER,
                  private BOOLEAN,
                  familysearch_sync TEXT);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists family;""")
    db.query(
        """CREATE TABLE family (
                 handle CHARACTER(25) PRIMARY KEY,
                 gid CHARACTER(25),
                 father_handle CHARACTER(25),
                 mother_handle CHARACTER(25),
                 the_type0 INTEGER,
                 the_type1 TEXT,
                 change INTEGER,
                 private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists place;""")
    db.query(
        """CREATE TABLE place (
                 handle CHARACTER(25) PRIMARY KEY,
                 gid CHARACTER(25),
                 title TEXT,
                 value TEXT,
                 the_type0 INTEGER,
                 the_type1 TEXT,
                 code TEXT,
                 long TEXT,
                 lat TEXT,
                 lang TEXT,
                 change INTEGER,
                 private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists place_ref;""")
    db.query(
        """CREATE TABLE place_ref (
                   handle             CHARACTER(25) PRIMARY KEY,
                   from_place_handle  CHARACTER(25),
                   to_place_handle    CHARACTER(25));"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists place_name;""")
    db.query(
        """CREATE TABLE place_name (
                  handle        CHARACTER(25) PRIMARY KEY,
                  from_handle   CHARACTER(25),
                  value         CHARACTER(25),
                  lang          CHARACTER(25));"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists event;""")
    db.query(
        """CREATE TABLE event (
                 handle CHARACTER(25) PRIMARY KEY,
                 gid CHARACTER(25),
                 the_type0 INTEGER,
                 the_type1 TEXT,
                 description TEXT,
                 change INTEGER,
                 private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists citation;""")
    db.query(
        """CREATE TABLE citation (
                 handle CHARACTER(25) PRIMARY KEY,
                 gid CHARACTER(25),
                 confidence INTEGER,
                 page CHARACTER(25),
                 source_handle CHARACTER(25),
                 change INTEGER,
                 private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists source;""")
    db.query(
        """CREATE TABLE source (
                 handle CHARACTER(25) PRIMARY KEY,
                 gid CHARACTER(25),
                 title TEXT,
                 author TEXT,
                 pubinfo TEXT,
                 abbrev TEXT,
                 change INTEGER,
                 private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists media;""")
    db.query(
        """CREATE TABLE media (
                 handle CHARACTER(25) PRIMARY KEY,
                 gid CHARACTER(25),
                 path TEXT,
                 mime TEXT,
                 desc TEXT,
                 checksum INTEGER,
                 change INTEGER,
                 private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists repository_ref;""")
    db.query(
        """CREATE TABLE repository_ref (
                 handle CHARACTER(25) PRIMARY KEY,
                 ref CHARACTER(25),
                 call_number TEXT,
                 source_media_type0 INTEGER,
                 source_media_type1 TEXT,
                 private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists repository;""")
    db.query(
        """CREATE TABLE repository (
                 handle CHARACTER(25) PRIMARY KEY,
                 gid CHARACTER(25),
                 the_type0 INTEGER,
                 the_type1 TEXT,
                 name TEXT,
                 change INTEGER,
                 private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    # One link to link them all
    db.query("""drop table if exists link;""")
    db.query(
        """CREATE TABLE link (
                 from_type CHARACTER(25),
                 from_handle CHARACTER(25),
                 to_type CHARACTER(25),
                 to_handle CHARACTER(25),
                 seq INTEGER);"""
    )
    count += 1
    callback(100 * count / total)

    db.query(
        """CREATE INDEX idx_link_to ON
                  link(from_type, from_handle, to_type);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists markup;""")
    db.query(
        """CREATE TABLE markup (
                 handle CHARACTER(25) PRIMARY KEY,
                 markup0 INTEGER,
                 markup1 TEXT,
                 value INTEGER,
                 start_stop_list TEXT);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists event_ref;""")
    db.query(
        """CREATE TABLE event_ref (
                 handle CHARACTER(25) PRIMARY KEY,
                 ref CHARACTER(25),
                 role0 INTEGER,
                 role1 TEXT,
                 private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists person_ref;""")
    db.query(
        """CREATE TABLE person_ref (
                 handle CHARACTER(25) PRIMARY KEY,
                 ref CHARACTER(25),
                 description TEXT,
                 private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists child_ref;""")
    db.query(
        """CREATE TABLE child_ref (
                 handle CHARACTER(25) PRIMARY KEY,
                 ref CHARACTER(25),
                 frel0 INTEGER,
                 frel1 CHARACTER(25),
                 mrel0 INTEGER,
                 mrel1 CHARACTER(25),
                 private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists lds;""")
    db.query(
        """CREATE TABLE lds (
                 handle CHARACTER(25) PRIMARY KEY,
                 type INTEGER,
                 place CHARACTER(25),
                 famc CHARACTER(25),
                 temple TEXT,
                 status INTEGER,
                 private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists media_ref;""")
    db.query(
        """CREATE TABLE media_ref (
                 handle CHARACTER(25) PRIMARY KEY,
                 ref CHARACTER(25),
                 role0 INTEGER,
                 role1 INTEGER,
                 role2 INTEGER,
                 role3 INTEGER,
                 private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists address;""")
    db.query(
        """CREATE TABLE address (
                handle CHARACTER(25) PRIMARY KEY,
                private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists location;""")
    db.query(
        """CREATE TABLE location (
                 handle CHARACTER(25) PRIMARY KEY,
                 street TEXT,
                 locality TEXT,
                 city TEXT,
                 county TEXT,
                 state TEXT,
                 country TEXT,
                 postal TEXT,
                 phone TEXT,
                 parish TEXT);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists attribute;""")
    db.query(
        """CREATE TABLE attribute (
                 handle CHARACTER(25) PRIMARY KEY,
                 the_type0 INTEGER,
                 the_type1 TEXT,
                 value TEXT,
                 private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists url;""")
    db.query(
        """CREATE TABLE url (
                 handle CHARACTER(25) PRIMARY KEY,
                 path TEXT,
                 desc TEXT,
                 type0 INTEGER,
                 type1 TEXT,
                 private BOOLEAN);
                 """
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists datamap;""")
    db.query(
        """CREATE TABLE datamap (
                 from_handle CHARACTER(25),
                 the_type0 INTEGER,
                 the_type1 TEXT,
                 value_field TXT,
                 private BOOLEAN);
                 """
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table if exists tag;""")
    db.query(
        """CREATE TABLE tag (
                 handle CHARACTER(25) PRIMARY KEY,
                 name TEXT,
                 color TEXT,
                 priority INTEGER,
                 change INTEGER);
                 """
    )
    count += 1
    callback(100 * count / total)

    # Lookup table describing integer codes that are not GrampsType
    # instances (date calendar/modifier/quality, gender, confidence,
    # LDS ordinance type/status), so a code's meaning can be read
    # directly from the exported database.
    db.query("""drop table if exists constants;""")
    db.query(
        """CREATE TABLE constants (
                 table_name CHARACTER(25),
                 column_name CHARACTER(25),
                 code INTEGER,
                 value TEXT);"""
    )
    count += 1
    callback(100 * count / total)

    # Copy of Gramps' name_group table, mapping a surname to the
    # header it is grouped under (e.g. for accented/variant spellings).
    db.query("""drop table if exists name_group;""")
    db.query(
        """CREATE TABLE name_group (
                 name CHARACTER(50) PRIMARY KEY,
                 grouping TEXT);"""
    )
    count += 1
    callback(100 * count / total)


# -------------------------------------------------------------------------
#
# Helper lookup
#
# -------------------------------------------------------------------------
def type_string(cls: type, type_dict: dict) -> str:
    """
    Return the translated display string for a GrampsType DataDict.

    The raw DataDict's "string" key only holds text for CUSTOM types; for
    standard types it is empty, so it must be resolved through the
    GrampsType subclass to get the readable name (e.g. "Birth").
    """
    return str(cls((type_dict["value"], type_dict["string"])))


def lookup(index: int, event_ref_list: list) -> str | None:
    """
    Return the event handle at position index in the event_ref_list DataDicts.
    """
    if index < 0:
        return None
    for i, event_ref in enumerate(event_ref_list):
        if i == index:
            return event_ref["ref"]
    return None


# -------------------------------------------------------------------------
#
# Export helper functions
#
# -------------------------------------------------------------------------
def export_link(
    db: Database,
    from_type: str,
    from_handle: str,
    to_type: str,
    to_handle: str | None,
) -> None:
    """Insert a single link record between two objects."""
    if to_handle:
        key = (from_type, from_handle, to_type)
        seq = db.link_seq.get(key, 0)
        db.link_seq[key] = seq + 1
        db.query(
            """insert into link (
                   from_type,
                   from_handle,
                   to_type,
                   to_handle,
                   seq) values (?, ?, ?, ?, ?)""",
            from_type,
            from_handle,
            to_type,
            to_handle,
            seq,
        )


def export_list(
    db: Database, from_type: str, from_handle: str, to_type: str, handle_list: list
) -> None:
    """Export a list of handle links from a parent to child objects."""
    for to_handle in handle_list:
        export_link(db, from_type, from_handle, to_type, to_handle)


def export_citation_list(
    db: Database, from_type: str, from_handle: str, citation_list: list
) -> None:
    """Export all citation references for a parent object."""
    for citation_handle in citation_list:
        export_link(db, from_type, from_handle, "citation", citation_handle)


def export_date(
    db: Database, from_type: str, from_handle: str, data: dict | None
) -> None:
    """Export a Date DataDict into the date table."""
    if data is None:
        return
    calendar = data["calendar"]
    modifier = data["modifier"]
    quality = data["quality"]
    dateval = data["dateval"]
    text = data["text"]
    sortval = data["sortval"]
    newyear = data["newyear"]

    if len(dateval) == 4:
        day1, month1, year1, slash1 = dateval
        day2, month2, year2, slash2 = 0, 0, 0, 0
    elif len(dateval) == 8:
        day1, month1, year1, slash1, day2, month2, year2, slash2 = dateval
    else:
        raise ValueError("ERROR: date dateval format: %s" % (dateval,))
    date_handle = create_id()
    db.query(
        """INSERT INTO date (
                  handle,
                  calendar,
                  modifier,
                  quality,
                  day1,
                  month1,
                  year1,
                  slash1,
                  day2,
                  month2,
                  year2,
                  slash2,
                  text,
                  sortval,
                  newyear) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                                   ?, ?, ?, ?, ?, ?);""",
        date_handle,
        calendar,
        modifier,
        quality,
        day1,
        month1,
        year1,
        slash1,
        day2,
        month2,
        year2,
        slash2,
        text,
        sortval,
        newyear,
    )
    export_link(db, from_type, from_handle, "date", date_handle)


def export_markup(
    db: Database,
    from_type: str,
    from_handle: str,
    markup_code0,
    markup_code1,
    value,
    start_stop_list,
) -> None:
    """Export a markup record for a Note."""
    markup_handle = create_id()
    db.query(
        """INSERT INTO markup (
                 handle,
                 markup0,
                 markup1,
                 value,
                 start_stop_list) VALUES (?,?,?,?,?);""",
        markup_handle,
        markup_code0,
        markup_code1,
        value,
        start_stop_list,
    )
    export_link(db, from_type, from_handle, "markup", markup_handle)


def export_attribute(
    db: Database, from_type: str, from_handle: str, attribute: dict
) -> None:
    """Export a single Attribute DataDict record."""
    private = attribute["private"]
    citation_list = attribute["citation_list"]
    note_list = attribute["note_list"]
    the_type = attribute["type"]
    value = attribute["value"]
    handle = create_id()
    db.query(
        """INSERT INTO attribute (
                 handle,
                 the_type0,
                 the_type1,
                 value,
                 private) VALUES (?,?,?,?,?);""",
        handle,
        the_type["value"],
        type_string(AttributeType, the_type),
        value,
        private,
    )
    export_citation_list(db, "attribute", handle, citation_list)
    export_list(db, "attribute", handle, "note", note_list)
    export_link(db, from_type, from_handle, "attribute", handle)


def export_attribute_list(
    db: Database, from_type: str, from_handle: str, attr_list: list
) -> None:
    """Export all attribute records for a parent object."""
    for attribute in attr_list:
        export_attribute(db, from_type, from_handle, attribute)


def export_src_attribute_list(db: Database, from_handle: str, src_attr_list: list) -> None:
    """Export SrcAttribute DataDicts for source/citation into the datamap table.

    SrcAttribute has no citation_list or note_list; it maps to the legacy
    datamap table that ImportSql reads back.
    """
    for src_attr in src_attr_list:
        private = src_attr["private"]
        the_type = src_attr["type"]
        value = src_attr["value"]
        db.query(
            """INSERT INTO datamap (
                     from_handle,
                     the_type0,
                     the_type1,
                     value_field,
                     private) VALUES (?,?,?,?,?);""",
            from_handle,
            the_type["value"],
            type_string(SrcAttributeType, the_type),
            value,
            private,
        )


def export_url_list(
    db: Database, from_type: str, from_handle: str, urls: list
) -> None:
    """Export all URL DataDict records for a parent object."""
    for url in urls:
        private = url["private"]
        path = url["path"]
        desc = url["desc"]
        the_type = url["type"]
        handle = create_id()
        db.query(
            """insert INTO url (
                 handle,
                 path,
                 desc,
                 type0,
                 type1,
                 private) VALUES (?, ?, ?, ?, ?, ?);
                 """,
            handle,
            path,
            desc,
            the_type["value"],
            type_string(UrlType, the_type),
            private,
        )
        export_link(db, from_type, from_handle, "url", handle)


def export_media_ref_list(
    db: Database, from_type: str, from_handle: str, media_list: list
) -> None:
    """Export all media reference DataDict records for a parent object."""
    for media in media_list:
        export_media_ref(db, from_type, from_handle, media)


def export_media_ref(
    db: Database, from_type: str, from_handle: str, media: dict
) -> None:
    """Export a single MediaRef DataDict record."""
    private = media["private"]
    citation_list = media["citation_list"]
    note_list = media["note_list"]
    attribute_list = media["attribute_list"]
    ref = media["ref"]
    # rect is the bounding box; stored in role columns for historical reasons
    rect = media.get("rect") or [-1, -1, -1, -1]
    handle = create_id()
    db.query(
        """INSERT into media_ref (
                 handle,
                 ref,
                 role0,
                 role1,
                 role2,
                 role3,
                 private) VALUES (?,?,?,?,?,?,?);""",
        handle,
        ref,
        rect[0],
        rect[1],
        rect[2],
        rect[3],
        private,
    )
    export_list(db, "media_ref", handle, "note", note_list)
    export_attribute_list(db, "media_ref", handle, attribute_list)
    export_citation_list(db, "media_ref", handle, citation_list)
    export_link(db, from_type, from_handle, "media_ref", handle)


def export_event_ref(
    db: Database, from_type: str, from_handle: str, event_ref: dict
) -> None:
    """Export a single EventRef DataDict record."""
    private = event_ref["private"]
    citation_list = event_ref["citation_list"]
    note_list = event_ref["note_list"]
    attribute_list = event_ref["attribute_list"]
    ref = event_ref["ref"]
    role = event_ref["role"]
    handle = create_id()
    db.query(
        """insert INTO event_ref (
                 handle,
                 ref,
                 role0,
                 role1,
                 private) VALUES (?,?,?,?,?);""",
        handle,
        ref,
        role["value"],
        type_string(EventRoleType, role),
        private,
    )
    export_list(db, "event_ref", handle, "note", note_list)
    export_attribute_list(db, "event_ref", handle, attribute_list)
    export_citation_list(db, "event_ref", handle, citation_list)
    export_link(db, from_type, from_handle, "event_ref", handle)


def export_person_ref_list(
    db: Database, from_type: str, from_handle: str, person_ref_list: list
) -> None:
    """Export all PersonRef DataDict records for a parent object."""
    for person_ref in person_ref_list:
        private = person_ref["private"]
        citation_list = person_ref["citation_list"]
        note_list = person_ref["note_list"]
        ref = person_ref["ref"]
        rel = person_ref["rel"]
        ref_handle = create_id()
        db.query(
            """INSERT INTO person_ref (
                    handle,
                    ref,
                    description,
                    private) VALUES (?, ?, ?, ?);""",
            ref_handle,
            ref,
            rel,
            private,
        )
        export_list(db, "person_ref", ref_handle, "note", note_list)
        export_citation_list(db, "person_ref", ref_handle, citation_list)
        export_link(db, from_type, from_handle, "person_ref", ref_handle)


def export_child_ref_list(
    db: Database, from_type: str, from_handle: str, to_type: str, ref_list: list
) -> None:
    """Export all ChildRef DataDict records for a family."""
    for child_ref in ref_list:
        private = child_ref["private"]
        citation_list = child_ref["citation_list"]
        note_list = child_ref["note_list"]
        ref = child_ref["ref"]
        frel = child_ref["frel"]
        mrel = child_ref["mrel"]
        handle = create_id()
        db.query(
            """INSERT INTO child_ref (handle,
                     ref, frel0, frel1, mrel0, mrel1, private)
                        VALUES (?, ?, ?, ?, ?, ?, ?);""",
            handle,
            ref,
            frel["value"],
            type_string(ChildRefType, frel),
            mrel["value"],
            type_string(ChildRefType, mrel),
            private,
        )
        export_citation_list(db, "child_ref", handle, citation_list)
        export_list(db, "child_ref", handle, "note", note_list)
        export_link(db, from_type, from_handle, "child_ref", handle)


def export_lds(
    db: Database, from_type: str, from_handle: str, ldsord: dict
) -> None:
    """Export a single LdsOrd DataDict record."""
    citation_list = ldsord["citation_list"]
    note_list = ldsord["note_list"]
    date = ldsord["date"]
    the_type = ldsord["type"]
    place = ldsord["place"]
    famc = ldsord["famc"]
    temple = ldsord["temple"]
    status = ldsord["status"]
    private = ldsord["private"]
    lds_handle = create_id()
    db.query(
        "INSERT into lds"
        " (handle, type, place, famc, temple, status, private) "
        "VALUES (?,?,?,?,?,?,?);",
        lds_handle,
        the_type,
        place,
        famc,
        temple,
        status,
        private,
    )
    export_link(db, "lds", lds_handle, "place", place)
    export_list(db, "lds", lds_handle, "note", note_list)
    export_date(db, "lds", lds_handle, date)
    export_citation_list(db, "lds", lds_handle, citation_list)
    export_link(db, from_type, from_handle, "lds", lds_handle)


def export_location(
    db: Database, from_type: str, from_handle: str, location: dict | None
) -> None:
    """Export a location DataDict (Location or Address) into the location table."""
    if location is None:
        return
    handle = create_id()
    db.query(
        """INSERT INTO location (
                 handle,
                 street,
                 locality,
                 city,
                 county,
                 state,
                 country,
                 postal,
                 phone,
                 parish) VALUES (?,?,?,?,?,?,?,?,?,?);""",
        handle,
        location.get("street", ""),
        location.get("locality", ""),
        location.get("city", ""),
        location.get("county", ""),
        location.get("state", ""),
        location.get("country", ""),
        location.get("postal", ""),
        location.get("phone", ""),
        location.get("parish"),
    )
    export_link(db, from_type, from_handle, "location", handle)


def export_address(
    db: Database, from_type: str, from_handle: str, address: dict
) -> None:
    """Export an Address DataDict record.

    In Gramps 6.1, Address carries its location fields directly
    (street, city, etc.) rather than via a nested Location object.
    """
    private = address["private"]
    citation_list = address["citation_list"]
    note_list = address["note_list"]
    date = address["date"]
    addr_handle = create_id()
    db.query(
        """INSERT INTO address (
                handle,
                private) VALUES (?, ?);""",
        addr_handle,
        private,
    )
    # Write inline location fields directly from the address dict
    export_location(db, "address", addr_handle, address)
    export_date(db, "address", addr_handle, date)
    export_list(db, "address", addr_handle, "note", note_list)
    export_citation_list(db, "address", addr_handle, citation_list)
    export_link(db, from_type, from_handle, "address", addr_handle)


def export_repository_ref_list(
    db: Database, from_type: str, from_handle: str, reporef_list: list
) -> None:
    """Export all RepositoryRef DataDict records for a source."""
    for repo in reporef_list:
        private = repo["private"]
        note_list = repo["note_list"]
        ref = repo["ref"]
        call_number = repo["call_number"]
        media_type = repo["media_type"]
        handle = create_id()
        db.query(
            """insert INTO repository_ref (
                     handle,
                     ref,
                     call_number,
                     source_media_type0,
                     source_media_type1,
                     private) VALUES (?,?,?,?,?,?);""",
            handle,
            ref,
            call_number,
            media_type["value"],
            type_string(SourceMediaType, media_type),
            private,
        )
        export_list(db, "repository_ref", handle, "note", note_list)
        export_link(db, from_type, from_handle, "repository_ref", handle)


def export_surname(db: Database, name_handle: str, surname_list: list) -> None:
    """Export all Surname DataDict records for a name."""
    for surname in surname_list:
        surname_handle = create_id()
        origin_type = surname["origintype"]
        db.query(
            """INSERT INTO surname (
                  handle,
                  surname,
                  prefix,
                  primary_surname,
                  origin_type0,
                  origin_type1,
                  connector) VALUES (?,?,?,?,?,?,?);""",
            surname_handle,
            surname["surname"],
            surname["prefix"],
            surname["primary"],
            origin_type["value"],
            type_string(NameOriginType, origin_type),
            surname["connector"],
        )
        export_link(db, "name", name_handle, "surname", surname_handle)


def export_name(
    db: Database,
    from_type: str,
    from_handle: str,
    primary: bool,
    name: dict | None,
) -> None:
    """Export a Name DataDict record into the name table."""
    if not name:
        return
    private = name["private"]
    citation_list = name["citation_list"]
    note_list = name["note_list"]
    date = name["date"]
    first_name = name["first_name"]
    surname_list = name["surname_list"]
    suffix = name["suffix"]
    title = name["title"]
    name_type = name["type"]
    group_as = name["group_as"]
    sort_as = name["sort_as"]
    display_as = name["display_as"]
    call = name["call"]
    nick = name["nick"]
    famnick = name["famnick"]
    handle = create_id()
    db.query(
        """INSERT into name (
                  handle,
                  primary_name,
                  private,
                  first_name,
                  suffix,
                  title,
                  name_type0,
                  name_type1,
                  group_as,
                  sort_as,
                  display_as,
                  call,
                  nick,
                  famnick
                    ) values (?, ?, ?, ?, ?, ?, ?,
                              ?, ?, ?, ?, ?, ?, ?);""",
        handle,
        primary,
        private,
        first_name,
        suffix,
        title,
        name_type["value"],
        type_string(NameType, name_type),
        group_as,
        sort_as,
        display_as,
        call,
        nick,
        famnick,
    )
    export_surname(db, handle, surname_list)
    export_date(db, "name", handle, date)
    export_list(db, "name", handle, "note", note_list)
    export_citation_list(db, "name", handle, citation_list)
    export_link(db, from_type, from_handle, "name", handle)


def export_place_name(db: Database, from_handle: str, place_name: dict) -> None:
    """Export a PlaceName DataDict record."""
    value = place_name["value"]
    date = place_name["date"]
    lang = place_name["lang"]
    ref_handle = create_id()
    db.query(
        "insert into place_name (handle, from_handle, value, lang)"
        " VALUES (?, ?, ?, ?);",
        ref_handle,
        from_handle,
        value,
        lang,
    )
    export_date(db, "place_name", ref_handle, date)


def export_place_ref(db: Database, from_handle: str, place_ref: dict) -> None:
    """Export a PlaceRef DataDict record."""
    to_place_handle = place_ref["ref"]
    date = place_ref["date"]
    ref_handle = create_id()
    db.query(
        "insert into place_ref"
        " (handle, from_place_handle, to_place_handle) VALUES (?, ?, ?);",
        ref_handle,
        from_handle,
        to_place_handle,
    )
    export_date(db, "place_ref", ref_handle, date)


# -------------------------------------------------------------------------
#
# Primary object export functions
#
# -------------------------------------------------------------------------
def export_note(db: Database, raw: dict) -> None:
    """Export a Note raw DataDict into the note table."""
    handle = raw["handle"]
    gid = raw["gramps_id"]
    styled_text = raw["text"]
    format_ = raw["format"]
    note_type = raw["type"]
    change = raw["change"]
    tag_list = raw["tag_list"]
    private = raw["private"]

    text = styled_text["string"]
    markup_list = styled_text["tags"]

    db.query(
        """INSERT into note (
                  handle,
                  gid,
                  text,
                  format,
                  note_type1,
                  note_type2,
                  change,
                  private) values (?, ?, ?, ?,
                                   ?, ?, ?, ?);""",
        handle,
        gid,
        text,
        format_,
        note_type["value"],
        type_string(NoteType, note_type),
        change,
        private,
    )
    for markup in markup_list:
        # Each markup is a StyledTextTag DataDict:
        # {"name": GrampsType dict, "value": ..., "ranges": [...]}
        markup_name = markup["name"]
        value = markup["value"]
        ranges = markup["ranges"]
        export_markup(
            db,
            "note",
            handle,
            markup_name["value"],
            type_string(StyledTextTagType, markup_name),
            value,
            str(ranges),
        )
    export_list(db, "note", handle, "tag", tag_list)


def export_event(db: Database, raw: dict) -> None:
    """Export an Event raw DataDict into the event table."""
    handle = raw["handle"]
    gid = raw["gramps_id"]
    the_type = raw["type"]
    date = raw["date"]
    description = raw["description"]
    place_handle = raw["place"]
    citation_list = raw["citation_list"]
    note_list = raw["note_list"]
    media_list = raw["media_list"]
    attribute_list = raw["attribute_list"]
    change = raw["change"]
    tag_list = raw["tag_list"]
    private = raw["private"]

    db.query(
        """INSERT INTO event (
                 handle,
                 gid,
                 the_type0,
                 the_type1,
                 description,
                 change,
                 private) VALUES (?,?,?,?,?,?,?);""",
        handle,
        gid,
        the_type["value"],
        type_string(EventType, the_type),
        description,
        change,
        private,
    )
    export_date(db, "event", handle, date)
    export_link(db, "event", handle, "place", place_handle)
    export_list(db, "event", handle, "note", note_list)
    export_list(db, "event", handle, "tag", tag_list)
    export_attribute_list(db, "event", handle, attribute_list)
    export_media_ref_list(db, "event", handle, media_list)
    export_citation_list(db, "event", handle, citation_list)


def export_person(db: Database, raw: dict) -> None:
    """
    Export a Person raw DataDict into the person table and related tables.

    Uses get_raw_person_data() output directly — all fields accessed by name,
    making this forward-compatible with new Person fields added in any core
    version (e.g. familysearch_sync added in Gramps 6.1).
    """
    handle = raw["handle"]
    gid = raw["gramps_id"]
    gender = raw["gender"]
    primary_name = raw["primary_name"]
    alternate_names = raw["alternate_names"]
    death_ref_index = raw["death_ref_index"]
    birth_ref_index = raw["birth_ref_index"]
    event_ref_list = raw["event_ref_list"]
    family_list = raw["family_list"]
    parent_family_list = raw["parent_family_list"]
    media_list = raw["media_list"]
    address_list = raw["address_list"]
    attribute_list = raw["attribute_list"]
    urls = raw["urls"]
    lds_ord_list = raw["lds_ord_list"]
    pcitation_list = raw["citation_list"]
    pnote_list = raw["note_list"]
    change = raw["change"]
    tag_list = raw["tag_list"]
    private = raw["private"]
    person_ref_list = raw["person_ref_list"]
    # familysearch_sync is present from Gramps 6.1; absent keys get None
    familysearch_sync = raw.get("familysearch_sync")

    db.query(
        """INSERT INTO person (
                  handle,
                  gid,
                  gender,
                  death_ref_handle,
                  birth_ref_handle,
                  change,
                  private,
                  familysearch_sync) values (?, ?, ?, ?, ?, ?, ?, ?);""",
        handle,
        gid,
        gender,
        lookup(death_ref_index, event_ref_list),
        lookup(birth_ref_index, event_ref_list),
        change,
        private,
        json.dumps(familysearch_sync) if familysearch_sync is not None else None,
    )

    for event_ref in event_ref_list:
        export_event_ref(db, "person", handle, event_ref)
    export_list(db, "person", handle, "family", family_list)
    export_list(db, "person", handle, "parent_family", parent_family_list)
    export_media_ref_list(db, "person", handle, media_list)
    export_list(db, "person", handle, "note", pnote_list)
    export_attribute_list(db, "person", handle, attribute_list)
    export_url_list(db, "person", handle, urls)
    export_person_ref_list(db, "person", handle, person_ref_list)
    export_citation_list(db, "person", handle, pcitation_list)
    export_list(db, "person", handle, "tag", tag_list)

    for address in address_list:
        export_address(db, "person", handle, address)

    for ldsord in lds_ord_list:
        export_lds(db, "person", handle, ldsord)

    export_name(db, "person", handle, True, primary_name)
    for name in alternate_names:
        export_name(db, "person", handle, False, name)


def export_family(db: Database, raw: dict) -> None:
    """Export a Family raw DataDict into the family table and related tables."""
    handle = raw["handle"]
    gid = raw["gramps_id"]
    father_handle = raw["father_handle"]
    mother_handle = raw["mother_handle"]
    the_type = raw["type"]
    child_ref_list = raw["child_ref_list"]
    event_ref_list = raw["event_ref_list"]
    media_list = raw["media_list"]
    attribute_list = raw["attribute_list"]
    lds_ord_list = raw["lds_ord_list"]
    citation_list = raw["citation_list"]
    note_list = raw["note_list"]
    change = raw["change"]
    tag_list = raw["tag_list"]
    private = raw["private"]

    db.query(
        """INSERT INTO family (
                 handle,
                 gid,
                 father_handle,
                 mother_handle,
                 the_type0,
                 the_type1,
                 change,
                 private) values (?,?,?,?,?,?,?,?);""",
        handle,
        gid,
        father_handle,
        mother_handle,
        the_type["value"],
        type_string(FamilyRelType, the_type),
        change,
        private,
    )

    export_child_ref_list(db, "family", handle, "child_ref", child_ref_list)
    export_list(db, "family", handle, "note", note_list)
    export_attribute_list(db, "family", handle, attribute_list)
    export_citation_list(db, "family", handle, citation_list)
    export_media_ref_list(db, "family", handle, media_list)
    export_list(db, "family", handle, "tag", tag_list)

    for event_ref in event_ref_list:
        export_event_ref(db, "family", handle, event_ref)

    for ldsord in lds_ord_list:
        export_lds(db, "family", handle, ldsord)


def export_repository(db: Database, raw: dict) -> None:
    """Export a Repository raw DataDict into the repository table."""
    handle = raw["handle"]
    gid = raw["gramps_id"]
    the_type = raw["type"]
    name = raw["name"]
    note_list = raw["note_list"]
    address_list = raw["address_list"]
    urls = raw["urls"]
    change = raw["change"]
    tag_list = raw["tag_list"]
    private = raw["private"]

    db.query(
        """INSERT INTO repository (
                 handle,
                 gid,
                 the_type0,
                 the_type1,
                 name,
                 change,
                 private) VALUES (?,?,?,?,?,?,?);""",
        handle,
        gid,
        the_type["value"],
        type_string(RepositoryType, the_type),
        name,
        change,
        private,
    )

    export_list(db, "repository", handle, "note", note_list)
    export_url_list(db, "repository", handle, urls)
    export_list(db, "repository", handle, "tag", tag_list)

    for address in address_list:
        export_address(db, "repository", handle, address)


def export_place(db: Database, raw: dict) -> None:
    """Export a Place raw DataDict into the place table and related tables."""
    handle = raw["handle"]
    gid = raw["gramps_id"]
    title = raw["title"]
    long = raw["long"]
    lat = raw["lat"]
    # In 6.1 DataDict: name (PlaceName dict), alt_names, placeref_list
    place_name = raw["name"]
    alt_names = raw["alt_names"]
    placeref_list = raw["placeref_list"]
    place_type = raw["place_type"]
    code = raw["code"]
    alt_loc = raw["alt_loc"]
    urls = raw["urls"]
    media_list = raw["media_list"]
    citation_list = raw["citation_list"]
    note_list = raw["note_list"]
    change = raw["change"]
    tag_list = raw["tag_list"]
    private = raw["private"]

    value = place_name["value"]
    lang = place_name.get("lang", "")

    db.query(
        """INSERT INTO place (
                 handle,
                 gid,
                 title,
                 value,
                 the_type0,
                 the_type1,
                 code,
                 long,
                 lat,
                 lang,
                 change,
                 private) values (?,?,?,?,?,?,?,?,?,?,?,?);""",
        handle,
        gid,
        title,
        value,
        place_type["value"],
        type_string(PlaceType, place_type),
        code,
        long,
        lat,
        lang,
        change,
        private,
    )

    export_date(db, "place", handle, place_name.get("date"))
    export_url_list(db, "place", handle, urls)
    export_media_ref_list(db, "place", handle, media_list)
    export_citation_list(db, "place", handle, citation_list)
    export_list(db, "place", handle, "note", note_list)
    export_list(db, "place", handle, "tag", tag_list)

    for alt_name in alt_names:
        export_place_name(db, handle, alt_name)

    for place_ref in placeref_list:
        export_place_ref(db, handle, place_ref)

    for location in alt_loc:
        export_location(db, "place_alt", handle, location)


def export_citation(db: Database, raw: dict) -> None:
    """Export a Citation raw DataDict into the citation table."""
    handle = raw["handle"]
    gid = raw["gramps_id"]
    date = raw["date"]
    page = raw["page"]
    confidence = raw["confidence"]
    source_handle = raw["source_handle"]
    note_list = raw["note_list"]
    media_list = raw["media_list"]
    attribute_list = raw["attribute_list"]
    change = raw["change"]
    tag_list = raw["tag_list"]
    private = raw["private"]

    db.query(
        """INSERT into citation (
                 handle,
                 gid,
                 confidence,
                 page,
                 source_handle,
                 change,
                 private
                 ) VALUES (?,?,?,?,?,?,?);""",
        handle,
        gid,
        confidence,
        page,
        source_handle,
        change,
        private,
    )
    export_src_attribute_list(db, handle, attribute_list)
    export_date(db, "citation", handle, date)
    export_list(db, "citation", handle, "note", note_list)
    export_media_ref_list(db, "citation", handle, media_list)
    export_list(db, "citation", handle, "tag", tag_list)


def export_source(db: Database, raw: dict) -> None:
    """Export a Source raw DataDict into the source table."""
    handle = raw["handle"]
    gid = raw["gramps_id"]
    title = raw["title"]
    author = raw["author"]
    pubinfo = raw["pubinfo"]
    note_list = raw["note_list"]
    media_list = raw["media_list"]
    abbrev = raw["abbrev"]
    change = raw["change"]
    attribute_list = raw["attribute_list"]
    reporef_list = raw["reporef_list"]
    tag_list = raw["tag_list"]
    private = raw["private"]

    db.query(
        """INSERT into source (
             handle,
             gid,
             title,
             author,
             pubinfo,
             abbrev,
             change,
             private
             ) VALUES (?,?,?,?,?,?,?,?);""",
        handle,
        gid,
        title,
        author,
        pubinfo,
        abbrev,
        change,
        private,
    )
    export_list(db, "source", handle, "note", note_list)
    export_list(db, "source", handle, "tag", tag_list)
    export_media_ref_list(db, "source", handle, media_list)
    export_src_attribute_list(db, handle, attribute_list)
    export_repository_ref_list(db, "source", handle, reporef_list)


def export_media(db: Database, raw: dict) -> None:
    """Export a Media raw DataDict into the media table."""
    handle = raw["handle"]
    gid = raw["gramps_id"]
    path = raw["path"]
    mime = raw["mime"]
    desc = raw["desc"]
    checksum = raw["checksum"]
    attribute_list = raw["attribute_list"]
    citation_list = raw["citation_list"]
    note_list = raw["note_list"]
    change = raw["change"]
    date = raw["date"]
    tag_list = raw["tag_list"]
    private = raw["private"]

    db.query(
        """INSERT INTO media (
            handle,
            gid,
            path,
            mime,
            desc,
            checksum,
            change,
            private) VALUES (?,?,?,?,?,?,?,?);""",
        handle,
        gid,
        path,
        mime,
        desc,
        checksum,
        change,
        private,
    )
    export_date(db, "media", handle, date)
    export_list(db, "media", handle, "note", note_list)
    export_citation_list(db, "media", handle, citation_list)
    export_attribute_list(db, "media", handle, attribute_list)
    export_list(db, "media", handle, "tag", tag_list)


def export_tag(db: Database, raw: dict) -> None:
    """Export a Tag raw DataDict into the tag table."""
    db.query(
        """INSERT INTO tag (
            handle,
            name,
            color,
            priority,
            change) VALUES (?,?,?,?,?);""",
        raw["handle"],
        raw["name"],
        raw["color"],
        raw["priority"],
        raw["change"],
    )


# -------------------------------------------------------------------------
#
# Constants and name_group export
#
# -------------------------------------------------------------------------
def export_constants(db: Database) -> None:
    """
    Export the meaning of integer codes that are not GrampsType instances.

    Date calendar/modifier/quality/newyear, person gender, citation
    confidence, LDS ordinance type/status, name display_as/sort_as, and
    note format are plain integer constants defined in Gramps core
    rather than per-record GrampsType DataDicts, so their names can't be
    resolved via type_string(). Record them once here, translated into
    the user's locale, instead of leaving bare integers in those columns.
    """
    rows = []
    for code, name in enumerate(Date.ui_calendar_names):
        rows.append(("date", "calendar", code, name))
    for code, name in (
        (Date.MOD_NONE, _("Regular")),
        (Date.MOD_BEFORE, _("Before")),
        (Date.MOD_AFTER, _("After")),
        (Date.MOD_ABOUT, _("About")),
        (Date.MOD_RANGE, _("Range")),
        (Date.MOD_FROM, _("From")),
        (Date.MOD_TO, _("To")),
        (Date.MOD_SPAN, _("Span")),
        (Date.MOD_TEXTONLY, _("Text only")),
    ):
        rows.append(("date", "modifier", code, name))
    for code, name in (
        (Date.QUAL_NONE, _("Regular")),
        (Date.QUAL_ESTIMATED, _("Estimated")),
        (Date.QUAL_CALCULATED, _("Calculated")),
    ):
        rows.append(("date", "quality", code, name))
    for code, name in (
        (Date.NEWYEAR_JAN1, _("January 1")),
        (Date.NEWYEAR_MAR1, _("March 1")),
        (Date.NEWYEAR_MAR25, _("March 25")),
        (Date.NEWYEAR_SEP1, _("September 1")),
    ):
        rows.append(("date", "newyear", code, name))
    for code, name in (
        (Person.FEMALE, _("female")),
        (Person.MALE, _("male")),
        (Person.UNKNOWN, _("unknown")),
        (Person.OTHER, _("other")),
    ):
        rows.append(("person", "gender", code, name))
    for code, name in (
        (Citation.CONF_VERY_LOW, _("Very Low")),
        (Citation.CONF_LOW, _("Low")),
        (Citation.CONF_NORMAL, _("Normal")),
        (Citation.CONF_HIGH, _("High")),
        (Citation.CONF_VERY_HIGH, _("Very High")),
    ):
        rows.append(("citation", "confidence", code, name))
    for code, name, _xml in LdsOrd._TYPE_MAP:
        rows.append(("lds", "type", code, name))
    for code, name, _xml in LdsOrd._STATUS_MAP:
        rows.append(("lds", "status", code, name))
    for code, name, _format, _active in name_displayer.STANDARD_FORMATS:
        rows.append(("name", "display_as", code, name))
        rows.append(("name", "sort_as", code, name))
    for code, name in (
        (Note.FLOWED, _("Flowed")),
        (Note.FORMATTED, _("Preformatted")),
    ):
        rows.append(("note", "format", code, name))

    for table_name, column_name, code, value in rows:
        db.query(
            """INSERT INTO constants (
                     table_name, column_name, code, value) VALUES (?,?,?,?);""",
            table_name,
            column_name,
            code,
            str(value),
        )


def export_name_group(db: Database, database) -> None:
    """Export Gramps' name_group table, mapping surnames to their grouping."""
    for name in database.get_name_group_keys():
        grouping = database.get_name_group_mapping(name)
        db.query(
            "INSERT INTO name_group (name, grouping) VALUES (?, ?);",
            name,
            grouping,
        )


# -------------------------------------------------------------------------
#
# Dummy callback
#
# -------------------------------------------------------------------------
def dummy_callback(*args) -> None:
    """No-op callback used when no real callback is provided."""


# -------------------------------------------------------------------------
#
# Main export entry point
#
# -------------------------------------------------------------------------
def exportData(database, filename: str, user, option_box) -> bool:
    """
    Export the Gramps database to a SQLite file.

    Uses get_raw_*_data() throughout so that all object fields — including
    any added in future core versions — are accessed by name from the raw
    DataDict rather than by position from a serialized tuple.

    :param database: The Gramps database to export.
    :param filename: Path to the output SQLite file.
    :param user: User object providing a callback for progress.
    :param option_box: Optional export option box (may filter the database).
    :returns: True on success.
    """
    if isinstance(user.callback, abc.Callable):
        callback = user.callback
    else:
        callback = dummy_callback

    if option_box:
        option_box.parse_options()
        database = option_box.get_filtered_database(database)

    start = time.time()
    total = (
        len(database.get_note_handles())
        + len(database.get_person_handles())
        + len(database.get_event_handles())
        + len(database.get_family_handles())
        + len(database.get_repository_handles())
        + len(database.get_place_handles())
        + len(database.get_media_handles())
        + len(database.get_tag_handles())
        + len(database.get_citation_handles())
        + len(database.get_source_handles())
    )
    count = 0.0

    db = Database(filename)
    makeDB(db, callback)

    db.batch = True  # don't commit till end

    export_constants(db)
    export_name_group(db, database)

    # ---------------------------------
    # Notes
    # ---------------------------------
    for handle in database.iter_note_handles():
        raw = database.get_raw_note_data(handle)
        if raw is None:
            continue
        export_note(db, raw)
        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Events
    # ---------------------------------
    for handle in database.iter_event_handles():
        raw = database.get_raw_event_data(handle)
        if raw is None:
            continue
        export_event(db, raw)
        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Persons
    # ---------------------------------
    for handle in database.iter_person_handles():
        raw = database.get_raw_person_data(handle)
        if raw is None:
            continue
        export_person(db, raw)
        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Families
    # ---------------------------------
    for handle in database.iter_family_handles():
        raw = database.get_raw_family_data(handle)
        if raw is None:
            continue
        export_family(db, raw)
        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Repositories
    # ---------------------------------
    for handle in database.iter_repository_handles():
        raw = database.get_raw_repository_data(handle)
        if raw is None:
            continue
        export_repository(db, raw)
        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Places
    # ---------------------------------
    for handle in database.iter_place_handles():
        raw = database.get_raw_place_data(handle)
        if raw is None:
            continue
        export_place(db, raw)
        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Citations
    # ---------------------------------
    for handle in database.iter_citation_handles():
        raw = database.get_raw_citation_data(handle)
        if raw is None:
            continue
        export_citation(db, raw)
        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Sources
    # ---------------------------------
    for handle in database.iter_source_handles():
        raw = database.get_raw_source_data(handle)
        if raw is None:
            continue
        export_source(db, raw)
        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Media
    # ---------------------------------
    for handle in database.iter_media_handles():
        raw = database.get_raw_media_data(handle)
        if raw is None:
            continue
        export_media(db, raw)
        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Tags
    # ---------------------------------
    for handle in database.iter_tag_handles():
        raw = database.get_raw_tag_data(handle)
        if raw is None:
            continue
        export_tag(db, raw)
        count += 1
        callback(100 * count / total)

    db.batch = False  # turn off batch processing
    db.db.commit()  # commit all changes
    db.db.close()

    total_time = round(time.time() - start)
    msg = (
        ngettext(
            "Export Complete: %d second", "Export Complete: %d seconds", total_time
        )
        % total_time
    )
    LOG.info(msg)
    return True
