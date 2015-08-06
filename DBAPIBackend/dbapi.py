#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2015 Douglas S. Blank <doug.blank@gmail.com>
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

#------------------------------------------------------------------------
#
# Gramps Modules
#
#------------------------------------------------------------------------
from gramps.gen.db.generic import *
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext

import dbapi_support

class DBAPI(DbGeneric):
    """
    Database backends class for DB-API 2.0 databases
    """

    def restore(self):
        """
        If you wish to support an optional restore routine, put it here.
        """
        pass

    def prepare_import(self):
        """
        Do anything needed before an import.
        """
        pass

    def commit_import(self):
        """
        Do anything needed after an import.
        """
        self.reindex_reference_map(lambda n: n)

    def write_version(self, directory):
        """Write files for a newly created DB."""
        versionpath = os.path.join(directory, str(DBBACKEND))
        LOG.debug("Write database backend file to 'dbapi'")
        with open(versionpath, "w") as version_file:
            version_file.write("dbapi")
        # Write default_settings, sqlite.db
        defaults = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "dbapi_support", "defaults")
        LOG.debug("Copy defaults from: " + defaults)
        for filename in os.listdir(defaults):
            fullpath = os.path.abspath(os.path.join(defaults, filename))
            if os.path.isfile(fullpath):
                shutil.copy2(fullpath, directory)

    def initialize_backend(self, directory):
        # Run code from directory
        default_settings = {"__file__": 
                            os.path.join(directory, "default_settings.py"),
                            "dbapi_support": dbapi_support}
        settings_file = os.path.join(directory, "default_settings.py")
        with open(settings_file) as f:
            code = compile(f.read(), settings_file, 'exec')
            exec(code, globals(), default_settings)

        self.dbapi = default_settings["dbapi"]

        # make sure schema is up to date:
        self.dbapi.try_execute("""CREATE TABLE person (
                                    handle    VARCHAR(50) PRIMARY KEY NOT NULL,
                                    given_name     TEXT        ,
                                    surname        TEXT        ,
                                    gender_type    INTEGER     ,
                                    order_by  TEXT             ,
                                    gramps_id TEXT             ,
                                    blob_data      BLOB
        );""")
        self.dbapi.try_execute("""CREATE TABLE family (
                                    handle    VARCHAR(50) PRIMARY KEY NOT NULL,
                                    gramps_id TEXT             ,
                                    blob_data      BLOB
        );""")
        self.dbapi.try_execute("""CREATE TABLE source (
                                    handle    VARCHAR(50) PRIMARY KEY NOT NULL,
                                    order_by  TEXT             ,
                                    gramps_id TEXT             ,
                                    blob_data      BLOB
        );""")
        self.dbapi.try_execute("""CREATE TABLE citation (
                                    handle    VARCHAR(50) PRIMARY KEY NOT NULL,
                                    order_by  TEXT             ,
                                    gramps_id TEXT             ,
                                    blob_data      BLOB
        );""")
        self.dbapi.try_execute("""CREATE TABLE event (
                                    handle    VARCHAR(50) PRIMARY KEY NOT NULL,
                                    gramps_id TEXT             ,
                                    blob_data      BLOB
        );""")
        self.dbapi.try_execute("""CREATE TABLE media (
                                    handle    VARCHAR(50) PRIMARY KEY NOT NULL,
                                    order_by  TEXT             ,
                                    gramps_id TEXT             ,
                                    blob_data      BLOB
        );""")
        self.dbapi.try_execute("""CREATE TABLE place (
                                    handle    VARCHAR(50) PRIMARY KEY NOT NULL,
                                    order_by  TEXT             ,
                                    gramps_id TEXT             ,
                                    blob_data      BLOB
        );""")
        self.dbapi.try_execute("""CREATE TABLE repository (
                                    handle    VARCHAR(50) PRIMARY KEY NOT NULL,
                                    gramps_id TEXT             ,
                                    blob_data      BLOB
        );""")
        self.dbapi.try_execute("""CREATE TABLE note (
                                    handle    VARCHAR(50) PRIMARY KEY NOT NULL,
                                    gramps_id TEXT             ,
                                    blob_data      BLOB
        );""")
        self.dbapi.try_execute("""CREATE TABLE tag (
                                    handle    VARCHAR(50) PRIMARY KEY NOT NULL,
                                    order_by  TEXT             ,
                                    blob_data      BLOB
        );""")
        # Secondary:
        self.dbapi.try_execute("""CREATE TABLE reference (
                                    obj_handle    VARCHAR(50),
                                    obj_class     TEXT,
                                    ref_handle    VARCHAR(50),
                                    ref_class     TEXT
        );""")
        self.dbapi.try_execute("""CREATE TABLE name_group (
                                    name     VARCHAR(50) PRIMARY KEY NOT NULL,
                                    grouping TEXT
        );""")
        self.dbapi.try_execute("""CREATE TABLE metadata (
                                    setting  VARCHAR(50) PRIMARY KEY NOT NULL,
                                    value    BLOB
        );""")
        self.dbapi.try_execute("""CREATE TABLE gender_stats (
                                    given_name TEXT, 
                                    female     INTEGER, 
                                    male       INTEGER, 
                                    unknown    INTEGER
        );""") 
        ## Indices:
        self.dbapi.try_execute("""CREATE INDEX  
                                  person_order_by ON person (order_by(50));
        """)
        self.dbapi.try_execute("""CREATE INDEX  
                                  person_gramps_id ON person (gramps_id(50));
        """)
        self.dbapi.try_execute("""CREATE INDEX  
                                  person_surname ON person (surname(50));
        """)
        self.dbapi.try_execute("""CREATE INDEX  
                                  person_given_name ON person (given_name(50));
        """)
        self.dbapi.try_execute("""CREATE INDEX  
                                  source_order_by ON source (order_by(50));
        """)
        self.dbapi.try_execute("""CREATE INDEX  
                                  source_gramps_id ON source (gramps_id(50));
        """)
        self.dbapi.try_execute("""CREATE INDEX  
                                  citation_order_by ON citation (order_by(50));
        """)
        self.dbapi.try_execute("""CREATE INDEX  
                                  citation_gramps_id ON citation (gramps_id(50));
        """)
        self.dbapi.try_execute("""CREATE INDEX  
                                  media_order_by ON media (order_by(50));
        """)
        self.dbapi.try_execute("""CREATE INDEX  
                                  media_gramps_id ON media (gramps_id(50));
        """)
        self.dbapi.try_execute("""CREATE INDEX  
                                  place_order_by ON place (order_by(50));
        """)
        self.dbapi.try_execute("""CREATE INDEX  
                                  place_gramps_id ON place (gramps_id(50));
        """)
        self.dbapi.try_execute("""CREATE INDEX  
                                  tag_order_by ON tag (order_by(50));
        """)
        self.dbapi.try_execute("""CREATE INDEX  
                                  reference_ref_handle ON reference (ref_handle);
        """)
        self.dbapi.try_execute("""CREATE INDEX  
                                  name_group_name ON name_group (name(50)); 
        """)

    def close_backend(self):
        self.dbapi.close()

    def transaction_commit(self, txn):
        """
        Executed after a batch operation.
        """
        self.dbapi.commit()
        self.transaction = None
        msg = txn.get_description()
        self.undodb.commit(txn, msg)
        self._after_commit(txn)
        txn.clear()
        self.has_changed = True

    def transaction_abort(self, txn):
        """
        Executed after a batch operation abort.
        """
        self.dbapi.rollback()
        self.transaction = None
        txn.clear()
        txn.first = None
        txn.last = None
        self._after_commit(txn)

    def get_metadata(self, key, default=[]):
        """
        Get an item from the database.
        """
        self.dbapi.execute("SELECT value FROM metadata WHERE setting = ?;", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])
        elif default == []:
            return []
        else:
            return default

    def set_metadata(self, key, value):
        """
        key: string
        value: item, will be serialized here
        """
        self.dbapi.execute("SELECT * FROM metadata WHERE setting = ?;", [key])
        row = self.dbapi.fetchone()
        if row:
            self.dbapi.execute("UPDATE metadata SET value = ? WHERE setting = ?;", 
                               [pickle.dumps(value), key])
        else:
            self.dbapi.execute("INSERT INTO metadata (setting, value) VALUES (?, ?);", 
                               [key, pickle.dumps(value)])
        self.dbapi.commit()

    def get_name_group_keys(self):
        self.dbapi.execute("SELECT name FROM name_group ORDER BY name;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_name_group_mapping(self, key):
        self.dbapi.execute("SELECT grouping FROM name_group WHERE name = ?;", 
                                 [key])
        row = self.dbapi.fetchone()
        if row:
            return row[0]
        else:
            return key

    def get_person_handles(self, sort_handles=False):
        if sort_handles:
            self.dbapi.execute("SELECT handle FROM person ORDER BY order_by;")
        else:
            self.dbapi.execute("SELECT handle FROM person;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_family_handles(self):
        self.dbapi.execute("SELECT handle FROM family;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_event_handles(self):
        self.dbapi.execute("SELECT handle FROM event;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_citation_handles(self, sort_handles=False):
        if sort_handles:
            self.dbapi.execute("SELECT handle FROM citation ORDER BY order_by;")
        else:
            self.dbapi.execute("SELECT handle FROM citation;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_source_handles(self, sort_handles=False):
        if sort_handles:
            self.dbapi.execute("SELECT handle FROM source ORDER BY order_by;")
        else:
            self.dbapi.execute("SELECT handle from source;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_place_handles(self, sort_handles=False):
        if sort_handles:
            self.dbapi.execute("SELECT handle FROM place ORDER BY order_by;")
        else:
            self.dbapi.execute("SELECT handle FROM place;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_repository_handles(self):
        self.dbapi.execute("SELECT handle FROM repository;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_media_object_handles(self, sort_handles=False):
        if sort_handles:
            self.dbapi.execute("SELECT handle FROM media ORDER BY order_by;")
        else:
            self.dbapi.execute("SELECT handle FROM media;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_note_handles(self):
        self.dbapi.execute("SELECT handle FROM note;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_tag_handles(self, sort_handles=False):
        if sort_handles:
            self.dbapi.execute("SELECT handle FROM tag ORDER BY order_by;")
        else:
            self.dbapi.execute("SELECT handle FROM tag;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def iter_person_handles(self):
        self.dbapi.execute("SELECT handle FROM person;")
        rows = self.dbapi.fetchall()
        for row in rows:
            yield row[0]

    def iter_family_handles(self):
        self.dbapi.execute("SELECT handle FROM family;")
        rows = self.dbapi.fetchall()
        for row in rows:
            yield row[0]

    def get_tag_from_name(self, name):
        self.dbapi.execute("""select handle from tag where order_by = ?;""",
                                 [self._order_by_tag_key(name)])
        row = self.dbapi.fetchone()
        if row:
            self.get_tag_from_handle(row[0])
        return None

    def get_number_of_people(self):
        self.dbapi.execute("SELECT count(handle) FROM person;")
        row = self.dbapi.fetchone()
        return row[0]

    def get_number_of_events(self):
        self.dbapi.execute("SELECT count(handle) FROM event;")
        row = self.dbapi.fetchone()
        return row[0]

    def get_number_of_places(self):
        self.dbapi.execute("SELECT count(handle) FROM place;")
        row = self.dbapi.fetchone()
        return row[0]

    def get_number_of_tags(self):
        self.dbapi.execute("SELECT count(handle) FROM tag;")
        row = self.dbapi.fetchone()
        return row[0]

    def get_number_of_families(self):
        self.dbapi.execute("SELECT count(handle) FROM family;")
        row = self.dbapi.fetchone()
        return row[0]

    def get_number_of_notes(self):
        self.dbapi.execute("SELECT count(handle) FROM note;")
        row = self.dbapi.fetchone()
        return row[0]

    def get_number_of_citations(self):
        self.dbapi.execute("SELECT count(handle) FROM citation;")
        row = self.dbapi.fetchone()
        return row[0]

    def get_number_of_sources(self):
        self.dbapi.execute("SELECT count(handle) FROM source;")
        row = self.dbapi.fetchone()
        return row[0]

    def get_number_of_media_objects(self):
        self.dbapi.execute("SELECT count(handle) FROM media;")
        row = self.dbapi.fetchone()
        return row[0]

    def get_number_of_repositories(self):
        self.dbapi.execute("SELECT count(handle) FROM repository;")
        row = self.dbapi.fetchone()
        return row[0]

    def has_name_group_key(self, key):
        self.dbapi.execute("SELECT grouping FROM name_group WHERE name = ?;", 
                                 [key])
        row = self.dbapi.fetchone()
        return True if row else False

    def set_name_group_mapping(self, name, grouping):
        self.dbapi.execute("SELECT * FROM name_group WHERE name = ?;", 
                                 [name])
        row = self.dbapi.fetchone()
        if row:
            self.dbapi.execute("DELETE FROM name_group WHERE name = ?;", 
                                     [name])
        self.dbapi.execute("INSERT INTO name_group (name, grouping) VALUES(?, ?);",
                                 [name, grouping])
        self.dbapi.commit()

    def commit_person(self, person, trans, change_time=None):
        emit = None
        old_person = None
        if person.handle in self.person_map:
            emit = "person-update"
            old_person = self.get_person_from_handle(person.handle)
            # Update gender statistics if necessary
            if (old_person.gender != person.gender or
                old_person.primary_name.first_name !=
                  person.primary_name.first_name):

                self.genderStats.uncount_person(old_person)
                self.genderStats.count_person(person)
            # Update surname list if necessary
            if (self._order_by_person_key(person) != 
                self._order_by_person_key(old_person)):
                self.remove_from_surname_list(old_person)
                self.add_to_surname_list(person, trans.batch)
            given_name, surname, gender_type = self.get_person_data(person)
            # update the person:
            self.dbapi.execute("""UPDATE person SET gramps_id = ?, 
                                                    order_by = ?,
                                                    blob_data = ?,
                                                    given_name = ?,
                                                    surname = ?,
                                                    gender_type = ?
                                                WHERE handle = ?;""",
                               [person.gramps_id, 
                                self._order_by_person_key(person),
                                pickle.dumps(person.serialize()),
                                given_name,
                                surname,
                                gender_type,
                                person.handle])
        else:
            emit = "person-add"
            self.genderStats.count_person(person)
            self.add_to_surname_list(person, trans.batch)
            given_name, surname, gender_type = self.get_person_data(person)
            # Insert the person:
            self.dbapi.execute("""INSERT INTO person (handle, order_by, gramps_id, blob_data,
                                                      given_name, surname, gender_type)
                            VALUES(?, ?, ?, ?, ?, ?, ?);""", 
                               [person.handle, 
                                self._order_by_person_key(person),
                                person.gramps_id, 
                                pickle.dumps(person.serialize()),
                                given_name, surname, gender_type])
        if not trans.batch:
            self.update_backlinks(person)
            self.dbapi.commit()
            if old_person:
                trans.add(PERSON_KEY, TXNUPD, person.handle, 
                          old_person.serialize(), 
                          person.serialize())
            else:
                trans.add(PERSON_KEY, TXNADD, person.handle, 
                          None, 
                          person.serialize())
        # Other misc update tasks:
        self.individual_attributes.update(
            [str(attr.type) for attr in person.attribute_list
             if attr.type.is_custom() and str(attr.type)])

        self.event_role_names.update([str(eref.role)
                                      for eref in person.event_ref_list
                                      if eref.role.is_custom()])

        self.name_types.update([str(name.type)
                                for name in ([person.primary_name]
                                             + person.alternate_names)
                                if name.type.is_custom()])
        all_surn = []  # new list we will use for storage
        all_surn += person.primary_name.get_surname_list() 
        for asurname in person.alternate_names:
            all_surn += asurname.get_surname_list()
        self.origin_types.update([str(surn.origintype) for surn in all_surn
                                if surn.origintype.is_custom()])
        all_surn = None
        self.url_types.update([str(url.type) for url in person.urls
                               if url.type.is_custom()])
        attr_list = []
        for mref in person.media_list:
            attr_list += [str(attr.type) for attr in mref.attribute_list
                          if attr.type.is_custom() and str(attr.type)]
        self.media_attributes.update(attr_list)
        # Emit after added:
        if emit:
            self.emit(emit, ([person.handle],))
        self.has_changed = True

    def commit_family(self, family, trans, change_time=None):
        emit = None
        old_family = None
        if family.handle in self.family_map:
            emit = "family-update"
            old_family = self.get_family_from_handle(family.handle).serialize()
            self.dbapi.execute("""UPDATE family SET gramps_id = ?, 
                                                    blob_data = ? 
                                                WHERE handle = ?;""",
                               [family.gramps_id, 
                                pickle.dumps(family.serialize()),
                                family.handle])
        else:
            emit = "family-add"
            self.dbapi.execute("""INSERT INTO family (handle, gramps_id, blob_data)
                    VALUES(?, ?, ?);""", 
                               [family.handle, family.gramps_id, 
                                pickle.dumps(family.serialize())])
        if not trans.batch:
            self.update_backlinks(family)
            self.dbapi.commit()
            op = TXNUPD if old_family else TXNADD
            trans.add(FAMILY_KEY, op, family.handle, 
                      old_family, 
                      family.serialize())

        # Misc updates:
        self.family_attributes.update(
            [str(attr.type) for attr in family.attribute_list
             if attr.type.is_custom() and str(attr.type)])

        rel_list = []
        for ref in family.child_ref_list:
            if ref.frel.is_custom():
                rel_list.append(str(ref.frel))
            if ref.mrel.is_custom():
                rel_list.append(str(ref.mrel))
        self.child_ref_types.update(rel_list)

        self.event_role_names.update(
            [str(eref.role) for eref in family.event_ref_list
             if eref.role.is_custom()])

        if family.type.is_custom():
            self.family_rel_types.add(str(family.type))

        attr_list = []
        for mref in family.media_list:
            attr_list += [str(attr.type) for attr in mref.attribute_list
                          if attr.type.is_custom() and str(attr.type)]
        self.media_attributes.update(attr_list)
        # Emit after added:
        if emit:
            self.emit(emit, ([family.handle],))
        self.has_changed = True

    def commit_citation(self, citation, trans, change_time=None):
        emit = None
        old_citation = None
        if citation.handle in self.citation_map:
            emit = "citation-update"
            old_citation = self.get_citation_from_handle(citation.handle).serialize()
            self.dbapi.execute("""UPDATE citation SET gramps_id = ?, 
                                                      order_by = ?,
                                                      blob_data = ? 
                                                WHERE handle = ?;""",
                               [citation.gramps_id, 
                                self._order_by_citation_key(citation),
                                pickle.dumps(citation.serialize()),
                                citation.handle])
        else:
            emit = "citation-add"
            self.dbapi.execute("""INSERT INTO citation (handle, order_by, gramps_id, blob_data)
                     VALUES(?, ?, ?, ?);""", 
                       [citation.handle, 
                        self._order_by_citation_key(citation),
                        citation.gramps_id, 
                        pickle.dumps(citation.serialize())])
        if not trans.batch:
            self.update_backlinks(citation)
            self.dbapi.commit()
            op = TXNUPD if old_citation else TXNADD
            trans.add(CITATION_KEY, op, citation.handle, 
                      old_citation, 
                      citation.serialize())
        # Misc updates:
        attr_list = []
        for mref in citation.media_list:
            attr_list += [str(attr.type) for attr in mref.attribute_list
                          if attr.type.is_custom() and str(attr.type)]
        self.media_attributes.update(attr_list)

        self.source_attributes.update(
            [str(attr.type) for attr in citation.attribute_list
             if attr.type.is_custom() and str(attr.type)])

        # Emit after added:
        if emit:
            self.emit(emit, ([citation.handle],))
        self.has_changed = True

    def commit_source(self, source, trans, change_time=None):
        emit = None
        old_source = None
        if source.handle in self.source_map:
            emit = "source-update"
            old_source = self.get_source_from_handle(source.handle).serialize()
            self.dbapi.execute("""UPDATE source SET gramps_id = ?, 
                                                    order_by = ?,
                                                    blob_data = ? 
                                                WHERE handle = ?;""",
                               [source.gramps_id, 
                                self._order_by_source_key(source),
                                pickle.dumps(source.serialize()),
                                source.handle])
        else:
            emit = "source-add"
            self.dbapi.execute("""INSERT INTO source (handle, order_by, gramps_id, blob_data)
                    VALUES(?, ?, ?, ?);""", 
                       [source.handle, 
                        self._order_by_source_key(source),
                        source.gramps_id, 
                        pickle.dumps(source.serialize())])
        if not trans.batch:
            self.update_backlinks(source)
            self.dbapi.commit()
            op = TXNUPD if old_source else TXNADD
            trans.add(SOURCE_KEY, op, source.handle, 
                      old_source, 
                      source.serialize())
        # Misc updates:
        self.source_media_types.update(
            [str(ref.media_type) for ref in source.reporef_list
             if ref.media_type.is_custom()])       

        attr_list = []
        for mref in source.media_list:
            attr_list += [str(attr.type) for attr in mref.attribute_list
                          if attr.type.is_custom() and str(attr.type)]
        self.media_attributes.update(attr_list)
        self.source_attributes.update(
            [str(attr.type) for attr in source.attribute_list
             if attr.type.is_custom() and str(attr.type)])
        # Emit after added:
        if emit:
            self.emit(emit, ([source.handle],))
        self.has_changed = True

    def commit_repository(self, repository, trans, change_time=None):
        emit = None
        old_repository = None
        if repository.handle in self.repository_map:
            emit = "repository-update"
            old_repository = self.get_repository_from_handle(repository.handle).serialize()
            self.dbapi.execute("""UPDATE repository SET gramps_id = ?, 
                                                    blob_data = ? 
                                                WHERE handle = ?;""",
                               [repository.gramps_id, 
                                pickle.dumps(repository.serialize()),
                                repository.handle])
        else:
            emit = "repository-add"
            self.dbapi.execute("""INSERT INTO repository (handle, gramps_id, blob_data)
                     VALUES(?, ?, ?);""", 
                       [repository.handle, repository.gramps_id, pickle.dumps(repository.serialize())])
        if not trans.batch:
            self.update_backlinks(repository)
            self.dbapi.commit()
            op = TXNUPD if old_repository else TXNADD
            trans.add(REPOSITORY_KEY, op, repository.handle, 
                      old_repository, 
                      repository.serialize())
        # Misc updates:
        if repository.type.is_custom():
            self.repository_types.add(str(repository.type))

        self.url_types.update([str(url.type) for url in repository.urls
                               if url.type.is_custom()])
        # Emit after added:
        if emit:
            self.emit(emit, ([repository.handle],))
        self.has_changed = True

    def commit_note(self, note, trans, change_time=None):
        emit = None
        old_note = None
        if note.handle in self.note_map:
            emit = "note-update"
            old_note = self.get_note_from_handle(note.handle).serialize()
            self.dbapi.execute("""UPDATE note SET gramps_id = ?, 
                                                    blob_data = ? 
                                                WHERE handle = ?;""",
                               [note.gramps_id, 
                                pickle.dumps(note.serialize()),
                                note.handle])
        else:
            emit = "note-add"
            self.dbapi.execute("""INSERT INTO note (handle, gramps_id, blob_data)
                     VALUES(?, ?, ?);""", 
                       [note.handle, note.gramps_id, pickle.dumps(note.serialize())])
        if not trans.batch:
            self.update_backlinks(note)
            self.dbapi.commit()
            op = TXNUPD if old_note else TXNADD
            trans.add(NOTE_KEY, op, note.handle, 
                      old_note, 
                      note.serialize())
        # Misc updates:
        if note.type.is_custom():
            self.note_types.add(str(note.type))        
        # Emit after added:
        if emit:
            self.emit(emit, ([note.handle],))
        self.has_changed = True

    def commit_place(self, place, trans, change_time=None):
        emit = None
        old_place = None
        if place.handle in self.place_map:
            emit = "place-update"
            old_place = self.get_place_from_handle(place.handle).serialize()
            self.dbapi.execute("""UPDATE place SET gramps_id = ?, 
                                                   order_by = ?,
                                                   blob_data = ? 
                                                WHERE handle = ?;""",
                               [place.gramps_id, 
                                self._order_by_place_key(place),
                                pickle.dumps(place.serialize()),
                                place.handle])
        else:
            emit = "place-add"
            self.dbapi.execute("""INSERT INTO place (handle, order_by, gramps_id, blob_data)
                    VALUES(?, ?, ?, ?);""", 
                       [place.handle, 
                        self._order_by_place_key(place),
                        place.gramps_id, 
                        pickle.dumps(place.serialize())])
        if not trans.batch:
            self.update_backlinks(place)
            self.dbapi.commit()
            op = TXNUPD if old_place else TXNADD
            trans.add(PLACE_KEY, op, place.handle, 
                      old_place, 
                      place.serialize())
        # Misc updates:
        if place.get_type().is_custom():
            self.place_types.add(str(place.get_type()))

        self.url_types.update([str(url.type) for url in place.urls
                               if url.type.is_custom()])

        attr_list = []
        for mref in place.media_list:
            attr_list += [str(attr.type) for attr in mref.attribute_list
                          if attr.type.is_custom() and str(attr.type)]
        self.media_attributes.update(attr_list)
        # Emit after added:
        if emit:
            self.emit(emit, ([place.handle],))
        self.has_changed = True

    def commit_event(self, event, trans, change_time=None):
        emit = None
        old_event = None
        if event.handle in self.event_map:
            emit = "event-update"
            old_event = self.get_event_from_handle(event.handle).serialize()
            self.dbapi.execute("""UPDATE event SET gramps_id = ?, 
                                                    blob_data = ? 
                                                WHERE handle = ?;""",
                               [event.gramps_id, 
                                pickle.dumps(event.serialize()),
                                event.handle])
        else:
            emit = "event-add"
            self.dbapi.execute("""INSERT INTO event (handle, gramps_id, blob_data)
                  VALUES(?, ?, ?);""", 
                       [event.handle, 
                        event.gramps_id, 
                        pickle.dumps(event.serialize())])
        if not trans.batch:
            self.update_backlinks(event)
            self.dbapi.commit()
            op = TXNUPD if old_event else TXNADD
            trans.add(EVENT_KEY, op, event.handle, 
                      old_event, 
                      event.serialize())
        # Misc updates:
        self.event_attributes.update(
            [str(attr.type) for attr in event.attribute_list
             if attr.type.is_custom() and str(attr.type)])
        if event.type.is_custom():
            self.event_names.add(str(event.type))
        attr_list = []
        for mref in event.media_list:
            attr_list += [str(attr.type) for attr in mref.attribute_list
                          if attr.type.is_custom() and str(attr.type)]
        self.media_attributes.update(attr_list)
        # Emit after added:
        if emit:
            self.emit(emit, ([event.handle],))
        self.has_changed = True

    def commit_tag(self, tag, trans, change_time=None):
        emit = None
        if tag.handle in self.tag_map:
            emit = "tag-update"
            self.dbapi.execute("""UPDATE tag SET blob_data = ?,
                                                 order_by = ?
                                         WHERE handle = ?;""",
                               [pickle.dumps(tag.serialize()),
                                self._order_by_tag_key(tag),
                                tag.handle])
        else:
            emit = "tag-add"
            self.dbapi.execute("""INSERT INTO tag (handle, order_by, blob_data)
                  VALUES(?, ?, ?);""", 
                       [tag.handle, 
                        self._order_by_tag_key(tag),
                        pickle.dumps(tag.serialize())])
        if not trans.batch:
            self.update_backlinks(tag)
            self.dbapi.commit()
        # Emit after added:
        if emit:
            self.emit(emit, ([tag.handle],))

    def commit_media_object(self, media, trans, change_time=None):
        emit = None
        old_media = None
        if media.handle in self.media_map:
            emit = "media-update"
            old_media = self.get_object_from_handle(media.handle).serialize()
            self.dbapi.execute("""UPDATE media SET gramps_id = ?, 
                                                   order_by = ?,
                                                   blob_data = ? 
                                                WHERE handle = ?;""",
                               [media.gramps_id, 
                                self._order_by_media_key(media),
                                pickle.dumps(media.serialize()),
                                media.handle])
        else:
            emit = "media-add"
            self.dbapi.execute("""INSERT INTO media (handle, order_by, gramps_id, blob_data)
                  VALUES(?, ?, ?, ?);""", 
                       [media.handle, 
                        self._order_by_media_key(media),
                        media.gramps_id, 
                        pickle.dumps(media.serialize())])
        if not trans.batch:
            self.update_backlinks(media)
            self.dbapi.commit()
            op = TXNUPD if old_media else TXNADD
            trans.add(MEDIA_KEY, op, media.handle, 
                      old_media, 
                      media.serialize())
        # Misc updates:
        self.media_attributes.update(
            [str(attr.type) for attr in media.attribute_list
             if attr.type.is_custom() and str(attr.type)])
        # Emit after added:
        if emit:
            self.emit(emit, ([media.handle],))

    def update_backlinks(self, obj):
        # First, delete the current references:
        self.dbapi.execute("DELETE FROM reference WHERE obj_handle = ?;",
                           [obj.handle])
        # Now, add the current ones:
        references = set(obj.get_referenced_handles_recursively())
        for (ref_class_name, ref_handle) in references:
            self.dbapi.execute("""INSERT INTO reference 
                       (obj_handle, obj_class, ref_handle, ref_class)
                       VALUES(?, ?, ?, ?);""",
                               [obj.handle, 
                                obj.__class__.__name__,
                                ref_handle, 
                                ref_class_name])
        # This function is followed by a commit.

    def remove_person(self, handle, transaction):
        """
        Remove the Person specified by the database handle from the database, 
        preserving the change in the passed transaction. 
        """

        if self.readonly or not handle:
            return
        if handle in self.person_map:
            person = Person.create(self.person_map[handle])
            self.dbapi.execute("DELETE FROM person WHERE handle = ?;", [handle])
            self.emit("person-delete", ([handle],))
            if not transaction.batch:
                self.dbapi.commit()
                transaction.add(PERSON_KEY, TXNDEL, person.handle, 
                                person.serialize(), None)

    def __do_remove(self, handle, transaction, data_map, data_id_map, key):
        key2table = {
            PERSON_KEY:     "person", 
            FAMILY_KEY:     "family", 
            SOURCE_KEY:     "source", 
            CITATION_KEY:   "citation", 
            EVENT_KEY:      "event", 
            MEDIA_KEY:      "media", 
            PLACE_KEY:      "place", 
            REPOSITORY_KEY: "repository", 
            NOTE_KEY:       "note", 
            }
        if self.readonly or not handle:
            return
        if handle in data_map:
            self.dbapi.execute("DELETE FROM %s WHERE handle = ?;" % key2table[key], 
                               [handle])
            self.emit(KEY_TO_NAME_MAP[key] + "-delete", ([handle],))
            if not transaction.batch:
                self.dbapi.commit()
                data = data_map[handle]
                transaction.add(key, TXNDEL, handle, data, None)

    def find_backlink_handles(self, handle, include_classes=None):
        """
        Find all objects that hold a reference to the object handle.
        
        Returns an interator over a list of (class_name, handle) tuples.

        :param handle: handle of the object to search for.
        :type handle: database handle
        :param include_classes: list of class names to include in the results.
            Default: None means include all classes.
        :type include_classes: list of class names

        Note that this is a generator function, it returns a iterator for
        use in loops. If you want a list of the results use::

            result_list = list(find_backlink_handles(handle))
        """
        self.dbapi.execute("SELECT obj_class, obj_handle FROM reference WHERE ref_handle = ?;",
                                 [handle])
        rows = self.dbapi.fetchall()
        for row in rows:
            if (include_classes is None) or (row[0] in include_classes):
                yield (row[0], row[1])

    def find_initial_person(self):
        handle = self.get_default_handle()
        person = None
        if handle:
            person = self.get_person_from_handle(handle)
            if person:
                return person
        self.dbapi.execute("SELECT handle FROM person;")
        row = self.dbapi.fetchone()
        if row:
            return self.get_person_from_handle(row[0])

    def iter_citation_handles(self):
        self.dbapi.execute("SELECT handle FROM citation;")
        rows = self.dbapi.fetchall()
        for row in rows:
            yield row[0]

    def iter_event_handles(self):
        self.dbapi.execute("SELECT handle FROM event;")
        rows = self.dbapi.fetchall()
        for row in rows:
            yield row[0]

    def iter_media_object_handles(self):
        self.dbapi.execute("SELECT handle FROM media;")
        rows = self.dbapi.fetchall()
        for row in rows:
            yield row[0]

    def iter_note_handles(self):
        self.dbapi.execute("SELECT handle FROM note;")
        rows = self.dbapi.fetchall()
        for row in rows:
            yield row[0]

    def iter_place_handles(self):
        self.dbapi.execute("SELECT handle FROM place;")
        rows = self.dbapi.fetchall()
        for row in rows:
            yield row[0]

    def iter_repository_handles(self):
        self.dbapi.execute("SELECT handle FROM repository;")
        rows = self.dbapi.fetchall()
        for row in rows:
            yield row[0]

    def iter_source_handles(self):
        self.dbapi.execute("SELECT handle FROM source;")
        rows = self.dbapi.fetchall()
        for row in rows:
            yield row[0]

    def iter_tag_handles(self):
        self.dbapi.execute("SELECT handle FROM tag;")
        rows = self.dbapi.fetchall()
        for row in rows:
            yield row[0]

    def reindex_reference_map(self, callback):
        callback(4)
        self.dbapi.execute("DELETE FROM reference;")
        primary_table = (
            (self.get_person_cursor, Person),
            (self.get_family_cursor, Family),
            (self.get_event_cursor, Event),
            (self.get_place_cursor, Place),
            (self.get_source_cursor, Source),
            (self.get_citation_cursor, Citation),
            (self.get_media_cursor, MediaObject),
            (self.get_repository_cursor, Repository),
            (self.get_note_cursor, Note),
            (self.get_tag_cursor, Tag),
        )
        # Now we use the functions and classes defined above
        # to loop through each of the primary object tables.
        for cursor_func, class_func in primary_table:
            logging.info("Rebuilding %s reference map" %
                         class_func.__name__)
            with cursor_func() as cursor:
                for found_handle, val in cursor:
                    obj = class_func.create(val)
                    references = set(obj.get_referenced_handles_recursively())
                    # handle addition of new references
                    for (ref_class_name, ref_handle) in references:
                        self.dbapi.execute("""INSERT INTO reference (obj_handle, obj_class, ref_handle, ref_class)
                                                 VALUES(?, ?, ?, ?);""",
                                           [obj.handle, 
                                            obj.__class__.__name__,
                                            ref_handle, 
                                            ref_class_name])
                                            
        self.dbapi.commit()
        callback(5)

    def rebuild_secondary(self, update):
        gstats = self.rebuild_gender_stats()
        self.genderStats = GenderStats(gstats) 
        self.dbapi.execute("""select blob_data from place;""")
        row = self.dbapi.fetchone()
        while row:
            place = Place.create(pickle.loads(row[0]))
            order_by = self._order_by_place_key(place)
            cur2 = self.dbapi.execute("""UPDATE place SET order_by = ? WHERE handle = ?;""",
                                      [order_by, place.handle])
            row = self.dbapi.fetchone()
        self.dbapi.commit()

    def has_handle_for_person(self, key):
        self.dbapi.execute("SELECT * FROM person WHERE handle = ?", [key])
        return self.dbapi.fetchone() != None

    def has_handle_for_family(self, key):
        self.dbapi.execute("SELECT * FROM family WHERE handle = ?", [key])
        return self.dbapi.fetchone() != None

    def has_handle_for_source(self, key):
        self.dbapi.execute("SELECT * FROM source WHERE handle = ?", [key])
        return self.dbapi.fetchone() != None

    def has_handle_for_citation(self, key):
        self.dbapi.execute("SELECT * FROM citation WHERE handle = ?", [key])
        return self.dbapi.fetchone() != None

    def has_handle_for_event(self, key):
        self.dbapi.execute("SELECT * FROM event WHERE handle = ?", [key])
        return self.dbapi.fetchone() != None

    def has_handle_for_media(self, key):
        self.dbapi.execute("SELECT * FROM media WHERE handle = ?", [key])
        return self.dbapi.fetchone() != None

    def has_handle_for_place(self, key):
        self.dbapi.execute("SELECT * FROM place WHERE handle = ?", [key])
        return self.dbapi.fetchone() != None

    def has_handle_for_repository(self, key):
        self.dbapi.execute("SELECT * FROM repository WHERE handle = ?", [key])
        return self.dbapi.fetchone() != None

    def has_handle_for_note(self, key):
        self.dbapi.execute("SELECT * FROM note WHERE handle = ?", [key])
        return self.dbapi.fetchone() != None

    def has_handle_for_tag(self, key):
        self.dbapi.execute("SELECT * FROM tag WHERE handle = ?", [key])
        return self.dbapi.fetchone() != None

    def has_gramps_id_for_person(self, key):
        self.dbapi.execute("SELECT * FROM person WHERE gramps_id = ?", [key])
        return self.dbapi.fetchone() != None

    def has_gramps_id_for_family(self, key):
        self.dbapi.execute("SELECT * FROM family WHERE gramps_id = ?", [key])
        return self.dbapi.fetchone() != None

    def has_gramps_id_for_source(self, key):
        self.dbapi.execute("SELECT * FROM source WHERE gramps_id = ?", [key])
        return self.dbapi.fetchone() != None

    def has_gramps_id_for_citation(self, key):
        self.dbapi.execute("SELECT * FROM citation WHERE gramps_id = ?", [key])
        return self.dbapi.fetchone() != None

    def has_gramps_id_for_event(self, key):
        self.dbapi.execute("SELECT * FROM event WHERE gramps_id = ?", [key])
        return self.dbapi.fetchone() != None

    def has_gramps_id_for_media(self, key):
        self.dbapi.execute("SELECT * FROM media WHERE gramps_id = ?", [key])
        return self.dbapi.fetchone() != None

    def has_gramps_id_for_place(self, key):
        self.dbapi.execute("SELECT * FROM place WHERE gramps_id = ?", [key])
        return self.dbapi.fetchone() != None

    def has_gramps_id_for_repository(self, key):
        self.dbapi.execute("SELECT * FROM repository WHERE gramps_id = ?", [key])
        return self.dbapi.fetchone() != None

    def has_gramps_id_for_note(self, key):
        self.dbapi.execute("SELECT * FROM note WHERE gramps_id = ?", [key])
        return self.dbapi.fetchone() != None

    def get_person_gramps_ids(self):
        self.dbapi.execute("SELECT gramps_id FROM person;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_family_gramps_ids(self):
        self.dbapi.execute("SELECT gramps_id FROM family;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_source_gramps_ids(self):
        self.dbapi.execute("SELECT gramps_id FROM source;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_citation_gramps_ids(self):
        self.dbapi.execute("SELECT gramps_id FROM citation;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_event_gramps_ids(self):
        self.dbapi.execute("SELECT gramps_id FROM event;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_media_gramps_ids(self):
        self.dbapi.execute("SELECT gramps_id FROM media;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_place_gramps_ids(self):
        self.dbapi.execute("SELECT gramps FROM place;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_repository_gramps_ids(self):
        self.dbapi.execute("SELECT gramps_id FROM repository;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def get_note_gramps_ids(self):
        self.dbapi.execute("SELECT gramps_id FROM note;")
        rows = self.dbapi.fetchall()
        return [row[0] for row in rows]

    def _get_raw_person_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM person WHERE handle = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_person_from_id_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM person WHERE gramps_id = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_family_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM family WHERE handle = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_family_from_id_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM family WHERE gramps_id = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_source_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM source WHERE handle = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_source_from_id_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM source WHERE gramps_id = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_citation_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM citation WHERE handle = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_citation_from_id_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM citation WHERE gramps_id = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_event_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM event WHERE handle = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_event_from_id_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM event WHERE gramps_id = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_media_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM media WHERE handle = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_media_from_id_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM media WHERE gramps_id = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_place_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM place WHERE handle = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_place_from_id_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM place WHERE gramps_id = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_repository_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM repository WHERE handle = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_repository_from_id_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM repository WHERE handle = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_note_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM note WHERE handle = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_note_from_id_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM note WHERE gramps_id = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def _get_raw_tag_data(self, key):
        self.dbapi.execute("SELECT blob_data FROM tag WHERE handle = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            return pickle.loads(row[0])

    def rebuild_gender_stats(self):
        """
        Returns a dictionary of 
        {given_name: (male_count, female_count, unknown_count)} 
        """
        self.dbapi.execute("""SELECT given_name, gender_type FROM person;""")
        gstats = {}
        for row in self.dbapi.fetchall():
            if row[0] not in gstats:
                gstats[row[0]] = [0, 0, 0]
            gstats[row[0]][row[1]] += 1
        return gstats

    def save_gender_stats(self, gstats):
        self.dbapi.execute("""DELETE FROM gender_stats;""")
        for key in gstats.stats:
            female, male, unknown = gstats.stats[key]
            self.dbapi.execute("""INSERT INTO gender_stats(given_name, female, male, unknown) 
                                              VALUES(?, ?, ?, ?);""",
                               [key, female, male, unknown]);
        self.dbapi.commit()

    def get_gender_stats(self):
        """
        Returns a dictionary of 
        {given_name: (male_count, female_count, unknown_count)} 
        """
        self.dbapi.execute("""SELECT given_name, female, male, unknown FROM gender_stats;""")
        gstats = {}
        for row in self.dbapi.fetchall():
            gstats[row[0]] = [row[1], row[2], row[3]]
        return gstats
        
    def get_surname_list(self):
        self.dbapi.execute("""SELECT DISTINCT surname FROM person ORDER BY surname;""")
        surname_list = []
        for row in self.dbapi.fetchall():
            surname_list.append(row[0])
        return surname_list

    def save_surname_list(self):
        """
        Save the surname_list into persistant storage.
        """
        # Nothing for DB-API to do; saves in person table
        pass

    def build_surname_list(self):
        """
        Rebuild the surname_list.
        """
        # Nothing for DB-API to do; saves in person table
        pass

    def drop_tables(self):
        """
        Useful in testing, reseting.
        """
        self.dbapi.try_execute("""DROP TABLE  person;""")
        self.dbapi.try_execute("""DROP TABLE  family;""")
        self.dbapi.try_execute("""DROP TABLE  source;""")
        self.dbapi.try_execute("""DROP TABLE  citation""")
        self.dbapi.try_execute("""DROP TABLE  event;""")
        self.dbapi.try_execute("""DROP TABLE  media;""")
        self.dbapi.try_execute("""DROP TABLE  place;""")
        self.dbapi.try_execute("""DROP TABLE  repository;""")
        self.dbapi.try_execute("""DROP TABLE  note;""")
        self.dbapi.try_execute("""DROP TABLE  tag;""")
        # Secondary:
        self.dbapi.try_execute("""DROP TABLE  reference;""")
        self.dbapi.try_execute("""DROP TABLE  name_group;""")
        self.dbapi.try_execute("""DROP TABLE  metadata;""")
        self.dbapi.try_execute("""DROP TABLE  gender_stats;""") 

