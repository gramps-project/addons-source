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

"""Test package for the FastRelationshipGraph addon.

Importing this package adds ``ADDON_DIR`` to ``sys.path`` and sets
``GRAMPS_RESOURCES`` if unset, so test modules can import ``gramps`` and
the addon's flat modules (``fast_relationship_graph``,
``fast_relationship_engine``) directly. GTK/Gdk version pinning is
handled repo-wide by the root ``tests/__init__.py`` (PR #950) -- this
addon doesn't touch GTK at all, but the `import gi` guard in each test
module still applies (see addons-source/AGENTS.md's Testing section).
"""

import os
import sys

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

if "GRAMPS_RESOURCES" not in os.environ:
    import gramps

    os.environ["GRAMPS_RESOURCES"] = os.path.dirname(os.path.dirname(gramps.__file__))
