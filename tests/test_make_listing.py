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


def _detect_gramps_version() -> tuple[str, str]:
    """
    Return ``(gramps_version_dir, gramps_target_version)`` from the
    installed gramps. The directory form is ``"gramps<major><minor>"``
    (e.g. ``"gramps60"``) — what make.py expects as its first
    positional argument. The target form is ``"<major>.<minor>"``
    (e.g. ``"6.0"``) — what a .gpr.py ``gramps_target_version`` must
    match for the addon to be eligible for listing.

    Detected at runtime so the same test passes against either
    addons-source/maintenance/gramps60 (gramps 6.0 install) or
    addons-source/maintenance/gramps61 (gramps 6.1 install).
    """
    import gramps.version  # local import: gramps may not be on path at module-load time

    major, minor = gramps.version.VERSION_TUPLE[:2]
    return "gramps%d%d" % (major, minor), "%d.%d" % (major, minor)


GRAMPS_VERSION, GRAMPS_TARGET_VERSION = _detect_gramps_version()


_GPR_TEMPLATE = """\
register(GRAMPLET,
    id='{name}',
    name='{name}',
    description='Synthetic test addon',
    version='1.0.0',
    gramps_target_version='{target}',
    status=STABLE,
    fname='{name}.py',
    height=200,
    gramplet='{name}',
    gramplet_title='{name}',
    include_in_listing={include_in_listing},
)
"""

_GPR_GRAMPLET_REGISTER = """\
register(GRAMPLET,
    id='{plugin_id}',
    name='{plugin_id}',
    description='Synthetic test gramplet',
    version='1.0.0',
    gramps_target_version='{target}',
    status=STABLE,
    fname='{plugin_id}.py',
    height=200,
    gramplet='{plugin_id}',
    gramplet_title='{plugin_id}',
)
"""

_GPR_QUICKREPORT_REGISTER = """\
register(QUICKREPORT,
    id='{plugin_id}',
    name='{plugin_id}',
    description='Synthetic test quickreport',
    version='1.0.0',
    gramps_target_version='{target}',
    status=STABLE,
    fname='{plugin_id}.py',
    category=CATEGORY_QR_PERSON,
    runfunc='run',
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
                "g": GRAMPS_TARGET_VERSION,
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
                    target=GRAMPS_TARGET_VERSION,
                    include_in_listing="True" if include_in_listing else "False",
                )
            )
        # make.py only emits an entry when the .tgz already exists.
        tgz_path = os.path.join(
            self.addons, GRAMPS_VERSION, "download", name + ".addon.tgz"
        )
        with open(tgz_path, "wb") as fp:
            fp.write(b"placeholder")

    def _make_multi_gpr_addon(
        self, name: str, gpr_files: dict[str, list[tuple[str, str]]]
    ) -> None:
        """
        Build an addon directory that contains multiple .gpr.py files
        and/or multiple register() calls per file.

        ``gpr_files`` maps a base .gpr.py filename (without suffix) to a
        list of ``(plugin_id, plugin_type)`` tuples to register inside
        that file. ``plugin_type`` is "gramplet" or "quickreport".
        """
        addon_dir = os.path.join(self.addons_source, name)
        os.makedirs(addon_dir)
        for gpr_base, registers in gpr_files.items():
            gpr_path = os.path.join(addon_dir, gpr_base + ".gpr.py")
            with open(gpr_path, "w", encoding="utf-8") as fp:
                for plugin_id, plugin_type in registers:
                    if plugin_type == "gramplet":
                        fp.write(
                            _GPR_GRAMPLET_REGISTER.format(
                                plugin_id=plugin_id,
                                target=GRAMPS_TARGET_VERSION,
                            )
                        )
                    elif plugin_type == "quickreport":
                        fp.write(
                            _GPR_QUICKREPORT_REGISTER.format(
                                plugin_id=plugin_id,
                                target=GRAMPS_TARGET_VERSION,
                            )
                        )
                    else:
                        raise ValueError(
                            "unknown plugin_type: %r" % (plugin_type,)
                        )
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

    def test_listing_multi_gpr_addon_does_not_duplicate_other_entries(
        self,
    ) -> None:
        """
        Regression for the PR 915 follow-up flagged by GaryGriffin: an
        addon that ships multiple ``.gpr.py`` files (or multiple
        ``register()`` calls in one file) used to corrupt the listings
        file with N copies of every existing entry.

        Pre-fix, the merge path's outer ``for plugin in sorted(listings...)``
        loop re-read the entire listings file on each iteration while
        accumulating into a shared ``output``. With three new plugins
        (two .gpr.py files - one with a single register, one with two)
        every existing entry ended up duplicated three times.

        Post-fix, the merge reads the existing file once, drops every
        row that belongs to cmd_arg, and inserts the fresh plugins at
        their sorted (t, i) positions. Result: exactly one entry per
        existing addon plus one per new plugin.
        """
        # Seed the listings file with one existing entry that belongs
        # to the multi-gpr addon (to verify replacement) and a few
        # unrelated entries (to verify they are preserved exactly).
        unrelated_a = {
            "n": "Other A",
            "i": "otheraddon_a",
            "t": 0,
            "d": "Unrelated entry",
            "v": "1.0.0",
            "g": GRAMPS_TARGET_VERSION,
            "s": 3,
            "z": "OtherAddonA.addon.tgz",
        }
        unrelated_b = {
            "n": "Other B",
            "i": "otheraddon_b",
            "t": 5,
            "d": "Unrelated entry",
            "v": "1.0.0",
            "g": GRAMPS_TARGET_VERSION,
            "s": 3,
            "z": "OtherAddonB.addon.tgz",
        }
        # Existing entry for our multi-gpr addon's gramplet, with a
        # stale version that the new listing must overwrite.
        stale_gramplet = {
            "n": "MyForm Gramplet",
            "i": "myform_gramplet",
            "t": 5,
            "d": "Stale entry from a prior build",
            "v": "0.9.0",
            "g": GRAMPS_TARGET_VERSION,
            "s": 3,
            "z": "MyForm.addon.tgz",
        }
        # Existing entry for cmd_arg that is no longer registered by
        # any .gpr.py - the merge should drop it.
        stale_dropped = {
            "n": "MyForm Removed",
            "i": "myform_removed",
            "t": 5,
            "d": "register() was removed from a .gpr.py - should be dropped",
            "v": "1.0.0",
            "g": GRAMPS_TARGET_VERSION,
            "s": 3,
            "z": "MyForm.addon.tgz",
        }
        # Write the existing file sorted by (t, i) - canonical order.
        seed = sorted(
            [unrelated_a, unrelated_b, stale_gramplet, stale_dropped],
            key=lambda p: (p["t"], p["i"]),
        )
        with open(self.listings_path, "w", encoding="utf-8") as fp:
            json.dump(seed, fp, indent=0)

        # Build MyForm with two .gpr.py files: one registers a single
        # gramplet, the other registers two quickreports. Mirrors the
        # real Form addon's layout (formgramplet.gpr.py +
        # CensusCheckQuickview.gpr.py).
        self._make_multi_gpr_addon(
            "MyForm",
            {
                "myform": [("myform_gramplet", "gramplet")],
                "censuscheck": [
                    ("myform_census", "quickreport"),
                    ("myform_censusup", "quickreport"),
                ],
            },
        )

        result = self._run_listing("MyForm")
        self.assertEqual(
            result.returncode,
            0,
            "make.py exited %s\nstdout:\n%s\nstderr:\n%s"
            % (result.returncode, result.stdout, result.stderr),
        )

        with open(self.listings_path, "r", encoding="utf-8") as fp:
            after = json.load(fp)

        ids = [e["i"] for e in after]
        # No duplicates anywhere - the core symptom Gary flagged.
        self.assertEqual(
            len(ids),
            len(set(ids)),
            "Multi-gpr listing must not duplicate entries. Got ids: %r"
            % (ids,),
        )

        # Unrelated entries preserved exactly.
        after_by_id = {e["i"]: e for e in after}
        self.assertIn("otheraddon_a", after_by_id)
        self.assertIn("otheraddon_b", after_by_id)
        self.assertEqual(after_by_id["otheraddon_a"], unrelated_a)
        self.assertEqual(after_by_id["otheraddon_b"], unrelated_b)

        # Three new plugins from MyForm present, in MyForm.addon.tgz.
        myform_entries = [e for e in after if e.get("z") == "MyForm.addon.tgz"]
        myform_ids = sorted(e["i"] for e in myform_entries)
        self.assertEqual(
            myform_ids,
            ["myform_census", "myform_censusup", "myform_gramplet"],
            "Expected the three MyForm plugins; got %r" % (myform_ids,),
        )

        # Stale entry for the removed plugin must be dropped.
        self.assertNotIn(
            "myform_removed",
            after_by_id,
            "An existing entry for cmd_arg that is no longer registered "
            "by any .gpr.py must be dropped during the merge.",
        )

        # Stale gramplet entry must have been replaced with the fresh
        # version (post-fix v=1.0.0 from the new register).
        self.assertEqual(
            after_by_id["myform_gramplet"]["v"],
            "1.0.0",
            "Existing myform_gramplet entry should have been replaced "
            "with the fresh v=1.0.0; got %r"
            % (after_by_id["myform_gramplet"],),
        )

        # File is sorted by (t, i).
        keys = [(e["t"], e["i"]) for e in after]
        self.assertEqual(
            keys,
            sorted(keys),
            "Output must remain sorted by (t, i); got %r" % (keys,),
        )


if __name__ == "__main__":
    unittest.main()
