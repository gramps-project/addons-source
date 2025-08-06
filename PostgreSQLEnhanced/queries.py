#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025       Greg Lamberson
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#

"""
Enhanced query implementations for PostgreSQL Enhanced

Provides advanced genealogical queries that are not possible
with blob-only storage.
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
import logging
from collections import defaultdict

# -------------------------------------------------------------------------
#
# PostgreSQL modules
#
# -------------------------------------------------------------------------
from psycopg import sql
from psycopg.rows import dict_row

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# -------------------------------------------------------------------------
#
# EnhancedQueries class
#
# -------------------------------------------------------------------------
class EnhancedQueries:
    """
    Advanced query implementations using PostgreSQL features.

    These queries leverage JSONB, recursive CTEs, and other
    PostgreSQL features for complex genealogical analysis.
    """

    def __init__(self, connection):
        """
        Initialize enhanced queries.

        :param connection: PostgreSQLConnection instance
        :type connection: PostgreSQLConnection
        """
        self.conn = connection
        self.log = logging.getLogger(".PostgreSQLEnhanced.Queries")

    def find_common_ancestors(self, handle1, handle2, max_generations=20):
        """
        Find common ancestors between two people.

        Uses recursive CTEs to traverse ancestry efficiently.

        :param handle1: First person's handle
        :type handle1: str
        :param handle2: Second person's handle
        :type handle2: str
        :param max_generations: Maximum generations to search
        :type max_generations: int
        :returns: List of (ancestor_handle, gen1, gen2) tuples
        :rtype: list
        """
        query = """
        WITH RECURSIVE
        -- Ancestors of person 1
        ancestors1 AS (
            SELECT handle, 0 as generation
            FROM person WHERE handle = %s

            UNION ALL

            SELECT DISTINCT p.handle, a.generation + 1
            FROM ancestors1 a
            JOIN person p ON p.handle IN (
                SELECT parent_handle
                FROM family f, jsonb_array_elements_text(f.json_data->'child_ref_list') child
                WHERE child = a.handle
                AND parent_handle IN (
                    SELECT jsonb_array_elements_text(f.json_data->'parent_handles')
                )
            )
            WHERE a.generation < %s
        ),
        -- Ancestors of person 2
        ancestors2 AS (
            SELECT handle, 0 as generation
            FROM person WHERE handle = %s

            UNION ALL

            SELECT DISTINCT p.handle, a.generation + 1
            FROM ancestors2 a
            JOIN person p ON p.handle IN (
                SELECT parent_handle
                FROM family f, jsonb_array_elements_text(f.json_data->'child_ref_list') child
                WHERE child = a.handle
                AND parent_handle IN (
                    SELECT jsonb_array_elements_text(f.json_data->'parent_handles')
                )
            )
            WHERE a.generation < %s
        )
        -- Find common ancestors
        SELECT
            a1.handle,
            a1.generation as gen_from_person1,
            a2.generation as gen_from_person2,
            p.json_data->>'gramps_id' as gramps_id,
            p.json_data->'names'->0->>'first_name' as first_name,
            p.json_data->'names'->0->>'surname' as surname
        FROM ancestors1 a1
        JOIN ancestors2 a2 ON a1.handle = a2.handle
        JOIN person p ON p.handle = a1.handle
        ORDER BY a1.generation + a2.generation, a1.handle
        """

        self.conn.execute(query, [handle1, max_generations, handle2, max_generations])
        return self.conn.fetchall()

    def find_relationship_path(self, handle1, handle2, max_depth=15):
        """
        Find the shortest relationship path between two people.

        Uses bidirectional search with PostgreSQL graph traversal.

        :param handle1: Start person's handle
        :type handle1: str
        :param handle2: End person's handle
        :type handle2: str
        :param max_depth: Maximum relationship depth to search
        :type max_depth: int
        :returns: List of handles forming the path, or None
        :rtype: list or None
        """
        # This is a simplified version - a full implementation would
        # use more sophisticated graph algorithms

        query = """
        WITH RECURSIVE relationship_graph AS (
            -- Start from person 1
            SELECT
                handle,
                ARRAY[handle] as path,
                0 as depth,
                false as found
            FROM person
            WHERE handle = %s

            UNION ALL

            SELECT DISTINCT
                CASE
                    WHEN f.json_data->'parent_handles' ? r.handle THEN child
                    ELSE parent
                END as handle,
                r.path || CASE
                    WHEN f.json_data->'parent_handles' ? r.handle THEN child
                    ELSE parent
                END as path,
                r.depth + 1,
                CASE
                    WHEN f.json_data->'parent_handles' ? r.handle THEN child = %s
                    ELSE parent = %s
                END as found
            FROM relationship_graph r
            JOIN family f ON (
                f.json_data->'parent_handles' ? r.handle OR
                f.json_data->'child_ref_list' ? r.handle
            ),
            LATERAL (
                SELECT jsonb_array_elements_text(f.json_data->'parent_handles') as parent
            ) parents,
            LATERAL (
                SELECT jsonb_array_elements_text(f.json_data->'child_ref_list') as child
            ) children
            WHERE r.depth < %s
            AND NOT r.found
            AND NOT (r.path @> ARRAY[CASE
                WHEN f.json_data->'parent_handles' ? r.handle THEN child
                ELSE parent
            END])
        )
        SELECT path
        FROM relationship_graph
        WHERE found = true
        ORDER BY depth
        LIMIT 1
        """

        self.conn.execute(query, [handle1, handle2, handle2, max_depth])
        result = self.conn.fetchone()
        return result[0] if result else None

    def search_all_text(self, search_term, limit=100):
        """
        Full-text search across all text fields in the database.

        Searches in:
        - Person names and attributes
        - Event descriptions
        - Place names
        - Source titles and text
        - All notes

        :param search_term: Text to search for
        :param limit: Maximum results to return
        :return: List of (object_type, handle, context) tuples
        """
        results = []

        # Search in person names
        query = """
        SELECT 'person' as obj_type, handle,
               json_data->>'gramps_id' as gramps_id,
               jsonb_pretty(json_data->'names') as context
        FROM person
        WHERE json_data::text ILIKE %s
        LIMIT %s
        """
        search_pattern = "%%s%" % search_term
        self.conn.execute(query, [search_pattern, limit])
        results.extend(self.conn.fetchall())

        # Search in notes
        query = """
        SELECT 'note' as obj_type, handle,
               json_data->>'gramps_id' as gramps_id,
               substring(json_data->>'text', 1, 200) as context
        FROM note
        WHERE json_data->>'text' ILIKE %s
        LIMIT %s
        """
        self.conn.execute(query, [search_pattern, limit - len(results)])
        results.extend(self.conn.fetchall())

        # Search in events
        query = """
        SELECT 'event' as obj_type, handle,
               json_data->>'gramps_id' as gramps_id,
               json_data->>'description' as context
        FROM event
        WHERE json_data->>'description' ILIKE %s
        LIMIT %s
        """
        self.conn.execute(query, [search_pattern, limit - len(results)])
        results.extend(self.conn.fetchall())

        return results[:limit]

    def get_descendants_tree(self, person_handle, max_depth=None):
        """
        Get complete descendants tree for a person.

        :param person_handle: Root person's handle
        :param max_depth: Maximum generations to retrieve
        :return: Hierarchical structure of descendants
        """
        if max_depth is None:
            max_depth = 99

        query = """
        WITH RECURSIVE descendants AS (
            -- Root person
            SELECT
                p.handle,
                p.json_data,
                0 as generation,
                ARRAY[p.handle] as path
            FROM person p
            WHERE p.handle = %s

            UNION ALL

            -- Children
            SELECT
                p.handle,
                p.json_data,
                d.generation + 1,
                d.path || p.handle
            FROM descendants d
            JOIN family f ON f.json_data->'parent_handles' ? d.handle
            JOIN person p ON p.handle IN (
                SELECT jsonb_array_elements_text(f.json_data->'child_ref_list')
            )
            WHERE d.generation < %s
        )
        SELECT
            handle,
            generation,
            path,
            json_data->>'gramps_id' as gramps_id,
            json_data->'names'->0->>'first_name' as first_name,
            json_data->'names'->0->>'surname' as surname,
            json_data->'birth_ref_index'->>'date' as birth_date,
            json_data->'death_ref_index'->>'date' as death_date
        FROM descendants
        ORDER BY generation, path
        """

        self.conn.execute(query, [person_handle, max_depth])

        # Build tree structure
        tree = {"handle": person_handle, "children": []}
        nodes = {person_handle: tree}

        for row in self.conn.fetchall():
            if row[0] != person_handle:  # Skip root
                parent_handle = row[2][-2] if len(row[2]) > 1 else person_handle
                node = {
                    "handle": row[0],
                    "gramps_id": row[3],
                    "name": "%s {row[5] or ''}" % row[4] or ''.strip(),
                    "birth_date": row[6],
                    "death_date": row[7],
                    "generation": row[1],
                    "children": [],
                }
                nodes[row[0]] = node
                if parent_handle in nodes:
                    nodes[parent_handle]["children"].append(node)

        return tree

    def find_potential_duplicates(self, threshold=0.8):
        """
        Find potential duplicate persons using name similarity.

        Requires pg_trgm extension for trigram similarity.

        :param threshold: Similarity threshold (0.0 to 1.0)
        :return: List of potential duplicate pairs
        """
        # Check if pg_trgm is available
        self.conn.execute(
            """
            SELECT COUNT(*) FROM pg_extension WHERE extname = 'pg_trgm'
        """
        )
        if self.conn.fetchone()[0] == 0:
            raise RuntimeError(_("pg_trgm extension required for duplicate detection"))

        query = """
        SELECT
            p1.handle as handle1,
            p2.handle as handle2,
            p1.json_data->>'gramps_id' as id1,
            p2.json_data->>'gramps_id' as id2,
            p1.json_data->'names'->0->>'first_name' as first1,
            p1.json_data->'names'->0->>'surname' as surname1,
            p2.json_data->'names'->0->>'first_name' as first2,
            p2.json_data->'names'->0->>'surname' as surname2,
            similarity(
                p1.json_data->'names'->0->>'first_name' || ' ' ||
                p1.json_data->'names'->0->>'surname',
                p2.json_data->'names'->0->>'first_name' || ' ' ||
                p2.json_data->'names'->0->>'surname'
            ) as name_similarity
        FROM person p1
        JOIN person p2 ON p1.handle < p2.handle
        WHERE similarity(
            p1.json_data->'names'->0->>'first_name' || ' ' ||
            p1.json_data->'names'->0->>'surname',
            p2.json_data->'names'->0->>'first_name' || ' ' ||
            p2.json_data->'names'->0->>'surname'
        ) > %s
        ORDER BY name_similarity DESC
        """

        self.conn.execute(query, [threshold])
        return self.conn.fetchall()

    def get_statistics(self):
        """
        Get detailed database statistics.

        :return: Dictionary of statistics
        """
        stats = {}

        # Basic counts
        for obj_type in [
            "person",
            "family",
            "event",
            "place",
            "source",
            "citation",
            "media",
            "repository",
            "note",
            "tag",
        ]:
            self.conn.execute("SELECT COUNT(*) FROM %s" % obj_type)
            stats["%s_count" % obj_type] = self.conn.fetchone()[0]

        # Gender distribution
        self.conn.execute(
            """
            SELECT
                json_data->>'gender' as gender,
                COUNT(*) as count
            FROM person
            WHERE json_data->>'gender' IS NOT NULL
            GROUP BY json_data->>'gender'
        """
        )
        stats["gender_distribution"] = dict(self.conn.fetchall())

        # Century distribution
        self.conn.execute(
            """
            SELECT
                SUBSTRING(json_data->'birth_ref_index'->>'date', 1, 2) || '00' as century,
                COUNT(*) as count
            FROM person
            WHERE json_data->'birth_ref_index'->>'date' ~ '^\\d{4}'
            GROUP BY century
            ORDER BY century
        """
        )
        stats["birth_centuries"] = dict(self.conn.fetchall())

        # Most common surnames
        self.conn.execute(
            """
            SELECT
                json_data->'names'->0->>'surname' as surname,
                COUNT(*) as count
            FROM person
            WHERE json_data->'names'->0->>'surname' IS NOT NULL
            GROUP BY surname
            ORDER BY count DESC
            LIMIT 10
        """
        )
        stats["top_surnames"] = self.conn.fetchall()

        # Average family size
        self.conn.execute(
            """
            SELECT
                AVG(jsonb_array_length(json_data->'child_ref_list')) as avg_children
            FROM family
            WHERE json_data->'child_ref_list' IS NOT NULL
        """
        )
        result = self.conn.fetchone()
        stats["avg_children_per_family"] = float(result[0]) if result[0] else 0

        return stats
