# -*- coding: utf-8 -*-
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
