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

"""The active-addon rule (include_in_listing) must be per-register and correct.

``active_addons.py`` replaced a file-granular grep with an ast parse. These
tests pin the semantics that make it *more correct* than the grep (per-register,
comment-proof, tolerant defaults) AND assert it is behaviour-identical to the
old grep rule over the real addon tree today — so the change ships proven
equivalent, and the first gpr that exercises the difference trips the oracle
test (a human then confirms the intent and updates the oracle), rather than
silently changing which addons CI gates on.

Pure stdlib; the bash integration test is skipped where bash is absent.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
_SCRIPTS = os.path.join(_REPO_ROOT, ".github", "scripts")
_HELPER_SH = os.path.join(_SCRIPTS, "active_addons.sh")

sys.path.insert(0, _SCRIPTS)
import active_addons as aa  # noqa: E402


class ActiveAddonSemantics(unittest.TestCase):
    """Per-register, comment-proof, tolerant classification."""

    def setUp(self) -> None:
        self.root = tempfile.mkdtemp(prefix="active_addons_")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _addon(self, name: str, gpr_body: str) -> str:
        d = os.path.join(self.root, name)
        os.makedirs(d, exist_ok=True)
        with open(
            os.path.join(d, f"{name.lower()}.gpr.py"), "w", encoding="utf-8"
        ) as fh:
            fh.write(gpr_body)
        return d

    def test_sibling_register_without_flag_is_active(self) -> None:
        # One register sets False, a sibling omits it (make.py default True) →
        # the addon IS built/released → active. (The old grep read this file as
        # inactive — the correctness bug this change fixes.)
        d = self._addon(
            "Mixed",
            'register(TOOL, id="a", include_in_listing=False)\n'
            'register(GRAMPLET, id="b")\n',
        )
        self.assertTrue(aa.addon_is_active(d))

    def test_all_registers_false_is_inactive(self) -> None:
        d = self._addon(
            "AllFalse",
            'register(TOOL, id="a", include_in_listing=False)\n'
            'register(GRAMPLET, id="b", include_in_listing=False)\n',
        )
        self.assertFalse(aa.addon_is_active(d))

    def test_explicit_true_is_active(self) -> None:
        d = self._addon("T", 'register(TOOL, id="a", include_in_listing=True)\n')
        self.assertTrue(aa.addon_is_active(d))

    def test_flag_only_in_comment_is_ignored(self) -> None:
        # A False in a comment must not flip an otherwise-listed addon inactive.
        d = self._addon(
            "Commented",
            "# include_in_listing=False  (historical note)\n"
            'register(GRAMPLET, id="a")\n',
        )
        self.assertTrue(aa.addon_is_active(d))

    def test_no_register_is_active(self) -> None:
        d = self._addon("NoReg", "PLUGINS = []  # descriptor with no register()\n")
        self.assertTrue(aa.addon_is_active(d))

    def test_unparsable_gpr_is_active(self) -> None:
        d = self._addon("Broken", "register(TOOL, id=  # truncated\n")
        self.assertTrue(aa.addon_is_active(d))

    def test_non_literal_flag_is_active(self) -> None:
        # A value we cannot evaluate statically must not be assumed False.
        d = self._addon(
            "Dynamic",
            'LISTED = True\nregister(GRAMPLET, id="a", include_in_listing=LISTED)\n',
        )
        self.assertTrue(aa.addon_is_active(d))

    def test_dir_without_gpr_not_listed(self) -> None:
        d = os.path.join(self.root, "NotAnAddon")
        os.makedirs(d)
        self.assertFalse(aa.addon_is_active(d))


class BehaviourIdentityWithOldGrep(unittest.TestCase):
    """The ast rule must match the old file-granular grep over the real tree."""

    @staticmethod
    def _old_grep_active(addon_dir: str) -> bool:
        # The exact rule active_addons.sh used to inline: per FILE, an
        # include_in_listing=True (anywhere) or the ABSENCE of any
        # include_in_listing= makes the addon active; else inactive.
        gprs = sorted(glob.glob(os.path.join(addon_dir, "*.gpr.py")))
        for gpr in gprs:
            with open(gpr, encoding="utf-8") as fh:
                text = fh.read()
            if re.search(r"include_in_listing[ \t]*=[ \t]*True", text):
                return True
            if not re.search(r"include_in_listing[ \t]*=", text):
                return True
        return False

    def test_ast_matches_grep_over_whole_tree(self) -> None:
        dirs = sorted(
            {
                os.path.dirname(g)
                for g in glob.glob(os.path.join(_REPO_ROOT, "*", "*.gpr.py"))
            }
        )
        self.assertGreater(len(dirs), 100, "addon tree not found from test location")
        diffs = [
            os.path.basename(d)
            for d in dirs
            if self._old_grep_active(d) != aa.addon_is_active(d)
        ]
        self.assertEqual(
            diffs,
            [],
            "active_addons.py disagrees with the old grep rule on: "
            f"{diffs}. This is the per-register/comment-proof semantic change "
            "biting a real addon for the first time — confirm the new (correct) "
            "classification is intended, then update this oracle to match.",
        )


@unittest.skipUnless(shutil.which("bash"), "bash not available")
class ShellHelperIntegration(unittest.TestCase):
    """active_addons.sh's is_active() must agree with active_addons.py."""

    def test_sourced_is_active_matches_check(self) -> None:
        root = tempfile.mkdtemp(prefix="active_addons_sh_")
        try:
            for name, body in (
                ("Active", 'register(GRAMPLET, id="a")\n'),
                ("Inactive", 'register(TOOL, id="a", include_in_listing=False)\n'),
            ):
                d = os.path.join(root, name)
                os.makedirs(d)
                with open(os.path.join(d, f"{name.lower()}.gpr.py"), "w") as fh:
                    fh.write(body)
            script = (
                f"source {_HELPER_SH}\n"
                "is_active Active && echo A:active || echo A:inactive\n"
                "is_active Inactive && echo I:active || echo I:inactive\n"
            )
            result = subprocess.run(
                ["bash", "-c", script],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertIn("A:active", result.stdout, result.stderr)
            self.assertIn("I:inactive", result.stdout, result.stderr)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
