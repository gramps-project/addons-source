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
# $Id: ExportSql.py 508 2010-08-16 01:48:01Z dsblank $
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

    def query(self, q: str, *args):
        """Execute a query and return all results."""
        args = list(args)
        if q.strip().upper().startswith("DROP"):
            try:
                self.cursor.execute(q, args)
                self.db.commit()
            except Exception:
                LOG.warning("no such table to drop: '%s'", q)
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
    total = 28

    db.query("""drop table note;""")
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

    db.query("""drop table name;""")
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

    db.query("""drop table surname;""")
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

    db.query("""drop table date;""")
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

    db.query("""drop table person;""")
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

    db.query("""drop table family;""")
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

    db.query("""drop table place;""")
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

    db.query("""drop table place_ref;""")
    db.query(
        """CREATE TABLE place_ref (
                   handle             CHARACTER(25) PRIMARY KEY,
                   from_place_handle  CHARACTER(25),
                   to_place_handle    CHARACTER(25));"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table place_name;""")
    db.query(
        """CREATE TABLE place_name (
                  handle        CHARACTER(25) PRIMARY KEY,
                  from_handle   CHARACTER(25),
                  value         CHARACTER(25),
                  lang          CHARACTER(25));"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table event;""")
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

    db.query("""drop table citation;""")
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

    db.query("""drop table source;""")
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

    db.query("""drop table media;""")
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

    db.query("""drop table repository_ref;""")
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

    db.query("""drop table repository;""")
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
    db.query("""drop table link;""")
    db.query(
        """CREATE TABLE link (
                 from_type CHARACTER(25),
                 from_handle CHARACTER(25),
                 to_type CHARACTER(25),
                 to_handle CHARACTER(25));"""
    )
    count += 1
    callback(100 * count / total)

    db.query(
        """CREATE INDEX idx_link_to ON
                  link(from_type, from_handle, to_type);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table markup;""")
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

    db.query("""drop table event_ref;""")
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

    db.query("""drop table person_ref;""")
    db.query(
        """CREATE TABLE person_ref (
                 handle CHARACTER(25) PRIMARY KEY,
                 ref CHARACTER(25),
                 description TEXT,
                 private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table child_ref;""")
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

    db.query("""drop table lds;""")
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

    db.query("""drop table media_ref;""")
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

    db.query("""drop table address;""")
    db.query(
        """CREATE TABLE address (
                handle CHARACTER(25) PRIMARY KEY,
                private BOOLEAN);"""
    )
    count += 1
    callback(100 * count / total)

    db.query("""drop table location;""")
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

    db.query("""drop table attribute;""")
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

    db.query("""drop table url;""")
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

    db.query("""drop table datamap;""")
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

    db.query("""drop table tag;""")
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


# -------------------------------------------------------------------------
#
# Helper lookup
#
# -------------------------------------------------------------------------
def lookup(index: int, event_ref_list) -> str | None:
    """
    Return the event handle at the given index in a serialized event_ref_list.
    """
    if index < 0:
        return None
    count = 0
    for event_ref in event_ref_list:
        (_private, _citation_list, _note_list, _attribute_list, ref, _role) = event_ref
        if index == count:
            return ref
        count += 1
    return None


# -------------------------------------------------------------------------
#
# Export helper functions
#
# -------------------------------------------------------------------------
def export_alt_place_name_list(
    db: Database, handle: str, alt_place_name_list
) -> None:
    """Export all alternate place names for a place."""
    for place_name in alt_place_name_list:
        export_place_name(db, handle, place_name)


def export_place_name(db: Database, handle: str, place_name) -> None:
    """Export a single place name record."""
    # alt_place_name_list = [('Ohio', None, ''), ...] [(value, date, lang)...]
    (value, date, lang) = place_name
    ref_handle = create_id()
    db.query(
        "insert into place_name (handle, from_handle, value, lang)"
        " VALUES (?, ?, ?, ?);",
        ref_handle,
        handle,
        value,
        lang,
    )
    export_date(db, "place_name", ref_handle, date)


def export_place_ref_list(db: Database, handle: str, place_ref_list) -> None:
    """Export all place reference records for a place."""
    # place_ref_list = Enclosed by:  [('4ECKQCWCLO5YIHXEXC', None)]
    # [(handle, date)...]
    for place_ref in place_ref_list:
        export_place_ref(db, handle, place_ref)


def export_place_ref(db: Database, handle: str, place_ref) -> None:
    """Export a single place reference."""
    (to_place_handle, date) = place_ref
    ref_handle = create_id()
    db.query(
        "insert into place_ref"
        " (handle, from_place_handle, to_place_handle) VALUES (?, ?, ?);",
        ref_handle,
        handle,
        to_place_handle,
    )
    export_date(db, "place_ref", ref_handle, date)


def export_location_list(
    db: Database, from_type: str, from_handle: str, locations
) -> None:
    """Export a list of location records."""
    for location in locations:
        export_location(db, from_type, from_handle, location)


def export_url_list(db: Database, from_type: str, from_handle: str, urls) -> None:
    """Export all URL records for a parent object."""
    for url in urls:
        # (False, 'http://www.gramps-project.org/', 'loleach', (0, 'kaabgo'))
        (private, path, desc, type_) = url
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
            type_[0],
            type_[1],
            private,
        )
        # finally, link this to parent
        export_link(db, from_type, from_handle, "url", handle)


def export_person_ref_list(
    db: Database, from_type: str, from_handle: str, person_ref_list
) -> None:
    """Export all person reference records for a parent object."""
    for person_ref in person_ref_list:
        (
            private,
            citation_list,
            note_list,
            handle,
            desc,
        ) = person_ref
        ref_handle = create_id()
        db.query(
            """INSERT INTO person_ref (
                    handle,
                    ref,
                    description,
                    private) VALUES (?, ?, ?, ?);""",
            ref_handle,
            handle,
            desc,
            private,
        )
        export_list(db, "person_ref", ref_handle, "note", note_list)
        export_citation_list(db, "person_ref", ref_handle, citation_list)
        # And finally, make a link from parent to new object
        export_link(db, from_type, from_handle, "person_ref", ref_handle)


def export_lds(db: Database, from_type: str, from_handle: str, data) -> None:
    """Export a single LDS ordinance record."""
    (lcitation_list, lnote_list, date, type_, place, famc, temple, status, private) = (
        data
    )
    lds_handle = create_id()
    db.query(
        "INSERT into lds"
        " (handle, type, place, famc, temple, status, private) "
        "VALUES (?,?,?,?,?,?,?);",
        lds_handle,
        type_,
        place,
        famc,
        temple,
        status,
        private,
    )
    export_link(db, "lds", lds_handle, "place", place)
    export_list(db, "lds", lds_handle, "note", lnote_list)
    export_date(db, "lds", lds_handle, date)
    export_citation_list(db, "lds", lds_handle, lcitation_list)
    # And finally, make a link from parent to new object
    export_link(db, from_type, from_handle, "lds", lds_handle)


def export_citation_ref(
    db: Database, from_type: str, from_handle: str, citation_handle: str
) -> None:
    """Export a single citation reference link."""
    export_link(db, from_type, from_handle, "citation", citation_handle)


def export_source(
    db: Database,
    handle: str,
    gid: str,
    title: str,
    author: str,
    pubinfo: str,
    abbrev: str,
    change: int,
    private: bool,
) -> None:
    """Insert a source record into the source table."""
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


def export_note(db: Database, data) -> None:
    """Export a serialized Note tuple into the note table."""
    (handle, gid, styled_text, format_, note_type, change, tag_list, private) = data
    text, markup_list = styled_text
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
        note_type[0],
        note_type[1],
        change,
        private,
    )
    for markup in markup_list:
        markup_code, value, start_stop_list = markup
        export_markup(
            db,
            "note",
            handle,
            markup_code[0],
            markup_code[1],
            value,
            str(start_stop_list),
        )  # Not normal form; use eval
    export_list(db, "note", handle, "tag", tag_list)


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
    # And finally, make a link from parent to new object
    export_link(db, from_type, from_handle, "markup", markup_handle)


def export_event(db: Database, data) -> None:
    """Export a serialized Event tuple into the event table."""
    (
        handle,
        gid,
        the_type,
        date,
        description,
        place_handle,
        citation_list,
        note_list,
        media_list,
        attribute_list,
        change,
        tag_list,
        private,
    ) = data
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
        the_type[0],
        the_type[1],
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


def export_event_ref(
    db: Database, from_type: str, from_handle: str, event_ref
) -> None:
    """Export a single event reference record."""
    (private, citation_list, note_list, attribute_list, ref, role) = event_ref
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
        role[0],
        role[1],
        private,
    )
    export_list(db, "event_ref", handle, "note", note_list)
    export_attribute_list(db, "event_ref", handle, attribute_list)
    export_citation_list(db, "event_ref", handle, citation_list)
    # finally, link this to parent
    export_link(db, from_type, from_handle, "event_ref", handle)


def export_person(db: Database, person) -> None:
    """
    Export a Person object into the person table and related tables.

    Accesses all fields by object attribute rather than positional tuple
    unpacking, making this forward-compatible with new Person fields (such
    as familysearch_sync added in Gramps 6.1).
    """
    handle = person.handle
    gid = person.gramps_id
    gender = person.gender
    primary_name = person.primary_name
    alternate_names = person.alternate_names
    death_ref_index = person.death_ref_index
    birth_ref_index = person.birth_ref_index
    event_ref_list = person.get_event_ref_list()
    family_list = person.family_list
    parent_family_list = person.parent_family_list
    media_list = person.get_media_list()
    address_list = person.get_address_list()
    attribute_list = person.get_attribute_list()
    urls = person.get_url_list()
    lds_ord_list = person.get_lds_ord_list()
    pcitation_list = person.get_citation_list()
    pnote_list = person.get_note_list()
    change = person.change
    tag_list = person.get_tag_list()
    private = person.private
    person_ref_list = person.get_person_ref_list()

    # Serialize event_ref_list for birth/death handle lookup (index -> handle)
    serialized_event_refs = [er.serialize() for er in event_ref_list]

    # familysearch_sync is a FamilySearchSync object; persist as JSON
    fs_sync_json = json.dumps(person.familysearch_sync.serialize())

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
        lookup(death_ref_index, serialized_event_refs),
        lookup(birth_ref_index, serialized_event_refs),
        change,
        private,
        fs_sync_json,
    )

    # Event Reference information
    for event_ref in event_ref_list:
        export_event_ref(db, "person", handle, event_ref.serialize())
    export_list(db, "person", handle, "family", family_list)
    export_list(db, "person", handle, "parent_family", parent_family_list)
    export_media_ref_list(db, "person", handle, [m.serialize() for m in media_list])
    export_list(db, "person", handle, "note", pnote_list)
    export_attribute_list(
        db, "person", handle, [a.serialize() for a in attribute_list]
    )
    export_url_list(db, "person", handle, [u.serialize() for u in urls])
    export_person_ref_list(
        db, "person", handle, [pr.serialize() for pr in person_ref_list]
    )
    export_citation_list(db, "person", handle, pcitation_list)
    export_list(db, "person", handle, "tag", tag_list)

    # -------------------------------------
    # Address
    # -------------------------------------
    for address in address_list:
        export_address(db, "person", handle, address.serialize())

    # -------------------------------------
    # LDS ord
    # -------------------------------------
    for ldsord in lds_ord_list:
        export_lds(db, "person", handle, ldsord.serialize())

    # -------------------------------------
    # Names
    # -------------------------------------
    export_name(db, "person", handle, True, primary_name.serialize())
    for name in alternate_names:
        export_name(db, "person", handle, False, name.serialize())


def export_date(db: Database, from_type: str, from_handle: str, data) -> None:
    """Export a serialized Date tuple into the date table."""
    if data is None:
        return
    (calendar, modifier, quality, dateval, text, sortval, newyear) = data
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


def export_surname(db: Database, name_handle: str, surname_list) -> None:
    """Export all surname records for a name."""
    for data in surname_list:
        surname_handle = create_id()
        (surname, prefix, primary, origin_type, connector) = data
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
            surname,
            prefix,
            primary,
            origin_type[0],
            origin_type[1],
            connector,
        )
        export_link(db, "name", name_handle, "surname", surname_handle)


def export_name(
    db: Database, from_type: str, from_handle: str, primary: bool, data
) -> None:
    """Export a serialized Name tuple into the name table."""
    if data:
        (
            private,
            citation_list,
            note_list,
            date,
            first_name,
            surname_list,
            suffix,
            title,
            name_type,
            group_as,
            sort_as,
            display_as,
            call,
            nick,
            famnick,
        ) = data
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
            name_type[0],
            name_type[1],
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
        # And finally, make a link from parent to new object
        export_link(db, from_type, from_handle, "name", handle)


def export_attribute(
    db: Database, from_type: str, from_handle: str, attribute
) -> None:
    """Export a single serialized attribute record."""
    (private, citation_list, note_list, the_type, value) = attribute
    handle = create_id()
    db.query(
        """INSERT INTO attribute (
                 handle,
                 the_type0,
                 the_type1,
                 value,
                 private) VALUES (?,?,?,?,?);""",
        handle,
        the_type[0],
        the_type[1],
        value,
        private,
    )
    export_citation_list(db, "attribute", handle, citation_list)
    export_list(db, "attribute", handle, "note", note_list)
    # finally, link the parent to the attribute
    export_link(db, from_type, from_handle, "attribute", handle)


def export_citation_list(
    db: Database, from_type: str, from_handle: str, citation_list
) -> None:
    """Export all citation references for a parent object."""
    for citation_handle in citation_list:
        export_citation_ref(db, from_type, from_handle, citation_handle)


def export_media_ref_list(
    db: Database, from_type: str, from_handle: str, media_list
) -> None:
    """Export all media reference records for a parent object."""
    for media in media_list:
        export_media_ref(db, from_type, from_handle, media)


def export_media_ref(db: Database, from_type: str, from_handle: str, media) -> None:
    """Export a single serialized media reference record."""
    (private, citation_list, note_list, attribute_list, ref, role) = media
    # handle is the media_ref handle; ref is the media handle
    handle = create_id()
    if role is None:
        role = (-1, -1, -1, -1)
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
        role[0],
        role[1],
        role[2],
        role[3],
        private,
    )
    export_list(db, "media_ref", handle, "note", note_list)
    export_attribute_list(db, "media_ref", handle, attribute_list)
    export_citation_list(db, "media_ref", handle, citation_list)
    # And finally, make a link from parent to new object
    export_link(db, from_type, from_handle, "media_ref", handle)


def export_attribute_list(
    db: Database, from_type: str, from_handle: str, attr_list
) -> None:
    """Export all attribute records for a parent object."""
    for attribute in attr_list:
        export_attribute(db, from_type, from_handle, attribute)


def export_child_ref_list(
    db: Database, from_type: str, from_handle: str, to_type: str, ref_list
) -> None:
    """Export all child reference records for a family."""
    for child_ref in ref_list:
        # family -> child_ref
        # (False, [], [], u'b305e96e39652d8f08c', (1, u''), (1, u''))
        (private, citation_list, note_list, ref, frel, mrel) = child_ref
        handle = create_id()
        db.query(
            """INSERT INTO child_ref (handle,
                     ref, frel0, frel1, mrel0, mrel1, private)
                        VALUES (?, ?, ?, ?, ?, ?, ?);""",
            handle,
            ref,
            frel[0],
            frel[1],
            mrel[0],
            mrel[1],
            private,
        )
        export_citation_list(db, "child_ref", handle, citation_list)
        export_list(db, "child_ref", handle, "note", note_list)
        # And finally, make a link from parent to new object
        export_link(db, from_type, from_handle, "child_ref", handle)


def export_list(
    db: Database, from_type: str, from_handle: str, to_type: str, handle_list
) -> None:
    """Export a list of handle links from a parent to child objects."""
    for to_handle in handle_list:
        export_link(db, from_type, from_handle, to_type, to_handle)


def export_link(
    db: Database,
    from_type: str,
    from_handle: str,
    to_type: str,
    to_handle: str | None,
) -> None:
    """Insert a single link record between two objects."""
    if to_handle:
        db.query(
            """insert into link (
                   from_type,
                   from_handle,
                   to_type,
                   to_handle) values (?, ?, ?, ?)""",
            from_type,
            from_handle,
            to_type,
            to_handle,
        )


def export_datamap_list(
    db: Database, from_type: str, from_handle: str, datamap
) -> None:
    """Export the datamap entries for a source or citation."""
    for private, data_type, data in datamap:
        db.query(
            """INSERT INTO datamap (
                      from_handle,
                      the_type0,
                      the_type1,
                      value_field,
                      private) values (?, ?, ?, ?, ?)""",
            from_handle,
            data_type[0],
            data_type[1],
            data,
            private,
        )


def export_address(db: Database, from_type: str, from_handle: str, address) -> None:
    """Export a single serialized address record."""
    (private, acitation_list, anote_list, date, location) = address
    addr_handle = create_id()
    db.query(
        """INSERT INTO address (
                handle,
                private) VALUES (?, ?);""",
        addr_handle,
        private,
    )
    export_location(db, "address", addr_handle, location)
    export_date(db, "address", addr_handle, date)
    export_list(db, "address", addr_handle, "note", anote_list)
    export_citation_list(db, "address", addr_handle, acitation_list)
    # finally, link the parent to the address
    export_link(db, from_type, from_handle, "address", addr_handle)


def export_location(db: Database, from_type: str, from_handle: str, location) -> None:
    """Export a single location record."""
    if location is None:
        return
    if len(location) == 8:
        (street, locality, city, county, state, country, postal, phone) = location
        parish = None
    elif len(location) == 2:
        (
            (street, locality, city, county, state, country, postal, phone),
            parish,
        ) = location
    else:
        LOG.error("what kind of location is this? %s", location)
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
        street,
        locality,
        city,
        county,
        state,
        country,
        postal,
        phone,
        parish,
    )
    # finally, link the parent to the location
    export_link(db, from_type, from_handle, "location", handle)


def export_repository_ref_list(
    db: Database, from_type: str, from_handle: str, reporef_list
) -> None:
    """Export all repository reference records for a source."""
    for repo in reporef_list:
        (
            note_list,
            ref,
            call_number,
            source_media_type,
            private,
        ) = repo
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
            source_media_type[0],
            source_media_type[1],
            private,
        )
        export_list(db, "repository_ref", handle, "note", note_list)
        # finally, link this to parent
        export_link(db, from_type, from_handle, "repository_ref", handle)


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

    :param database: The Gramps database to export.
    :param filename: Path to the output SQLite file.
    :param user: User object providing a callback for progress.
    :param option_box: Optional export option box (may filter the database).
    :returns: True on success.
    """
    if isinstance(user.callback, abc.Callable):  # is really callable
        callback = user.callback
    else:
        callback = dummy_callback  # dummy

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
    # ---------------------------------
    # Notes
    # ---------------------------------
    for note_handle in database.iter_note_handles():
        data = database.get_note_from_handle(note_handle)
        if data is None:
            continue
        export_note(db, data.serialize())
        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Event
    # ---------------------------------
    for event_handle in database.iter_event_handles():
        data = database.get_event_from_handle(event_handle)
        if data is None:
            continue
        export_event(db, data.serialize())
        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Person
    # ---------------------------------
    for person_handle in database.iter_person_handles():
        person = database.get_person_from_handle(person_handle)
        if person is None:
            continue
        export_person(db, person)
        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Family
    # ---------------------------------
    for family_handle in database.iter_family_handles():
        family = database.get_family_from_handle(family_handle)
        if family is None:
            continue
        handle = family.handle
        gid = family.gramps_id
        father_handle = family.father_handle
        mother_handle = family.mother_handle
        child_ref_list = family.child_ref_list
        the_type = family.type.serialize()
        event_ref_list = family.get_event_ref_list()
        media_list = family.get_media_list()
        attribute_list = family.get_attribute_list()
        lds_seal_list = family.get_lds_ord_list()
        citation_list = family.get_citation_list()
        note_list = family.get_note_list()
        change = family.change
        tag_list = family.get_tag_list()
        private = family.private

        # father_handle and/or mother_handle can be None
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
            the_type[0],
            the_type[1],
            change,
            private,
        )

        export_child_ref_list(
            db,
            "family",
            handle,
            "child_ref",
            [cr.serialize() for cr in child_ref_list],
        )
        export_list(db, "family", handle, "note", note_list)
        export_attribute_list(
            db, "family", handle, [a.serialize() for a in attribute_list]
        )
        export_citation_list(db, "family", handle, citation_list)
        export_media_ref_list(
            db, "family", handle, [m.serialize() for m in media_list]
        )
        export_list(db, "family", handle, "tag", tag_list)

        # Event Reference information
        for event_ref in event_ref_list:
            export_event_ref(db, "family", handle, event_ref.serialize())

        # -------------------------------------
        # LDS
        # -------------------------------------
        for ldsord in lds_seal_list:
            export_lds(db, "family", handle, ldsord.serialize())

        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Repository
    # ---------------------------------
    for repository_handle in database.iter_repository_handles():
        repository = database.get_repository_from_handle(repository_handle)
        if repository is None:
            continue
        (
            handle,
            gid,
            the_type,
            name,
            note_list,
            address_list,
            urls,
            change,
            tag_list,
            private,
        ) = repository.serialize()

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
            the_type[0],
            the_type[1],
            name,
            change,
            private,
        )

        export_list(db, "repository", handle, "note", note_list)
        export_url_list(db, "repository", handle, urls)
        export_list(db, "repository", handle, "tag", tag_list)

        for address in address_list:
            export_address(db, "repository", handle, address)

        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Place
    # ---------------------------------
    for place_handle in database.iter_place_handles():
        place = database.get_place_from_handle(place_handle)
        if place is None:
            continue
        (
            handle,
            gid,
            title,
            long,
            lat,
            place_ref_list,
            place_name,
            alt_place_name_list,
            place_type,
            code,
            alt_location_list,
            urls,
            media_list,
            citation_list,
            note_list,
            change,
            tag_list,
            private,
        ) = place.serialize()

        value, date, lang = place_name

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
            place_type[0],
            place_type[1],
            code,
            long,
            lat,
            lang,
            change,
            private,
        )

        export_date(db, "place", handle, date)
        export_url_list(db, "place", handle, urls)
        export_media_ref_list(db, "place", handle, media_list)
        export_citation_list(db, "place", handle, citation_list)
        export_list(db, "place", handle, "note", note_list)
        export_list(db, "place", handle, "tag", tag_list)

        # 1. alt_place_name_list = [('Ohio', None, ''), ...]
        # [(value, date, lang)...]
        # 2. place_ref_list = Enclosed by:  [('4ECKQCWCLO5YIHXEXC', None)]
        # [(handle, date)...]

        export_alt_place_name_list(db, handle, alt_place_name_list)
        export_place_ref_list(db, handle, place_ref_list)

        # But we need to link these:
        export_location_list(db, "place_alt", handle, alt_location_list)

        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Citation
    # ---------------------------------
    for citation_handle in database.iter_citation_handles():
        citation = database.get_citation_from_handle(citation_handle)
        if citation is None:
            continue
        (
            handle,  # 0
            gid,  # 1
            date,  # 2
            page,  # 3
            confidence,  # 4
            source_handle,  # 5
            note_list,  # 6
            media_list,  # 7
            datamap,  # 8
            change,  # 9
            tag_list,
            private,
        ) = citation.serialize()
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
        export_datamap_list(db, "citation", handle, datamap)
        export_date(db, "citation", handle, date)
        export_list(db, "citation", handle, "note", note_list)
        export_media_ref_list(db, "citation", handle, media_list)
        export_list(db, "citation", handle, "tag", tag_list)
        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Source
    # ---------------------------------
    for source_handle in database.iter_source_handles():
        source = database.get_source_from_handle(source_handle)
        if source is None:
            continue
        (
            handle,
            gid,
            title,
            author,
            pubinfo,
            note_list,
            media_list,
            abbrev,
            change,
            datamap,
            reporef_list,
            tag_list,
            private,
        ) = source.serialize()

        export_source(db, handle, gid, title, author, pubinfo, abbrev, change, private)
        export_list(db, "source", handle, "note", note_list)
        export_list(db, "source", handle, "tag", tag_list)
        export_media_ref_list(db, "source", handle, media_list)
        export_datamap_list(db, "source", handle, datamap)
        export_repository_ref_list(db, "source", handle, reporef_list)
        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Media
    # ---------------------------------
    for media_handle in database.iter_media_handles():
        media = database.get_media_from_handle(media_handle)
        if media is None:
            continue
        (
            handle,
            gid,
            path,
            mime,
            desc,
            checksum,
            attribute_list,
            citation_list,
            note_list,
            change,
            date,
            tag_list,
            private,
        ) = media.serialize()

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
        count += 1
        callback(100 * count / total)

    # ---------------------------------
    # Tags
    # ---------------------------------
    for tag_handle in database.iter_tag_handles():
        tag_object = database.get_tag_from_handle(tag_handle)
        if tag_object is None:
            continue
        (handle, name, color, priority, change) = tag_object.serialize()
        db.query(
            """INSERT INTO tag (
            handle,
            name,
            color,
            priority,
            change) VALUES (?,?,?,?,?);""",
            handle,
            name,
            color,
            priority,
            change,
        )
        count += 1
        callback(100 * count / total)

    db.batch = False  # turn off batch processing
    db.db.commit()  # commit all changes
    db.db.close()

    total_time = time.time() - start
    msg = (
        ngettext(
            "Export Complete: %d second", "Export Complete: %d seconds", total_time
        )
        % total_time
    )
    LOG.info(msg)
    return True
