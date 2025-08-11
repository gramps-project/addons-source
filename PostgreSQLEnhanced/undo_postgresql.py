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
PostgreSQL-native undo implementation for Gramps.

This module provides a database-native undo/redo system that stores
transaction history in PostgreSQL tables instead of files. It's compatible
with both Gramps desktop and GrampsWeb without requiring any GrampsWeb imports.
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
import logging
import os
import pickle
import json
from datetime import datetime

# -------------------------------------------------------------------------
#
# PostgreSQL modules
#
# -------------------------------------------------------------------------
import psycopg
from psycopg import sql

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.db import DbUndo


# -------------------------------------------------------------------------
#
# DbUndoPostgreSQL class
#
# -------------------------------------------------------------------------
class DbUndoPostgreSQL(DbUndo):
    """
    PostgreSQL-native undo implementation.
    
    Stores undo data in PostgreSQL tables instead of files, providing:
    - Full transaction history with timestamps
    - User tracking capability
    - Efficient JSONB storage
    - Compatible with GrampsWeb's get_transactions() method
    - No external dependencies beyond psycopg3
    """
    
    def __init__(self, grampsdb, connection):
        """
        Initialize PostgreSQL undo system.
        
        :param grampsdb: The Gramps database object
        :param connection: PostgreSQL connection object
        """
        super().__init__(grampsdb)
        self.connection = connection
        
        # IMPORTANT: Handle both monolithic and separate modes
        # In monolithic mode, table_prefix is like "tree_6894f36d_"
        # In separate mode, table_prefix is empty ""
        self.table_prefix = getattr(grampsdb, 'table_prefix', '')
        
        # If we have a wrapped connection (TablePrefixWrapper), get the real connection
        if hasattr(connection, '_connection'):
            self.connection = connection._connection
        else:
            self.connection = connection
            
        self.log = logging.getLogger(".PostgreSQLUndo")
        
        # Create undo tables if they don't exist
        self._create_undo_tables()
        
        # Track current transaction
        self.current_trans_id = None
        self.current_trans_changes = []
        
        # Get current user if available
        self.user_id = os.environ.get('USER', 'unknown')
        if 'GRAMPSWEB_USER' in os.environ:
            self.user_id = os.environ['GRAMPSWEB_USER']
    
    def open(self):
        """Open the undo system (tables already created in __init__)."""
        self.log.debug("PostgreSQL undo system opened for %s", self.table_prefix)
    
    def close(self):
        """Close the undo system (commit any pending changes)."""
        if self.current_trans_id:
            self._finalize_transaction()
        self.log.debug("PostgreSQL undo system closed")
    
    def _create_undo_tables(self):
        """Create undo tables if they don't exist."""
        with self.connection.cursor() as cur:
            # Transaction log table
            cur.execute(sql.SQL("""
                CREATE TABLE IF NOT EXISTS {} (
                    trans_id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id TEXT,
                    description TEXT,
                    first_change_id INTEGER,
                    last_change_id INTEGER,
                    is_undo BOOLEAN DEFAULT FALSE
                )
            """).format(sql.Identifier(f"{self.table_prefix}transactions")))
            
            # Individual changes table
            cur.execute(sql.SQL("""
                CREATE TABLE IF NOT EXISTS {} (
                    change_id SERIAL PRIMARY KEY,
                    trans_id INTEGER REFERENCES {}(trans_id) ON DELETE CASCADE,
                    obj_class TEXT,
                    trans_type INTEGER,
                    obj_handle TEXT,
                    ref_handle TEXT,
                    old_data JSONB,
                    new_data JSONB,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """).format(
                sql.Identifier(f"{self.table_prefix}changes"),
                sql.Identifier(f"{self.table_prefix}transactions")
            ))
            
            # Create indexes for performance
            cur.execute(sql.SQL("""
                CREATE INDEX IF NOT EXISTS {} ON {}(trans_id)
            """).format(
                sql.Identifier(f"{self.table_prefix}changes_trans_idx"),
                sql.Identifier(f"{self.table_prefix}changes")
            ))
            
            cur.execute(sql.SQL("""
                CREATE INDEX IF NOT EXISTS {} ON {}(obj_handle)
            """).format(
                sql.Identifier(f"{self.table_prefix}changes_handle_idx"),
                sql.Identifier(f"{self.table_prefix}changes")
            ))
            
            cur.execute(sql.SQL("""
                CREATE INDEX IF NOT EXISTS {} ON {}(timestamp DESC)
            """).format(
                sql.Identifier(f"{self.table_prefix}transactions_ts_idx"),
                sql.Identifier(f"{self.table_prefix}transactions")
            ))
            
            self.connection.commit()
            self.log.debug("Undo tables created/verified for %s", self.table_prefix)
    
    def commit(self, msg=""):
        """
        Commit current transaction with optional message.
        
        :param msg: Description of the transaction
        """
        if self.current_trans_changes:
            self._finalize_transaction(msg)
        
        # Start new transaction
        self._start_transaction(msg)
    
    def _start_transaction(self, description=""):
        """Start a new undo transaction."""
        with self.connection.cursor() as cur:
            cur.execute(sql.SQL("""
                INSERT INTO {} (user_id, description)
                VALUES (%s, %s)
                RETURNING trans_id
            """).format(sql.Identifier(f"{self.table_prefix}transactions")),
            (self.user_id, description))
            
            self.current_trans_id = cur.fetchone()[0]
            self.current_trans_changes = []
            self.connection.commit()
    
    def _finalize_transaction(self, description=""):
        """Finalize the current transaction."""
        if not self.current_trans_id:
            return
        
        # Update transaction with change IDs
        if self.current_trans_changes:
            with self.connection.cursor() as cur:
                cur.execute(sql.SQL("""
                    UPDATE {}
                    SET first_change_id = %s,
                        last_change_id = %s,
                        description = COALESCE(NULLIF(%s, ''), description)
                    WHERE trans_id = %s
                """).format(sql.Identifier(f"{self.table_prefix}transactions")),
                (
                    min(self.current_trans_changes),
                    max(self.current_trans_changes),
                    description,
                    self.current_trans_id
                ))
                self.connection.commit()
        
        self.current_trans_id = None
        self.current_trans_changes = []
    
    def append(self, value):
        """
        Add a change to current transaction.
        
        :param value: Pickled tuple of (obj_type, trans_type, handle, old_data, new_data)
        """
        try:
            # Ensure we have a current transaction
            if not self.current_trans_id:
                self._start_transaction()
            
            # Unpack the change data
            data = pickle.loads(value)
            if len(data) == 5:
                (obj_type, trans_type, handle, old_data, new_data) = data
            else:
                self.log.warning("Unexpected undo data format: %s items", len(data))
                return
            
            # Handle tuple handles (for references)
            if isinstance(handle, tuple):
                obj_handle, ref_handle = handle
            else:
                obj_handle, ref_handle = handle, None
            
            # Store change in database
            with self.connection.cursor() as cur:
                cur.execute(sql.SQL("""
                    INSERT INTO {} 
                    (trans_id, obj_class, trans_type, obj_handle, ref_handle, old_data, new_data)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING change_id
                """).format(sql.Identifier(f"{self.table_prefix}changes")),
                (
                    self.current_trans_id,
                    obj_type,
                    trans_type,
                    obj_handle,
                    ref_handle,
                    json.dumps(self._serialize_for_json(old_data)) if old_data else None,
                    json.dumps(self._serialize_for_json(new_data)) if new_data else None
                ))
                
                change_id = cur.fetchone()[0]
                self.current_trans_changes.append(change_id)
                self.connection.commit()
                
        except Exception as e:
            self.log.error("Error appending undo data: %s", e)
            self.connection.rollback()
    
    def _serialize_for_json(self, data):
        """
        Convert Gramps objects to JSON-serializable format.
        
        :param data: Data to serialize
        :returns: JSON-serializable version of the data
        """
        if data is None:
            return None
        
        # If it's already a dict/list, return as-is
        if isinstance(data, (dict, list, str, int, float, bool)):
            return data
        
        # If it has a serialize method (Gramps objects), use it
        if hasattr(data, 'serialize'):
            return data.serialize()
        
        # For bytes, convert to base64
        if isinstance(data, bytes):
            import base64
            return {'__bytes__': base64.b64encode(data).decode('ascii')}
        
        # For other types, try to convert to string
        return str(data)
    
    def get_transactions(self, page=1, pagesize=20, old_data=False, new_data=False,
                        ascending=False, before=None, after=None):
        """
        Get transaction history with pagination.
        
        This method is compatible with GrampsWeb's expectations but doesn't
        require any GrampsWeb imports.
        
        :param page: Page number (1-based)
        :param pagesize: Number of results per page
        :param old_data: Include old values in results
        :param new_data: Include new values in results
        :param ascending: Sort ascending by timestamp (default descending)
        :param before: Filter transactions before this timestamp
        :param after: Filter transactions after this timestamp
        :returns: (transactions, total_count) tuple
        """
        offset = (page - 1) * pagesize
        
        try:
            with self.connection.cursor() as cur:
                # Build WHERE clause
                where_clauses = []
                params = []
                
                if before:
                    where_clauses.append("timestamp < %s")
                    params.append(datetime.fromtimestamp(before))
                
                if after:
                    where_clauses.append("timestamp > %s")
                    params.append(datetime.fromtimestamp(after))
                
                where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
                
                # Get total count
                cur.execute(sql.SQL("""
                    SELECT COUNT(*) FROM {}
                    WHERE {}
                """).format(
                    sql.Identifier(f"{self.table_prefix}transactions"),
                    sql.SQL(where_sql)
                ), params)
                total_count = cur.fetchone()[0]
                
                # Get paginated results
                order_dir = "ASC" if ascending else "DESC"
                cur.execute(sql.SQL("""
                    SELECT trans_id, timestamp, user_id, description, is_undo
                    FROM {}
                    WHERE {}
                    ORDER BY trans_id {}
                    LIMIT %s OFFSET %s
                """).format(
                    sql.Identifier(f"{self.table_prefix}transactions"),
                    sql.SQL(where_sql),
                    sql.SQL(order_dir)
                ), params + [pagesize, offset])
                
                transactions = []
                for row in cur.fetchall():
                    trans = {
                        'id': row[0],
                        'timestamp': row[1].timestamp() if row[1] else 0,
                        'user_id': row[2] or 'unknown',
                        'description': row[3] or '',
                        'is_undo': row[4] or False
                    }
                    
                    # Get changes for this transaction if data is requested
                    if old_data or new_data:
                        cur.execute(sql.SQL("""
                            SELECT obj_class, trans_type, obj_handle, old_data, new_data
                            FROM {}
                            WHERE trans_id = %s
                            ORDER BY change_id
                        """).format(sql.Identifier(f"{self.table_prefix}changes")),
                        (row[0],))
                        
                        changes = []
                        for change_row in cur.fetchall():
                            change = {
                                'obj_class': change_row[0],
                                'trans_type': change_row[1],
                                'obj_handle': change_row[2]
                            }
                            
                            if old_data and change_row[3]:
                                change['old_data'] = change_row[3]
                            
                            if new_data and change_row[4]:
                                change['new_data'] = change_row[4]
                            
                            changes.append(change)
                        
                        if changes:
                            trans['changes'] = changes
                    
                    transactions.append(trans)
                
                return transactions, total_count
                
        except Exception as e:
            self.log.error("Error getting transactions: %s", e)
            return [], 0
    
    def undo(self, update_history=True):
        """
        Undo the last committed transaction.
        
        :param update_history: Whether to update history
        :returns: True if successful
        """
        # For now, return False as full undo is complex
        # This would need to replay changes in reverse
        self.log.info("Undo requested but not yet implemented in PostgreSQL backend")
        return False
    
    def redo(self, update_history=True):
        """
        Redo the last undone transaction.
        
        :param update_history: Whether to update history
        :returns: True if successful
        """
        # For now, return False as full redo is complex
        self.log.info("Redo requested but not yet implemented in PostgreSQL backend")
        return False
    
    def clean(self):
        """Clean up old transaction data."""
        # Could implement cleanup of old transactions here
        pass