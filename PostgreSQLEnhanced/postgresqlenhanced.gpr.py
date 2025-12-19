#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Greg Lamberson
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
PostgreSQL Enhanced Database Backend Registration
"""

import importlib

from gramps.gen.plug._pluginreg import register, STABLE, DATABASE, DEVELOPER
from gramps.gen.const import GRAMPS_LOCALE as glocale

_ = glocale.translation.gettext

# Check for psycopg3 availability before registering
try:
    import importlib.util

    PSYCOPG_AVAILABLE = importlib.util.find_spec("psycopg") is not None
except (ImportError, ValueError, AttributeError):
    PSYCOPG_AVAILABLE = False

# Only register if dependency available or building addon
if PSYCOPG_AVAILABLE or locals().get("build_script"):
    # Register Monolithic mode - all trees share one database
    register(
        DATABASE,
        id="postgresqlenhanced-monolithic",
        name=_("PostgreSQL Enhanced (Monolithic)"),
        name_accell=_("PostgreSQL Enhanced (_Monolithic)"),
        description=_(
            "PostgreSQL backend with all trees in shared database. "
            "Recommended for most users. Uses table prefixes for multi-tree support. "
            "Requires PostgreSQL 15+ and psycopg 3+."
        ),
        version = '1.7.3',
        gramps_target_version="6.0",
        status=STABLE,
        fname="postgresqlenhanced.py",
        databaseclass="PostgreSQLEnhancedMonolithic",
        authors=["Greg Lamberson"],
        authors_email=["lamberson@yahoo.com"],
        maintainers=["Greg Lamberson"],
        maintainers_email=["lamberson@yahoo.com"],
        help_url="https://github.com/glamberson/gramps-postgresql-enhanced",
    )

    # Register Separate mode - one database per tree
    register(
        DATABASE,
        id="postgresqlenhanced-separate",
        name=_("PostgreSQL Enhanced (Separate)"),
        name_accell=_("PostgreSQL Enhanced (_Separate)"),
        description=_(
            "PostgreSQL backend with individual database per tree. "
            "For advanced users requiring complete tree isolation. "
            "Requires PostgreSQL 15+ with CREATEDB privilege and psycopg 3+."
        ),
        version = '1.7.3',
        gramps_target_version="6.0",
        status=STABLE,
        fname="postgresqlenhanced.py",
        databaseclass="PostgreSQLEnhancedSeparate",
        authors=["Greg Lamberson"],
        authors_email=["lamberson@yahoo.com"],
        maintainers=["Greg Lamberson"],
        maintainers_email=["lamberson@yahoo.com"],
        help_url="https://github.com/glamberson/gramps-postgresql-enhanced",
    )
