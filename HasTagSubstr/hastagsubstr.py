#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025  Doug Blank <doug.blank@gmail.com>
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
"""Filter rules to match objects with a tag whose name contains a substring."""

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules import Rule
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

# -------------------------------------------------------------------------
#
# Typing modules
#
# -------------------------------------------------------------------------
from typing import Set
from gramps.gen.lib.primaryobj import PrimaryObject
from gramps.gen.db import Database
from gramps.gen.types import PrimaryObjectHandle


# -------------------------------------------------------------------------
#
# HasTagSubstrBase
#
# -------------------------------------------------------------------------
class HasTagSubstrBase(Rule):
    """Rule that matches objects with a tag whose name contains a substring."""

    labels = [_("Substring:")]
    name = "Objects with a tag containing <substring>"
    description = "Matches objects with a tag whose name contains the given substring"
    category = _("General filters")
    namespace = ""

    def prepare(self, db: Database, user) -> None:
        """Build the set of matching object handles once, before filtering begins.

        Scans all tags for names containing the substring, then uses backlinks
        to collect the handles of every object in this namespace that carries
        at least one of those tags.  The optimizer sees self.selected_handles
        and skips apply_to_one entirely for handles not in the set.
        """
        substring = self.list[0].upper()
        self.selected_handles: Set[PrimaryObjectHandle] = set()
        for tag_handle in db.get_tag_handles():
            tag = db.get_tag_from_handle(tag_handle)
            if tag is not None and substring in tag.get_name().upper():
                for _classname, obj_handle in db.find_backlink_handles(
                    tag_handle, include_classes=[self.namespace]
                ):
                    self.selected_handles.add(obj_handle)

    def apply_to_one(self, db: Database, obj: PrimaryObject) -> bool:
        """Return True if this object's handle is in the pre-built match set."""
        return obj.handle in self.selected_handles


# -------------------------------------------------------------------------
#
# Per-namespace subclasses
#
# -------------------------------------------------------------------------
class PersonHasTagSubstr(HasTagSubstrBase):
    """Matches people with a tag whose name contains a substring."""

    labels = [_("Substring:")]
    name = _("People with a tag containing <substring>")
    description = _("Matches people with a tag whose name contains the given substring")
    namespace = "Person"


class FamilyHasTagSubstr(HasTagSubstrBase):
    """Matches families with a tag whose name contains a substring."""

    labels = [_("Substring:")]
    name = _("Families with a tag containing <substring>")
    description = _(
        "Matches families with a tag whose name contains the given substring"
    )
    namespace = "Family"


class EventHasTagSubstr(HasTagSubstrBase):
    """Matches events with a tag whose name contains a substring."""

    labels = [_("Substring:")]
    name = _("Events with a tag containing <substring>")
    description = _(
        "Matches events with a tag whose name contains the given substring"
    )
    namespace = "Event"


class PlaceHasTagSubstr(HasTagSubstrBase):
    """Matches places with a tag whose name contains a substring."""

    labels = [_("Substring:")]
    name = _("Places with a tag containing <substring>")
    description = _(
        "Matches places with a tag whose name contains the given substring"
    )
    namespace = "Place"


class SourceHasTagSubstr(HasTagSubstrBase):
    """Matches sources with a tag whose name contains a substring."""

    labels = [_("Substring:")]
    name = _("Sources with a tag containing <substring>")
    description = _(
        "Matches sources with a tag whose name contains the given substring"
    )
    namespace = "Source"


class CitationHasTagSubstr(HasTagSubstrBase):
    """Matches citations with a tag whose name contains a substring."""

    labels = [_("Substring:")]
    name = _("Citations with a tag containing <substring>")
    description = _(
        "Matches citations with a tag whose name contains the given substring"
    )
    namespace = "Citation"


class RepositoryHasTagSubstr(HasTagSubstrBase):
    """Matches repositories with a tag whose name contains a substring."""

    labels = [_("Substring:")]
    name = _("Repositories with a tag containing <substring>")
    description = _(
        "Matches repositories with a tag whose name contains the given substring"
    )
    namespace = "Repository"


class MediaHasTagSubstr(HasTagSubstrBase):
    """Matches media objects with a tag whose name contains a substring."""

    labels = [_("Substring:")]
    name = _("Media objects with a tag containing <substring>")
    description = _(
        "Matches media objects with a tag whose name contains the given substring"
    )
    namespace = "Media"


class NoteHasTagSubstr(HasTagSubstrBase):
    """Matches notes with a tag whose name contains a substring."""

    labels = [_("Substring:")]
    name = _("Notes with a tag containing <substring>")
    description = _(
        "Matches notes with a tag whose name contains the given substring"
    )
    namespace = "Note"
