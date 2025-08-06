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

from gramps.gen.plug._pluginreg import register, STABLE, DATABASE, DEVELOPER
from gramps.gen.const import GRAMPS_LOCALE as glocale

_ = glocale.translation.gettext

register(
    DATABASE,
    id="postgresqlenhanced",
    name=_("PostgreSQL Enhanced"),
    name_accell=_("PostgreSQL _Enhanced Database"),
    description=_(
        "EXPERIMENTAL: Advanced PostgreSQL database backend using modern psycopg (v3). "
        "Features dual storage (pickle + JSONB), advanced queries, "
        "and support for large databases. Thoroughly tested but still experimental. "
        "Requires PostgreSQL 15+ and psycopg>=3."
    ),
    version = '0.1.0',
    gramps_target_version="6.0",
    status=STABLE,
    audience=DEVELOPER,
    fname="postgresqlenhanced.py",
    databaseclass="PostgreSQLEnhanced",
    authors=["Greg Lamberson"],
    authors_email=["greg@aigenealogyinsights.com"],
    maintainers=["Greg Lamberson"],
    maintainers_email=["greg@aigenealogyinsights.com"],
    requires_mod=[],  # psycopg3 requirement handled separately
    requires_exe=[],  # No external executables required
    depends_on=[],  # No dependencies on other Gramps plugins
    help_url="https://github.com/gramps-project/addons-source/wiki/PostgreSQLEnhanced",
)
