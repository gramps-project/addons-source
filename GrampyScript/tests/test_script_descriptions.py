"""
Consistency checks between scripts/*.gram.py and SCRIPT_DESCRIPTIONS.

script_descriptions.py has no GTK dependency (only gramps.gen.const), so
it can be imported directly here, unlike GrampyScript.py itself.
"""

import ast
import glob
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from script_descriptions import SCRIPT_DESCRIPTIONS
from update_script_descriptions import (
    DESCRIPTIONS_PATH,
    _load_header,
    build_source,
    collect_entries,
)

SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
)


def _script_basenames():
    return {
        os.path.basename(path)
        for path in glob.glob(os.path.join(SCRIPTS_DIR, "*.gram.py"))
    }


class TestScriptDescriptionsCoverage(unittest.TestCase):
    def test_every_script_has_a_description(self):
        missing = _script_basenames() - set(SCRIPT_DESCRIPTIONS)
        self.assertEqual(missing, set(), "scripts missing from SCRIPT_DESCRIPTIONS")

    def test_no_stale_entries(self):
        stale = set(SCRIPT_DESCRIPTIONS) - _script_basenames()
        self.assertEqual(stale, set(), "SCRIPT_DESCRIPTIONS keys with no matching file")

    def test_entries_have_title_and_description(self):
        for name, entry in SCRIPT_DESCRIPTIONS.items():
            self.assertEqual(len(entry), 2, name)
            title, description = entry
            self.assertTrue(title.strip(), "%s has an empty title" % name)
            self.assertTrue(description.strip(), "%s has an empty description" % name)


class TestScriptDescriptionsIsGenerated(unittest.TestCase):
    def test_regenerating_produces_no_changes(self):
        entries, errors = collect_entries()
        self.assertEqual(errors, [])
        header = _load_header(DESCRIPTIONS_PATH)
        regenerated = build_source(entries, header)
        on_disk = open(DESCRIPTIONS_PATH, encoding="utf-8").read()
        self.assertEqual(
            regenerated,
            on_disk,
            "script_descriptions.py is out of sync with scripts/*.gram.py -- "
            "run `python3 update_script_descriptions.py` to regenerate it.",
        )


class TestScriptsAreValidPython(unittest.TestCase):
    def test_all_scripts_parse(self):
        for path in glob.glob(os.path.join(SCRIPTS_DIR, "*.gram.py")):
            with self.subTest(path=path):
                ast.parse(open(path).read())


if __name__ == "__main__":
    unittest.main()
