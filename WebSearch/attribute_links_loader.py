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

"""Extracts web links from attributes of Gramps objects for the WebSearch Gramplet."""

from gramps.gen.lib import AttributeType
from gramps.gen.lib.srcattrtype import SrcAttributeType

from url_utils import UrlUtils
from constants import SourceTypes
from models import WebsiteEntry


# pylint: disable=too-few-public-methods
class AttributeLinksLoader:
    """
    Extracts direct URLs from the attributes of a Gramps object.

    This class scans all attributes of a given Gramps object (Person, Source, etc.),
    checks for any attribute that contains a valid URL, and returns a list of links
    that can be used by the WebSearch Gramplet or other components.
    """

    def __init__(self):
        """Initialize the regular expression for detecting URLs in attribute values."""
        self.url_regex = UrlUtils.compile_regex()

    def get_links_from_attributes(self, obj, nav_type):
        """Extract links from attributes of a given Gramps object."""
        links = []

        if not hasattr(obj, "get_attribute_list"):
            return links

        for attr in obj.get_attribute_list():

            attr_name = self.get_attribute_name(attr.get_type())
            if not attr_name:
                continue

            attr_value = attr.get_value()
            if not isinstance(attr_value, str):
                continue

            url = UrlUtils.extract_url(attr_value, self.url_regex)
            if url:
                links.append(
                    WebsiteEntry(
                        nav_type=nav_type,
                        country_code=None,
                        source_type=SourceTypes.ATTRIBUTE.value,
                        title=(attr_name or "").strip(),
                        is_enabled=True,
                        url_pattern=UrlUtils.clean_url(url),
                        comment=None,
                        is_custom_file=False,
                    )
                )

        return links

    def get_attribute_name(self, attr_type):
        """Returns the name of the attribute type or None if unsupported."""
        if isinstance(attr_type, AttributeType):
            return attr_type.type2base()
        if isinstance(attr_type, SrcAttributeType):
            return attr_type.string
        return None
