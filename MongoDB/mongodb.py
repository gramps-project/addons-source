#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2015-2016 Douglas S. Blank <doug.blank@gmail.com>
# Copyright (C) 2016-2018 Nick Hall
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

#-------------------------------------------------------------------------
#
# Standard python modules
#
#-------------------------------------------------------------------------
import os
import time
import logging
import json
from pymongo import MongoClient, version, ASCENDING

#------------------------------------------------------------------------
#
# Gramps Modules
#
#------------------------------------------------------------------------
from gramps.gen.db.dbconst import (DBLOGNAME, DBBACKEND, KEY_TO_NAME_MAP,
                                   KEY_TO_CLASS_MAP, TXNADD, TXNUPD, TXNDEL,
                                   PERSON_KEY, FAMILY_KEY, SOURCE_KEY,
                                   EVENT_KEY, MEDIA_KEY, PLACE_KEY, NOTE_KEY,
                                   TAG_KEY, CITATION_KEY, REPOSITORY_KEY,
                                   REFERENCE_KEY)
from gramps.gen.db.generic import DbGeneric
from gramps.gen.lib import (Tag, Media, Person, Family, Source,
                            Citation, Event, Place, Repository, Note)
from gramps.gen.lib.genderstats import GenderStats
from gramps.gen.lib.serialize import to_json, from_json
from gramps.gen.utils.configmanager import ConfigManager
from gramps.gen.config import config
from gramps.gen.const import GRAMPS_LOCALE as glocale

LOG = logging.getLogger(".mongodb")
_LOG = logging.getLogger(DBLOGNAME)

def obj_to_doc(obj):
    """
    Convert a Gramps object into a MongoDB document.
    """
    doc = json.loads(to_json(obj))
    doc['_id'] = doc['handle']
    del doc['handle']
    return doc

def doc_to_obj(doc):
    """
    Convert a MongoDB document into a Gramps object.
    """
    doc['handle'] = doc['_id']
    del doc['_id']
    obj = from_json(json.dumps(doc))
    return obj

class MongoDB(DbGeneric):
    """
    Backend for MongoDB database
    """
    def get_summary(self):
        """
        Return a dictionary of information about this database backend.
        """
        summary = super().get_summary()
        summary.update({
            _("Database version"): version,
        })
        return summary

    def _initialize(self, directory, username, password):
        config_file = os.path.join(directory, 'settings.ini')
        config_mgr = ConfigManager(config_file)
        config_mgr.register('database.dbname', '')
        config_mgr.register('database.host', '')
        config_mgr.register('database.port', '')

        if not os.path.exists(config_file):
            name_file = os.path.join(directory, 'name.txt')
            with open(name_file, 'r', encoding='utf8') as file:
                dbname = file.readline().strip()
            config_mgr.set('database.dbname', dbname)
            config_mgr.set('database.host', config.get('database.host'))
            config_mgr.set('database.port', config.get('database.port'))
            config_mgr.save()

        config_mgr.load()

        dbkwargs = {}
        for key in config_mgr.get_section_settings('database'):
            value = config_mgr.get('database.' + key)
            if key != 'dbname':
                if value:
                    dbkwargs[key] = value
            else:
                dbname = value
        if username:
            dbkwargs['user'] = username
        if password:
            dbkwargs['password'] = password

        self.client = MongoClient(**dbkwargs)
        self.db = self.client[dbname]

    def _schema_exists(self):
        """
        Check to see if the schema exists.

        We use the existence of the person collection as a proxy for the
        database being new.
        """
        return "person" in self.db.list_collection_names()

    def _create_schema(self):
        """
        Create and update schema.
        """
        self.db.create_collection("person")
        self.db.create_collection("family")
        self.db.create_collection("event")
        self.db.create_collection("place")
        self.db.create_collection("repository")
        self.db.create_collection("source")
        self.db.create_collection("citation")
        self.db.create_collection("media")
        self.db.create_collection("note")
        self.db.create_collection("tag")

        self.db.create_collection("reference")
        self.db.create_collection("metadata")
        self.db.create_collection("name_group")
        self.db.create_collection("gender_stats")

        self.db.person.create_index("gramps_id")
        self.db.person.create_index("primary_name.first_name")
        self.db.person.create_index("primary_name.surname_list.surname")
        self.db.family.create_index("gramps_id")
        self.db.event.create_index("gramps_id")
        self.db.place.create_index("gramps_id")
        self.db.place.create_index("placeref_list.0.ref")
        self.db.repository.create_index("gramps_id")
        self.db.source.create_index("gramps_id")
        self.db.source.create_index("title")
        self.db.citation.create_index("gramps_id")
        self.db.citation.create_index("page")
        self.db.media.create_index("gramps_id")
        self.db.media.create_index("desc")
        self.db.note.create_index("gramps_id")
        self.db.tag.create_index("gramps_id")
        self.db.tag.create_index("name")

        self.db.reference.create_index("obj_handle")
        self.db.reference.create_index("ref_handle")
        self.db.metadata.create_index("setting")
        self.db.name_group.create_index("name")
        self.db.gender_stats.create_index("given_name")

    def _close(self):
        self.client.close()

    def _txn_begin(self):
        """
        Lowlevel interface to the backend transaction.
        Executes a db BEGIN;
        """
        pass

    def _txn_commit(self):
        """
        Lowlevel interface to the backend transaction.
        Executes a db END;
        """
        pass

    def _txn_abort(self):
        """
        Lowlevel interface to the backend transaction.
        Executes a db ROLLBACK;
        """
        pass

    def transaction_begin(self, transaction):
        """
        Transactions are handled automatically by the db layer.
        """
        _LOG.debug("    %sDBAPI %s transaction begin for '%s'",
                   "Batch " if transaction.batch else "",
                   hex(id(self)), transaction.get_description())
        self.transaction = transaction
        return transaction

    def transaction_commit(self, txn):
        """
        Executed at the end of a transaction.
        """
        _LOG.debug("    %sDBAPI %s transaction commit for '%s'",
                   "Batch " if txn.batch else "",
                   hex(id(self)), txn.get_description())

        action = {TXNADD: "-add",
                  TXNUPD: "-update",
                  TXNDEL: "-delete",
                  None: "-delete"}
        if txn.batch:
            # FIXME: need a User GUI update callback here:
            self.reindex_reference_map(lambda percent: percent)
        if not txn.batch:
            # Now, emit signals:
            # do deletes and adds first
            for trans_type in [TXNDEL, TXNADD, TXNUPD]:
                for obj_type in range(11):
                    if obj_type != REFERENCE_KEY and \
                            (obj_type, trans_type) in txn:
                        if trans_type == TXNDEL:
                            handles = [handle for (handle, data) in
                                       txn[(obj_type, trans_type)]]
                        else:
                            handles = [handle for (handle, data) in
                                       txn[(obj_type, trans_type)]
                                       if (handle, None)
                                       not in txn[(obj_type, TXNDEL)]]
                        if handles:
                            signal = KEY_TO_NAME_MAP[
                                obj_type] + action[trans_type]
                            self.emit(signal, (handles, ))
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
        self.transaction = None
        txn.clear()
        txn.first = None
        txn.last = None
        self._after_commit(txn)

    def _get_metadata(self, key, default=[]):
        """
        Get an item from the database.

        Default is an empty list, which is a mutable and
        thus a bad default (pylint will complain).

        However, it is just used as a value, and not altered, so
        its use here is ok.
        """
        doc = self.db.metadata.find_one({"setting": key})
        if doc:
            type_name = doc["type"]
            if type_name in ('int', 'str', 'list'):
                return doc["value"]
            elif type_name == 'set':
                return set(doc["value"])
            elif type_name == 'tuple':
                return tuple(doc["value"])
            else:
                return from_json(json.dumps(doc["value"]))
        elif default == []:
            return []
        else:
            return default

    def _set_metadata(self, key, value):
        """
        key: string
        value: item, will be serialized here
        """
        type_name = type(value).__name__
        if type_name in ('set', 'tuple'):
            value = list(value)
        elif type_name not in ('int', 'str', 'list'):
            value = json.loads(to_json(value))
        self.db.metadata.update_one(
            {"setting": key},
            {"$set": {"value": value, "type": type_name}},
            upsert=True)

    def get_name_group_keys(self):
        """
        Return the defined names that have been assigned to a default grouping.
        """
        cursor = self.db.name_group.find({}, {"name": 1})
        return [doc["name"] for doc in cursor]

    def get_name_group_mapping(self, key):
        """
        Return the default grouping name for a surname.
        """
        doc = self.db.name_group.find_one({"name": key})
        if doc:
            return doc["grouping"]
        else:
            return key

    def get_person_handles(self, sort_handles=False, locale=glocale):
        """
        Return a list of database handles, one handle for each Person in
        the database.

        :param sort_handles: If True, the list is sorted by surnames.
        :type sort_handles: bool
        :param locale: The locale to use for collation.
        :type locale: A GrampsLocale object.
        """
        cursor = self.db.person.find({}, {"_id": 1})
        if sort_handles:
            cursor.sort("primary_name.surname_list.surname", ASCENDING)
        return [doc["_id"] for doc in cursor]

    def get_family_handles(self, sort_handles=False, locale=glocale):
        """
        Return a list of database handles, one handle for each Family in
        the database.

        :param sort_handles: If True, the list is sorted by surnames.
        :type sort_handles: bool
        :param locale: The locale to use for collation.
        :type locale: A GrampsLocale object.
        """
        cursor = self.db.family.find({}, {"_id": 1})
        if sort_handles:
            # FIXME: Need to order by father and mother surname
            pass
        return [doc["_id"] for doc in cursor]

    def get_event_handles(self):
        """
        Return a list of database handles, one handle for each Event in the
        database.
        """
        cursor = self.db.event.find({})
        return [doc["_id"] for doc in cursor]

    def get_citation_handles(self, sort_handles=False, locale=glocale):
        """
        Return a list of database handles, one handle for each Citation in
        the database.

        :param sort_handles: If True, the list is sorted by Citation title.
        :type sort_handles: bool
        :param locale: The locale to use for collation.
        :type locale: A GrampsLocale object.
        """
        cursor = self.db.citation.find({}, {"_id": 1})
        if sort_handles:
            cursor.sort("page", ASCENDING)
        return [doc["_id"] for doc in cursor]

    def get_source_handles(self, sort_handles=False, locale=glocale):
        """
        Return a list of database handles, one handle for each Source in
        the database.

        :param sort_handles: If True, the list is sorted by Source title.
        :type sort_handles: bool
        :param locale: The locale to use for collation.
        :type locale: A GrampsLocale object.
        """
        cursor = self.db.source.find({}, {"_id": 1})
        if sort_handles:
            cursor.sort("title", ASCENDING)
        return [doc["_id"] for doc in cursor]

    def get_place_handles(self, sort_handles=False, locale=glocale):
        """
        Return a list of database handles, one handle for each Place in
        the database.

        :param sort_handles: If True, the list is sorted by Place title.
        :type sort_handles: bool
        :param locale: The locale to use for collation.
        :type locale: A GrampsLocale object.
        """
        cursor = self.db.place.find({}, {"_id": 1})
        if sort_handles:
            cursor.sort("title", ASCENDING)
        return [doc["_id"] for doc in cursor]

    def get_repository_handles(self):
        """
        Return a list of database handles, one handle for each Repository in
        the database.
        """
        cursor = self.db.repository.find({})
        return [doc["_id"] for doc in cursor]

    def get_media_handles(self, sort_handles=False, locale=glocale):
        """
        Return a list of database handles, one handle for each Media in
        the database.

        :param sort_handles: If True, the list is sorted by title.
        :type sort_handles: bool
        :param locale: The locale to use for collation.
        :type locale: A GrampsLocale object.
        """
        cursor = self.db.media.find({}, {"_id": 1})
        if sort_handles:
            cursor.sort("desc", ASCENDING)
        return [doc["_id"] for doc in cursor]

    def get_note_handles(self):
        """
        Return a list of database handles, one handle for each Note in the
        database.
        """
        cursor = self.db.note.find({})
        return [doc["_id"] for doc in cursor]

    def get_tag_handles(self, sort_handles=False, locale=glocale):
        """
        Return a list of database handles, one handle for each Tag in
        the database.

        :param sort_handles: If True, the list is sorted by Tag name.
        :type sort_handles: bool
        :param locale: The locale to use for collation.
        :type locale: A GrampsLocale object.
        """
        cursor = self.db.tag.find({}, {"_id": 1})
        if sort_handles:
            cursor.sort("name", ASCENDING)
        return [doc["_id"] for doc in cursor]

    def get_tag_from_name(self, name):
        """
        Find a Tag in the database from the passed Tag name.

        If no such Tag exists, None is returned.
        """
        doc = self.db.tag.find_one({"name": name})
        if doc:
            return doc_to_obj(doc)
        return None

    def _get_number_of(self, obj_key):
        table = KEY_TO_NAME_MAP[obj_key]
        total = self.db[table].find().count()
        return total

    def has_name_group_key(self, key):
        """
        Return if a key exists in the name_group table.
        """
        doc = self.db.tag.find_one({"name": key})
        return True if doc else False

    def set_name_group_mapping(self, name, grouping):
        """
        Set the default grouping name for a surname.
        """
        self.db.name_group.update_one(
            {"name": name},
            {"$set": {"grouping": grouping}},
            upsert=True)

    def _commit_base(self, obj, obj_key, trans, change_time):
        """
        Commit the specified object to the database, storing the changes as
        part of the transaction.
        """
        old_data = None
        obj.change = int(change_time or time.time())
        table = KEY_TO_NAME_MAP[obj_key]

        if self._has_handle(obj_key, obj.handle):
            old_data = self._get_raw_data(obj_key, obj.handle)

        doc = obj_to_doc(obj)
        self.db[table].replace_one({"_id": obj.handle}, doc, upsert=True)

        if not trans.batch:
            self._update_backlinks(obj, trans)
            if old_data:
                trans.add(obj_key, TXNUPD, obj.handle,
                          old_data,
                          obj.serialize())
            else:
                trans.add(obj_key, TXNADD, obj.handle,
                          None,
                          obj.serialize())

        return old_data

    def _update_backlinks(self, obj, transaction):

        # Find existing references
        cursor = self.db.reference.find({"obj_handle": obj.handle})
        existing_references = set([(doc["ref_class"], doc["ref_handle"])
                                   for doc in cursor])

        # Once we have the list of rows that already have a reference
        # we need to compare it with the list of objects that are
        # still references from the primary object.
        current_references = set(obj.get_referenced_handles_recursively())
        no_longer_required_references = existing_references.difference(
                                                            current_references)
        new_references = current_references.difference(existing_references)

        # Delete the existing references
        self.db.reference.delete_one({"obj_handle": obj.handle})

        # Now, add the current ones
        for (ref_class_name, ref_handle) in current_references:
            self.db.reference.insert_one({"obj_handle": obj.handle,
                                          "obj_class": obj.__class__.__name__,
                                          "ref_handle": ref_handle,
                                          "ref_class": ref_class_name})

        if not transaction.batch:
            # Add new references to the transaction
            for (ref_class_name, ref_handle) in new_references:
                key = (obj.handle, ref_handle)
                data = (obj.handle, obj.__class__.__name__,
                        ref_handle, ref_class_name)
                transaction.add(REFERENCE_KEY, TXNADD, key, None, data)

            # Add old references to the transaction
            for (ref_class_name, ref_handle) in no_longer_required_references:
                key = (obj.handle, ref_handle)
                old_data = (obj.handle, obj.__class__.__name__,
                            ref_handle, ref_class_name)
                transaction.add(REFERENCE_KEY, TXNDEL, key, old_data, None)

    def _do_remove(self, handle, transaction, obj_key):
        if self.readonly or not handle:
            return
        if self._has_handle(obj_key, handle):
            data = self._get_raw_data(obj_key, handle)
            obj_class = KEY_TO_CLASS_MAP[obj_key]
            self._remove_backlinks(obj_class, handle, transaction)
            table = KEY_TO_NAME_MAP[obj_key]
            self.db[table].delete_one({"_id": handle})
            if not transaction.batch:
                transaction.add(obj_key, TXNDEL, handle, data, None)

    def _remove_backlinks(self, obj_class, obj_handle, transaction):
        """
        Removes all references from this object (backlinks).
        """
        # collect backlinks from this object for undo
        cursor = self.db.reference.find({"obj_handle": obj_handle})

        # Now, delete backlinks from this object:
        self.db.reference.delete_many({"obj_handle": obj_handle})

        # Add old references to the transaction
        if not transaction.batch:
            for doc in cursor:
                ref_class_name = doc["ref_class_name"]
                ref_handle = doc["ref_handle"]
                key = (obj_handle, ref_handle)
                old_data = (obj_handle, obj_class, ref_handle, ref_class_name)
                transaction.add(REFERENCE_KEY, TXNDEL, key, old_data, None)

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
        cursor = self.db.reference.find({"ref_handle": handle})
        for doc in cursor:
            if ((include_classes is None) or
                    (doc["obj_class"] in include_classes)):
                yield (doc["obj_class"], doc["obj_handle"])

    def find_initial_person(self):
        """
        Returns first person in the database
        """
        handle = self.get_default_handle()
        person = None
        if handle:
            person = self.get_person_from_handle(handle)
            if person:
                return person
        doc = self.db.person.find_one()
        if doc:
            return self.get_person_from_handle(doc["_id"])

    def _iter_handles(self, obj_key):
        """
        Return an iterator over handles in the database
        """
        table = KEY_TO_NAME_MAP[obj_key]
        cursor = self.db[table].find()
        for doc in cursor:
            yield doc["_id"]

    def _iter_raw_data(self, obj_key):
        """
        Return an iterator over raw data in the database.
        """
        table = KEY_TO_NAME_MAP[obj_key]
        cursor = self.db[table].find()
        for doc in cursor:
            obj = doc_to_obj(doc)
            yield (obj.handle, obj.serialize())

    def _iter_raw_place_tree_data(self):
        """
        Return an iterator over raw data in the place hierarchy.
        """
        to_do = ['']
        while to_do:
            handle = to_do.pop()
            if handle == '':
                cursor = self.db.place.find({"placeref_list": {"$size": 0}})
            else:
                cursor = self.db.place.find({"placeref_list.0.ref": handle})
            for doc in cursor:
                to_do.append(doc["_id"])
                obj = doc_to_obj(doc)
                yield (obj.handle, obj.serialize())

    def reindex_reference_map(self, callback):
        """
        Reindex all primary records in the database.
        """
        callback(4)
        self.db.reference.delete_many({})
        primary_table = (
            (self.get_person_cursor, Person),
            (self.get_family_cursor, Family),
            (self.get_event_cursor, Event),
            (self.get_place_cursor, Place),
            (self.get_source_cursor, Source),
            (self.get_citation_cursor, Citation),
            (self.get_media_cursor, Media),
            (self.get_repository_cursor, Repository),
            (self.get_note_cursor, Note),
            (self.get_tag_cursor, Tag),
        )
        # Now we use the functions and classes defined above
        # to loop through each of the primary object tables.
        for cursor_func, class_func in primary_table:
            logging.info("Rebuilding %s reference map", class_func.__name__)
            with cursor_func() as cursor:
                for found_handle, val in cursor:
                    obj = class_func.create(val)
                    references = set(obj.get_referenced_handles_recursively())
                    # handle addition of new references
                    for (ref_class_name, ref_handle) in references:
                        self.db.reference.insert_one(
                            {"obj_handle": obj.handle,
                             "obj_class": obj.__class__.__name__,
                             "ref_handle": ref_handle,
                             "ref_class": ref_class_name})
        callback(5)

    def rebuild_secondary(self, update):
        """
        Rebuild secondary indices
        """
        # First, expand blob to individual fields:
        self._update_secondary_values()
        # Next, rebuild stats:
        gstats = self.get_gender_stats()
        self.genderStats = GenderStats(gstats)

    def _has_handle(self, obj_key, handle):
        table = KEY_TO_NAME_MAP[obj_key]
        doc = self.db[table].find_one({"_id": handle})
        return doc is not None

    def _has_gramps_id(self, obj_key, gramps_id):
        table = KEY_TO_NAME_MAP[obj_key]
        doc = self.db[table].find_one({"gramps_id": gramps_id})
        return doc is not None

    def _get_gramps_ids(self, obj_key):
        table = KEY_TO_NAME_MAP[obj_key]
        cursor = self.db[table].find()
        return [doc["gramps_id"] for doc in cursor]

    def _get_raw_data(self, obj_key, handle):
        table = KEY_TO_NAME_MAP[obj_key]
        doc = self.db[table].find_one({"_id": handle})
        if doc:
            obj = doc_to_obj(doc)
            return obj.serialize()

    def _get_raw_from_id_data(self, obj_key, gramps_id):
        table = KEY_TO_NAME_MAP[obj_key]
        doc = self.db[table].find_one({"gramps_id": gramps_id})
        if doc:
            obj = doc_to_obj(doc)
            return obj.serialize()

    def get_gender_stats(self):
        """
        Returns a dictionary of
        {given_name: (male_count, female_count, unknown_count)}
        """
        gstats = {}
        cursor = self.db.gender_stats.find()
        for doc in cursor:
            gstats[doc["given_name"]] = (doc["male"],
                                         doc["female"],
                                         doc["unknown"])
        return gstats

    def save_gender_stats(self, gstats):
        self.db.gender_stats.delete_many({})
        for key in gstats.stats:
            female, male, unknown = gstats.stats[key]
            self.db.gender_stats.insert_one({"given_name": key,
                                             "male": male,
                                             "female": female,
                                             "unknown": unknown})

    def get_surname_list(self):
        """
        Return the list of locale-sorted surnames contained in the database.
        """
        return self.db.person.distinct("primary_name.surname_list.surname")

    def undo_reference(self, data, handle):
        """
        Helper method to undo a reference map entry
        """
        if data is None:
            self.db.reference.delete_one({"obj_handle": handle[0],
                                          "ref_handle": handle[1]})
        else:
            self.db.reference.insert_one({"obj_handle": data[0],
                                          "obj_class": data[1],
                                          "ref_handle": data[2],
                                          "ref_class": data[3]})

    def undo_data(self, data, handle, obj_key):
        """
        Helper method to undo/redo the changes made
        """
        cls = KEY_TO_CLASS_MAP[obj_key]
        table = cls.lower()
        if data is None:
            self.db[table].delete_one({"_id": handle})
        else:
            obj = self._get_table_func(cls)["class_func"].create(data)
            doc = obj_to_doc(obj)
            self.db[table].replace_one({"_id": handle}, doc, upsert=True)
