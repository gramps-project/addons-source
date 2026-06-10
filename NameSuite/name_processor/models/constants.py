#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Dmitry Bryndin
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
Constants for the services layer (business logic).
"""

# Severity level constants
SEVERITY_ERROR = "ERROR"
SEVERITY_WARNING = "WARNING"
SEVERITY_INFO = "INFO"

# Locale constants
LOCALE_RU = "ru"
LOCALE_UK = "uk"
LOCALE_BE = "be"
LOCALE_UNIVERSAL = "*"
LOCALE_EAST_SLAVIC = {LOCALE_RU, LOCALE_UK, LOCALE_BE}

# Historical year constants
REFORM_YEAR = 1918
DEFAULT_DB_MEDIAN_YEAR = 1920

# Reference source constants
REF_SOURCE_LATEST_EVENT = "LATEST_EVENT"
REF_SOURCE_GRAPH_BFS = "GRAPH_BFS"
REF_SOURCE_DB_MEDIAN_FALLBACK = "DB_MEDIAN"
