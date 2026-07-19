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
Regression test for the unrecognized-object branch in
``JSONImport.importData``.

Historically the ``else`` of that function's isinstance dispatch read::

    LOG.warn("ignored: " + data)

— but ``data`` was never bound, so any unparseable / unrecognized
input line raised ``NameError`` instead of being logged. This test
forces the ``else`` branch and asserts the log call happens cleanly
with the post-fix variable (``repr(obj)``).
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

# Make sure addon modules are importable from the parent directory
# (matches the convention used by TMGimporter/Form/WebSearch tests).
# Required when this test is loaded via its dotted path
# (`JSON.tests.test_jsonimport_ignored_log`) rather than discovered
# from inside `tests/`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import JSONImport


class TestImportDataUnrecognizedObjectIsLogged(unittest.TestCase):
    """Cover the else branch of importData's parsed-object dispatch."""

    def test_unrecognized_object_logged_without_nameerror(self):
        """When ``string_to_object`` returns a non-Gramps type the else
        branch must log the ignored value and not raise NameError."""
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False) as f:
            f.write('{"_class": "UnknownType"}\n')
            filename = f.name
        try:
            db = mock.MagicMock()
            user = mock.MagicMock()

            # Stub DbTxn to a no-op context manager so the function's
            # `with DbTxn(...) as trans:` block is callable without a
            # real Gramps database.
            ctx = mock.MagicMock()
            ctx.__enter__ = mock.MagicMock(return_value=ctx)
            ctx.__exit__ = mock.MagicMock(return_value=None)

            # Force the else branch: string_to_object returns a value
            # that is none of the eleven handled Gramps classes
            # (Person, Family, Event, Media, Repository, Tag, Source,
            #  Citation, Note, Place — plus the also-handled Note).
            sentinel = "not-a-gramps-object"
            with mock.patch.object(JSONImport, "string_to_object",
                                   return_value=sentinel), \
                    mock.patch.object(JSONImport, "DbTxn", return_value=ctx), \
                    mock.patch.object(JSONImport, "LOG") as mock_log:
                JSONImport.importData(db, filename, user)

            self.assertTrue(
                mock_log.warn.called,
                "LOG.warn must be called when an object is unrecognized",
            )
            (msg,), _kw = mock_log.warn.call_args
            self.assertTrue(
                msg.startswith("ignored: "),
                "log message should start with 'ignored: ', got %r" % (msg,),
            )
            # The post-fix code uses repr(obj); confirm the sentinel
            # appears in the message so a future refactor that reverts
            # to an unrelated variable trips this assertion.
            self.assertIn(repr(sentinel), msg)
        finally:
            os.unlink(filename)


if __name__ == "__main__":
    unittest.main()
