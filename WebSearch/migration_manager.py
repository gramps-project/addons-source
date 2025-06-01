#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Yurii Liubymyi <jurchello@gmail.com>
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

# ----------------------------------------------------------------------------

"""
MigrationManager module.

This module provides functionality for managing database migrations.
It loads and applies pending migration files, and tracks applied migrations
using a simple DBFileTable storage.
"""

import os
import importlib.util

from db_file_table import DBFileTable
from models import DBFileTableConfig
from constants import MIGRATIONS_DIR, DBFileTables


class MigrationManager:
    """Handles running pending database migrations using DBFileTable."""

    def __init__(self):
        """Initialize the MigrationManager."""
        if not os.path.exists(MIGRATIONS_DIR):
            os.makedirs(MIGRATIONS_DIR)
        self.db_file_table = DBFileTable(
            DBFileTableConfig(
                filename=DBFileTables.MIGRATIONS.value,
                cache_fields=None,
                unique_fields=["migration_name"],
                required_fields=["migration_name"],
            )
        )
        self.applied_migrations = self._load_applied_migrations()

    def _load_applied_migrations(self):
        """Return the list of applied migration names."""
        records = self.db_file_table.all()
        return [record["migration_name"] for record in records]

    def migrate(self):
        """Run pending migrations."""

        migration_files = sorted(
            f[:-3]
            for f in os.listdir(MIGRATIONS_DIR)
            if f.endswith(".py") and f != "__init__.py"
        )

        for migration_name in migration_files:
            if migration_name not in self.applied_migrations:
                self._apply_migration(migration_name)

    def _apply_migration(self, migration_name):
        """Apply a single migration."""
        migration_file = os.path.join(MIGRATIONS_DIR, f"{migration_name}.py")
        spec = importlib.util.spec_from_file_location(migration_name, migration_file)
        migration_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration_module)
        migration_module.migrate()
        self.db_file_table.create({"migration_name": migration_name})
        self.applied_migrations.append(migration_name)
