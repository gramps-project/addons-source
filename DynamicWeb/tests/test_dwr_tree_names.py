#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Gramps developers
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

"""
Regression test for Mantis 11437 — the Dynamic Web Report tree (SVG) view must
not rewrite a hyphen inside a name to a space.

The hyphen->space rewrite lives entirely in the SVG renderer
``templates/dwr_default/data/dwr_svg.js``: ``textLine()`` splits a tree-node
name into words for line-wrapping and historically used ``/[ \\-]+/g`` — which
treats a hyphen as a word separator exactly like a space. ``calcTextTab()`` then
rejoins the same-line fragments with a single space (``t[o] += ' ' + tab[i]``),
so "HAMILTON-SMITH" is rendered "HAMILTON SMITH". Every other DWR surface keeps
the hyphen because they emit the Python-side name string verbatim; only the tree
passes the name through this splitter.

There is no Python production seam for the rewrite, and ``textLine()`` itself is
GUI-entangled (Raphael/SVG DOM), so it cannot be executed headless. This test
therefore drives the **actual production splitter regex read from the shipped
dwr_svg.js** and reproduces production's same-line join, asserting the hyphen
survives. Reverting the JS fix flips the regex back to ``/[ \\-]+/g`` and turns
this test red; the fix turns it green.
"""

import os
import re
import unittest

# The production SVG renderer, relative to this test file.
_DWR_SVG_JS = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "templates",
        "dwr_default",
        "data",
        "dwr_svg.js",
    )
)


def _textline_split_pattern(js_source):
    """Return the word-split regex body that production ``textLine()`` applies
    to a tree-node name, read live from the shipped dwr_svg.js.

    ``textLine()`` is the only place that does ``txt.split(/.../g)``, so the
    assignment uniquely identifies the splitter the tree uses.
    """
    match = re.search(r"txt\.split\(\s*/(?P<body>.+?)/g\s*\)", js_source)
    if not match:
        raise AssertionError(
            "could not locate the textLine() name splitter "
            "(txt.split(/.../g)) in %s" % _DWR_SVG_JS
        )
    return match.group("body")


class TreeNameHyphenTest(unittest.TestCase):
    """The DWR tree splitter must preserve hyphens inside names."""

    # Names a user may enter; each must render in the tree exactly as stored.
    HYPHENATED_NAMES = ["Jan-Åke", "HAMILTON-SMITH", "Joe St-Pierre"]

    def setUp(self):
        with open(_DWR_SVG_JS, encoding="utf-8") as handle:
            self.js_source = handle.read()
        self.split_re = re.compile(_textline_split_pattern(self.js_source))

    def _render_single_line(self, name):
        """Reproduce what the tree draws for a name that fits on one line:
        ``textLine()`` splits the name, then ``calcTextTab()`` rejoins same-line
        fragments with a single space (dwr_svg.js: ``t[o] += ' ' + tab[i]``)."""
        fragments = [frag for frag in self.split_re.split(name) if frag]
        return " ".join(fragments)

    def test_tree_node_name_keeps_hyphen(self):
        for name in self.HYPHENATED_NAMES:
            with self.subTest(name=name):
                self.assertEqual(
                    self._render_single_line(name),
                    name,
                    "DWR tree splitter rewrote %r -> %r (hyphen lost)"
                    % (name, self._render_single_line(name)),
                )


if __name__ == "__main__":
    unittest.main()
