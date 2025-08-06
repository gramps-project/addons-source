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

"""PostgreSQL Enhanced Database Backend for Gramps"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------

# -------------------------------------------------------------------------
#
# Local modules
#
# -------------------------------------------------------------------------
# Fix relative import for Gramps plugin loading
try:
    from .postgresqlenhanced import PostgreSQLEnhanced
except ImportError:
    # When loaded as a Gramps plugin, relative imports don't work
    import sys
    import os

    plugin_dir = os.path.dirname(__file__)
    if plugin_dir not in sys.path:
        sys.path.insert(0, plugin_dir)
    from postgresqlenhanced import PostgreSQLEnhanced

__all__ = ["PostgreSQLEnhanced"]

__version__ = "1.0.0"
__author__ = "Greg Lamberson"
