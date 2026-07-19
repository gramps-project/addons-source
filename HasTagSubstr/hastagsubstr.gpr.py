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

register(
    RULE,
    id="PersonHasTagSubstr",
    name=_("People with a tag containing <substring>"),
    description=_("Matches people with a tag whose name contains the given substring"),
    version = '1.0.2',
    authors=["Doug Blank"],
    authors_email=["doug.blank@gmail.com"],
    gramps_target_version="6.0",
    status=STABLE,
    fname="hastagsubstr.py",
    ruleclass="PersonHasTagSubstr",
    namespace="Person",
)

register(
    RULE,
    id="FamilyHasTagSubstr",
    name=_("Families with a tag containing <substring>"),
    description=_(
        "Matches families with a tag whose name contains the given substring"
    ),
    version = '1.0.2',
    authors=["Doug Blank"],
    authors_email=["doug.blank@gmail.com"],
    gramps_target_version="6.0",
    status=STABLE,
    fname="hastagsubstr.py",
    ruleclass="FamilyHasTagSubstr",
    namespace="Family",
)

register(
    RULE,
    id="EventHasTagSubstr",
    name=_("Events with a tag containing <substring>"),
    description=_(
        "Matches events with a tag whose name contains the given substring"
    ),
    version = '1.0.2',
    authors=["Doug Blank"],
    authors_email=["doug.blank@gmail.com"],
    gramps_target_version="6.0",
    status=STABLE,
    fname="hastagsubstr.py",
    ruleclass="EventHasTagSubstr",
    namespace="Event",
)

register(
    RULE,
    id="PlaceHasTagSubstr",
    name=_("Places with a tag containing <substring>"),
    description=_(
        "Matches places with a tag whose name contains the given substring"
    ),
    version = '1.0.2',
    authors=["Doug Blank"],
    authors_email=["doug.blank@gmail.com"],
    gramps_target_version="6.0",
    status=STABLE,
    fname="hastagsubstr.py",
    ruleclass="PlaceHasTagSubstr",
    namespace="Place",
)

register(
    RULE,
    id="SourceHasTagSubstr",
    name=_("Sources with a tag containing <substring>"),
    description=_(
        "Matches sources with a tag whose name contains the given substring"
    ),
    version = '1.0.2',
    authors=["Doug Blank"],
    authors_email=["doug.blank@gmail.com"],
    gramps_target_version="6.0",
    status=STABLE,
    fname="hastagsubstr.py",
    ruleclass="SourceHasTagSubstr",
    namespace="Source",
)

register(
    RULE,
    id="CitationHasTagSubstr",
    name=_("Citations with a tag containing <substring>"),
    description=_(
        "Matches citations with a tag whose name contains the given substring"
    ),
    version = '1.0.2',
    authors=["Doug Blank"],
    authors_email=["doug.blank@gmail.com"],
    gramps_target_version="6.0",
    status=STABLE,
    fname="hastagsubstr.py",
    ruleclass="CitationHasTagSubstr",
    namespace="Citation",
)

register(
    RULE,
    id="RepositoryHasTagSubstr",
    name=_("Repositories with a tag containing <substring>"),
    description=_(
        "Matches repositories with a tag whose name contains the given substring"
    ),
    version = '1.0.2',
    authors=["Doug Blank"],
    authors_email=["doug.blank@gmail.com"],
    gramps_target_version="6.0",
    status=STABLE,
    fname="hastagsubstr.py",
    ruleclass="RepositoryHasTagSubstr",
    namespace="Repository",
)

register(
    RULE,
    id="MediaHasTagSubstr",
    name=_("Media objects with a tag containing <substring>"),
    description=_(
        "Matches media objects with a tag whose name contains the given substring"
    ),
    version = '1.0.2',
    authors=["Doug Blank"],
    authors_email=["doug.blank@gmail.com"],
    gramps_target_version="6.0",
    status=STABLE,
    fname="hastagsubstr.py",
    ruleclass="MediaHasTagSubstr",
    namespace="Media",
)

register(
    RULE,
    id="NoteHasTagSubstr",
    name=_("Notes with a tag containing <substring>"),
    description=_(
        "Matches notes with a tag whose name contains the given substring"
    ),
    version = '1.0.2',
    authors=["Doug Blank"],
    authors_email=["doug.blank@gmail.com"],
    gramps_target_version="6.0",
    status=STABLE,
    fname="hastagsubstr.py",
    ruleclass="NoteHasTagSubstr",
    namespace="Note",
)
