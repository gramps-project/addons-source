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
Regression test for the ``Person.gramps_id`` setter in libaccess.

Historically the ``gramps_id`` entry of ``libaccess.Person.setters``
read::

    "gramps_id": lambda self: self.setit("gramps_id", value),

— note the missing ``value`` parameter. Setting
``person.gramps_id = "I0001"`` via the libaccess alias interface
routes through ``Object.__setattr__`` which calls
``self.setters[attr](self, value)`` — i.e. with two positional
arguments. The lambda accepts only one, so the call raised
``TypeError`` (and ruff F821 also flags the bare ``value`` reference
inside the lambda body as an undefined name).

This test exercises the full ``__setattr__`` → setters dispatch →
``setit`` path and asserts the underlying instance attribute is
updated, with no exception. Before the fix the test fails with
``TypeError``; after, it passes.
"""

import os
import sys
import unittest
from unittest import mock

# Make sure addon modules are importable from the parent directory.
# Required when this test is loaded via its dotted path
# (``libaccess.tests.test_libaccess_setattr``) rather than via
# ``unittest discover`` from inside ``tests/``.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The addon directory is named ``libaccess`` and contains both
# ``libaccess.py`` (the implementation module) and ``tests/`` (this
# test). Under dotted-path loading the directory is treated as a
# namespace package, so ``import libaccess`` would bind the package
# rather than the implementation module. Import via the explicit
# submodule path and rebind. (This is the same package-shadowing
# class as gramps bug 0012691; see addons-source-CI dotted-path
# loader notes.)
from libaccess import libaccess  # noqa: E402


class TestGrampsIdSetter(unittest.TestCase):
    """Cover Person.setters['gramps_id'] via the __setattr__ alias."""

    def setUp(self):
        # The upstream libaccess.py module uses ``_(...)`` for gettext
        # without binding ``_`` (a separate F821 addressed by another
        # PR). To exercise the lambda fix in isolation here, install a
        # passthrough ``_`` for the duration of this test. Restored in
        # tearDown.
        self._had_gettext = hasattr(libaccess, "_")
        self._saved_gettext = getattr(libaccess, "_", None)
        libaccess._ = lambda s: s

    def tearDown(self):
        if self._had_gettext:
            libaccess._ = self._saved_gettext
        else:
            try:
                del libaccess._
            except AttributeError:
                pass

    def test_set_gramps_id_via_setattr_does_not_raise(self):
        """Setting ``person.gramps_id = "I0001"`` must succeed.

        Before the fix the ``gramps_id`` lambda took only ``self``,
        so ``Object.__setattr__`` invoking ``setters[attr](self,
        value)`` with two arguments raised
        ``TypeError: <lambda>() takes 1 positional argument but 2
        were given``.
        """
        # A stub Gramps Person — only the attributes/methods that
        # libaccess.Person.setit touches are exercised:
        #   self.instance.gramps_id = value
        stub_person_instance = mock.MagicMock()
        stub_person_instance.gramps_id = "I-original"

        person = libaccess.Person(stub_person_instance)

        # Patch the DbTxn context manager and the module-level
        # ``database`` global so ``setit`` does not need a real
        # Gramps backend.
        ctx = mock.MagicMock()
        ctx.__enter__ = mock.MagicMock(return_value=ctx)
        ctx.__exit__ = mock.MagicMock(return_value=None)

        with mock.patch.object(libaccess, "DbTxn", return_value=ctx), \
                mock.patch.object(libaccess, "database", mock.MagicMock()):
            # The actual call that exercises the buggy lambda. Before
            # the fix this raises TypeError on the lambda invocation
            # inside Object.__setattr__.
            person.gramps_id = "I-new"

        # The fixed lambda forwards (self, value) to setit, which
        # assigns to self.instance.gramps_id.
        self.assertEqual(stub_person_instance.gramps_id, "I-new")

    def test_handle_setter_remains_functional(self):
        """The neighbouring ``handle`` setter (already correct) must
        also work — pins down that the fix didn't accidentally
        regress the symmetric entry."""
        stub_person_instance = mock.MagicMock()
        stub_person_instance.handle = "h-original"

        person = libaccess.Person(stub_person_instance)

        ctx = mock.MagicMock()
        ctx.__enter__ = mock.MagicMock(return_value=ctx)
        ctx.__exit__ = mock.MagicMock(return_value=None)

        with mock.patch.object(libaccess, "DbTxn", return_value=ctx), \
                mock.patch.object(libaccess, "database", mock.MagicMock()):
            person.handle = "h-new"

        self.assertEqual(stub_person_instance.handle, "h-new")


if __name__ == "__main__":
    unittest.main()
