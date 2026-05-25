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
Repro-or-close test for bug 13420: Text Import gramplet death event
is not shown as the person's death fallback until re-validated in the
editor.

The reporter's input was XML produced by a no-code Android tool with
UUID handles and longer-than-normal change-times; no developer
reproduced the symptom on conformant Gramps XML. Per the triage
verdict in `triage/batches/batch-03-confirmed-velocity/issue_13420.md`
the decisive test is:

  - Build CONFORMANT minimal Gramps XML (one person, Birth + Death
    events both role Primary, standard Gramps handles)
  - Import via the addon's `AtomicGrampsParser` (the wrapper the
    ImportGramplet uses for its XML branch)
  - Assert person.get_death_ref() returns the Death event ref
    WITHOUT manual editor re-save

If clean XML imports correctly → reporter's XML was malformed; close
13420 as cannot-reproduce. If clean XML still fails → real addon bug,
fix needed.

The fallback-setting logic lives in gramps CORE at
`gramps/plugins/importer/importxml.py:1434-1473` (`start_eventref`)
and is shared between the standard XML import and AtomicGrampsParser
(AtomicGrampsParser only overrides `parse()` for an atomic DbTxn
wrapper, not the per-element handlers). The note above
`start_eventref` itself spells out the precondition: "We count here
on events being already parsed prior to parsing people or families.
This code will fail if this is not true." So the test fixture lists
events BEFORE people.
"""

import os
import shutil
import sys
import tempfile
import unittest

# AtomicGrampsParser pulls `from gi.repository import Gtk` at module
# load (via ImportGramplet.py). Pin Gtk to 3.0 before importing; skip
# cleanly if PyGObject / GTK 3 aren't available.
try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
except (ImportError, ValueError) as err:
    raise unittest.SkipTest("GTK 3.0 / PyGObject not available: %s" % err)

# Make sure addon modules are importable from the parent directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Minimal CONFORMANT Gramps XML. Events listed before people, both
# events role Primary, standard Gramps handles (no UUIDs). Mirrors
# the structure in `example/gramps/example.gramps`.
CLEAN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE database PUBLIC "-//Gramps//DTD Gramps XML 1.7.2//EN"
"http://gramps-project.org/xml/1.7.2/grampsxml.dtd">
<database xmlns="http://gramps-project.org/xml/1.7.2/">
  <header>
    <created date="2026-05-25" version="6.0.0"/>
    <researcher>
      <resname>Bug 13420 Test</resname>
    </researcher>
  </header>
  <events>
    <event handle="_a5af0eb667015e355db" change="1284030602" id="E00001">
      <type>Birth</type>
      <dateval val="1900-01-01"/>
      <description>Birth of Test, Person</description>
    </event>
    <event handle="_a5af0eb696917232725" change="1284030602" id="E00002">
      <type>Death</type>
      <dateval val="1970-12-31"/>
      <description>Death of Test, Person</description>
    </event>
  </events>
  <people>
    <person handle="_aaa0bbb111ccc222ddd" change="1284030602" id="I00001">
      <gender>M</gender>
      <name type="Birth Name">
        <first>Person</first>
        <surname>Test</surname>
      </name>
      <eventref hlink="_a5af0eb667015e355db" role="Primary"/>
      <eventref hlink="_a5af0eb696917232725" role="Primary"/>
    </person>
  </people>
</database>
"""


class TestImportGrampletDeathFallback(unittest.TestCase):
    """Repro-or-close for bug 13420."""

    def setUp(self):
        # Per Sqlite/tests/test_sqlite.py: create a sqlite in-memory-
        # equivalent db in a tempdir, import the XML, exercise.
        from gramps.gen.db.utils import make_database  # pylint: disable=import-outside-toplevel

        self.db_dir = tempfile.mkdtemp(prefix="bug13420_")
        self.database = make_database("sqlite")
        self.database.load(self.db_dir)

    def tearDown(self):
        try:
            self.database.close()
        except Exception:  # pylint: disable=broad-except
            pass
        shutil.rmtree(self.db_dir, ignore_errors=True)

    def test_clean_xml_imports_set_death_ref_via_atomic_parser(self):
        """Clean XML through AtomicGrampsParser must set the
        person's death_ref to the Death event.

        This is the repro-or-close decision point for bug 13420.
        If it passes, the reporter's malformed XML (UUID handles)
        was the cause; if it fails, the addon's atomic parser is
        skipping the fallback wiring.
        """
        from io import BytesIO  # pylint: disable=import-outside-toplevel
        import time  # pylint: disable=import-outside-toplevel
        from gramps.cli.user import User  # pylint: disable=import-outside-toplevel

        # Importing the addon transitively imports Gtk -- this is why
        # the test is gated above on gi.require_version("Gtk", "3.0").
        from ImportGramplet.ImportGramplet import AtomicGrampsParser  # pylint: disable=import-outside-toplevel

        user = User()
        change = int(time.time())
        parser = AtomicGrampsParser(self.database, user, change)
        ifile = BytesIO(CLEAN_XML.encode("utf-8"))
        parser.parse(ifile)

        person = self.database.get_person_from_gramps_id("I00001")
        self.assertIsNotNone(
            person,
            "Person I00001 must exist after XML import",
        )

        death_ref = person.get_death_ref()
        self.assertIsNotNone(
            death_ref,
            "Person.get_death_ref() must return the Death event ref "
            "after clean-XML import via AtomicGrampsParser. If this "
            "assertion fails, bug 13420 reproduces on conformant XML "
            "and is a real addon defect.",
        )

        death_event = self.database.get_event_from_handle(death_ref.ref)
        self.assertIsNotNone(death_event)
        self.assertEqual(str(death_event.get_type()), "Death")

        # Birth ref must also be wired up -- same logic in core
        # start_eventref. If birth is fine but death is not, the bug
        # is type-specific; if both fail, it's the whole fallback
        # path.
        birth_ref = person.get_birth_ref()
        self.assertIsNotNone(birth_ref)
        birth_event = self.database.get_event_from_handle(birth_ref.ref)
        self.assertEqual(str(birth_event.get_type()), "Birth")


if __name__ == "__main__":
    unittest.main()
