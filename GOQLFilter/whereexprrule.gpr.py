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

"""Filter rules matching objects against a GOQL where-expression."""

_HELP = "Addon:GrampsObjectQueryLanguage"
_AUTHORS = ["Douglas Blank"]
_AUTHORS_EMAIL = ["doug.blank@gmail.com"]

register(
    RULE,
    id="PersonMatchesExpression",
    name=_("People matching the <GOQL expression>"),
    description=_(
        "Matches people for which the given gramps-object-query-language "
        "where-expression evaluates to true"
    ),
    version="1.0.0",
    gramps_target_version="6.1",
    status=STABLE,
    fname="whereexprrule.py",
    ruleclass="PersonMatchesExpression",  # must be rule class name
    namespace="Person",  # one of the primary object classes
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
    requires_mod=["gramps_object_query_language"],
)

register(
    RULE,
    id="FamilyMatchesExpression",
    name=_("Families matching the <GOQL expression>"),
    description=_(
        "Matches families for which the given gramps-object-query-language "
        "where-expression evaluates to true"
    ),
    version="1.0.0",
    gramps_target_version="6.1",
    status=STABLE,
    fname="whereexprrule.py",
    ruleclass="FamilyMatchesExpression",
    namespace="Family",
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
    requires_mod=["gramps_object_query_language"],
)

register(
    RULE,
    id="EventMatchesExpression",
    name=_("Events matching the <GOQL expression>"),
    description=_(
        "Matches events for which the given gramps-object-query-language "
        "where-expression evaluates to true"
    ),
    version="1.0.0",
    gramps_target_version="6.1",
    status=STABLE,
    fname="whereexprrule.py",
    ruleclass="EventMatchesExpression",
    namespace="Event",
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
    requires_mod=["gramps_object_query_language"],
)

register(
    RULE,
    id="PlaceMatchesExpression",
    name=_("Places matching the <GOQL expression>"),
    description=_(
        "Matches places for which the given gramps-object-query-language "
        "where-expression evaluates to true"
    ),
    version="1.0.0",
    gramps_target_version="6.1",
    status=STABLE,
    fname="whereexprrule.py",
    ruleclass="PlaceMatchesExpression",
    namespace="Place",
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
    requires_mod=["gramps_object_query_language"],
)

register(
    RULE,
    id="RepositoryMatchesExpression",
    name=_("Repositories matching the <GOQL expression>"),
    description=_(
        "Matches repositories for which the given gramps-object-query-language "
        "where-expression evaluates to true"
    ),
    version="1.0.0",
    gramps_target_version="6.1",
    status=STABLE,
    fname="whereexprrule.py",
    ruleclass="RepositoryMatchesExpression",
    namespace="Repository",
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
    requires_mod=["gramps_object_query_language"],
)

register(
    RULE,
    id="SourceMatchesExpression",
    name=_("Sources matching the <GOQL expression>"),
    description=_(
        "Matches sources for which the given gramps-object-query-language "
        "where-expression evaluates to true"
    ),
    version="1.0.0",
    gramps_target_version="6.1",
    status=STABLE,
    fname="whereexprrule.py",
    ruleclass="SourceMatchesExpression",
    namespace="Source",
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
    requires_mod=["gramps_object_query_language"],
)

register(
    RULE,
    id="CitationMatchesExpression",
    name=_("Citations matching the <GOQL expression>"),
    description=_(
        "Matches citations for which the given gramps-object-query-language "
        "where-expression evaluates to true"
    ),
    version="1.0.0",
    gramps_target_version="6.1",
    status=STABLE,
    fname="whereexprrule.py",
    ruleclass="CitationMatchesExpression",
    namespace="Citation",
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
    requires_mod=["gramps_object_query_language"],
)

register(
    RULE,
    id="MediaMatchesExpression",
    name=_("Media matching the <GOQL expression>"),
    description=_(
        "Matches media for which the given gramps-object-query-language "
        "where-expression evaluates to true"
    ),
    version="1.0.0",
    gramps_target_version="6.1",
    status=STABLE,
    fname="whereexprrule.py",
    ruleclass="MediaMatchesExpression",
    namespace="Media",
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
    requires_mod=["gramps_object_query_language"],
)

register(
    RULE,
    id="NoteMatchesExpression",
    name=_("Notes matching the <GOQL expression>"),
    description=_(
        "Matches notes for which the given gramps-object-query-language "
        "where-expression evaluates to true"
    ),
    version="1.0.0",
    gramps_target_version="6.1",
    status=STABLE,
    fname="whereexprrule.py",
    ruleclass="NoteMatchesExpression",
    namespace="Note",
    authors=_AUTHORS,
    authors_email=_AUTHORS_EMAIL,
    help_url=_HELP,
    requires_mod=["gramps_object_query_language"],
)
