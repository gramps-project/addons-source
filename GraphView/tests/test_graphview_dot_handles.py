#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Eduard Ralph
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

"""
Unit tests for Graphviz node-id quoting in the GraphView addon (bug 13832).
"""

import unittest
from io import StringIO

# GraphView imports gi/GooCanvas at module load. Skip ONLY when those Python
# modules are genuinely absent (ImportError, e.g. PyGObject not installed). A
# wrong/unavailable GI version (ValueError from require_version) or a missing
# system dep (GraphView raises if GooCanvas/dot are absent) must NOT be laundered
# into a skip that reads as success — let it surface as a hard error. The testbed
# image / CI provide these deps and the system-deps drift-guard enforces them.
try:
    import gi

    gi.require_version("Gtk", "3.0")
    from GraphView.graphview import DotSvgGenerator

    _IMPORT_ERROR = None
except ImportError as err:  # genuine absence of gi / the addon's Python modules
    DotSvgGenerator = None
    _IMPORT_ERROR = err


# A Gramps-Web UUIDv4 handle (hyphens) vs. a desktop handle (no hyphens).
HYPHEN_HANDLE = "22e6b2a0-269e-4c58-8e27-0c38b2ef5a10"
PLAIN_HANDLE = "fe4861b093015ddcbb08044be02"


# ------------------------------------------------------------
#
# DotHandleQuotingTest
#
# ------------------------------------------------------------
@unittest.skipIf(
    DotSvgGenerator is None,
    "GraphView import unavailable (gi/GooCanvas/display): %s" % (_IMPORT_ERROR,),
)
class DotHandleQuotingTest(unittest.TestCase):
    """
    The DOT generator emits Gramps handles as node ids. Handles are
    arbitrary schema-valid strings (<=50 chars); Gramps-Web creates
    UUIDv4 handles containing hyphens. An unquoted Graphviz id is split at
    the first hyphen, so the node/edge/cluster name is mangled and the
    Graph View blanks (bug 13832). Every handle written into the DOT must
    therefore be quoted.
    """

    def _generator(self):
        # Bypass __init__ (which needs a live dbstate/view); the DOT-writing
        # methods only touch the attributes set up here.
        gen = DotSvgGenerator.__new__(DotSvgGenerator)
        gen.dot = StringIO()
        gen.current_list = set()
        gen.colors = {"link_color": "#000000"}
        return gen

    def test_add_node_quotes_hyphenated_handle(self):
        gen = self._generator()
        gen.add_node(HYPHEN_HANDLE, "Some Label")
        out = gen.dot.getvalue()
        self.assertIn('"_%s"' % HYPHEN_HANDLE, out)

    def test_add_node_quotes_plain_handle(self):
        gen = self._generator()
        gen.add_node(PLAIN_HANDLE, "Some Label")
        out = gen.dot.getvalue()
        self.assertIn('"_%s"' % PLAIN_HANDLE, out)

    def test_add_link_quotes_both_endpoints(self):
        gen = self._generator()
        gen.add_link(HYPHEN_HANDLE, PLAIN_HANDLE)
        out = gen.dot.getvalue()
        self.assertIn('"_%s" -> "_%s"' % (HYPHEN_HANDLE, PLAIN_HANDLE), out)

    def test_start_subgraph_quotes_cluster_name(self):
        gen = self._generator()
        gen.start_subgraph(HYPHEN_HANDLE)
        out = gen.dot.getvalue()
        self.assertIn('"cluster_%s"' % HYPHEN_HANDLE, out)


if __name__ == "__main__":
    unittest.main()
