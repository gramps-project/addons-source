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
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""
Regression test for bug 13979: PluginManager Enhanced raised IndexError
on the PostgreSQL Enhanced row.

The addon's gpr.py declares ``requires_exe=[]`` which lands in the
addons-<lang>.json listing as ``"re": []``. gramps core's
:class:`Requirements.info` still emits an Executables label paired with
an empty table for that key, and :meth:`PluginStatus.__info` then tries
``" ".join(req_lst[0])`` on the empty list, raising
``IndexError: list index out of range``.
"""

# ------------------------
# Python modules
# ------------------------
import os
import unittest
from unittest.mock import Mock


def _has_gtk_display():
    """
    Return True only if a real Gtk display is available.

    PluginManager.py imports Gtk at module load. Constructing a real
    PluginStatus is impossible without a display, and we sidestep that
    via ``__new__``-bypass below - but the import alone can still trip
    on hosts where Gtk has no backend (CI with GDK_BACKEND=-).
    """
    if not os.environ.get("DISPLAY"):
        return False
    if os.environ.get("GDK_BACKEND") == "-":
        return False
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        return bool(Gtk.init_check([])[0])
    except Exception:  # pylint: disable=broad-except
        return False


_HAS_GTK_DISPLAY = _has_gtk_display()


# ------------------------------------------------------------
#
# TestPluginManagerInfoEmptyRequires
#
# ------------------------------------------------------------
@unittest.skipUnless(
    _HAS_GTK_DISPLAY,
    "needs a real Gtk display (run under xvfb-run)",
)
class TestPluginManagerInfoEmptyRequires(unittest.TestCase):
    """
    Regression for bug 13979.
    """

    def _make_addon(self):
        """
        Listing-shaped dict matching the real PostgreSQL Enhanced entry
        in ``addons/gramps61/listings/addons-en.json`` - the unique
        trigger of the original crash (the only addon currently shipping
        with a present-but-empty ``re`` key).
        """
        return {
            "n": "PostgreSQL Enhanced",
            "i": "postgresqlenhanced",
            "t": 12,
            "d": "Advanced PostgreSQL backend.",
            "v": "1.5.4",
            "g": "6.1",
            "s": 3,
            "z": "PostgreSQLEnhanced.addon.tgz",
            "rm": ["psycopg"],
            "re": [],
            "h": "https://example.invalid/wiki/PostgreSQLEnhanced",
            "a": 1,
            "_u": "https://example.invalid/download/",
        }

    def _make_status(self, addon):
        """
        Build a PluginStatus via ``__new__``-bypass, stubbing only the
        attributes that ``__info`` touches.
        """
        # Import inside the method so the module-level Gtk imports run
        # only after the display skip has been evaluated.
        from PluginManager.PluginManager import PluginStatus

        status = PluginStatus.__new__(PluginStatus)
        status.addons = [addon]
        # get_plugin returns None so __info takes the "installed plugins"
        # branch where the bug lives.
        status._preg = Mock()
        status._preg.get_plugin.return_value = None
        # _bufin is a Gtk text-buffer mutator; we only care that __info
        # gets through it without raising, not what it writes.
        status._bufin = Mock()
        # __info also consults _pmgr for loaded/failed lists and self.hidden
        # after the requirements block. Stub them to return empty.
        status._pmgr = Mock()
        status._pmgr.get_success_list.return_value = []
        status._pmgr.get_fail_list.return_value = []
        status.hidden = []
        status.help = ""
        status.helpname = ""
        return status

    def test_info_with_empty_requires_exe_does_not_raise(self):
        """
        Pre-fix this raised ``IndexError`` at
        ``PluginManager.py:655  txt = " ".join(req_lst[0])`` when
        iterating to the Executables entry of the Requirements list
        (whose table is empty for PostgreSQL Enhanced). Post-fix the
        empty entry is skipped.
        """
        status = self._make_status(self._make_addon())

        try:
            # __info is name-mangled on PluginStatus.
            status._PluginStatus__info("postgresqlenhanced")
        except IndexError as exc:
            self.fail(
                "Bug 13979: PluginStatus.__info() must not crash on an "
                "addon whose listing has a present-but-empty requires "
                "key (e.g. PostgreSQL Enhanced's `\"re\": []`). Got: %s"
                % exc
            )

        # Sanity: the Python modules requirement still gets rendered.
        bufin_labels = [
            call.args[0] for call in status._bufin.call_args_list if call.args
        ]
        self.assertTrue(
            any("Python modules" in label for label in bufin_labels),
            "Expected the non-empty Python modules requirement to still "
            "be rendered; the fix must only skip empty tables. Got "
            "labels: %r" % bufin_labels,
        )
        # And the empty Executables entry must NOT be rendered.
        self.assertFalse(
            any("Executables" in label for label in bufin_labels),
            "Empty Executables entry should be skipped, not rendered. "
            "Got labels: %r" % bufin_labels,
        )


if __name__ == "__main__":
    unittest.main()
