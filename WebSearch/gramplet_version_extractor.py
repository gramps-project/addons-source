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
Extracts the version string from the WebSearch Gramplet .gpr.py file.
"""

import re
import os


# pylint: disable=too-few-public-methods
class GrampletVersionExtractor:
    """Extracts the version of the WebSearch Gramplet from the current directory."""

    def __init__(self):
        """Initializes the extractor with the default Gramplet file name."""
        self.file_name = "WebSearch.gpr.py"
        self.file_path = os.path.join(os.path.dirname(__file__), self.file_name)

    def get(self):
        """Extracts the version from the WebSearch Gramplet file."""
        if not os.path.isfile(self.file_path):
            return f"File '{self.file_name}' not found in the current directory."

        try:
            with open(self.file_path, "r", encoding="utf-8") as file:
                content = file.read()

            match = re.search(r'version\s*=\s*"(.*?)"', content)
            if match:
                return match.group(1)
            return "Version not found"
        except Exception as e:  # pylint: disable=broad-exception-caught
            return f"Error reading file: {e}"
