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
PostgreSQL concurrency features for PostgreSQL Enhanced

Provides advanced concurrency control features including:
- LISTEN/NOTIFY for real-time multi-user updates
- Advisory locks for concurrent access control
- Transaction isolation levels
- Optimistic concurrency control

All features gracefully fallback when not available.
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
import logging
import time
import threading
from typing import Optional, Dict, Any, Callable, List

# -------------------------------------------------------------------------
#
# PostgreSQL modules
#
# -------------------------------------------------------------------------
try:
    import psycopg
    from psycopg import sql
    PSYCOPG_AVAILABLE = True
except ImportError:
    PSYCOPG_AVAILABLE = False

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


class ConcurrencyError(Exception):
    """Raised when concurrency control operations fail."""
    pass


class PostgreSQLConcurrency:
    """
    PostgreSQL concurrency control features with graceful fallbacks.
    
    Provides advanced concurrency features that are safe to use
    regardless of PostgreSQL version or capabilities.
    """

    def __init__(self, connection):
        """
        Initialize concurrency controller.

        :param connection: PostgreSQL connection instance
        :type connection: PostgreSQLConnection
        """
        self.conn = connection
        self.log = logging.getLogger(".PostgreSQLEnhanced.Concurrency")
        
        # Track capabilities
        self._listen_notify_available = None
        self._advisory_locks_available = None
        self._isolation_levels_available = None
        
        # Track active listeners and locks
        self._active_listeners: Dict[str, Callable] = {}
        self._active_locks: Dict[str, int] = {}
        self._notification_thread: Optional[threading.Thread] = None
        self._stop_notifications = threading.Event()
        
        # Initialize capabilities
        self._check_capabilities()

    def _check_capabilities(self):
        """Check what concurrency features are available."""
        try:
            # Check PostgreSQL version
            self.conn.execute("SELECT version()")
            version_str = self.conn.fetchone()[0]
            
            # LISTEN/NOTIFY available in all modern PostgreSQL versions
            self._listen_notify_available = True
            
            # Advisory locks available in PostgreSQL 8.2+
            self._advisory_locks_available = True
            
            # Isolation levels available in all PostgreSQL versions
            self._isolation_levels_available = True
            
            self.log.debug("Concurrency capabilities: LISTEN/NOTIFY=%s, Advisory Locks=%s, Isolation Levels=%s",
                          self._listen_notify_available, self._advisory_locks_available, self._isolation_levels_available)
            
        except Exception as e:
            self.log.warning(f"Could not check concurrency capabilities: {e}")
            self._listen_notify_available = False
            self._advisory_locks_available = False
            self._isolation_levels_available = False

    # -------------------------------------------------------------------------
    # LISTEN/NOTIFY for real-time updates
    # -------------------------------------------------------------------------

    def setup_listen_notify(self, channels: List[str] = None):
        """
        Set up PostgreSQL LISTEN/NOTIFY for real-time updates.

        :param channels: List of channels to listen on
        :type channels: list[str]
        :returns: Success status
        :rtype: bool
        """
        if not self._listen_notify_available:
            self.log.info("LISTEN/NOTIFY not available - real-time updates disabled")
            return False

        if channels is None:
            channels = ['person_changes', 'family_changes', 'event_changes', 'place_changes']

        try:
            for channel in channels:
                self.conn.execute(f"LISTEN {channel}")
                self.log.debug(f"Listening on channel: {channel}")
            
            # Start notification processing thread if not already running
            if not self._notification_thread or not self._notification_thread.is_alive():
                self._start_notification_thread()
            
            return True
        except Exception as e:
            self.log.warning(f"Failed to set up LISTEN/NOTIFY: {e}")
            return False

    def notify_change(self, obj_type: str, handle: str, change_type: str, payload: Dict[str, Any] = None):
        """
        Notify other clients of changes.

        :param obj_type: Type of object (person, family, etc.)
        :type obj_type: str
        :param handle: Object handle
        :type handle: str
        :param change_type: Type of change (create, update, delete)
        :type change_type: str
        :param payload: Additional data to send
        :type payload: dict
        :returns: Success status
        :rtype: bool
        """
        if not self._listen_notify_available:
            return False

        channel = f"{obj_type}_changes"
        
        # Create notification message
        message_data = {
            'change_type': change_type,
            'handle': handle,
            'timestamp': time.time()
        }
        if payload:
            message_data.update(payload)

        try:
            # PostgreSQL NOTIFY payload is limited to 8000 bytes
            message = str(message_data)[:7900]  # Leave room for safety
            
            self.conn.execute("NOTIFY %s, %s", (channel, message))
            self.log.debug(f"Sent notification: {channel} - {change_type}:{handle}")
            return True
        except Exception as e:
            self.log.warning(f"Failed to send notification: {e}")
            return False

    def add_change_listener(self, obj_type: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Add a listener for object changes.

        :param obj_type: Type of object to listen for
        :type obj_type: str
        :param callback: Function to call when changes occur
        :type callback: callable
        """
        if not self._listen_notify_available:
            self.log.info(f"Cannot add listener for {obj_type} - LISTEN/NOTIFY not available")
            return

        channel = f"{obj_type}_changes"
        self._active_listeners[channel] = callback
        self.log.debug(f"Added change listener for {channel}")

    def remove_change_listener(self, obj_type: str):
        """
        Remove a change listener.

        :param obj_type: Type of object to stop listening for
        :type obj_type: str
        """
        channel = f"{obj_type}_changes"
        if channel in self._active_listeners:
            del self._active_listeners[channel]
            try:
                self.conn.execute(f"UNLISTEN {channel}")
            except Exception as e:
                self.log.debug(f"Error removing listener for {channel}: {e}")

    def _start_notification_thread(self):
        """Start the notification processing thread."""
        if not self._listen_notify_available:
            return

        self._stop_notifications.clear()
        self._notification_thread = threading.Thread(target=self._process_notifications, daemon=True)
        self._notification_thread.start()
        self.log.debug("Notification processing thread started")

    def _process_notifications(self):
        """Process incoming notifications (runs in separate thread)."""
        try:
            while not self._stop_notifications.is_set():
                try:
                    # Check for notifications (non-blocking)
                    if hasattr(self.conn.connection, 'notifies'):
                        self.conn.connection.poll()
                        
                        while self.conn.connection.notifies:
                            notify = self.conn.connection.notifies.popleft()
                            self._handle_notification(notify)
                    
                    # Sleep briefly to avoid busy waiting
                    time.sleep(0.1)
                    
                except Exception as e:
                    self.log.warning(f"Error processing notifications: {e}")
                    time.sleep(1)  # Wait longer after error
                    
        except Exception as e:
            self.log.error(f"Notification thread crashed: {e}")

    def _handle_notification(self, notify):
        """Handle a received notification."""
        try:
            channel = notify.channel
            payload = notify.payload
            
            if channel in self._active_listeners:
                callback = self._active_listeners[channel]
                
                # Parse payload back to dict
                import ast
                try:
                    data = ast.literal_eval(payload)
                except (ValueError, SyntaxError):
                    # Fallback to string payload
                    data = {'message': payload}
                
                # Call listener in thread-safe way
                try:
                    callback(data)
                except Exception as e:
                    self.log.error(f"Error in change listener callback: {e}")
                    
        except Exception as e:
            self.log.warning(f"Error handling notification: {e}")

    def stop_notifications(self):
        """Stop the notification processing thread."""
        self._stop_notifications.set()
        if self._notification_thread and self._notification_thread.is_alive():
            self._notification_thread.join(timeout=2.0)

    # -------------------------------------------------------------------------
    # Advisory Locks for concurrent access control
    # -------------------------------------------------------------------------

    def acquire_object_lock(self, obj_type: str, handle: str, exclusive: bool = True, timeout: float = 5.0) -> bool:
        """
        Acquire advisory lock on object.

        :param obj_type: Type of object
        :type obj_type: str
        :param handle: Object handle
        :type handle: str
        :param exclusive: Whether to acquire exclusive lock
        :type exclusive: bool
        :param timeout: Lock acquisition timeout in seconds
        :type timeout: float
        :returns: True if lock acquired successfully
        :rtype: bool
        """
        if not self._advisory_locks_available:
            self.log.debug(f"Advisory locks not available - allowing access to {obj_type}:{handle}")
            return True

        # Generate consistent lock ID from object type and handle
        lock_key = f"{obj_type}:{handle}"
        lock_id = abs(hash(lock_key)) % (2**31)  # 32-bit signed int
        
        try:
            if exclusive:
                query = "SELECT pg_try_advisory_lock(%s)"
            else:
                query = "SELECT pg_try_advisory_lock_shared(%s)"
            
            start_time = time.time()
            while time.time() - start_time < timeout:
                self.conn.execute(query, (lock_id,))
                result = self.conn.fetchone()
                
                if result and result[0]:
                    self._active_locks[lock_key] = lock_id
                    self.log.debug(f"Acquired {'exclusive' if exclusive else 'shared'} lock on {lock_key}")
                    return True
                
                # Wait briefly before retrying
                time.sleep(0.1)
            
            self.log.warning(f"Failed to acquire lock on {lock_key} within {timeout}s")
            return False
            
        except Exception as e:
            self.log.warning(f"Error acquiring lock on {lock_key}: {e}")
            return False  # Fail safe - allow access

    def release_object_lock(self, obj_type: str, handle: str):
        """
        Release advisory lock on object.

        :param obj_type: Type of object
        :type obj_type: str
        :param handle: Object handle
        :type handle: str
        :returns: Success status
        :rtype: bool
        """
        if not self._advisory_locks_available:
            return True

        lock_key = f"{obj_type}:{handle}"
        
        if lock_key not in self._active_locks:
            self.log.debug(f"No active lock found for {lock_key}")
            return True

        try:
            lock_id = self._active_locks[lock_key]
            self.conn.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))
            
            del self._active_locks[lock_key]
            self.log.debug(f"Released lock on {lock_key}")
            return True
            
        except Exception as e:
            self.log.warning(f"Error releasing lock on {lock_key}: {e}")
            return False

    def release_all_locks(self):
        """Release all advisory locks held by this session."""
        if not self._advisory_locks_available:
            return

        try:
            self.conn.execute("SELECT pg_advisory_unlock_all()")
            self._active_locks.clear()
            self.log.debug("Released all advisory locks")
        except Exception as e:
            self.log.warning(f"Error releasing all locks: {e}")

    # -------------------------------------------------------------------------
    # Transaction Isolation Levels
    # -------------------------------------------------------------------------

    def begin_transaction(self, isolation_level: str = 'READ_COMMITTED'):
        """
        Begin transaction with specific isolation level.

        :param isolation_level: Isolation level to use
        :type isolation_level: str
        :returns: Success status
        :rtype: bool
        """
        if not self._isolation_levels_available:
            self.log.debug("Isolation levels not available - using default transaction")
            try:
                self.conn.execute("BEGIN")
                return True
            except Exception:
                return False

        valid_levels = ['READ_UNCOMMITTED', 'READ_COMMITTED', 'REPEATABLE_READ', 'SERIALIZABLE']
        if isolation_level not in valid_levels:
            self.log.warning(f"Invalid isolation level {isolation_level}, using READ_COMMITTED")
            isolation_level = 'READ_COMMITTED'

        try:
            self.conn.execute("BEGIN")
            self.conn.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}")
            self.log.debug(f"Started transaction with isolation level {isolation_level}")
            return True
        except Exception as e:
            self.log.warning(f"Failed to set isolation level {isolation_level}: {e}")
            try:
                # Fallback to basic transaction
                self.conn.execute("BEGIN")
                return True
            except Exception:
                return False

    # -------------------------------------------------------------------------
    # Optimistic Concurrency Control
    # -------------------------------------------------------------------------

    def get_object_version(self, obj_type: str, handle: str) -> Optional[float]:
        """
        Get the current version/timestamp of an object.

        :param obj_type: Type of object
        :type obj_type: str
        :param handle: Object handle
        :type handle: str
        :returns: Version timestamp or None if not found
        :rtype: float or None
        """
        try:
            # Try to get change_time from object data
            table_name = obj_type  # Assuming table name matches object type
            
            query = f"SELECT change_time FROM {table_name} WHERE handle = %s"
            self.conn.execute(query, (handle,))
            result = self.conn.fetchone()
            
            return float(result[0]) if result else None
            
        except Exception as e:
            self.log.debug(f"Could not get version for {obj_type}:{handle}: {e}")
            return None

    def check_object_version(self, obj_type: str, handle: str, expected_version: float):
        """
        Check if object has been modified since expected version.

        :param obj_type: Type of object
        :type obj_type: str
        :param handle: Object handle
        :type handle: str
        :param expected_version: Expected version timestamp
        :type expected_version: float
        :raises ConcurrencyError: If object was modified by another user
        """
        current_version = self.get_object_version(obj_type, handle)
        
        if current_version is None:
            # Object doesn't exist or version check not available
            return
        
        if abs(current_version - expected_version) > 0.001:  # Allow small floating point differences
            raise ConcurrencyError(
                _("Object {obj_type}:{handle} was modified by another user")
                .format(obj_type=obj_type, handle=handle)
            )

    # -------------------------------------------------------------------------
    # Context managers for safe resource management
    # -------------------------------------------------------------------------

    class ObjectLock:
        """Context manager for object locks."""
        
        def __init__(self, concurrency, obj_type: str, handle: str, exclusive: bool = True, timeout: float = 5.0):
            self.concurrency = concurrency
            self.obj_type = obj_type
            self.handle = handle
            self.exclusive = exclusive
            self.timeout = timeout
            self.acquired = False

        def __enter__(self):
            self.acquired = self.concurrency.acquire_object_lock(
                self.obj_type, self.handle, self.exclusive, self.timeout
            )
            if not self.acquired:
                raise ConcurrencyError(f"Could not acquire lock on {self.obj_type}:{self.handle}")
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.acquired:
                self.concurrency.release_object_lock(self.obj_type, self.handle)

    def object_lock(self, obj_type: str, handle: str, exclusive: bool = True, timeout: float = 5.0):
        """
        Create a context manager for object locking.

        :param obj_type: Type of object
        :param handle: Object handle  
        :param exclusive: Whether to acquire exclusive lock
        :param timeout: Lock acquisition timeout
        :returns: Context manager for the lock
        """
        return self.ObjectLock(self, obj_type, handle, exclusive, timeout)

    def __del__(self):
        """Cleanup when object is destroyed."""
        try:
            self.stop_notifications()
            self.release_all_locks()
        except Exception:
            pass  # Ignore cleanup errors