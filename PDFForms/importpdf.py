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
import os
import re
import shutil
from datetime import datetime
from io import StringIO

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.config import config
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.db import DbTxn
from gramps.gen.errors import GrampsImportError
from gramps.gen.lib import Media, MediaRef
from gramps.gen.mime import get_type
from gramps.plugins.importer.importcsv import CSVParser

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

try:
    from importformpdf import _import_form_data as _import_form_data
    _IMPORTFORMPDF_AVAILABLE = True
except ImportError:
    _IMPORTFORMPDF_AVAILABLE = False

LOG = logging.getLogger(__name__)

_GRAMPS_ID_RE = re.compile(r"\[([^\]]+)\]")

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
for _n in range(2, 32):
    _GENDER[_n] = "male" if _n % 2 == 0 else "female"

# Marriage date/place field prefix for each couple (husband number → prefix).
_MARRIAGE_FIELD_BASE = {
    n: n for n in [1, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30]
}

# Couples: (husband_ahnentafel, wife_ahnentafel).
_COUPLES = [
    (1, 0),   # subject + spouse
    (2, 3),   (4, 5),   (6, 7),   (8, 9),
    (10, 11), (12, 13), (14, 15),
    (16, 17), (18, 19), (20, 21), (22, 23),
    (24, 25), (26, 27), (28, 29), (30, 31),
]

# For each couple, which child does the family produce?
_COUPLE_CHILD = {
    (2, 3): 1,
    (4, 5): 2,   (6, 7): 3,
    (8, 9): 4,   (10, 11): 5,  (12, 13): 6,  (14, 15): 7,
    (16, 17): 8, (18, 19): 9,  (20, 21): 10, (22, 23): 11,
    (24, 25): 12,(26, 27): 13, (28, 29): 14, (30, 31): 15,
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


def _compute_needed_unknowns(present_persons: set[int], max_person: int = 31) -> set[int]:
    """
    Return Ahnentafel numbers that are missing but lie on a path between two
    known people, and must therefore be added as Unknown persons to preserve
    connectivity.
    """
    needed: set[int] = set()
    for n in range(2, max_person + 1):
        if n in present_persons:
            continue

        has_known_descendant = False
        d = n // 2
        while d >= 1:
            if d in present_persons:
                has_known_descendant = True
                break
            d = d // 2
        if not has_known_descendant:
            continue

        stack = [2 * n, 2 * n + 1]
        found_ancestor = False
        while stack and not found_ancestor:
            a = stack.pop()
            if a > max_person:
                continue
            if a in present_persons:
                found_ancestor = True
            else:
                stack.extend([2 * a, 2 * a + 1])
        if found_ancestor:
            needed.add(n)

    return needed


def _build_csv(fields: dict, max_person: int = 31) -> tuple[str, int]:
    """
    Convert a normalised Ahnentafel field dict into a Gramps CSV string.

    Field keys expected: ``Name``, ``Spouse``, ``Father{n}``, ``Mother{n}``,
    ``Birth{n}``, ``BirthPlace{n}``, ``Death{n}``, ``DeathPlace{n}``,
    ``Marriage{n}``, ``MarriagePlace{n}``.

    Unknown placeholder persons are inserted only where needed to bridge
    gaps between two known people.
    """
    buf = StringIO()
    writer = csv.writer(buf, lineterminator="\n")

    # ------------------------------------------------------------------
    # Person table
    # ------------------------------------------------------------------
    writer.writerow(
        ["Person", "Firstname", "Surname", "Gender",
         "Birthdate", "Birthplace", "Deathdate", "Deathplace"]
    )

    present_persons: set[int] = set()
    person_refs: dict[int, str] = {}

    for n in [1] + list(range(2, max_person + 1)) + [0]:
        name_key = _name_field(n)
        full_name = fields.get(name_key, "")
        if not full_name:
            continue

        id_match = _GRAMPS_ID_RE.search(full_name)
        if id_match:
            ref = f"[{id_match.group(1)}]"
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
            ref, firstname, surname, _GENDER.get(n, "unknown"),
            fields.get(birth_key, "") if birth_key else "",
            fields.get(birthplace_key, "") if birthplace_key else "",
            fields.get(death_key, "") if death_key else "",
            fields.get(deathplace_key, "") if deathplace_key else "",
        ])
        present_persons.add(n)
        person_refs[n] = ref

    needed_unknowns = _compute_needed_unknowns(present_persons, max_person)
    effective_persons = present_persons | needed_unknowns

    for n in sorted(needed_unknowns):
        ref = _pid(n)
        person_refs[n] = ref
        writer.writerow([ref, "", "", _GENDER.get(n, "unknown"), "", "", "", ""])

    # ------------------------------------------------------------------
    # Marriage table
    # ------------------------------------------------------------------
    writer.writerow([])
    writer.writerow(["Marriage", "Husband", "Wife", "Date", "Place"])

    present_couples: list[tuple[int, int]] = []

    for husband, wife in _COUPLES:
        if wife == 0:
            if 0 not in present_persons or 1 not in effective_persons:
                continue
            h_ref = person_refs.get(husband, _pid(husband))
            w_ref = person_refs.get(wife, _pid(wife))
        else:
            if husband > max_person and wife > max_person:
                continue
            child_n = _COUPLE_CHILD.get((husband, wife))
            if husband not in effective_persons and wife not in effective_persons:
                continue
            if child_n not in effective_persons:
                continue
            h_ref = person_refs.get(husband, "") if husband in effective_persons else ""
            w_ref = person_refs.get(wife, "") if wife in effective_persons else ""

        base = _MARRIAGE_FIELD_BASE.get(husband, husband)
        date = fields.get(f"Marriage{base}", "")
        place = fields.get(f"MarriagePlace{base}", "")

        writer.writerow([_mid(husband, wife), h_ref, w_ref, date, place])
        present_couples.append((husband, wife))

    # ------------------------------------------------------------------
    # Family / child table
    # ------------------------------------------------------------------
    writer.writerow([])
    writer.writerow(["Family", "Child"])

    for couple in present_couples:
        child_n = _COUPLE_CHILD.get(couple)
        if child_n is not None and child_n in effective_persons:
            writer.writerow([_mid(*couple), person_refs[child_n]])

    return buf.getvalue(), len(present_persons)


# -------------------------------------------------------------------------
#
# Media helpers
#
# -------------------------------------------------------------------------


def _copy_to_media_dir(dbase, src_path):
    """Copy *src_path* into the database media directory; return stored path.

    The destination filename has a timestamp suffix so that multiple imports
    of the same form template produce distinct files.  If no media directory
    is configured, *src_path* is returned unchanged.
    """
    from gramps.gen.utils.file import media_path, relative_path

    base = media_path(dbase)
    if not base:
        return src_path

    os.makedirs(base, exist_ok=True)
    name, ext = os.path.splitext(os.path.basename(src_path))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(base, f"{name}_{stamp}{ext}")
    shutil.copy2(src_path, dest)
    return relative_path(dest, base)


def _add_media_refs(dbase, filename, person_handles, event_handles):
    """Copy the PDF to the media dir, create a Media record, and add MediaRefs."""
    stored_path = _copy_to_media_dir(dbase, filename)

    with DbTxn(_("Add media reference: PDF import"), dbase) as trans:
        media = Media()
        media.set_path(stored_path)
        media.set_mime_type(get_type(filename))
        media.set_description(os.path.basename(filename))
        dbase.add_media(media, trans)

        for handle in person_handles:
            person = dbase.get_person_from_handle(handle)
            ref = MediaRef()
            ref.set_reference_handle(media.handle)
            person.add_media_reference(ref)
            dbase.commit_person(person, trans)

        for handle in event_handles:
            event = dbase.get_event_from_handle(handle)
            ref = MediaRef()
            ref.set_reference_handle(media.handle)
            event.add_media_reference(ref)
            dbase.commit_event(event, trans)


# -------------------------------------------------------------------------
#
# Pedigree form importer
#
# -------------------------------------------------------------------------


def _import_pedigree_data(dbase, fields, user):
    """
    Import from a Gramps-generated Ahnentafel pedigree PDF.

    ``generate_pedigree_pdf.py`` uses the same field names that :func:`_build_csv`
    expects (``Name``, ``Father2``, ``Birth2``, ``BirthPlace2``, etc.), so the
    fields dict is passed directly with no translation.
    """
    form_id = fields.get("_form_id", "").strip()
    try:
        max_gen = int(form_id[len("pedigree"):])
    except (ValueError, IndexError):
        max_gen = 5
    max_person = 2 ** max_gen - 1

    csv_text, person_count = _build_csv(fields, max_person)
    LOG.debug("Generated pedigree CSV:\n%s", csv_text)

    if person_count == 0:
        user.notify_error(
            _("PDF import: no data found"),
            _("No names were found in the pedigree form.\n\n"
              "Fill in the form fields and try again."),
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

    filename = fields.get("_pdf_filename", "")
    persons_before = set(dbase.get_person_handles()) if filename else set()
    events_before = set(dbase.get_event_handles()) if filename else set()

    filehandle = StringIO(csv_text)
    msg = parser.parse(filehandle)
    if msg:
        user.notify_error(_("Bad references in PDF import"), msg)

    if filename:
        new_persons = set(dbase.get_person_handles()) - persons_before
        new_events = set(dbase.get_event_handles()) - events_before
        if new_persons or new_events:
            _add_media_refs(dbase, filename, new_persons, new_events)


# -------------------------------------------------------------------------
#
# Entry point
#
# -------------------------------------------------------------------------


def importData(dbase, filename, user):
    """Import genealogy data from a Gramps-generated fillable PDF form."""
    try:
        fields = _extract_fields(filename)
    except GrampsImportError as err:
        user.notify_error(_("PDF import error"), str(err))
        return

    fields["_pdf_filename"] = filename
    form_id = fields.get("_form_id", "").strip()

    if form_id.startswith("pedigree"):
        _import_pedigree_data(dbase, fields, user)
    elif form_id:
        if not _IMPORTFORMPDF_AVAILABLE:
            user.notify_error(
                _("Form importer unavailable"),
                _("importformpdf.py is missing from the PDFForms addon directory.")
            )
            return
        _import_form_data(dbase, fields, user)
    else:
        user.notify_error(
            _("PDF import: unrecognized format"),
            _("No Gramps form ID found in '%s'.\n\n"
              "Only PDFs generated by Gramps (pedigree or form templates) "
              "can be imported.") % filename,
        )
