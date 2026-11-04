"""Regression test for the requires_mod / is_active CI de-duplication.

ci.yml used to inline an identical ``requires_mod`` derivation heredoc in three
jobs and an identical ``is_active()`` bash helper in ~six job steps. The fix
moves the derivation into ``.github/scripts/addon_python_deps.py`` and the
helper into ``.github/scripts/active_addons.sh``, each consumed from one place.

This test pins two things, so the duplication cannot silently come back and the
refactor is proven behaviour-preserving:

1. Behaviour preservation — the single ``addon_python_deps`` module derives the
   *same* install union and the *same* raw declared-name set the old inline
   heredoc did (computed here by an independent oracle over the real tree).

2. The DRY invariant, stated per-category — NO inline ``is_active()`` definition
   and NO ``requires_mod`` heredoc survive in ci.yml, and EVERY job step that
   *calls* ``is_active`` sources the shared helper (a missed step is caught, not
   masked by an "at least one source" check).

Pure stdlib / GUI-import-free on purpose: it imports the production module the
ci.yml jobs call (not a copy), runs headless, and needs no gi / gramps.gui.
"""

from __future__ import annotations

import ast
import glob
import os
import re
import sys
import unittest
from unittest import mock

# Repo layout is fixed relative to this file: tests/ sits at the addons-source
# root, and the CI scripts live under .github/scripts/ — resolve both from
# __file__ so the test is cwd-independent (the C4 runner cd's into the repo, CI
# discover runs from the root).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.join(_REPO_ROOT, ".github", "scripts")
_CI_YML = os.path.join(_REPO_ROOT, ".github", "workflows", "ci.yml")
_HELPER = os.path.join(_SCRIPTS, "active_addons.sh")

if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

# Imported at module load: the production module the three ci.yml jobs invoke.
# With the fix reverted (module file removed) this import fails and every test
# below errors — the red half of the red->green contract.
import addon_python_deps  # noqa: E402

# --- independent oracle: the OLD inline heredoc algorithm, verbatim ----------
_OLD_RE = re.compile(r"requires_mod\s*=\s*(\[[^\]]*\])")
# Install-name map the heredoc lacked; install-only (find_spec gate stays raw).
_INSTALL_MAP = {"PIL": "Pillow"}


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _old_raw_union(root):
    mods = set()
    for fn in sorted(glob.glob(os.path.join(root, "*", "*.gpr.py"))):
        try:
            text = _read(fn)
        except OSError:
            continue
        for m in _OLD_RE.finditer(text):
            try:
                mods.update(ast.literal_eval(m.group(1)))
            except (ValueError, SyntaxError):
                pass
    return {m for m in mods if m}


def _ci_steps():
    """Yield each ci.yml step body as a string. A step starts at a 6-space
    `- ` line and runs until the next one (no YAML dependency needed)."""
    lines = _read(_CI_YML).splitlines(keepends=True)
    steps, cur = [], None
    for line in lines:
        if re.match(r"^      - ", line):
            if cur is not None:
                steps.append("".join(cur))
            cur = [line]
        elif cur is not None:
            cur.append(line)
    if cur is not None:
        steps.append("".join(cur))
    return steps


class RequiresModDerivationDedup(unittest.TestCase):
    """The derivation is single-sourced AND behaviour-preserving."""

    def test_install_list_matches_old_heredoc(self):
        old = _old_raw_union(_REPO_ROOT)
        expected = sorted(_INSTALL_MAP.get(m, m) for m in old)
        # Pin the import->distribution table to the LOCAL mirror for this
        # comparison. The oracle (_INSTALL_MAP) states the old heredoc's
        # behaviour plus the install-only map; production install_list() now
        # ALSO consults gramps' authoritative _IMPORT_TO_PYPI when a gramps
        # >= 6.1 is importable (the gramps61 lanes). Without this pin, an
        # upstream table gaining a mapping for a *declared* mod would flip this
        # oracle red for a change that is not a regression here. If that
        # happens: the GrampsTableSync guard reds first (re-sync the mirror in
        # addon_python_deps.py), then extend _INSTALL_MAP above to match.
        with mock.patch.object(
            addon_python_deps,
            "_distribution_map",
            return_value=dict(addon_python_deps._IMPORT_TO_DISTRIBUTION),
        ):
            self.assertEqual(addon_python_deps.install_list(_REPO_ROOT), expected)

    def test_declared_raw_names_match_old_heredoc(self):
        # The find_spec gate consumes RAW import names — these must equal the
        # old union exactly (the install map must NOT leak into them).
        self.assertEqual(
            addon_python_deps.declared_mods(_REPO_ROOT), _old_raw_union(_REPO_ROOT)
        )

    def test_install_map_is_install_only(self):
        # PIL maps to Pillow on the install side, but the raw declared-name set
        # never contains the distribution name (so Gramps' find_spec gate, which
        # the module's --check-resolves mirrors, keeps checking the import name).
        self.assertNotIn("Pillow", addon_python_deps.declared_mods(_REPO_ROOT))

    def test_no_requires_mod_heredoc_remains(self):
        # The previous assertion (re.findall(r"requires_mod\s*=\s*\(\[", ...))
        # was a tautology: the old inline heredoc's distinctive line was
        #   pat = re.compile(r"requires_mod\s*=\s*(\[[^\]]*\])")
        # whose text contains the LITERAL characters `\s*`, which the guard's
        # own `\s*` (matching whitespace) can never match — so it never bit,
        # and pasting the heredoc back in stayed green. Match the heredoc's
        # own literal fragments instead; both appear verbatim in the pre-dedup
        # ci.yml and in none of the current file.
        text = _read(_CI_YML)
        for fragment in ('re.compile(r"requires_mod', r"requires_mod\s*"):
            self.assertNotIn(
                fragment,
                text,
                "a requires_mod derivation heredoc still lives inline in ci.yml "
                f"(found {fragment!r})",
            )

    def test_three_jobs_consume_the_module(self):
        text = _read(_CI_YML)
        self.assertEqual(
            len(re.findall(r"addon_python_deps\.py --install-list", text)), 3
        )
        self.assertEqual(
            len(re.findall(r"addon_python_deps\.py --check-resolves", text)), 3
        )


class IsActiveHelperDedup(unittest.TestCase):
    """is_active() lives in one sourced helper, consumed by EVERY filtering step."""

    def test_helper_file_defines_is_active(self):
        self.assertTrue(os.path.isfile(_HELPER))
        self.assertIn("is_active()", _read(_HELPER))

    def test_no_inline_is_active_definition_remains(self):
        text = _read(_CI_YML)
        self.assertEqual(
            re.findall(r"is_active\(\)\s*\{", text),
            [],
            "an inline is_active() definition still lives in ci.yml",
        )

    def test_every_is_active_call_site_sources_the_helper(self):
        # Per-category invariant: every job step that CALLS is_active must also
        # source the shared helper. Asserting "sourced at least once" would miss
        # a step that calls a now-undefined is_active; this checks each site.
        calling = [s for s in _ci_steps() if re.search(r'is_active\s+"', s)]
        self.assertGreaterEqual(
            len(calling), 6, "expected >=6 active-addon filtering steps"
        )
        for step in calling:
            self.assertIn(
                "source .github/scripts/active_addons.sh",
                step,
                "a step calls is_active without sourcing active_addons.sh:\n" + step,
            )


if __name__ == "__main__":
    unittest.main()
