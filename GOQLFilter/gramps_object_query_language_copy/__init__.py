#
# gramps-object-query-language - Object query language and SQL compiler for Gramps data
#
# Copyright (C) 2026      Douglas Blank
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#

"""Object query language and SQL compiler for Gramps data.

Standalone, privacy-agnostic: compiles a structured query (select/where/
order_by/limit/after) or an "almost Python" expression string into
parameterized SQL against Gramps' flattened secondary columns. Carries no
knowledge of proxies, permissions, or Gramps Web API request handling --
callers are responsible for only invoking it against an unproxied database
handle.

VENDORED COPY -- do not edit directly. This is a verbatim copy of the
"gramps_object_query_language" package (PyPI: gramps-object-query-language,
https://github.com/dsblank/gramps-object-query-language), pinned at
version 0.5.0 / commit ffdcde3a97e3a6dc194779a14dd2d234d113f4c1, imported
here as "gramps_object_query_language_copy" (not the upstream package name)
so it can't collide with a real pip-installed copy of the same library on
the same interpreter.

Why vendored instead of a plain `pip install gramps-object-query-language`
dependency (which is what the gramps61 branch of this addon uses, via
`requires_mod`): pip installs of pure-Python addon dependencies are
unreliable across Gramps 6.0's various AIO installers, so this gramps60
branch bundles the library directly instead.

To refresh this copy: replace every file in this directory (except this
notice) with the corresponding file from a newer gramps_object_query_language
release, update the pinned version/commit above, and re-run GOQLFilter's
test suite.

Licensed AGPL-3.0-or-later, same as upstream (see LICENSE in this
directory) -- GOQLFilter's own files are GPL-2.0-or-later ("or later"),
which is what makes combining the two into one distributed addon permitted
under AGPLv3's own compatibility clause (AGPLv3 section 13). This has not
been reviewed by a lawyer; flag it for review before this addon is
released more broadly.
"""
