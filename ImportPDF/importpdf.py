#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Douglas S. Blank
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

"""Import genealogy data from a filled-in Ahnentafel pedigree PDF form."""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
import csv
import logging
import re
from io import StringIO

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.config import config
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.errors import GrampsImportError
from gramps.plugins.importer.importcsv import CSVParser

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

LOG = logging.getLogger(__name__)

_GRAMPS_ID_RE = re.compile(r"^\[I\d+\]$")

# -------------------------------------------------------------------------
#
# Ahnentafel field map
#
# For each person number 1-15 this records which PDF field holds the name
# and which gender to assign.  Even numbers >= 2 are fathers (male); odd
# numbers >= 3 are mothers (female); person 1 is the subject (unknown).
# The special key 0 represents the spouse of person 1.
#
# Marriage data (date + place) lives on the even-numbered person of each
# couple, except that person 1's marriage data uses fields Marriage1 /
# MarriagePlace1.
#
# -------------------------------------------------------------------------
_GENDER = {0: "unknown", 1: "unknown"}
for _n in range(2, 16):
    _GENDER[_n] = "male" if _n % 2 == 0 else "female"

# Marriage date/place field prefix for each couple (husband number → prefix).
# Couple (1, spouse): date=Marriage1, place=MarriagePlace1
# Couple (2, 3):      date=Marriage2, place=MarriagePlace2
# …
_MARRIAGE_FIELD_BASE = {n: n for n in [1, 2, 4, 6, 8, 10, 12, 14]}

# Couples: (husband_ahnentafel, wife_ahnentafel).
# Couple 0 uses (1, 0) where 0 = Spouse.
_COUPLES = [
    (1, 0),   # subject + spouse
    (2, 3),   # parents of 1
    (4, 5),   # parents of 2
    (6, 7),   # parents of 3
    (8, 9),   # parents of 4
    (10, 11), # parents of 5
    (12, 13), # parents of 6
    (14, 15), # parents of 7
]

# For each couple, which child does the family produce?
# couple (2,3) → child p1, couple (4,5) → child p2, …
# couple (1, 0) has no ancestor child in the chart.
_COUPLE_CHILD = {
    (2, 3): 1,
    (4, 5): 2,
    (6, 7): 3,
    (8, 9): 4,
    (10, 11): 5,
    (12, 13): 6,
    (14, 15): 7,
}


# -------------------------------------------------------------------------
#
# Helper functions
#
# -------------------------------------------------------------------------


def _field_value(raw: str | None) -> str:
    """Return a stripped field value, or empty string if absent."""
    if raw is None:
        return ""
    return str(raw).strip()


def _name_field(n: int) -> str:
    """Return the PDF field name that holds person n's full name."""
    if n == 1:
        return "Name"
    if n == 0:
        return "Spouse"
    if n % 2 == 0:
        return f"Father{n}"
    return f"Mother{n}"


def _split_name(full: str) -> tuple[str, str]:
    """
    Split a full name into (firstname, surname).

    Accepts two formats (matching the DataEntryGramplet convention):
      "Surname, Given"  →  firstname="Given", surname="Surname"
      "Given Surname"   →  firstname="Given", surname="Surname" (last token)

    Single-token names are treated as surname only.
    """
    full = full.strip()
    if "," in full:
        surname, _, firstname = full.partition(",")
        return (firstname.strip(), surname.strip())
    parts = full.split()
    if not parts:
        return ("", "")
    if len(parts) == 1:
        return ("", parts[0])
    return (" ".join(parts[:-1]), parts[-1])


def _pid(n: int) -> str:
    """Return the CSV person reference for Ahnentafel number n."""
    if n == 0:
        return "pspouse"
    return f"p{n}"


def _mid(husband: int, wife: int) -> str:
    """Return the CSV marriage reference for a couple."""
    return f"m{husband}_{wife}"


# -------------------------------------------------------------------------
#
# PDF extraction
#
# -------------------------------------------------------------------------


def _extract_fields(filename: str) -> dict:
    """
    Read all AcroForm field values from a fillable PDF.

    Values are read from the page annotation objects directly, which is
    more reliable than get_fields() for PDFs saved by different viewers.

    :returns: dict mapping field name → string value.
    :raises GrampsImportError: if pypdf cannot open the file.
    """
    try:
        import pypdf
    except ImportError as exc:
        raise GrampsImportError(
            _("The pypdf package is required to import PDF pedigree forms.\n"
              "Install it with:  pip install pypdf")
        ) from exc

    try:
        reader = pypdf.PdfReader(filename)
    except Exception as exc:
        raise GrampsImportError(
            _("Could not open PDF file: %s") % str(exc)
        ) from exc

    fields: dict[str, str] = {}
    for page in reader.pages:
        annots_ref = page.get("/Annots")
        if annots_ref is None:
            continue
        for a in annots_ref.get_object():
            obj = a.get_object()
            name = obj.get("/T")
            value = obj.get("/V")
            if name is not None:
                fields[str(name)] = _field_value(value)
    return fields


# -------------------------------------------------------------------------
#
# CSV builder
#
# -------------------------------------------------------------------------


def _compute_needed_unknowns(present_persons: set[int]) -> set[int]:
    """
    Return Ahnentafel numbers that are missing but lie on a path between two
    known people, and must therefore be added as Unknown persons to preserve
    connectivity.

    Person n is needed when there is a known person in its descendant chain
    toward person 1 AND a known person in its ancestor subtree above it.
    Persons at the top generation (8-15) can never be needed unknowns because
    the chart contains no data above them.
    """
    needed: set[int] = set()
    for n in range(2, 16):
        if n in present_persons:
            continue

        # Walk down toward person 1; stop at the first known person found.
        has_known_descendant = False
        d = n // 2
        while d >= 1:
            if d in present_persons:
                has_known_descendant = True
                break
            d = d // 2
        if not has_known_descendant:
            continue

        # BFS upward from n through all ancestor positions up to 15.
        stack = [2 * n, 2 * n + 1]
        found_ancestor = False
        while stack and not found_ancestor:
            a = stack.pop()
            if a > 15:
                continue
            if a in present_persons:
                found_ancestor = True
            else:
                stack.extend([2 * a, 2 * a + 1])
        if found_ancestor:
            needed.add(n)

    return needed


def _build_csv(fields: dict) -> str:
    """
    Convert extracted PDF field values into a Gramps CSV string.

    Persons, marriages, and family/child relationships are written as
    separate tables separated by blank lines, matching the format expected
    by CSVParser.

    Unknown placeholder persons are inserted only where they are needed to
    bridge a gap between two known people.  A missing person at the leaf
    end of a lineage (no known ancestors above them) is simply omitted.
    """
    buf = StringIO()
    writer = csv.writer(buf, lineterminator="\n")

    # ------------------------------------------------------------------
    # Person table — filled-in people first, then needed unknowns
    # ------------------------------------------------------------------
    writer.writerow(
        ["Person", "Firstname", "Surname", "Gender",
         "Birthdate", "Birthplace", "Deathdate", "Deathplace"]
    )

    present_persons: set[int] = set()
    # Maps Ahnentafel number → the CSV person reference actually used,
    # either a local ref like "p2" or a Gramps ID like "[I0023]".
    person_refs: dict[int, str] = {}

    for n in [1] + list(range(2, 16)) + [0]:
        name_key = _name_field(n)
        full_name = fields.get(name_key, "")
        if not full_name:
            continue

        if _GRAMPS_ID_RE.match(full_name):
            # Caller pre-filled a Gramps ID — link to the existing record.
            ref = full_name
            firstname, surname = "", ""
        else:
            ref = _pid(n)
            firstname, surname = _split_name(full_name)

        if n == 0:
            birth_key = death_key = birthplace_key = deathplace_key = None
        else:
            birth_key = f"Birth{n}"
            birthplace_key = f"BirthPlace{n}"
            death_key = f"Death{n}"
            deathplace_key = f"DeathPlace{n}"

        writer.writerow([
            ref,
            firstname,
            surname,
            _GENDER[n],
            fields.get(birth_key, "") if birth_key else "",
            fields.get(birthplace_key, "") if birthplace_key else "",
            fields.get(death_key, "") if death_key else "",
            fields.get(deathplace_key, "") if deathplace_key else "",
        ])
        present_persons.add(n)
        person_refs[n] = ref

    needed_unknowns = _compute_needed_unknowns(present_persons)
    effective_persons = present_persons | needed_unknowns

    for n in sorted(needed_unknowns):
        ref = _pid(n)
        person_refs[n] = ref
        writer.writerow([ref, "", "", _GENDER[n], "", "", "", ""])

    # ------------------------------------------------------------------
    # Marriage table
    # ------------------------------------------------------------------
    writer.writerow([])  # blank line between tables
    writer.writerow(["Marriage", "Husband", "Wife", "Date", "Place"])

    present_couples: list[tuple[int, int]] = []

    for husband, wife in _COUPLES:
        # Couple (1, spouse): only include when the spouse is actually present.
        if wife == 0:
            if 0 not in present_persons or 1 not in effective_persons:
                continue
            h_ref = person_refs.get(husband, _pid(husband))
            w_ref = person_refs.get(wife, _pid(wife))
        else:
            child_n = _COUPLE_CHILD.get((husband, wife))
            # Skip if neither parent is known and no child needs them.
            if husband not in effective_persons and wife not in effective_persons:
                continue
            if child_n not in effective_persons:
                continue
            h_ref = person_refs.get(husband, "") if husband in effective_persons else ""
            w_ref = person_refs.get(wife, "") if wife in effective_persons else ""

        # Marriage date/place live on the even-numbered person's fields.
        base = _MARRIAGE_FIELD_BASE.get(husband, husband)
        date = fields.get(f"Marriage{base}", "")
        place = fields.get(f"MarriagePlace{base}", "")

        writer.writerow([_mid(husband, wife), h_ref, w_ref, date, place])
        present_couples.append((husband, wife))

    # ------------------------------------------------------------------
    # Family / child table
    # ------------------------------------------------------------------
    writer.writerow([])  # blank line between tables
    writer.writerow(["Family", "Child"])

    for couple in present_couples:
        child_n = _COUPLE_CHILD.get(couple)
        if child_n is not None and child_n in effective_persons:
            writer.writerow([_mid(*couple), person_refs[child_n]])

    return buf.getvalue(), len(present_persons)


# -------------------------------------------------------------------------
#
# Entry point
#
# -------------------------------------------------------------------------


def importData(dbase, filename, user):
    """
    Import genealogy data from a filled-in Ahnentafel pedigree PDF form.

    Extracts AcroForm fields from *filename*, converts them to Gramps CSV
    format, and delegates to CSVParser for the actual database import.
    """
    try:
        fields = _extract_fields(filename)
    except GrampsImportError as err:
        user.notify_error(_("PDF import error"), str(err))
        return

    csv_text, person_count = _build_csv(fields)
    LOG.debug("Generated CSV:\n%s", csv_text)

    if person_count == 0:
        user.notify_error(
            _("PDF import: no data found"),
            _("No names were found in '%s'.\n\n"
              "This may be the blank template. Fill in the form fields "
              "and try again.") % filename,
        )
        return

    if dbase.get_feature("skip-import-additions"):
        parser = CSVParser(dbase, user, None)
    else:
        tag_format = (
            config.get("preferences.tag-on-import-format")
            if config.get("preferences.tag-on-import")
            else None
        )
        parser = CSVParser(dbase, user, tag_format)

    filehandle = StringIO(csv_text)
    msg = parser.parse(filehandle)
    if msg:
        user.notify_error(_("Bad references in PDF import"), msg)
