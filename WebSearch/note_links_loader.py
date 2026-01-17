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
Parses and returns URLs from note objects in the Gramps database.
Supports both manually entered URLs and Gramps-internal note links.
"""

from gettext import gettext as _
from gramps.gen.lib import Note

from url_utils import UrlUtils
from constants import SourceTypes
from models import WebsiteEntry


class NoteLinksLoader:
    """Loads URLs from notes and returns them in a unified format for WebSearch."""

    def __init__(self, db):
        """Initializes the loader with a database and compiles the URL pattern."""
        self.db = db
        self.url_regex = UrlUtils.compile_regex()

    def get_links_from_notes(self, obj, nav_type):
        """Returns all URLs found in the notes attached to the given object."""
        links = []
        if hasattr(obj, "get_note_list"):
            for note_handle in obj.get_note_list():
                note_obj = self.get_note_object(note_handle)
                if note_obj:
                    links.extend(self.get_links_from_note_obj(note_obj, nav_type))
        elif isinstance(obj, Note):
            links.extend(self.get_links_from_note_obj(obj, nav_type))
        return links

    def get_links_from_note_obj(self, note_obj, nav_type):
        """Extract links from a single note object."""
        links = []
        parsed_links = self.parse_links_from_text(note_obj.get())
        existing_links = self.get_existing_links(note_obj)

        for url in parsed_links:
            if url not in existing_links:
                link_data = WebsiteEntry(
                    nav_type=nav_type,
                    country_code=None,
                    source_type=SourceTypes.NOTE.value,
                    title=_("Note Link (parsed)"),
                    is_enabled=True,  # pylint: disable=duplicate-code
                    url_pattern=UrlUtils.clean_url(url),
                    comment=None,
                    is_custom_file=False,
                    source_file_path=None,
                )
                links.append(link_data)
                existing_links.add(url)

        for link in note_obj.get_links():
            link_data = self.create_existing_link_data(nav_type, link)
            if link_data:
                links.append(link_data)

        return links

    def parse_links_from_text(self, note_text):
        """Extract URLs from the note text."""
        matches = self.url_regex.findall(note_text)
        return list({UrlUtils.clean_url(url) for url in matches})

    def get_existing_links(self, note_obj):
        """Extract existing URLs from structured Gramps note links."""
        links = set()
        for link in note_obj.get_links():
            if len(link) == 4:
                source, _, _, handle = link
                if source != "gramps":
                    links.add(UrlUtils.clean_url(handle))
        return links

    def get_note_object(self, note_handle):
        """Retrieve the note object from the database."""
        try:
            note_obj = self.db.get_note_from_handle(note_handle)
            return note_obj
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    def create_existing_link_data(self, nav_type, link):
        """Creates structured data for a note's existing link."""
        if len(link) != 4:
            return None

        source, obj_type, sub_type, handle = link
        if not (source and obj_type and sub_type and handle):
            return None

        if source == "gramps":
            url = f"{source}://{obj_type}/{sub_type}/{handle}"
            title = _("Note Link (internal)")
        else:
            url = handle
            title = _("Note Link (external)")

        return WebsiteEntry(
            nav_type=nav_type,
            country_code=None,
            source_type=SourceTypes.NOTE.value,
            title=title,
            is_enabled=True,
            url_pattern=UrlUtils.clean_url(url),
            comment=None,
            is_custom_file=False,
            source_file_path=None,
        )
