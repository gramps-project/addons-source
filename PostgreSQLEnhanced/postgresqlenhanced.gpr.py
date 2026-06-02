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

register(
    DATABASE,
    id="postgresqlenhanced",
    name=_("PostgreSQL Enhanced"),
    name_accell=_("PostgreSQL _Enhanced Database"),
    description=_(
        "Advanced PostgreSQL backend with JSONB storage, "
        "graph database support (Apache AGE), vector similarity (pgvector), "
        "and AI/ML capabilities. For advanced users. "
        "Requires PostgreSQL 15+ with extensions. Gramps Web compatible."
    ),
    version = '1.5.5',
    gramps_target_version="6.1",
    status=STABLE,
    audience=EXPERT,  # For advanced users who can configure PostgreSQL
    fname="postgresqlenhanced.py",
    databaseclass="PostgreSQLEnhanced",
    authors=["Greg Lamberson"],
    authors_email=["lamberson@yahoo.com"],
    maintainers=["Greg Lamberson"],
    maintainers_email=["lamberson@yahoo.com"],
    requires_mod=['psycopg'],  # psycopg3 (checks before installation)
    requires_exe=[],  # No external executables required
    depends_on=[],  # No dependencies on other Gramps plugins
    help_url="https://github.com/gramps-project/addons-source/wiki/PostgreSQLEnhanced",
    # Note: features attribute may not be supported in all Gramps versions
    # Capabilities: monolithic-mode, separate-mode, grampsweb-compatible, jsonb-storage
)
