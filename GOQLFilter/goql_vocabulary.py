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

"""Shared where-expression token vocabulary.

The small, fixed set of non-column tokens a where-expression can use --
``goql_completion.py`` (Tab completion) and ``goql_highlight.py`` (syntax
coloring) both need this same list and previously each kept their own
copy, which is exactly the kind of thing that quietly drifts apart when
one gets updated and the other doesn't. One source of truth instead.

``and``/``or``/``not``/``in`` are real Python keywords (and thus real
where_expr operators); ``like``/``Date``/``exists``/``count`` are the
whitelisted function-call forms ``gramps_object_query_language.query_lang``
recognizes -- see that module's docstring.
"""

KEYWORDS = frozenset({"and", "or", "not", "in", "like", "Date", "exists", "count"})

COMPARISON_OPERATORS = frozenset({"==", "!=", "<", "<=", ">", ">="})
