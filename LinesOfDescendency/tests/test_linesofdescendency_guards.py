#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Gramps Development Team
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
Regression test for the descendent/ancestor guards in
``LinesOfDescendency.__init__``.

``__init__`` looks up two people by Gramps ID::

    self.descendent = database.get_person_from_gramps_id(pid)
    ...
    self.ancestor = database.get_person_from_gramps_id(ancestor)

A Gramps ID that is not in the database makes the lookup return
``None``. Historically the only guard was ``if self.descendent == None``
placed *after* ``self.descendent.get_handle()`` — so a missing
descendent raised ``AttributeError`` before the guard could run, the
missing-ancestor case was never guarded at all, and ``ReportError`` was
not even imported (the guard would itself have raised ``NameError``).

These tests drive ``__init__`` with a mock options/database and assert
that a missing descendent *or* a missing ancestor raises
``ReportError`` naming the offending ID. ``Report.__init__`` (the base
class) is stubbed, so no real Gramps report backend is needed.
"""

import importlib.util
import os
import unittest
from unittest import mock

# The addon module's filename contains a hyphen, so it cannot be loaded
# with a normal `import` statement / dotted path — it is loaded directly
# from its file location instead.
_IMPL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "lines-of-descendency.py",
)


def _load_impl():
    """Load and return the lines-of-descendency.py module by file path."""
    spec = importlib.util.spec_from_file_location(
        "linesofdescendency_impl", _IMPL_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_options(pid, ancestor_id):
    """Build a mock options object exposing the 'pid'/'ancestor' menu options."""
    options = mock.MagicMock()
    values = {"pid": pid, "ancestor": ancestor_id}

    def get_option_by_name(name):
        opt = mock.MagicMock()
        opt.get_value.return_value = values[name]
        return opt

    options.menu.get_option_by_name.side_effect = get_option_by_name
    return options


class TestLinesOfDescendencyGuards(unittest.TestCase):
    """Cover the missing-person guards in LinesOfDescendency.__init__."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.impl = _load_impl()
        except ImportError as err:
            raise unittest.SkipTest("Gramps not importable: %s" % err)
        cls.LinesOfDescendency = cls.impl.LinesOfDescendency
        cls.ReportError = cls.impl.ReportError

    def _build(self, descendent, ancestor, pid="I9999", ancestor_id="I0001"):
        """Instantiate the report against a database returning the given people.

        ``Report.__init__`` is stubbed so no real report backend is needed.
        """
        database = mock.MagicMock()
        people = {pid: descendent, ancestor_id: ancestor}
        database.get_person_from_gramps_id.side_effect = lambda gid: people[gid]
        options = _make_options(pid, ancestor_id)
        with mock.patch.object(self.impl, "Report"):
            return self.LinesOfDescendency(database, options, mock.MagicMock())

    def test_missing_descendent_raises_report_error(self):
        """A descendent ID absent from the database raises ReportError."""
        with self.assertRaises(self.ReportError) as ctx:
            self._build(descendent=None, ancestor=mock.MagicMock())
        self.assertIn("I9999", str(ctx.exception))

    def test_missing_ancestor_raises_report_error(self):
        """An ancestor ID absent from the database raises ReportError.

        Before the fix this case was not guarded at all.
        """
        with self.assertRaises(self.ReportError) as ctx:
            self._build(descendent=mock.MagicMock(), ancestor=None)
        self.assertIn("I0001", str(ctx.exception))

    def test_both_present_does_not_raise(self):
        """With both people present, __init__ completes without error."""
        report = self._build(
            descendent=mock.MagicMock(), ancestor=mock.MagicMock()
        )
        self.assertIsNotNone(report.descendent)
        self.assertIsNotNone(report.ancestor)


if __name__ == "__main__":
    unittest.main()
