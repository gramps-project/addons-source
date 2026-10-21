#
# FastRelationshipGraph -- a standalone addon, independent of gramps-core
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program. If not, see
# <https://www.gnu.org/licenses/>.
#

"""Shared helpers for this addon's test modules -- not a pytest
``conftest.py`` (this repo's tests use plain ``unittest.TestCase``, see
``addons-source/AGENTS.md``'s Testing section), just an ordinary module
each test file imports.
"""

import os

import gramps
from gramps.gen.utils.grampslocale import GrampsLocale
from gramps.gen.utils.resourcepath import ResourcePath

_resources = ResourcePath()


def find_example_gramps():
    """Locate the example.gramps file bundled with the installed
    ``gramps`` package -- checks GRAMPS_RESOURCES first (set by the
    caller, or auto-detected by each test module's own import block),
    then falls back to deriving it from ``gramps.__file__`` directly."""
    candidates = []
    res = os.environ.get("GRAMPS_RESOURCES")
    if res:
        candidates.append(os.path.join(res, "example", "gramps", "example.gramps"))
    root = os.path.dirname(os.path.dirname(os.path.abspath(gramps.__file__)))
    candidates.append(os.path.join(root, "example", "gramps", "example.gramps"))
    doc_candidate = os.path.join(_resources.doc_dir, "example", "gramps", "example.gramps")
    candidates.append(doc_candidate)
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def locale_for(lang: str) -> GrampsLocale:
    """A GrampsLocale for `lang` that resolves translations via the
    installed `gramps` package's own locale directory explicitly."""
    return GrampsLocale(lang=lang, localedir=_resources.locale_dir)
