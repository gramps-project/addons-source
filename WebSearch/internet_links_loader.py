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

"""Extracts and formats links from the 'Internet' tab of Gramps objects."""

from url_utils import UrlUtils
from constants import SourceTypes
from models import WebsiteEntry


# pylint: disable=too-few-public-methods
class InternetLinksLoader:
    """Loader for extracting and formatting URLs from the 'Internet' tab."""

    def __init__(self):
        """Compiles the regular expression for URL detection."""
        self.url_regex = UrlUtils.compile_regex()

    def get_links_from_internet_objects(self, obj, nav_type):
        """Extracts formatted URLs from an object's 'Internet' tab."""
        links = []
        url_list = obj.get_url_list()
        for url_obj in url_list:
            full_path = url_obj.get_full_path()
            url_type = url_obj.get_type()
            title = self.get_url_title(url_type)
            # pylint: disable=duplicate-code
            url = UrlUtils.extract_url(full_path, self.url_regex)
            if url:
                links.append(
                    WebsiteEntry(
                        nav_type=nav_type,
                        country_code=None,
                        source_type=SourceTypes.INTERNET.value,
                        title=(title or "").strip(),
                        is_enabled=True,
                        url_pattern=UrlUtils.clean_url(url),
                        comment=(url_obj.get_description() or "").strip(),
                        is_custom_file=False,
                    )
                )

        return links

    def get_url_title(self, url_type):
        """Returns a cleaned title from the URL type object, or a default title."""
        if url_type:
            raw_title = url_type.xml_str()
            return (raw_title or "No title").strip()
        return "No title"
