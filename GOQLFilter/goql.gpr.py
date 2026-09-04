#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026       Douglas Blank
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

"""Gramplets providing a gramps-object-query-language filter for each
primary object view."""

_HELP = "Addon:GrampsObjectQueryLanguage"
_AUTHORS = ["Douglas Blank"]
_AUTHORS_EMAIL = ["doug.blank@gmail.com"]

register(
    GRAMPLET,
    id="Person GOQL Filter",
    name=_("Person GOQL Filter"),
    description=_("Gramplet providing a gramps-object-query-language person filter"),
    version = '1.0.3',
    gramps_target_version="6.0",
    status=STABLE,
    fname="goql.py",
    height=260,
    gramplet="PersonQueryFilter",
    gramplet_title=_("GOQL Filter"),
    navtypes=["Person"],
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
)

register(
    GRAMPLET,
    id="Family GOQL Filter",
    name=_("Family GOQL Filter"),
    description=_("Gramplet providing a gramps-object-query-language family filter"),
    version = '1.0.3',
    gramps_target_version="6.0",
    status=STABLE,
    fname="goql.py",
    height=260,
    gramplet="FamilyQueryFilter",
    gramplet_title=_("GOQL Filter"),
    navtypes=["Family"],
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
)

register(
    GRAMPLET,
    id="Event GOQL Filter",
    name=_("Event GOQL Filter"),
    description=_("Gramplet providing a gramps-object-query-language event filter"),
    version = '1.0.3',
    gramps_target_version="6.0",
    status=STABLE,
    fname="goql.py",
    height=260,
    gramplet="EventQueryFilter",
    gramplet_title=_("GOQL Filter"),
    navtypes=["Event"],
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
)

register(
    GRAMPLET,
    id="Place GOQL Filter",
    name=_("Place GOQL Filter"),
    description=_("Gramplet providing a gramps-object-query-language place filter"),
    version = '1.0.3',
    gramps_target_version="6.0",
    status=STABLE,
    fname="goql.py",
    height=260,
    gramplet="PlaceQueryFilter",
    gramplet_title=_("GOQL Filter"),
    navtypes=["Place"],
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
)

register(
    GRAMPLET,
    id="Repository GOQL Filter",
    name=_("Repository GOQL Filter"),
    description=_(
        "Gramplet providing a gramps-object-query-language repository filter"
    ),
    version = '1.0.3',
    gramps_target_version="6.0",
    status=STABLE,
    fname="goql.py",
    height=260,
    gramplet="RepositoryQueryFilter",
    gramplet_title=_("GOQL Filter"),
    navtypes=["Repository"],
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
)

register(
    GRAMPLET,
    id="Source GOQL Filter",
    name=_("Source GOQL Filter"),
    description=_("Gramplet providing a gramps-object-query-language source filter"),
    version = '1.0.3',
    gramps_target_version="6.0",
    status=STABLE,
    fname="goql.py",
    height=260,
    gramplet="SourceQueryFilter",
    gramplet_title=_("GOQL Filter"),
    navtypes=["Source"],
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
)

register(
    GRAMPLET,
    id="Citation GOQL Filter",
    name=_("Citation GOQL Filter"),
    description=_("Gramplet providing a gramps-object-query-language citation filter"),
    version = '1.0.3',
    gramps_target_version="6.0",
    status=STABLE,
    fname="goql.py",
    height=260,
    gramplet="CitationQueryFilter",
    gramplet_title=_("GOQL Filter"),
    navtypes=["Citation"],
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
)

register(
    GRAMPLET,
    id="Media GOQL Filter",
    name=_("Media GOQL Filter"),
    description=_("Gramplet providing a gramps-object-query-language media filter"),
    version = '1.0.3',
    gramps_target_version="6.0",
    status=STABLE,
    fname="goql.py",
    height=260,
    gramplet="MediaQueryFilter",
    gramplet_title=_("GOQL Filter"),
    navtypes=["Media"],
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
)

register(
    GRAMPLET,
    id="Note GOQL Filter",
    name=_("Note GOQL Filter"),
    description=_("Gramplet providing a gramps-object-query-language note filter"),
    version = '1.0.3',
    gramps_target_version="6.0",
    status=STABLE,
    fname="goql.py",
    height=260,
    gramplet="NoteQueryFilter",
    gramplet_title=_("GOQL Filter"),
    navtypes=["Note"],
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
)
