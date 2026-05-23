#
# Gramps - a GTK+/GNOME based genealogy program
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301 USA.
#

"""Regression test for Mantis bug 10512 — the Sandclock Genealogy Tree
report rendered only one page of an arbitrarily-large tree because
genealogytree's default ``database`` template lays the tree out so
widely that big sandclocks clip off the page.

SNoiraud's 2018-12-20 workaround on the Mantis ticket was to add
``template=database pole reduced`` to the ``\\genealogytree[…]``
parameter list, which gives ~4x more space per page at the cost of
denser per-node formatting.  This PR exposes that as a user-facing
"Compact tree layout" option on the Sandclock report.

These tests cover the option-list assembly without driving a full
report run (no LaTeX, no Gramps GUI).  They instantiate
``SandclockTree`` via ``__new__`` so we never enter ``Report.__init__``,
set just the attributes ``_build_tree_options`` reads, and assert the
template directive is present exactly when ``compact=True``.
"""

import importlib.util
import os
import unittest


_IMPL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "gt_sandclock.py",
)


def _load_impl():
    """Load and return the gt_sandclock module by file path.

    The addon directory is not necessarily on ``sys.path`` from a
    bare unit-test invocation, so we load by file location.
    """
    spec = importlib.util.spec_from_file_location(
        "gt_sandclock_impl", _IMPL_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SandclockCompactTemplateTest(unittest.TestCase):
    """``_build_tree_options`` emits ``template=database pole reduced``
    if and only if the report's ``compact`` option is True."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.impl = _load_impl()
        except ImportError as err:
            raise unittest.SkipTest("Gramps not importable: %s" % err)
        cls.SandclockTree = cls.impl.SandclockTree

    def _build_report(self, compact, include_images=False):
        """Return a SandclockTree skeleton with just the attributes
        ``_build_tree_options`` reads."""
        report = self.SandclockTree.__new__(self.SandclockTree)
        report.compact = compact
        report.include_images = include_images
        return report

    def test_default_layout_has_no_template_directive(self):
        """With ``compact=False`` (the default), the option list does
        not carry a ``template=`` entry — genealogytree uses its
        default ``database`` template."""
        opts = self._build_report(compact=False)._build_tree_options()
        for entry in opts:
            self.assertFalse(
                entry.startswith("template="),
                f"unexpected template directive: {entry!r}",
            )

    def test_compact_layout_appends_database_pole_reduced(self):
        """With ``compact=True``, the option list contains exactly the
        SNoiraud-suggested directive."""
        opts = self._build_report(compact=True)._build_tree_options()
        self.assertIn("template=database pole reduced", opts)

    def test_compact_template_is_last_option(self):
        """The template directive must come *after* the other genealogy-
        tree options so it overrides node-spacing defaults that
        treedoc.py's built-in keys may have set earlier in the parameter
        list.  pgfkeys is order-sensitive: a later ``template=`` resets
        the keys the template controls."""
        opts = self._build_report(compact=True)._build_tree_options()
        self.assertEqual(
            opts[-1],
            "template=database pole reduced",
            f"template directive must be the LAST option; got {opts!r}",
        )

    def test_compact_layout_preserves_existing_options(self):
        """Turning ``compact`` on must not drop the pref-code, list-
        separator, place-text, or box options that the default option
        list already carries."""
        opts = self._build_report(compact=True)._build_tree_options()
        self.assertIn("pref code={\\underline{#1}}", opts)
        self.assertIn("list separators hang", opts)
        self.assertIn("place text={\\newline}{}", opts)
        # Box option is the one before the template directive.
        self.assertTrue(
            any(entry.startswith("box={") for entry in opts),
            f"box directive missing from option list: {opts!r}",
        )

    def test_images_and_compact_coexist(self):
        """``include_images=True`` and ``compact=True`` both contribute
        their own entries — neither suppresses the other."""
        opts = self._build_report(
            compact=True, include_images=True
        )._build_tree_options()
        self.assertIn("template=database pole reduced", opts)
        # The images path produces a longer box option that contains
        # the genealogytree image-overlay directive ``\gtrDBimage``.
        self.assertTrue(
            any("\\gtrDBimage" in entry for entry in opts),
            f"image directive missing when include_images=True: {opts!r}",
        )


if __name__ == "__main__":
    unittest.main()
