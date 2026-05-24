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
Integration tests for the ``make.py`` listing command.

Tests run ``make.py`` as a subprocess against a synthetic addon tree, so the
command-line parsing, glob, and listings-file I/O are exercised end-to-end.
"""

# ------------------------
# Python modules
# ------------------------
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


ADDONS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAKE_PY = os.path.join(ADDONS_ROOT, "make.py")
GRAMPS_VERSION = "gramps61"


_GPR_TEMPLATE = """\
register(GRAMPLET,
    id='{name}',
    name='{name}',
    description='Synthetic test addon',
    version='1.0.0',
    gramps_target_version='6.1',
    status=STABLE,
    fname='{name}.py',
    height=200,
    gramplet='{name}',
    gramplet_title='{name}',
    include_in_listing={include_in_listing},
)
"""


# ------------------------------------------------------------
#
# MakeListingTest
#
# ------------------------------------------------------------
class MakeListingTest(unittest.TestCase):
    """
    Tests that ``make.py <ver> listing <addon>`` does not corrupt the
    listings file when the targeted addon is not eligible for listing.
    """

    def setUp(self) -> None:
        self.workdir = tempfile.mkdtemp(prefix="make_listing_test_")
        self.addons_source = os.path.join(self.workdir, "addons-source")
        self.addons = os.path.join(self.workdir, "addons")
        os.makedirs(self.addons_source)
        os.makedirs(os.path.join(self.addons, GRAMPS_VERSION, "download"))
        os.makedirs(os.path.join(self.addons, GRAMPS_VERSION, "listings"))

        shutil.copy(MAKE_PY, self.addons_source)

        # Seed addons-en.json with a real-looking entry that must survive.
        self.listings_path = os.path.join(
            self.addons, GRAMPS_VERSION, "listings", "addons-en.json"
        )
        self.seed_entries = [
            {
                "n": "ExistingAddon",
                "i": "ExistingAddon",
                "t": 3,
                "d": "Seeded entry that must not be wiped",
                "v": "1.0.0",
                "g": "6.1",
                "s": 3,
                "z": "ExistingAddon.addon.tgz",
            }
        ]
        with open(self.listings_path, "w", encoding="utf-8") as fp:
            json.dump(self.seed_entries, fp, indent=0)

    def tearDown(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)

    def _make_addon(self, name: str, include_in_listing: bool) -> None:
        addon_dir = os.path.join(self.addons_source, name)
        os.makedirs(addon_dir)
        with open(
            os.path.join(addon_dir, name + ".gpr.py"), "w", encoding="utf-8"
        ) as fp:
            fp.write(
                _GPR_TEMPLATE.format(
                    name=name,
                    include_in_listing="True" if include_in_listing else "False",
                )
            )
        # make.py only emits an entry when the .tgz already exists.
        tgz_path = os.path.join(
            self.addons, GRAMPS_VERSION, "download", name + ".addon.tgz"
        )
        with open(tgz_path, "wb") as fp:
            fp.write(b"placeholder")

    def _run_listing(self, addon_name: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        # make.py imports gramps.gen.const / gramps.gen.plug from GRAMPSPATH.
        if "GRAMPSPATH" not in env:
            import gramps  # noqa: WPS433

            env["GRAMPSPATH"] = os.path.dirname(os.path.dirname(gramps.__file__))
        return subprocess.run(
            [sys.executable, "make.py", GRAMPS_VERSION, "listing", addon_name],
            cwd=self.addons_source,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_listing_excluded_addon_does_not_wipe_listings(self) -> None:
        """
        Regression for bug 13694.

        Running ``make.py <ver> listing <Addon>`` on an addon whose .gpr.py
        declares ``include_in_listing=False`` must not overwrite the
        ``addons-<lang>.json`` listings file with ``[]``. Pre-fix, the
        single-addon update path produced an empty ``output`` list when no
        plugin was eligible and then wrote that empty list, wiping every
        previously listed addon.
        """
        self._make_addon("ExcludedAddon", include_in_listing=False)

        result = self._run_listing("ExcludedAddon")
        self.assertEqual(
            result.returncode,
            0,
            "make.py exited %s\nstdout:\n%s\nstderr:\n%s"
            % (result.returncode, result.stdout, result.stderr),
        )

        with open(self.listings_path, "r", encoding="utf-8") as fp:
            after = json.load(fp)

        self.assertEqual(
            after,
            self.seed_entries,
            "Bug 13694: listing an include_in_listing=False addon must not "
            "wipe the existing addons-<lang>.json. Got %r." % (after,),
        )


if __name__ == "__main__":
    unittest.main()
