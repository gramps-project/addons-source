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
Regression test for bug 14145: FRWebConnectPack Geneanet link is stale.

Pre-fix WEBSITES entry pointed at
``https://search.geneanet.org/result.php?lang=fr&name=<surname>`` --
Geneanet deprecated that URL, returning an unusable page, and the
template only carried the surname (Geneanet's current individus search
takes both ``nom`` and ``prenom``). Reporter on Mantis 14145 supplied
the corrected URL; callmedave confirmed the bug (note 5) despite
recommending the WebSearch Gramplet as a longer-term replacement, so
the live FrWebConnectPack addon still needs fixing.

The test imports ``WEBSITES`` from ``FRWebConnectPack.FRWebPack`` and
applies the same ``pattern % dict`` formatting libwebconnect itself
uses (see ``libwebconnect.Search.callback``). No network, no display,
no Gtk -- pure string assertion.
"""

import os
import sys
import unittest

# Make sure addon modules are importable from the parent directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGeneanetUrl(unittest.TestCase):
    """Regression: the Geneanet WEBSITES entry must build a working URL."""

    @staticmethod
    def _geneanet_pattern():
        # Addon dir and impl module share the name ``FRWebConnectPack``
        # under the addon's package namespace; load the implementation
        # via the explicit submodule path to dodge the namespace-package
        # shadowing trap (gramps bug 0012691 family).
        from FRWebConnectPack import FRWebPack  # pylint: disable=import-outside-toplevel

        for entry in FRWebPack.WEBSITES:
            # entry: [nav_type, key, name, url_pattern]
            if entry[1] == "Geneanet":
                return entry[3]
        raise AssertionError("Geneanet entry missing from FRWebPack.WEBSITES")

    def test_built_url_contains_both_name_parts(self):
        """Geneanet URL template must take given AND surname.

        Pre-fix the template only carried ``%(surname)s``; reporter
        on 14145 noted searches returned the wrong people because the
        given name was discarded.
        """
        pattern = self._geneanet_pattern()
        url = pattern % {
            "surname": "Dupont",
            "given": "Marie",
            "middle": "",
            "birth": "",
            "death": "",
        }
        self.assertIn("Dupont", url, "surname must appear in built URL")
        self.assertIn("Marie", url, "given name must appear in built URL")

    def test_built_url_uses_current_geneanet_host_and_path(self):
        """Geneanet URL must target the current individus search.

        Pre-fix the template hit ``search.geneanet.org/result.php`` --
        deprecated. Reporter on 14145 supplied the replacement
        ``www.geneanet.org/fonds/individus/?go=1&nom=...&prenom=...``.
        """
        pattern = self._geneanet_pattern()
        url = pattern % {
            "surname": "Dupont",
            "given": "Marie",
            "middle": "",
            "birth": "",
            "death": "",
        }
        # Stale form -- must NOT appear after the fix.
        self.assertNotIn(
            "result.php",
            url,
            "deprecated Geneanet search URL must not be used",
        )
        self.assertNotIn(
            "search.geneanet.org",
            url,
            "deprecated Geneanet search host must not be used",
        )
        # Corrected form -- must appear.
        self.assertIn(
            "www.geneanet.org/fonds/individus/",
            url,
            "current Geneanet individus search path must be used",
        )
        self.assertIn(
            "nom=Dupont",
            url,
            "surname must be passed as the 'nom' query parameter",
        )
        self.assertIn(
            "prenom=Marie",
            url,
            "given name must be passed as the 'prenom' query parameter",
        )


if __name__ == "__main__":
    unittest.main()
