#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Kevin White
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""GWizard Media Fix tool: Find missing media, consolidate media locations, and apply filename standards."""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
from __future__ import annotations
import difflib
import hashlib
import logging
import os
import re
from typing import Any

# -------------------------------------------------------------------------
#
# GTK modules
#
# -------------------------------------------------------------------------
from gi.repository import Gtk

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.config import config
from gramps.gen.const import GRAMPS_LOCALE as glocale, USER_HOME, USER_PICTURES
from gramps.gen.db import DbReadBase, DbTxn, DbWriteBase
from gramps.gen.types import EventHandle, MediaHandle, PersonHandle
from gramps.gen.utils.db import get_birth_or_fallback, get_death_or_fallback
from gramps.gen.utils.file import expand_path, media_path, media_path_full
from gramps.gui.dialog import OkDialog, QuestionDialog2
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.plug import tool

# -------------------------------------------------------------------------
#
# GWizard modules
#
# -------------------------------------------------------------------------
try:
    from gwizard_common import (
        SelectableLabel,
        TableLabel,
        HeaderLabel,
        create_table_grid,
        clean_path,
        is_absolute_path,
        path_key,
        to_db_path,
        unique_destination,
        relocate_file,
        build_basename_index,
        MoveLog,
        MOVE_LOG_NAME,
        undo_logged_run,
        last_logged_run,
        read_move_log,
        escape_markup,
        full_media_path,
        is_bare_media,
        has_media_fixed_tag,
        add_media_fixed_tag,
    )
except (ImportError, ValueError):
    from gwizard_common import (  # type: ignore[import-not-found,no-redef]
        SelectableLabel,
        TableLabel,
        HeaderLabel,
        create_table_grid,
        clean_path,
        is_absolute_path,
        path_key,
        to_db_path,
        unique_destination,
        relocate_file,
        build_basename_index,
        MoveLog,
        MOVE_LOG_NAME,
        undo_logged_run,
        last_logged_run,
        read_move_log,
        escape_markup,
        full_media_path,
        is_bare_media,
        has_media_fixed_tag,
        add_media_fixed_tag,
    )

try:
    from gw_fixmediareferencesdialog import (
        FixMediaReferencesDialog,
        find_duplicate_media_groups,
    )
except (ImportError, ValueError):
    from gw_fixmediareferencesdialog import (  # type: ignore[import-not-found,no-redef]
        FixMediaReferencesDialog,
        find_duplicate_media_groups,
    )

_ = glocale.translation.sgettext
ngettext = glocale.translation.ngettext
LOG = logging.getLogger(__name__)

CONFIG_TEMPLATE_KEY = "preferences.gwizardmediafix-filename-template"
DEFAULT_FILENAME_TEMPLATE = "{ref_id}_{surname}_{given}-{doc_type}-{year}.{ext}"
config.register(CONFIG_TEMPLATE_KEY, DEFAULT_FILENAME_TEMPLATE)

FILENAME_PRESETS: list[tuple[str, str]] = [
    (
        "{ref_id}_{surname}_{given}-{doc_type}-{year}.{ext}",
        _(
            "Reference ID + Community Standard ({ref_id}_{surname}_{given}-{doc_type}-{year})"
        ),
    ),
    (
        "{surname}_{given}-{doc_type}-{year}.{ext}",
        _("Community Standard ({surname}_{given}-{doc_type}-{year})"),
    ),
    (
        "{ref_id}_{doc_type}-{year}.{ext}",
        _("Reference ID + Document Type ({ref_id}_{doc_type}-{year})"),
    ),
    (
        "{id}_{doc_type}-{year}.{ext}",
        _("Media ID + Document Type ({id}_{doc_type}-{year})"),
    ),
    (
        "{id}_{orig}.{ext}",
        _("Media ID + Original Name ({id}_{orig})"),
    ),
    (
        "{orig}.{ext}",
        _("Sanitized Original Name ({orig})"),
    ),
    (
        "{ref_id}_{surname}_{given}-{doc_type}-{year}-{hash}.{ext}",
        _("Community Standard + content hash (never clashes for different files)"),
    ),
]


# ------------------------------------------------------------
#
# Helper utilities for media analysis
#
# ------------------------------------------------------------
def get_path_ancestors(path: str) -> list[str]:
    """Return all ancestors of a path from root down to the target path."""
    clean_p = clean_path(path)
    if not clean_p:
        return []
    norm = os.path.normpath(os.path.abspath(clean_p))
    parts: list[str] = []
    curr = norm
    while True:
        parts.append(curr)
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent
    parts.reverse()
    return parts


def check_path_permission(path: str) -> tuple[bool, str | None]:
    """Check if a path or any of its parent directories has permission denied.

    Walks from the root directory downwards to identify the highest-level directory
    which cannot be read.

    :returns: ``(has_permission_issue, highest_inaccessible_dir_or_file)``
    """
    clean_p = clean_path(path)
    if not clean_p:
        return False, None

    ancestors = get_path_ancestors(clean_p)
    for comp in ancestors:
        try:
            try:
                st = os.stat(comp)
            except PermissionError:
                return True, comp
            except FileNotFoundError:
                continue
            except OSError as err:
                if getattr(err, "winerror", None) == 5 or err.errno in (13, 1):
                    return True, comp
                continue

            # Stat succeeded, so comp exists on disk. Now verify read access:
            if not os.access(comp, os.R_OK):
                return True, comp

            import stat as _stat

            if _stat.S_ISDIR(st.st_mode):
                try:
                    with os.scandir(comp):
                        pass
                except PermissionError:
                    return True, comp
                except OSError as err:
                    if getattr(err, "winerror", None) == 5 or err.errno in (13, 1):
                        return True, comp
            else:
                try:
                    with open(comp, "rb") as f:
                        f.read(1)
                except PermissionError:
                    return True, comp
                except OSError as err:
                    if getattr(err, "winerror", None) == 5 or err.errno in (13, 1):
                        return True, comp
        except PermissionError:
            return True, comp
        except (OSError, ValueError):
            pass

    return False, None


def expand_base_path(mpath: str | None, db: DbReadBase | None = None) -> str:
    """
    Resolve a base media path string exactly the way Gramps does.

    This mirrors ``gramps.gen.utils.file.expand_media_path`` so the folder the
    tool shows, searches and moves files into is the folder Gramps will use
    to open relative media paths:

    - not set (``None``): the user's Pictures folder (``USER_PICTURES``);
    - ``{VAR}`` placeholders are expanded (Gramps' ``expand_path``); ``~`` and
      ``$VAR`` are *not*, because Gramps does not expand them either;
    - a relative path is relative to the family tree's own folder.

    The one difference: surrounding quotes are stripped, as the tool already
    strips them when it saves a base path.  Unlike Gramps the result keeps its
    letter case (compare paths with :func:`path_key`).

    :param mpath: The base media path setting (``db.get_mediapath()``).
    :param db: The database, for the family tree's folder.
    :returns: An absolute, normalised directory path.
    """
    if mpath is None:
        return os.path.normpath(os.path.abspath(USER_PICTURES))
    path = clean_path(mpath)
    try:
        path = expand_path(path, False)
    except Exception:  # a stray "{" in the path; Gramps would fail too
        pass
    if not os.path.isabs(path):
        basepath = None
        if db is not None and hasattr(db, "get_save_path"):
            try:
                basepath = db.get_save_path()
            except Exception:
                basepath = None
        path = os.path.join(os.path.abspath(basepath or USER_HOME), path)
    return os.path.normpath(os.path.abspath(path))


def get_media_base_path(db: DbReadBase | None) -> str:
    """
    Return the folder Gramps resolves relative media paths against.

    See :func:`expand_base_path`.  (This used to fall back to the home folder
    while Gramps falls back to Pictures, so the tool could store a relative
    path that Gramps could not open.)

    :param db: The database (or ``None``).
    :returns: The base media directory.
    """
    mpath: str | None = None
    if db is not None and hasattr(db, "get_mediapath"):
        try:
            mpath = db.get_mediapath()
        except Exception:
            mpath = None
    return expand_base_path(mpath, db)


def is_in_default_path(raw_path: str, base_dir: str) -> bool:
    """Check if a raw path is located within the base/default media directory."""
    clean_raw = clean_path(raw_path)
    clean_base = clean_path(base_dir)
    if not clean_raw or not clean_base:
        return False
    if not is_absolute_path(clean_raw):
        # Relative paths resolve against base_dir, unless they climb out of it.
        return ".." not in re.split(r"[\\/]+", clean_raw)
    try:
        norm_raw = os.path.normcase(os.path.normpath(os.path.abspath(clean_raw)))
        norm_base = os.path.normcase(os.path.normpath(os.path.abspath(clean_base)))
        return os.path.commonpath([norm_raw, norm_base]) == norm_base
    except Exception:
        return False


def find_unreferenced_default_path_files(
    db: DbReadBase,
    base_dir: str,
    max_scan_files: int = 5000,
    stats: dict[str, Any] | None = None,
) -> list[str]:
    """Scan base_dir for multimedia files with no connection to database media objects.

    Returns a sorted list of file paths relative to base_dir.
    """
    if not base_dir or not os.path.isdir(base_dir) or not db:
        return []

    # Collect all normalized file paths referenced in the database
    db_media_paths: set[str] = set()
    for media in db.iter_media():
        raw_paths: list[str] = [str(media.get_path() or "")]

        for raw_path in raw_paths:
            raw_path = raw_path.strip()
            if not raw_path:
                continue
            try:
                full_path = media_path_full(db, raw_path)
                db_media_paths.add(
                    os.path.normcase(os.path.normpath(os.path.abspath(full_path)))
                )
            except Exception:
                pass
            if not is_absolute_path(raw_path) and base_dir:
                try:
                    db_media_paths.add(
                        os.path.normcase(
                            os.path.normpath(
                                os.path.abspath(os.path.join(base_dir, raw_path))
                            )
                        )
                    )
                except Exception:
                    pass

    multimedia_exts = {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".tif",
        ".tiff",
        ".webp",
        ".svg",
        ".ico",
        ".pdf",
        ".mp3",
        ".wav",
        ".ogg",
        ".flac",
        ".m4a",
        ".aac",
        ".wma",
        ".mp4",
        ".avi",
        ".mov",
        ".wmv",
        ".mkv",
        ".webm",
        ".mpg",
        ".mpeg",
        ".txt",
        ".rtf",
        ".doc",
        ".docx",
        ".odt",
    }

    skip_dirs = {
        ".git",
        ".svn",
        ".hg",
        ".cache",
        "node_modules",
        "venv",
        ".venv",
        "appdata",
        "application data",
        "local settings",
        "windows",
        "program files",
        "program files (x86)",
        "system volume information",
        "$recycle.bin",
        ".local",
        ".config",
        ".thumbnails",
    }

    norm_base = os.path.normcase(os.path.normpath(os.path.abspath(base_dir)))
    norm_user_home = os.path.normcase(os.path.normpath(os.path.abspath(USER_HOME)))
    is_user_home = norm_base == norm_user_home
    if is_user_home:
        skip_dirs.update(
            {
                "downloads",
                "desktop",
                "documents",
                "music",
                "videos",
                "onedrive",
                "contacts",
                "searches",
                "saved games",
                "3d objects",
            }
        )

    unreferenced: list[str] = []
    scanned_count = 0

    for root, dirs, files in os.walk(base_dir):
        rel_to_base = os.path.relpath(root, base_dir)
        depth = (
            0 if rel_to_base == "." else len(rel_to_base.replace("\\", "/").split("/"))
        )
        if is_user_home and depth > 1:
            dirs.clear()
            continue

        dirs[:] = [
            d for d in dirs if not d.startswith(".") and d.lower() not in skip_dirs
        ]

        for fname in files:
            if fname.startswith("."):
                continue
            _base, ext = os.path.splitext(fname)
            if ext.lower() not in multimedia_exts:
                continue

            full_file = os.path.join(root, fname)
            norm_file = os.path.normcase(os.path.normpath(os.path.abspath(full_file)))
            if norm_file not in db_media_paths:
                try:
                    rel_path = os.path.relpath(full_file, base_dir).replace("\\", "/")
                except Exception:
                    rel_path = full_file
                unreferenced.append(rel_path)

            scanned_count += 1
            if scanned_count >= max_scan_files:
                if stats is not None:
                    stats["truncated"] = True
                break
        if scanned_count >= max_scan_files:
            break

    unreferenced.sort()
    return unreferenced


def find_in_media_dir(
    base_dir: str, basename: str, index: dict[str, list[str]] | None
) -> str:
    """Return a DB-style path for basename found in base_dir, or "".

    With an index (recursive search) the match must be unique; otherwise only
    the top level of base_dir is checked.
    """
    if not base_dir or not basename:
        return ""
    if index is not None:
        hits = index.get(basename.lower(), [])
        return to_db_path(hits[0], base_dir) if len(hits) == 1 else ""
    flat = os.path.join(base_dir, basename)
    return basename if os.path.exists(flat) else ""


def ambiguous_matches(
    candidates: list[tuple[MediaHandle, str, str]],
) -> set[MediaHandle]:
    """Return the handles whose suggested file is also wanted by another record.

    Matching a missing file by name alone is only safe when every record that
    is pointed at the found file had the same original path.  Two different
    records ("C:/Smith/scan1.jpg" and "D:/Jones/scan1.jpg") that both match
    one "scan1.jpg" would otherwise be repointed at the same file and then
    merged as duplicates, so neither is changed automatically.

    :param candidates: (handle, original_raw_path, suggested_path) triples.
    :returns: The handles that must not be repointed automatically.
    """
    origins: dict[str, set[str]] = {}
    for _handle, raw, found in candidates:
        origins.setdefault(path_key(found), set()).add(path_key(raw))
    return {
        handle
        for handle, _raw, found in candidates
        if len(origins[path_key(found)]) > 1
    }


def media_dir_index(db: DbReadBase, base_dir: str) -> dict[str, list[str]] | None:
    """Recursive file index of base_dir, only when the user configured a media
    base path (never walk the whole home folder by accident)."""
    try:
        configured = bool((db.get_mediapath() or "").strip())
    except Exception:
        configured = False
    if configured and base_dir and os.path.isdir(base_dir):
        return build_basename_index(base_dir)
    return None


def scan_unreadable_media(
    db: DbReadBase,
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str, str]]]:
    """Classify every media record whose file cannot be opened *right now*.

    Returns (missing, permission_denied).  Run it after all fix steps so that
    records merged away earlier are not reported and each file is reported once,
    under the correct reason.
    """
    missing: list[tuple[str, str, str]] = []
    denied: list[tuple[str, str, str, str]] = []
    for media in list(db.iter_media()):
        raw = str(media.get_path() or "")
        clean_raw = clean_path(raw)
        if not clean_raw:
            continue
        gid = str(media.get_gramps_id() or "")
        desc = str(media.get_description() or "")
        try:
            full = media_path_full(db, clean_raw)
        except Exception:
            full = clean_raw
        if os.path.exists(full) or (
            is_absolute_path(clean_raw) and os.path.exists(clean_raw)
        ):
            continue
        perm, where = check_path_permission(full)
        if not perm and is_absolute_path(clean_raw):
            perm, where = check_path_permission(clean_raw)
        if perm and where:
            denied.append((gid, desc, raw, where))
        else:
            missing.append((gid, desc, raw))
    return missing, denied


def clean_token(val: Any) -> str:
    """Sanitize an individual token value to contain only alphanumeric characters, underscores, and hyphens."""
    if not val:
        return ""
    s = re.sub(r"[\s_]*-+[\s_]*", "-", str(val))
    clean = re.sub(r"[^\w\-]+", "_", s)
    clean = re.sub(r"_+", "_", clean)
    clean = re.sub(r"[-_]*-[_\s-]*", "-", clean)
    clean = re.sub(r"-+", "-", clean)
    return clean.strip("_-")


def parse_name_from_text(text: str) -> tuple[str, str, str]:
    """Parse 'Surname, Given - Rest' or 'Surname, Given_Rest' from text."""
    if not text:
        return "", "", ""
    m = re.match(
        r"^\s*((?:[^\W\d_]|[\s'\-])+?)\s*,\s*((?:[^\W\d_]|[\s'\-])+?)\s*[-_:]+\s*(.+)$",
        text,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    return "", "", text


def extract_year_and_clean_doctype(
    doc_type: str, surname: str = "", given: str = ""
) -> tuple[str, str]:
    """Extract 4-digit document year and strip redundant person names from doc_type."""
    if not doc_type:
        return "", ""

    year = ""
    y_match = re.search(r"(?:^|[^\d])(1[5-9]\d{2}|20\d{2})(?:[^\d]|$)", doc_type)
    if y_match:
        year = y_match.group(1)
        doc_type = doc_type[: y_match.start(1)] + " " + doc_type[y_match.end(1) :]

    # Strip any leading 'Surname, Given -' pattern from doc_type
    sur_giv_m = re.match(
        r"^\s*(?:[^\W\d_]|[\s'\-])+?,\s*(?:[^\W\d_]|[\s'\-])+?\s*[-_:]+\s*(.+)$",
        doc_type,
    )
    if sur_giv_m:
        doc_type = sur_giv_m.group(1)

    if surname:
        pats = (
            [
                rf"(?i)^\s*{re.escape(surname)}\s*,\s*{re.escape(given)}\s*[-_:]*\s*",
                rf"(?i)^\s*{re.escape(given)}\s+{re.escape(surname)}\s*[-_:]*\s*",
                rf"(?i)^\s*{re.escape(surname)}\s*[-_:]*\s*",
                rf"(?i)[-_:]*\s*{re.escape(surname)}\s*,\s*{re.escape(given)}\s*$",
                rf"(?i)[-_:]*\s*{re.escape(surname)}\s*$",
            ]
            if given
            else [rf"(?i)^\s*{re.escape(surname)}\s*[-_:]*\s*"]
        )
        for pat in pats:
            doc_type = re.sub(pat, "", doc_type)

    clean = re.sub(r"[^\w\-]+", "_", doc_type)
    clean = re.sub(r"[\s_]*-+[\s_]*", "-", clean)
    clean = re.sub(r"[-_]*-[_\s-]*", "-", clean)
    clean = re.sub(r"_+", "_", clean).strip("_-")
    return clean, year


def _norm_name(text: Any) -> str:
    """
    Normalise a name for comparison: letters and digits only, case-folded.

    :param text: Any name text.
    :returns: The comparison key.
    """
    return re.sub(r"\W+", "", str(text or "")).casefold()


def _db_get(db: DbReadBase, cname: str, handle: str) -> Any:
    """
    Fetch a primary object by class name and handle, or ``None``.

    :param db: The database.
    :param cname: Class name as used in backlinks, e.g. ``"Person"``.
    :param handle: The object's handle.
    :returns: The object, or ``None`` if it cannot be fetched.
    """
    getter = getattr(db, "get_%s_from_handle" % cname.lower(), None)
    try:
        return getter(handle) if getter else None
    except Exception:
        return None


def _persons_of(db: DbReadBase, cname: str, handle: str, _depth: int = 0) -> list[Any]:
    """People reachable from a backlink: the person itself, the participants of
    an event or family, or whoever a citation is attached to."""
    obj = _db_get(db, cname, handle)
    if obj is None or _depth > 3:
        return []
    if cname == "Person":
        return [obj]
    found: list[Any] = []
    if cname == "Family":
        for h in (obj.get_father_handle(), obj.get_mother_handle()):
            p = _db_get(db, "Person", h) if h else None
            if p is not None:
                found.append(p)
    elif cname in ("Event", "Citation"):
        try:
            owners = list(db.find_backlink_handles(handle))
        except Exception:
            owners = []
        for c2, h2 in owners:
            if c2 in ("Person", "Family", "Event"):
                found.extend(_persons_of(db, c2, h2, _depth + 1))
    return found


def _person_matches(person: Any, surname: str, given: str) -> bool:
    """
    Return True if a person's primary name matches a surname and given name.

    Given names match when one starts with the other ("Harry" / "Harry Jay").

    :param person: The person.
    :param surname: Surname to match.
    :param given: Given name to match (may be empty).
    :returns: Whether the names match.
    """
    name = person.get_primary_name()
    if not name or not surname:
        return False
    if _norm_name(name.get_surname()) != _norm_name(surname):
        return False
    pg, dg = _norm_name(name.get_first_name()), _norm_name(given)
    return not dg or pg.startswith(dg) or dg.startswith(pg)


def _gid_of(obj: Any) -> str:
    """
    Return an object's Gramps ID as a string, for stable sorting.

    :param obj: Any Gramps primary object.
    :returns: The Gramps ID, or ``""``.
    """
    return str(obj.get_gramps_id() or "")


def _name_score(person: Any, surname: str, given: str) -> float:
    """
    Score how well a person matches the name written in a description.

    An exact (normalised) match scores 2.0; a close surname spelling variant
    ("Duvault" for "Devault") with a compatible given name scores the surname
    similarity (0.75 - 1.0); anything else scores 0.0.

    :param person: The candidate person.
    :param surname: Surname parsed from the description.
    :param given: Given name parsed from the description.
    :returns: The match score.
    """
    if _person_matches(person, surname, given):
        return 2.0
    pname = person.get_primary_name()
    if not pname or not surname:
        return 0.0
    ratio = difflib.SequenceMatcher(
        None, _norm_name(surname), _norm_name(pname.get_surname())
    ).ratio()
    if ratio < 0.75:
        return 0.0
    pg, dg = _norm_name(pname.get_first_name()), _norm_name(given)
    return ratio if (not dg or pg.startswith(dg) or dg.startswith(pg)) else 0.0


def _best_person(db: DbReadBase, handles: list[PersonHandle], text: str) -> Any:
    """
    Choose the person a media file is *of* from several candidates.

    A census event is usually shared by a whole household, so "the first
    participant" depends on database order and is often the wrong person.
    The person named in the description ("Surname, Given - ...") wins, then
    the closest spelling variant; otherwise the lowest Gramps ID, so the
    choice is the same on every run.

    :param db: The database.
    :param handles: Candidate person handles.
    :param text: The media description (or original file name).
    :returns: The chosen person, or ``None`` if no handle resolves.
    """
    people = [p for p in (_db_get(db, "Person", h) for h in handles) if p is not None]
    if not people:
        return None
    people.sort(key=_gid_of)
    sur, giv, _rest = parse_name_from_text(text or "")
    if sur:
        # max() keeps the first of equal scores, i.e. the lowest Gramps ID
        best = max(people, key=lambda p: _name_score(p, sur, giv))
        if _name_score(best, sur, giv) > 0:
            return best
    return people[0]


def _event_person_handles(
    db: DbReadBase, event_handle: EventHandle
) -> list[PersonHandle]:
    """
    Return the handles of people who reference an event.

    :param db: The database.
    :param event_handle: The event's handle.
    :returns: Person handles (possibly empty).
    """
    try:
        links = list(db.find_backlink_handles(event_handle, include_classes=["Person"]))
    except Exception:
        return []
    return [h for cname, h in links if cname == "Person"]


def _order_backlinks(
    db: DbReadBase, backlinks: list[tuple[str, str]], text: str
) -> list[tuple[str, str]]:
    """Return backlinks in a stable order.  When the description names a person
    ("Surname, Given - ..."), only backlinks leading to that person are kept, so
    a file shared by several people is named after the one it is *of*."""

    def gid(b: tuple[str, str]) -> str:
        """Return the Gramps ID of a backlinked object, for sorting."""
        obj = _db_get(db, b[0], b[1])
        return str(obj.get_gramps_id() or "") if obj is not None else ""

    ordered = sorted(backlinks, key=lambda b: (b[0], gid(b), b[1]))
    sur, giv, _rest = parse_name_from_text(text or "")
    if sur:
        matched = [
            b
            for b in ordered
            if any(_person_matches(p, sur, giv) for p in _persons_of(db, b[0], b[1]))
        ]
        if matched:
            return matched
    return ordered


def find_name_mismatches(
    db: DbReadBase,
) -> list[tuple[str, str, str, str, str]]:
    """Media whose description names someone ("Surname, Given - ...") who is not
    among the people it is attached to, e.g. 'Duvault' vs 'Devault'.

    Returns (media_id, description, name_in_description, linked_name, kind).
    """
    out: list[tuple[str, str, str, str, str]] = []
    for media in db.iter_media():
        desc = str(media.get_description() or "")
        sur, giv, _rest = parse_name_from_text(desc)
        if not sur:
            continue
        try:
            backlinks = list(db.find_backlink_handles(media.get_handle()))
        except Exception:
            continue
        people: list[Any] = []
        for cname, handle in backlinks:
            people.extend(_persons_of(db, cname, handle))
        if not people or any(_person_matches(p, sur, giv) for p in people):
            continue
        best_name, best_ratio = "", 0.0
        for p in people:
            pn = p.get_primary_name()
            ratio = difflib.SequenceMatcher(
                None, _norm_name(sur), _norm_name(pn.get_surname())
            ).ratio()
            if ratio >= best_ratio:
                best_ratio = ratio
                best_name = "%s, %s" % (pn.get_surname(), pn.get_first_name())
        kind = "probable spelling variant" if best_ratio >= 0.75 else "different person"
        out.append(
            (
                str(media.get_gramps_id() or ""),
                desc,
                "%s, %s" % (sur, giv),
                best_name,
                kind,
            )
        )
    return out


def find_duplicate_media_references(
    db: DbReadBase | None, cache: dict[str, dict[str, str]] | None = None
) -> dict[str, list[tuple[str, str, str, str]]]:
    """Find media records pointing to the same file path on disk.

    Returns a dict mapping normalized path to list of (gramps_id, description, raw_path, assoc).
    """
    if not db:
        return {}
    path_map: dict[str, list[tuple[str, str, str, str]]] = {}
    for media in db.iter_media():
        m_gid = str(media.get_gramps_id() or "")
        desc = str(media.get_description() or "")
        raw_path = clean_path(str(media.get_path() or ""))
        if not raw_path:
            continue
        # Same key as find_duplicate_media_groups(), so the report and the
        # Fix media references dialog always agree on what is a duplicate.
        key = path_key(full_media_path(db, raw_path))

        ctx = resolve_media_reference_context(db, media, cache)
        assoc_str = ctx.get("assoc", "")

        if key not in path_map:
            path_map[key] = []
        path_map[key].append((m_gid, desc, raw_path, assoc_str))

    return {k: v for k, v in path_map.items() if len(v) > 1}


def get_person_year(db: DbReadBase, person: Any) -> str:
    """Extract a representative year for a person (birth, death, or first dated event)."""
    if not person or not db:
        return ""
    try:
        birth = get_birth_or_fallback(db, person)
        if birth and birth.get_date_object() and birth.get_date_object().get_year() > 0:
            return str(birth.get_date_object().get_year())
        death = get_death_or_fallback(db, person)
        if death and death.get_date_object() and death.get_date_object().get_year() > 0:
            return str(death.get_date_object().get_year())
    except Exception:
        pass
    if hasattr(person, "get_event_ref_list"):
        for eref in person.get_event_ref_list():
            if hasattr(eref, "ref") and eref.ref:
                try:
                    evt = db.get_event_from_handle(eref.ref)
                    if (
                        evt
                        and evt.get_date_object()
                        and evt.get_date_object().get_year() > 0
                    ):
                        return str(evt.get_date_object().get_year())
                except Exception:
                    continue
    return ""


def _resolve_media_reference_context_uncached(
    db: DbReadBase | None, media: Any
) -> dict[str, str]:
    """Resolve context tokens (surname, given, doc_type, year, ref_id, assoc) for a media object."""
    context: dict[str, str] = {
        "id": str(media.get_gramps_id() or "") if media else "",
        "desc": str(media.get_description() or "") if media else "",
        "orig": "",
        "ext": "",
        "ref_id": str(media.get_gramps_id() or "") if media else "",
        "surname": "",
        "given": "",
        "doc_type": "",
        "year": "",
        "assoc": "",
        "hash": "",
    }

    if media:
        raw_path = str(media.get_path() or "")
        if raw_path:
            _dir, basename = os.path.split(raw_path)
            name, ext = os.path.splitext(basename)
            context["orig"] = name
            context["ext"] = ext.lstrip(".").lower()

        if hasattr(media, "get_date_object"):
            d_obj = media.get_date_object()
            if d_obj and hasattr(d_obj, "get_year") and d_obj.get_year() > 0:
                context["year"] = str(d_obj.get_year())

    if not db or not media or not hasattr(db, "find_backlink_handles"):
        sur, giv, rest = parse_name_from_text(context["desc"] or context["orig"])
        if sur:
            context["surname"] = sur
            context["given"] = giv
            context["doc_type"] = rest
        clean_dt, extracted_year = extract_year_and_clean_doctype(
            context["doc_type"] or context["desc"] or "Photo",
            context["surname"],
            context["given"],
        )
        if extracted_year:
            context["year"] = extracted_year
        if clean_dt:
            context["doc_type"] = clean_dt
        if not context["doc_type"]:
            context["doc_type"] = "Photo" if context["surname"] else "Media"
        context["assoc"] = _("Top-Level / Global (Unreferenced)")
        return context

    media_handle = media.get_handle()
    if not media_handle:
        context["doc_type"] = context["desc"] or "media"
        context["assoc"] = _("Top-Level / Global (Unreferenced)")
        return context

    backlinks = _order_backlinks(
        db,
        list(db.find_backlink_handles(media_handle)),
        context["desc"] or context["orig"],
    )

    # Text that may name the person the file is of ("Surname, Given - ...")
    name_text = context["desc"] or context["orig"]

    # Priority 1: Person backlink
    for cname, handle in backlinks:
        if cname == "Person":
            person = db.get_person_from_handle(handle)
            if person:
                context["ref_id"] = str(person.get_gramps_id() or context["ref_id"])
                pname = person.get_primary_name()
                if pname:
                    context["surname"] = str(pname.get_surname() or "")
                    context["given"] = str(pname.get_first_name() or "")
                context["doc_type"] = context["desc"] or "Photo"
                if not context["year"]:
                    context["year"] = get_person_year(db, person)
                context["assoc"] = (
                    f"Person: {context['surname']}, {context['given']} [{context['ref_id']}]"
                )
                break

    # Priority 2: Event backlink
    if not context["assoc"]:
        for cname, handle in backlinks:
            if cname == "Event":
                event = db.get_event_from_handle(handle)
                if event:
                    event_gid = str(event.get_gramps_id() or "")
                    e_type = str(event.get_type() or "Event")
                    context["doc_type"] = context["desc"] or e_type
                    e_date = event.get_date_object()
                    if e_date and hasattr(e_date, "get_year") and e_date.get_year() > 0:
                        context["year"] = str(e_date.get_year())

                    # Find the participant the file is *of* (a shared census
                    # event has several), not merely the first one returned.
                    e_backlinks = list(
                        db.find_backlink_handles(
                            handle, include_classes=["Person", "Family"]
                        )
                    )
                    p_name_str = ""
                    person = _best_person(
                        db,
                        [h for c, h in e_backlinks if c == "Person"],
                        name_text,
                    )
                    families = sorted(
                        (
                            f
                            for f in (
                                _db_get(db, "Family", h)
                                for c, h in e_backlinks
                                if c == "Family"
                            )
                            if f is not None
                        ),
                        key=_gid_of,
                    )
                    if person is not None:
                        context["ref_id"] = str(person.get_gramps_id() or event_gid)
                        pname = person.get_primary_name()
                        if pname:
                            context["surname"] = str(pname.get_surname() or "")
                            context["given"] = str(pname.get_first_name() or "")
                            p_name_str = f"{context['surname']}, {context['given']} [{context['ref_id']}]"
                    elif families and not context["surname"]:
                        family = families[0]
                        if family:
                            context["ref_id"] = str(family.get_gramps_id() or event_gid)
                            f_handle = (
                                family.get_father_handle()
                                if hasattr(family, "get_father_handle")
                                else None
                            )
                            father = (
                                db.get_person_from_handle(f_handle)
                                if f_handle
                                else None
                            )
                            if father and father.get_primary_name():
                                context["surname"] = str(
                                    father.get_primary_name().get_surname() or ""
                                )
                                p_name_str = f"Family: {context['surname']} [{context['ref_id']}]"
                    if not context["ref_id"] or context["ref_id"] == context["id"]:
                        context["ref_id"] = event_gid
                    context["assoc"] = (
                        f"Event: {e_type}"
                        + (f" {context['year']}" if context["year"] else "")
                        + (f" [{p_name_str}]" if p_name_str else "")
                    )
                    break

    # Priority 3: Family backlink
    if not context["assoc"]:
        for cname, handle in backlinks:
            if cname == "Family":
                family = db.get_family_from_handle(handle)
                if family:
                    context["ref_id"] = str(family.get_gramps_id() or context["ref_id"])
                    context["doc_type"] = context["desc"] or "Family"
                    f_handle = (
                        family.get_father_handle()
                        if hasattr(family, "get_father_handle")
                        else None
                    )
                    father = db.get_person_from_handle(f_handle) if f_handle else None
                    if father and father.get_primary_name():
                        context["surname"] = str(
                            father.get_primary_name().get_surname() or ""
                        )
                    context["assoc"] = (
                        f"Family: {context['surname']} [{context['ref_id']}]"
                    )
                    break

    # Priority 4: Citation backlink (with deep traversal to Event, Person, Family)
    if not context["assoc"]:
        for cname, handle in backlinks:
            if cname == "Citation":
                cit = db.get_citation_from_handle(handle)
                if cit:
                    cit_gid = str(cit.get_gramps_id() or "")
                    s_handle = (
                        cit.get_reference_handle()
                        if hasattr(cit, "get_reference_handle")
                        else None
                    )
                    src = db.get_source_from_handle(s_handle) if s_handle else None
                    src_title = str(src.get_title() or "") if src else ""
                    page = str(cit.get_page() or "")

                    # Deep traverse: check what references this Citation.
                    # Events are taken in Gramps-ID order; one with the
                    # described person among its participants wins.
                    c_backlinks = list(db.find_backlink_handles(handle))
                    events = sorted(
                        (
                            e
                            for e in (
                                _db_get(db, "Event", h)
                                for c, h in c_backlinks
                                if c == "Event"
                            )
                            if e is not None
                        ),
                        key=_gid_of,
                    )
                    found_event = None
                    event_person = None
                    d_sur, d_giv, _d_rest = parse_name_from_text(name_text)
                    if d_sur:
                        for ev in events:
                            cand = _best_person(
                                db,
                                _event_person_handles(db, ev.get_handle()),
                                name_text,
                            )
                            if cand is not None and _name_score(cand, d_sur, d_giv) > 0:
                                found_event, event_person = ev, cand
                                break
                    if found_event is None and events:
                        found_event = events[0]
                        event_person = _best_person(
                            db,
                            _event_person_handles(db, found_event.get_handle()),
                            name_text,
                        )

                    if found_event:
                        event_gid = str(found_event.get_gramps_id() or "")
                        e_type = str(found_event.get_type() or "Event")
                        e_date = found_event.get_date_object()
                        if (
                            e_date
                            and hasattr(e_date, "get_year")
                            and e_date.get_year() > 0
                        ):
                            context["year"] = str(e_date.get_year())
                        context["doc_type"] = context["desc"] or e_type

                        p_name_str = ""
                        p = event_person
                        if p is not None:
                            context["ref_id"] = str(p.get_gramps_id() or event_gid)
                            pname = p.get_primary_name()
                            if pname:
                                context["surname"] = str(pname.get_surname() or "")
                                context["given"] = str(pname.get_first_name() or "")
                                p_name_str = f"{context['surname']}, {context['given']} [{context['ref_id']}]"
                        context["ref_id"] = context["ref_id"] or event_gid or cit_gid
                        context["assoc"] = (
                            f"Citation: {cit_gid} ({src_title or 'Source'}) -> Event: {e_type}"
                            + (f" {context['year']}" if context["year"] else "")
                            + (f" [{p_name_str}]" if p_name_str else "")
                        )
                        break

                    found_person = _best_person(
                        db,
                        [h for c, h in c_backlinks if c == "Person"],
                        name_text,
                    )

                    if found_person:
                        context["ref_id"] = str(found_person.get_gramps_id() or cit_gid)
                        pname = found_person.get_primary_name()
                        if pname:
                            context["surname"] = str(pname.get_surname() or "")
                            context["given"] = str(pname.get_first_name() or "")
                        context["doc_type"] = (
                            context["desc"] or page or src_title or "Citation"
                        )
                        if not context["year"]:
                            context["year"] = get_person_year(db, found_person)
                        context["assoc"] = (
                            f"Citation: {cit_gid} ({src_title or 'Source'}) -> Person: {context['surname']}, {context['given']} [{context['ref_id']}]"
                        )
                        break

                    context["ref_id"] = cit_gid
                    context["doc_type"] = (
                        context["desc"] or page or src_title or "Citation"
                    )
                    context["assoc"] = f"Citation: {cit_gid} ({src_title or 'Source'})"
                    break

    # Priority 5: Source backlink
    if not context["assoc"]:
        for cname, handle in backlinks:
            if cname == "Source":
                src = db.get_source_from_handle(handle)
                if src:
                    context["ref_id"] = str(src.get_gramps_id() or context["ref_id"])
                    context["doc_type"] = context["desc"] or str(
                        src.get_title() or "Source"
                    )
                    context["assoc"] = (
                        f"Source: {src.get_title()} [{context['ref_id']}]"
                    )
                    break

    # Fallback to text parsing if surname is missing
    if not context["surname"]:
        text_to_parse = context["desc"] or context["orig"]
        sur, giv, rest = parse_name_from_text(text_to_parse)
        if sur:
            context["surname"] = sur
            context["given"] = giv
            if rest and (
                not context["doc_type"]
                or context["doc_type"] in ("media", "Photo", "Citation")
            ):
                context["doc_type"] = rest

    # Clean doc_type and extract document year
    clean_dt, extracted_year = extract_year_and_clean_doctype(
        context["doc_type"] or context["desc"] or context["orig"] or "Photo",
        context["surname"],
        context["given"],
    )
    if extracted_year:
        context["year"] = extracted_year
    if clean_dt:
        context["doc_type"] = clean_dt

    if not context["assoc"]:
        context["assoc"] = _("Top-Level / Global (Unreferenced)")

    if not context["doc_type"]:
        context["doc_type"] = "Photo" if context["surname"] else "Media"

    return context


def resolve_media_reference_context(
    db: DbReadBase, media: Any, cache: dict[str, dict[str, str]] | None = None
) -> dict[str, str]:
    """Resolve naming context for a media object (optionally memoised per media
    handle in *cache*, which avoids repeating the backlink traversal)."""
    key = str(media.get_handle() or "") if (cache is not None and media) else ""
    if key and key in cache:  # type: ignore[operator]
        return dict(cache[key])  # type: ignore[index]
    ctx = _resolve_media_reference_context_uncached(db, media)
    if key:
        cache[key] = dict(ctx)  # type: ignore[index]
    return ctx


def format_standard_filename(
    template: str, context: dict[str, str], max_stem_len: int = 85
) -> str:
    """Format and sanitize a filename using template tokens and context."""
    ext = clean_token(context.get("ext", "jpg")).lower()
    if not ext:
        ext = "jpg"

    safe_context = {k: clean_token(v) for k, v in context.items() if k != "ext"}
    safe_context["ext"] = ext

    try:
        rendered = template.format(**safe_context)
    except (KeyError, ValueError, IndexError):
        rendered = f"{safe_context.get('ref_id', '')}_{safe_context.get('orig', 'media')}.{ext}"

    if "." in rendered:
        base, _ext = rendered.rsplit(".", 1)
    else:
        base = rendered

    base = re.sub(r"[\s_]*-+[\s_]*", "-", base)
    base = re.sub(r"[^\w\-]+", "_", base)
    base = re.sub(r"_+", "_", base)
    base = re.sub(r"[-_]*-[_\s-]*", "-", base)
    base = re.sub(r"-+", "-", base)
    base = base.strip("_-")

    if not base:
        base = safe_context.get("orig") or safe_context.get("id") or "media"
        base = clean_token(base) or "media"

    if len(base) > max_stem_len:
        base = base[:max_stem_len].rstrip("_-")

    return f"{base}.{ext}"


def sanitize_standard_filename(
    path: str,
    db: DbReadBase | None = None,
    media: Any = None,
    template: str | None = None,
    cache: dict[str, dict[str, str]] | None = None,
) -> str:
    """Return a sanitized standard filename adhering to platform-safe naming templates."""
    dirname, basename = os.path.split(path)
    name, ext = os.path.splitext(basename)
    ext_clean = ext.lstrip(".").lower()

    if db is not None and media is not None:
        tmpl = template or config.get(CONFIG_TEMPLATE_KEY) or DEFAULT_FILENAME_TEMPLATE
        ctx = resolve_media_reference_context(db, media, cache)
        ctx["orig"] = name
        ctx["ext"] = ext_clean
        if "{hash}" in tmpl:
            try:
                ctx["hash"] = file_content_hash(media_path_full(db, path))
            except Exception:
                ctx["hash"] = ""
        standard_basename = format_standard_filename(tmpl, ctx)
    else:
        tmpl = template or "{orig}.{ext}"
        ctx = {"orig": name, "ext": ext_clean, "id": "media", "ref_id": "media"}
        standard_basename = format_standard_filename(tmpl, ctx)

    return os.path.join(dirname, standard_basename) if dirname else standard_basename


def file_content_hash(path: str, length: int = 6) -> str:
    """Short, stable content hash of a file ("" if it cannot be read)."""
    try:
        digest = hashlib.sha1()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()[:length]
    except OSError:
        return ""


# ------------------------------------------------------------
#
# Progress meter (no-op if Gramps' ProgressMeter is unavailable)
#
# ------------------------------------------------------------
class _Progress:
    def __init__(self, title: str, total: int, parent: Any = None) -> None:
        """
        Open a Gramps progress meter, if one can be created.

        :param title: Title and pass label.
        :param total: Number of steps.
        :param parent: Parent window.
        """
        self.meter: Any = None
        try:
            from gramps.gui.utils import ProgressMeter

            self.meter = ProgressMeter(title, can_cancel=False, parent=parent)
            self.meter.set_pass(title, max(int(total), 1), ProgressMeter.MODE_FRACTION)
        except Exception:
            self.meter = None

    def step(self) -> None:
        """Advance the meter by one step."""
        if self.meter is not None:
            try:
                self.meter.step()
            except Exception:
                pass

    def close(self) -> None:
        """Close the meter."""
        if self.meter is not None:
            try:
                self.meter.close()
            except Exception:
                pass
            self.meter = None


# ------------------------------------------------------------
#
# Stale "Records not imported into OBJE" notes left by the Legacy import
#
# ------------------------------------------------------------
IMPORT_NOTE_PREFIX = "Records not imported into OBJE"


def find_stale_import_notes(
    db: DbReadBase, only_resolved: bool = True
) -> list[tuple[str, str, str, str]]:
    """Import-failure notes attached to media.  With only_resolved, only those
    whose file is now readable (so the note's complaint is out of date).

    Returns (media_handle, media_id, note_handle, note_id).
    """
    items: list[tuple[str, str, str, str]] = []
    for media in list(db.iter_media()):
        notes = list(media.get_note_list() or [])
        if not notes:
            continue
        if only_resolved:
            raw = clean_path(str(media.get_path() or ""))
            try:
                full = media_path_full(db, raw)
            except Exception:
                full = raw
            if not raw or not (
                os.path.exists(full) or (is_absolute_path(raw) and os.path.exists(raw))
            ):
                continue
        for nh in notes:
            note = db.get_note_from_handle(nh)
            text = str(note.get() or "") if note is not None else ""
            if text.lstrip().startswith(IMPORT_NOTE_PREFIX):
                items.append(
                    (
                        str(media.get_handle() or ""),
                        str(media.get_gramps_id() or ""),
                        nh,
                        str(note.get_gramps_id() or ""),
                    )
                )
    return items


def remove_import_notes(db: DbWriteBase, items: list[tuple[str, str, str, str]]) -> int:
    """
    Detach the notes from their media and delete notes nothing else uses.

    :param db: The database.
    :param items: Result of :func:`find_stale_import_notes`.
    :returns: Number of notes removed from media.
        A note still used elsewhere is detached but not deleted; it is
        counted, since the user asked for it to be removed from the media.
    """
    removed = 0
    with DbTxn(_("Remove stale import notes"), db) as trans:
        for mh, _mgid, nh, _ngid in items:
            media = db.get_media_from_handle(mh)
            if media is None:
                continue
            media.remove_note(nh)
            db.commit_media(media, trans)
            removed += 1
            others = [
                b for b in db.find_backlink_handles(nh) if tuple(b) != ("Media", mh)
            ]
            if not others:
                db.remove_note(nh, trans)
    return removed


# ------------------------------------------------------------
#
# Keeping records valid when the base media path changes
#
# ------------------------------------------------------------
def snapshot_resolved_paths(db: DbReadBase) -> dict[MediaHandle, str]:
    """
    Record where every relative media record's file is *now*.

    Call this before changing the base media path.  Only records whose file
    exists are included: a record that is missing under the old base path may
    well be found under the new one, so it is left to resolve normally.

    :param db: The database.
    :returns: Mapping of media handle to the file's current full path.
    """
    snapshot: dict[MediaHandle, str] = {}
    for media in db.iter_media():
        raw = clean_path(str(media.get_path() or ""))
        if not raw or is_absolute_path(raw):
            continue
        full = full_media_path(db, raw)
        if os.path.exists(full):
            snapshot[media.get_handle()] = full
    return snapshot


def keep_records_pointing_at_files(
    db: DbWriteBase,
    snapshot: dict[MediaHandle, str],
    trans: Any,
    skip: set[MediaHandle],
) -> int:
    """
    Repoint records that a base-path change would otherwise break.

    A relative path is resolved against the base media path, so changing the
    base silently re-roots every relative record that was not part of the
    batch.  For each record in *snapshot* whose path no longer resolves to the
    same file, store a path to that file again: relative to the new base when
    the file is inside it, otherwise absolute.

    :param db: The database (base path already changed).
    :param snapshot: Result of :func:`snapshot_resolved_paths` taken before
        the change.
    :param trans: The open transaction.
    :param skip: Handles already repointed in this batch.
    :returns: Number of records repointed.
    """
    new_base = media_path(db)
    fixed = 0
    for handle, old_full in snapshot.items():
        if handle in skip:
            continue
        try:
            media = db.get_media_from_handle(handle)
        except Exception:
            media = None
        if media is None:
            continue
        raw = clean_path(str(media.get_path() or ""))
        if path_key(full_media_path(db, raw)) == path_key(old_full):
            continue  # still finds its file (e.g. the base did not really move)
        media.set_path(to_db_path(old_full, new_base))
        add_media_fixed_tag(db, media, txn=trans)
        db.commit_media(media, trans)
        fixed += 1
    return fixed


def move_log_summary(move_log: MoveLog) -> str:
    """
    Write a run's move log and describe where it went.

    :param move_log: The run's log (nothing is written when it is empty).
    :returns: Text to append to a result message ("" when nothing was logged).
    """
    if not len(move_log):
        return ""
    err = move_log.write()
    if err:
        return (
            "\n\n"
            + str(
                _(
                    "WARNING: the file-move log could not be written (%s), so "
                    "'Undo last file moves' cannot reverse this run."
                )
            )
            % err
        )
    return (
        "\n\n"
        + str(
            _(
                "File operations were logged in %s. Use 'Undo last file moves' to "
                "reverse them (Edit > Undo would only revert the database)."
            )
        )
        % move_log.path
    )


def base_change_summary(fixed: int) -> str:
    """
    Describe what a base-path change did to records outside the batch.

    :param fixed: Records repointed by :func:`keep_records_pointing_at_files`.
    :returns: Text for the result dialog ("" when there is nothing to say).
    """
    parts: list[str] = []
    if fixed:
        parts.append(
            ngettext(
                "The base media path changed: %d other record was updated so "
                "it still points at its file.",
                "The base media path changed: %d other records were updated so "
                "they still point at their files.",
                fixed,
            )
            % fixed
        )
    return "\n\n".join(parts)


# ------------------------------------------------------------
#
# Consolidation planner (shared by the preview and the real run)
#
# ------------------------------------------------------------
def namer_rank(db: DbReadBase, media: Any) -> tuple[int, str]:
    """
    Sort key choosing which of several records sharing a file names it.

    The record with the most references comes first, then the lowest Gramps
    ID, so the choice is stable.

    :param db: The database.
    :param media: A media record.
    :returns: A sort key (lower sorts first).
    """
    try:
        n_refs = len(list(db.find_backlink_handles(media.get_handle())))
    except Exception:
        n_refs = 0
    return (-n_refs, _gid_of(media))


def plan_consolidation_moves(
    db: DbReadBase,
    base_dir: str,
    template: str,
    effective: dict[str, str] | None = None,
    gone: set[str] | None = None,
    found_handles: set[str] | None = None,
    cache: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """
    Work out which files consolidation would move, without changing anything.

    Records that point at the same file are planned *together*: the file is
    moved once and every record is repointed, so a shared file no longer
    blocks consolidation.  The Accept-all preview and the real run both call this
    function, so the preview cannot promise moves the run will not make.

    :param db: The database.
    :param base_dir: The media base directory files are moved into.
    :param template: Filename template for standard names.
    :param effective: Paths to use instead of the stored ones (handle -> path),
        e.g. the result of a planned "find missing" step.
    :param gone: Handles to ignore (records that will be merged or deleted).
    :param found_handles: Handles whose effective path is relative to
        ``base_dir`` because it was found there.
    :param cache: Reference-context cache shared with other planning steps.
    :returns: The moves.  Each is a dict with ``media`` (list), ``gids``,
        ``raw``, ``src_full``, ``dest_full`` and ``renamed``.
    """
    effective = effective or {}
    gone = gone or set()
    found_handles = found_handles or set()

    groups: dict[str, list[tuple[Any, str, str]]] = {}
    for media in list(db.iter_media()):
        handle = str(media.get_handle() or "")
        if handle in gone:
            continue
        raw = effective.get(handle) or clean_path(str(media.get_path() or ""))
        if not raw:
            continue
        if handle in found_handles:
            src_full = os.path.join(base_dir, raw)
        else:
            src_full = full_media_path(db, raw)
        groups.setdefault(path_key(src_full), []).append((media, raw, src_full))

    moves: list[dict[str, Any]] = []
    claimed: set[str] = set()
    for members in groups.values():
        members.sort(key=lambda item: namer_rank(db, item[0]))
        namer, namer_raw, src_full = members[0]
        gids = ", ".join(_gid_of(m) for m, _r, _s in members)

        std = sanitize_standard_filename(
            namer_raw, db=db, media=namer, template=template, cache=cache
        )
        dest_full = os.path.join(base_dir, os.path.basename(std))
        target_rel = to_db_path(dest_full, base_dir)
        if path_key(src_full) == path_key(dest_full) and all(
            raw == target_rel for _m, raw, _s in members
        ):
            claimed.add(path_key(dest_full))  # already consolidated
            continue
        if not os.path.exists(src_full):
            # Missing or unreadable: reported once, with the right reason,
            # by scan_unreadable_media().
            continue
        final = unique_destination(dest_full, claimed, src_full)
        moves.append(
            {
                "media": [m for m, _r, _s in members],
                "gids": gids,
                "raw": namer_raw,
                "src_full": src_full,
                "dest_full": final,
                "renamed": path_key(final) != path_key(dest_full),
            }
        )
    return moves


# ------------------------------------------------------------
#
# Accept-all preview (dry run)
#
# ------------------------------------------------------------
def build_accept_all_plan(
    db: DbReadBase, base_dir: str, base_set: bool
) -> dict[str, Any]:
    """Work out, WITHOUT changing anything, what 'Accept all hints' would do."""
    plan: dict[str, Any] = {
        "base_dir": base_dir,
        "base_set": base_set,
        "find": [],
        "ambiguous": [],
        "merges": [],
        "delete": [],
        "keep_unref": [],
        "moves": [],
        "halted": "",
        "missing": [],
        "denied": [],
    }
    template = config.get(CONFIG_TEMPLATE_KEY) or DEFAULT_FILENAME_TEMPLATE
    cache: dict[str, dict[str, str]] = {}
    index = media_dir_index(db, base_dir)

    # Step 1: find missing
    effective: dict[str, str] = {}
    found_handles: set[str] = set()
    find_candidates: list[tuple[str, str, str, str]] = []  # handle, gid, raw, rel
    for media in list(db.iter_media()):
        handle = str(media.get_handle() or "")
        raw = clean_path(str(media.get_path() or ""))
        if not raw:
            continue
        effective[handle] = raw
        try:
            full = media_path_full(db, raw)
        except Exception:
            full = raw
        if os.path.exists(full) or (is_absolute_path(raw) and os.path.exists(raw)):
            continue
        rel = find_in_media_dir(
            base_dir, os.path.basename(raw.replace("\\", "/")), index
        )
        if rel:
            find_candidates.append((handle, str(media.get_gramps_id() or ""), raw, rel))
    unsafe = ambiguous_matches(
        [(MediaHandle(h), raw, rel) for h, _g, raw, rel in find_candidates]
    )
    for handle, gid, raw, rel in find_candidates:
        if handle in unsafe:
            plan["ambiguous"].append((gid, raw, rel))
            continue
        plan["find"].append((gid, raw, rel))
        effective[handle] = rel
        found_handles.add(handle)

    # Step 2: references
    gone: set[str] = set()
    merged_gids: set[str] = set()
    for group in find_duplicate_media_groups(db, cache):
        keeper = group["keeper"]
        if group.get("type", "duplicate") == "duplicate":
            others = [r for r in group["records"] if r["handle"] != keeper["handle"]]
            if not others:
                continue
            gone |= {r["handle"] for r in others}
            merged_gids |= {r["gramps_id"] for r in others}
            plan["merges"].append(
                (
                    keeper["gramps_id"],
                    [r["gramps_id"] for r in others],
                    group["raw_path"],
                )
            )
        else:
            if is_bare_media(keeper["media"]):
                plan["delete"].append((keeper["gramps_id"], group["raw_path"]))
                gone.add(keeper["handle"])
            else:
                plan["keep_unref"].append((keeper["gramps_id"], group["raw_path"]))

    # Step 3: consolidate
    if not base_set:
        plan["halted"] = (
            "no base media path is set (set one under 'Consolidate media location')"
        )
    else:
        moves = plan_consolidation_moves(
            db, base_dir, template, effective, gone, found_handles, cache
        )
        plan["moves"] = [
            (
                mv["gids"],
                mv["raw"],
                to_db_path(mv["dest_full"], base_dir),
                mv["renamed"],
            )
            for mv in moves
        ]

    missing, denied = scan_unreadable_media(db)
    fixed = {g for g, _o, _n in plan["find"]}
    plan["missing"] = [
        x for x in missing if x[0] not in fixed and x[0] not in merged_gids
    ]
    plan["denied"] = [
        x for x in denied if x[0] not in fixed and x[0] not in merged_gids
    ]
    return plan


def plan_has_changes(plan: dict[str, Any]) -> bool:
    """
    Return True if an Accept-all plan would change anything.

    :param plan: Result of :func:`build_accept_all_plan`.
    :returns: Whether there is anything to apply.
    """
    return any(plan[k] for k in ("find", "merges", "delete", "moves"))


def format_plan(plan: dict[str, Any], limit: int = 6) -> str:
    """Human-readable preview text."""
    lines: list[str] = [str(_("PREVIEW - nothing has been changed yet.")), ""]

    def section(title: str, rows: list[str]) -> None:
        """Add a titled section, listing at most *limit* rows."""
        lines.append(title)
        lines.extend("    " + r for r in rows[:limit])
        if len(rows) > limit:
            lines.append("    " + str(_("... and %d more")) % (len(rows) - limit))
        lines.append("")

    if plan["find"]:
        section(
            ngettext(
                "1. Find missing media - repoint %d record:",
                "1. Find missing media - repoint %d records:",
                len(plan["find"]),
            )
            % len(plan["find"]),
            ["[%s] %s  ->  %s" % r for r in plan["find"]],
        )
    if plan.get("ambiguous"):
        section(
            str(
                _(
                    "1. Find missing media - NOT repointed, several different "
                    "records match the same file (%d):"
                )
            )
            % len(plan["ambiguous"]),
            ["[%s] %s  ?  %s" % r for r in plan["ambiguous"]],
        )
    if plan["merges"]:
        section(
            ngettext(
                "2. Merge duplicate records - %d file group:",
                "2. Merge duplicate records - %d file groups:",
                len(plan["merges"]),
            )
            % len(plan["merges"]),
            [
                "[%s] absorbs %s  (%s)" % (k, ", ".join(o), p)
                for k, o, p in plan["merges"]
            ],
        )
    if plan["delete"]:
        section(
            str(_("2. Delete empty unreferenced records (%d):")) % len(plan["delete"]),
            ["[%s] %s" % r for r in plan["delete"]],
        )
    if plan["keep_unref"]:
        section(
            str(_("2. Unreferenced but has notes/tags/attributes - KEPT (%d):"))
            % len(plan["keep_unref"]),
            ["[%s] %s" % r for r in plan["keep_unref"]],
        )
    if plan["halted"]:
        lines += [str(_("3. Move/rename files: SKIPPED - %s")) % plan["halted"], ""]
    elif plan["moves"]:
        section(
            _("3. Move/rename files into '%(folder)s' (%(count)d):")
            % {"folder": plan["base_dir"], "count": len(plan["moves"])},
            [
                "[%s] %s  ->  %s%s"
                % (g, o, n, "  (renamed: name already taken)" if c else "")
                for g, o, n, c in plan["moves"]
            ],
        )
    if plan["missing"] or plan["denied"]:
        lines.append(str(_("NEEDS YOUR ATTENTION (cannot be fixed automatically):")))
        if plan["missing"]:
            lines.append(
                "    "
                + ngettext(
                    "%d file not found on disk",
                    "%d files not found on disk",
                    len(plan["missing"]),
                )
                % len(plan["missing"])
            )
        if plan["denied"]:
            lines.append(
                "    "
                + ngettext(
                    "%d file exists but cannot be read (permission denied)",
                    "%d files exist but cannot be read (permission denied)",
                    len(plan["denied"]),
                )
                % len(plan["denied"])
            )
        lines.append("")
    lines.append(
        str(
            _(
                "Notes: names in step 3 are recomputed after merging, so shared files "
                "may be named slightly differently. File moves are logged: use "
                "'Undo last file moves' to reverse them. Edit > Undo alone would "
                "revert the database but leave the files moved."
            )
        )
    )
    return "\n".join(lines)


def confirm_plan(parent: Any, text: str) -> bool:
    """Scrollable preview with Cancel / Accept all; True if accepted."""
    dlg = Gtk.Dialog(
        title=str(_("Accept all hints - preview")),
        transient_for=parent,
        modal=True,
        destroy_with_parent=True,
    )
    dlg.set_default_size(800, 540)
    dlg.add_button(str(_("_Cancel")), Gtk.ResponseType.CANCEL)
    dlg.add_button(str(_("_Accept all")), Gtk.ResponseType.OK)
    content = dlg.get_content_area()
    content.set_border_width(12)
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_hexpand(True)
    scrolled.set_vexpand(True)
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scrolled.add(
        SelectableLabel(label=text, selectable=True, wrap=True, can_focus=True)
    )
    content.pack_start(scrolled, True, True, 0)
    dlg.show_all()
    resp = dlg.run()
    dlg.destroy()
    return resp == Gtk.ResponseType.OK


def missing_file_name(raw_path: str) -> str:
    """Return the file name of a stored media path (either slash style)."""
    return os.path.basename(clean_path(raw_path).replace("\\", "/"))


def missing_file_dir(raw_path: str) -> str:
    """Return a comparable key for the folder part of a stored media path."""
    return path_key(os.path.dirname(clean_path(raw_path).replace("\\", "/")))


# ------------------------------------------------------------
#
# FindMissingMediaDialog
#
# ------------------------------------------------------------
class FindMissingMediaDialog(Gtk.Dialog):
    """Review media records where the file is missing from disk."""

    def __init__(
        self,
        title: str | None = None,
        dbstate: Any = None,
        transient_for: Gtk.Window | None = None,
    ) -> None:
        """
        Scan for media records whose file is missing and build the review table.

        :param title: Window title (defaults to "Find Missing Media").
        :param dbstate: The Gramps database state.
        :param transient_for: Parent window.
        """
        dialog_title = title or str(_("Find Missing Media"))
        super().__init__(
            title=dialog_title,
            transient_for=transient_for,
            modal=True,
            destroy_with_parent=True,
        )
        self.dbstate = dbstate
        self.rows: list[dict[str, Any]] = []
        self.row_targets: list[dict[str, Any]] = []
        self._last_pick_dir = ""
        self.set_default_size(1360, 520)
        curr_mpath = (
            self.dbstate.db.get_mediapath()
            if self.dbstate
            and self.dbstate.db
            and hasattr(self.dbstate.db, "get_mediapath")
            else ""
        )
        self._orig_mediapath = (curr_mpath or "").strip()
        self._mediapath_text = self._orig_mediapath

        # Scan database for missing media files
        base_dir = (
            get_media_base_path(dbstate.db)
            if dbstate and dbstate.db
            else get_media_base_path(None)
        )
        self.base_dir = base_dir
        name_index = media_dir_index(dbstate.db, base_dir)
        for media in dbstate.db.iter_media():
            m_handle = str(media.get_handle() or "")
            m_gid = str(media.get_gramps_id() or "")
            desc = str(media.get_description() or "")
            raw_path = str(media.get_path() or "")
            clean_raw = clean_path(raw_path)

            try:
                full_path = media_path_full(dbstate.db, clean_raw)
            except Exception:
                full_path = clean_raw

            exists = os.path.exists(full_path) or (
                is_absolute_path(clean_raw) and os.path.exists(clean_raw)
            )

            if not exists:
                # Look for the file name in the media directory (recursively
                # when a media base path is configured)
                basename = os.path.basename(clean_raw.replace("\\", "/"))
                sug_path = ""
                hint = _("File not found on disk")
                perm_issue = False
                inaccess_dir = None

                # Check for permission denied along the directory path
                perm_issue, inaccess_dir = check_path_permission(full_path)
                if not perm_issue and is_absolute_path(clean_raw):
                    perm_issue, inaccess_dir = check_path_permission(clean_raw)

                if perm_issue and inaccess_dir:
                    hint = _("Permission denied: cannot read '%s'") % inaccess_dir
                else:
                    sug_path = find_in_media_dir(base_dir, basename, name_index)
                    if sug_path:
                        hint = _("Found in media directory: suggest '%s'") % sug_path

                self.rows.append(
                    {
                        "handle": m_handle,
                        "gramps_id": m_gid,
                        "desc": desc,
                        "raw_path": raw_path,
                        "full_path": full_path,
                        "suggested_path": sug_path,
                        "hint_text": hint,
                        "perm_denied": perm_issue,
                        "inaccess_dir": inaccess_dir,
                    }
                )

        # A file found by name for several different records is not a safe
        # hint: offering it to all of them would make them duplicates.
        unsafe = ambiguous_matches(
            [
                (r["handle"], r["raw_path"], r["suggested_path"])
                for r in self.rows
                if r.get("suggested_path")
            ]
        )
        for r in self.rows:
            if r["handle"] in unsafe:
                r["hint_text"] = (
                    _(
                        "'%s' also matches other missing records: choose the path manually"
                    )
                    % r["suggested_path"]
                )
                r["suggested_path"] = ""

        n_hints = sum(1 for r in self.rows if r.get("suggested_path"))
        self.accept_button = Gtk.Button(label=str(_("Accept hints (%d)")) % n_hints)
        self.accept_button.set_sensitive(n_hints > 0)
        self.accept_button.connect("clicked", self.cb_accept_hints)
        self.add_action_widget(self.accept_button, Gtk.ResponseType.NONE)

        self.copy_button = Gtk.Button(label=str(_("Copy from folder...")))
        self.copy_button.set_sensitive(len(self.rows) > 0)
        self.copy_button.connect("clicked", self.cb_copy_from_folder)
        self.add_action_widget(self.copy_button, Gtk.ResponseType.NONE)

        self.apply_button = Gtk.Button(label=str(_("Apply")))
        self.apply_button.set_sensitive(len(self.rows) > 0)
        self.apply_button.connect("clicked", self.cb_apply)
        self.add_action_widget(self.apply_button, Gtk.ResponseType.NONE)

        self.add_button(str(_("_Close")), Gtk.ResponseType.CLOSE)

        content = self.get_content_area()
        content.set_border_width(12)
        content.set_spacing(6)

        info = Gtk.Label(
            label=str(
                _(
                    "Review media records whose files are missing on disk. "
                    "Type the updated path, choose the file with the folder button next to it, "
                    "or click 'Accept hints' if found in the media directory, then press 'Apply'. "
                    "Choosing a file also fills in other records missing a file of the same name."
                )
            )
        )
        info.set_line_wrap(True)
        info.set_halign(Gtk.Align.START)
        content.add(info)

        path_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        path_label = HeaderLabel(str(_("Base media path:")))
        path_box.pack_start(path_label, False, False, 0)

        self.path_entry = Gtk.Entry()
        if curr_mpath:
            self.path_entry.set_text(curr_mpath)
        self.path_entry.connect("changed", self.cb_set_mediapath)
        self.path_entry.set_hexpand(True)
        path_box.pack_start(self.path_entry, True, True, 0)

        self.path_button = Gtk.Button()
        self.path_button.connect("clicked", self.cb_select_mediapath)
        image = Gtk.Image()
        image.set_from_icon_name("document-open", Gtk.IconSize.BUTTON)
        image.show()
        self.path_button.add(image)
        path_box.pack_start(self.path_button, False, False, 0)
        content.add(path_box)

        self.base_path_label = SelectableLabel(
            label="<b>%s</b> %s"
            % (escape_markup(_("Media Base Path:")), escape_markup(self.base_dir)),
            markup=True,
        )
        content.add(self.base_path_label)

        if not self.rows:
            done = Gtk.Label(label=str(_("No missing media files found.")))
            done.set_halign(Gtk.Align.START)
            content.add(done)
            return

        count_label = Gtk.Label(
            label=str(_("Total missing media records found: %d") % len(self.rows))
        )
        count_label.set_halign(Gtk.Align.START)
        content.add(count_label)

        # Header grid
        header_grid = create_table_grid(col_spacing=6, row_spacing=0)
        header_grid.set_vexpand(False)

        media_head = HeaderLabel(str(_("Media")))
        path_head = HeaderLabel(str(_("Current Path")))
        new_path_head = HeaderLabel(str(_("New Path")))
        new_path_head.set_hexpand(True)
        hint_head = HeaderLabel(str(_("Hint")))

        header_grid.attach(media_head, 0, 0, 1, 1)
        header_grid.attach(path_head, 1, 0, 1, 1)
        header_grid.attach(new_path_head, 2, 0, 1, 1)
        header_grid.attach(hint_head, 3, 0, 1, 1)
        content.add(header_grid)

        self.column_sizegroups = [
            Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL) for _ in range(4)
        ]
        self.column_sizegroups[0].add_widget(media_head)
        self.column_sizegroups[1].add_widget(path_head)
        self.column_sizegroups[2].add_widget(new_path_head)
        self.column_sizegroups[3].add_widget(hint_head)

        content.pack_start(self.build_rows(self.rows), True, True, 0)

    def build_rows(self, entries: list[dict[str, Any]]) -> Gtk.ScrolledWindow:
        """
        Build one table row (media, current path, new path, hint) per record.

        :param entries: The missing-media rows.
        :returns: A scrolled window holding the table.
        """
        grid = create_table_grid()

        row_index = 0
        for entry in entries:
            # Column 0: Media description & ID (20% wider)
            m_text = "%s (%s)" % (
                entry.get("desc") or _("(unnamed)"),
                entry.get("gramps_id", ""),
            )
            media_label = TableLabel(m_text, width_chars=31, width_request=240)
            grid.attach(media_label, 0, row_index, 1, 1)

            # Column 1: Current Path (50% wider)
            curr_label = TableLabel(
                entry.get("raw_path", ""), width_chars=48, width_request=360
            )
            grid.attach(curr_label, 1, row_index, 1, 1)

            # Column 2: New Path entry (2.5x wider) with a file picker button
            path_entry = Gtk.Entry()
            path_entry.set_width_chars(70)
            path_entry.set_hexpand(True)
            path_entry.set_text("")
            browse_button = Gtk.Button()
            browse_button.set_tooltip_text(
                str(_("Choose the file for this media record"))
            )
            browse_image = Gtk.Image()
            browse_image.set_from_icon_name("document-open", Gtk.IconSize.BUTTON)
            browse_button.add(browse_image)
            path_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            path_box.pack_start(path_entry, True, True, 0)
            path_box.pack_start(browse_button, False, False, 0)
            grid.attach(path_box, 2, row_index, 1, 1)

            # Column 3: Hint label
            hint_label = TableLabel(
                entry.get("hint_text", ""), width_chars=28, width_request=220
            )
            grid.attach(hint_label, 3, row_index, 1, 1)

            if row_index == 0 and hasattr(self, "column_sizegroups"):
                self.column_sizegroups[0].add_widget(media_label)
                self.column_sizegroups[1].add_widget(curr_label)
                self.column_sizegroups[2].add_widget(path_box)
                self.column_sizegroups[3].add_widget(hint_label)

            target = {
                "entry": entry,
                "path_entry": path_entry,
                "hint_label": hint_label,
            }
            browse_button.connect("clicked", self.cb_pick_file, target)
            self.row_targets.append(target)
            row_index += 1

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_min_content_height(280)
        scrolled.set_min_content_width(1320)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.add(grid)
        return scrolled

    def cb_accept_hints(self, _button: Gtk.Button) -> None:
        """
        Copy each suggested path into its empty "New Path" entry.

        :param _button: The button that was clicked.
        """
        count = 0
        for target in self.row_targets:
            sug = target["entry"].get("suggested_path", "")
            if sug and not target["path_entry"].get_text():
                target["path_entry"].set_text(sug)
                count += 1
        OkDialog(
            str(_("Hints accepted")),
            str(
                _("Populated paths for %d media records. Review and press Apply.")
                % count
            ),
            parent=self,
        )

    def cb_pick_file(self, _button: Gtk.Button, target: dict[str, Any]) -> None:
        """
        Choose the file for one record, then fill in the other records that
        are missing a file with the same name.

        :param _button: The row's folder button.
        :param target: The row the button belongs to.
        """
        entry = target["entry"]
        missing_name = missing_file_name(entry.get("raw_path", ""))
        chooser = Gtk.FileChooserDialog(
            title=str(_("Select the file for %s"))
            % (entry.get("gramps_id") or missing_name),
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(
                str(_("_Cancel")),
                Gtk.ResponseType.CANCEL,
                str(_("_Open")),
                Gtk.ResponseType.OK,
            ),
        )
        chooser.set_default_size(800, 500)
        start_dir = self._last_pick_dir or self.base_dir
        if start_dir and os.path.isdir(start_dir):
            chooser.set_current_folder(start_dir)
        picked = (
            chooser.get_filename() if chooser.run() == Gtk.ResponseType.OK else None
        )
        chooser.destroy()
        if not picked:
            return
        self._last_pick_dir = os.path.dirname(picked)
        chosen = str(_("Chosen: %s")) % picked
        self.set_picked_file(target, picked, chosen)
        filled = self.fill_same_name(target, picked)
        if filled:
            target["hint_label"].set_text(
                chosen
                + " "
                + ngettext(
                    "Also filled %d other record missing a file of this name.",
                    "Also filled %d other records missing a file of this name.",
                    filled,
                )
                % filled
            )

    def set_picked_file(self, target: dict[str, Any], picked: str, hint: str) -> None:
        """
        Put a chosen file into a row's New Path entry.

        A file inside the media base path is shown relative to it, as Gramps
        stores it.  Any copy queued by "Copy from folder..." is dropped, because
        the chosen file is used where it is.

        :param target: The row to fill.
        :param picked: Full path of the chosen file.
        :param hint: Text for the row's hint column.
        """
        text = to_db_path(picked, self.base_dir)
        target.pop("copy_src", None)
        target["picked"] = picked
        target["picked_text"] = text
        target["path_entry"].set_text(text)
        target["hint_label"].set_text(hint)

    def fill_same_name(self, source: dict[str, Any], picked: str) -> int:
        """
        Fill every other empty row whose missing file has the same
        name as the chosen file.

        :param source: The row the file was chosen for.
        :param picked: Full path of the chosen file.
        :returns: How many rows were filled.
        """
        wanted = os.path.normcase(os.path.basename(picked))
        source_dir = missing_file_dir(source["entry"].get("raw_path", ""))
        source_id = source["entry"].get("gramps_id") or picked
        filled = 0
        for target in self.row_targets:
            if target is source:
                continue
            if target["path_entry"].get_text().strip():
                continue  # never overwrite a path already entered
            raw = target["entry"].get("raw_path", "")
            if os.path.normcase(missing_file_name(raw)) != wanted:
                continue
            if missing_file_dir(raw) == source_dir:
                hint = str(_("Same file as %s")) % source_id
            else:
                hint = (
                    str(
                        _(
                            "Same file name as %s, but it was in a different "
                            "folder: check it is the same file"
                        )
                    )
                    % source_id
                )
            self.set_picked_file(target, picked, hint)
            filled += 1
        return filled

    def cb_set_mediapath(self, *_args: Any) -> None:
        """Track the base path to use for copies and save it when changes are applied."""
        text = clean_path(self.path_entry.get_text())
        self._mediapath_text = text
        # Saved as None when emptied; resolved exactly as Gramps will.
        self.base_dir = expand_base_path(text or None, self.dbstate.db)
        self.base_path_label.set_markup(
            "<b>%s</b> %s"
            % (escape_markup(_("Media Base Path:")), escape_markup(self.base_dir))
        )

    def cb_select_mediapath(self, *_args: Any) -> None:
        """Open a folder chooser for the base media path."""
        chooser = Gtk.FileChooserDialog(
            title=str(_("Select media directory")),
            transient_for=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            buttons=(
                str(_("_Cancel")),
                Gtk.ResponseType.CANCEL,
                str(_("_Apply")),
                Gtk.ResponseType.OK,
            ),
        )
        if hasattr(chooser, "set_default_size"):
            chooser.set_default_size(600, 400)
        current_path = self._mediapath_text or self.base_dir
        if current_path and os.path.exists(current_path):
            chooser.set_current_folder(
                current_path
                if os.path.isdir(current_path)
                else os.path.dirname(current_path)
            )
        status = chooser.run()
        if status == Gtk.ResponseType.OK:
            selected_path = chooser.get_filename()
            if selected_path:
                self.path_entry.set_text(selected_path)
        chooser.destroy()

    def cb_copy_from_folder(self, _button: Gtk.Button) -> None:
        """Match missing files by name in a folder you can read and queue copies
        into the media directory (performed when Apply is pressed)."""
        if not self._mediapath_text:
            OkDialog(
                str(_("Set a base media path first")),
                str(
                    _(
                        "Copying needs a destination. Set the base media path above, "
                        "then try again."
                    )
                ),
                parent=self,
            )
            return
        chooser = Gtk.FileChooserDialog(
            title=str(_("Select folder containing the missing files")),
            transient_for=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            buttons=(
                str(_("_Cancel")),
                Gtk.ResponseType.CANCEL,
                str(_("_Select")),
                Gtk.ResponseType.OK,
            ),
        )
        folder = (
            chooser.get_filename() if chooser.run() == Gtk.ResponseType.OK else None
        )
        chooser.destroy()
        if not folder:
            return
        perm, where = check_path_permission(folder)
        if perm:
            OkDialog(
                str(_("Folder not readable")),
                str(_("Cannot read '%s'. Copy the files to a folder you own first."))
                % (where or folder),
                parent=self,
            )
            return
        index = build_basename_index(folder)
        queued = 0
        for target in self.row_targets:
            if target["path_entry"].get_text():
                continue
            raw = clean_path(target["entry"].get("raw_path", ""))
            hits = index.get(os.path.basename(raw.replace("\\", "/")).lower(), [])
            if len(hits) != 1:  # none, or ambiguous
                continue
            target["copy_src"] = hits[0]
            target["path_entry"].set_text(os.path.basename(hits[0]))
            target["hint_label"].set_text(str(_("Will copy from %s")) % hits[0])
            queued += 1
        OkDialog(
            str(_("Copies queued")),
            ngettext(
                "Queued %d file to copy into the media directory. "
                "Review and press Apply.",
                "Queued %d files to copy into the media directory. "
                "Review and press Apply.",
                queued,
            )
            % queued,
            parent=self,
        )

    def cb_apply(self, _button: Gtk.Button) -> None:
        """
        Repoint records to the entered paths, copying queued files first.

        A record is never pointed at a file that does not exist. If the base
        media path changed, other relative records are kept pointing at their
        files.

        :param _button: The button that was clicked.
        """
        applied = 0
        copied = 0
        skipped: list[str] = []
        claimed: set[str] = set()
        repointed: set[MediaHandle] = set()
        base = self.base_dir
        # Note where every relative record's file is before a base-path
        # change, so records outside this batch keep pointing at their files.
        base_changed = self._mediapath_text != self._orig_mediapath
        snapshot = snapshot_resolved_paths(self.dbstate.db) if base_changed else {}
        rebased = 0
        move_log = MoveLog(base, "Find missing media")
        with DbTxn(_("Update Missing Media Paths"), self.dbstate.db) as trans:
            if base_changed:
                self.dbstate.db.set_mediapath(self._mediapath_text or None)
                self._orig_mediapath = self._mediapath_text
            for target in self.row_targets:
                new_path = clean_path(target["path_entry"].get_text())
                if not new_path:
                    continue
                if target.get("picked") and new_path == target.get("picked_text"):
                    # A chosen file: store it relative to the base path in
                    # force now, in case the base path was changed afterwards.
                    new_path = to_db_path(target["picked"], base)
                try:
                    media = self.dbstate.db.get_media_from_handle(
                        target["entry"].get("handle")
                    )
                except Exception:
                    media = None
                if media is None:
                    continue
                store_path = new_path
                copy_src = target.get("copy_src")
                if copy_src:
                    dest = (
                        new_path
                        if is_absolute_path(new_path)
                        else os.path.join(base, new_path)
                    )
                    dest = unique_destination(dest, claimed, copy_src)
                    ok, err = relocate_file(copy_src, dest, copy=True)
                    if not ok:
                        skipped.append("%s (%s)" % (new_path, err))
                        continue
                    store_path = to_db_path(dest, base)
                    move_log.record(
                        "copy",
                        media,
                        clean_path(str(media.get_path() or "")),
                        store_path,
                        copy_src,
                        dest,
                    )
                    copied += 1
                else:
                    # A relative path is checked against the base media path
                    # only (it used to fall back to the working directory, so
                    # a path Gramps cannot open could be stored).
                    exists = os.path.exists(full_media_path(self.dbstate.db, new_path))
                    if not exists:  # never repoint a record at a missing file
                        skipped.append(new_path)
                        continue
                media.set_path(store_path)
                add_media_fixed_tag(self.dbstate.db, media, txn=trans)
                self.dbstate.db.commit_media(media, trans)
                repointed.add(media.get_handle())
                applied += 1

            if snapshot:
                rebased = keep_records_pointing_at_files(
                    self.dbstate.db, snapshot, trans, repointed
                )

        extra = base_change_summary(rebased)
        if applied == 0 and not skipped and not extra:
            OkDialog(
                str(_("Nothing to apply")),
                str(_("No paths entered. Press 'Accept hints' or enter paths first.")),
                parent=self,
            )
            return

        msg = str(_("Updated %d media file paths in the database.")) % applied
        if copied:
            msg += (
                " "
                + ngettext(
                    "Copied %d file into the media directory.",
                    "Copied %d files into the media directory.",
                    copied,
                )
                % copied
            )
        if skipped:
            msg += "\n\n" + _(
                "Skipped %(count)d (not found or copy failed):\n%(paths)s"
            ) % {"count": len(skipped), "paths": "\n".join(skipped[:10])}
        if extra:
            msg += "\n\n" + extra
        msg += move_log_summary(move_log)
        OkDialog(str(_("Media Paths Updated")), msg, parent=self)

    def show_dialog(self) -> None:
        """Show the dialog and run it until it is closed."""
        self.show_all()
        while True:
            resp = self.run()
            if resp in (
                Gtk.ResponseType.CLOSE,
                Gtk.ResponseType.CANCEL,
                Gtk.ResponseType.DELETE_EVENT,
            ):
                break
        self.destroy()


# ------------------------------------------------------------
#
# ConsolidateMediaLocationDialog
#
# ------------------------------------------------------------
class ConsolidateMediaLocationDialog(Gtk.Dialog):
    """Review and consolidate absolute/scattered media paths into relative media directory paths."""

    def __init__(
        self,
        title: str | None = None,
        dbstate: Any = None,
        transient_for: Gtk.Window | None = None,
    ) -> None:
        """
        Build the consolidation table; records sharing a file share one row.

        :param title: Window title (defaults to "Consolidate Media Location").
        :param dbstate: The Gramps database state.
        :param transient_for: Parent window.
        """
        dialog_title = title or str(_("Consolidate Media Location"))
        super().__init__(
            title=dialog_title,
            transient_for=transient_for,
            modal=True,
            destroy_with_parent=True,
        )
        self.dbstate = dbstate
        self.rows: list[dict[str, Any]] = []
        self.row_targets: list[dict[str, Any]] = []
        # Reference contexts do not depend on the template, so one cache serves
        # every hint recompute (template edits used to redo every backlink
        # traversal on each keystroke).
        self._ctx_cache: dict[str, dict[str, str]] = {}
        self.set_default_size(1360, 560)

        self.base_dir = (
            get_media_base_path(dbstate.db)
            if dbstate and dbstate.db
            else get_media_base_path(None)
        )

        content = self.get_content_area()
        content.set_border_width(12)
        content.set_spacing(6)

        info = Gtk.Label(
            label=str(
                _(
                    "Review media records with hardcoded absolute or non-standard paths. "
                    "Press 'Accept hints' to convert them to relative paths within your media directory, then press 'Apply'."
                )
            )
        )
        info.set_line_wrap(True)
        info.set_halign(Gtk.Align.START)
        content.add(info)

        # Media Base Path selector widget matching Preferences Family Tree tab
        path_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        path_label = HeaderLabel(str(_("Base media path:")))
        path_box.pack_start(path_label, False, False, 0)

        self.path_entry = Gtk.Entry()
        curr_mpath = (
            self.dbstate.db.get_mediapath()
            if self.dbstate
            and self.dbstate.db
            and hasattr(self.dbstate.db, "get_mediapath")
            else ""
        )
        self._orig_mediapath = (curr_mpath or "").strip()
        self._mediapath_text = self._orig_mediapath
        if curr_mpath:
            self.path_entry.set_text(curr_mpath)
        self.path_entry.connect("changed", self.cb_set_mediapath)
        self.path_entry.set_hexpand(True)
        path_box.pack_start(self.path_entry, True, True, 0)

        path_btn = Gtk.Button()
        path_btn.connect("clicked", self.cb_select_mediapath)
        image = Gtk.Image()
        image.set_from_icon_name("document-open", Gtk.IconSize.BUTTON)
        image.show()
        path_btn.add(image)
        self.path_button = path_btn
        path_box.pack_start(path_btn, False, False, 0)

        content.add(path_box)

        self.base_path_label = SelectableLabel(
            label="<b>%s</b> %s"
            % (escape_markup(_("Media Base Path:")), escape_markup(self.base_dir)),
            markup=True,
        )
        content.add(self.base_path_label)

        # Naming Template selection row
        tmpl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        tmpl_label = HeaderLabel(str(_("Naming Template:")))
        tmpl_box.pack_start(tmpl_label, False, False, 0)

        self.tmpl_combo = Gtk.ComboBoxText.new_with_entry()
        self.tmpl_combo.set_hexpand(True)
        for tmpl_str, tmpl_desc in FILENAME_PRESETS:
            self.tmpl_combo.append_text(tmpl_desc)

        curr_tmpl = config.get(CONFIG_TEMPLATE_KEY) or DEFAULT_FILENAME_TEMPLATE
        entry = self.tmpl_combo.get_child()
        if hasattr(entry, "set_text"):
            entry.set_text(curr_tmpl)
            if hasattr(entry, "connect"):
                entry.connect("activate", self.cb_template_entry_activated)

        self.tmpl_combo.connect("changed", self.cb_template_changed)
        tmpl_box.pack_start(self.tmpl_combo, True, True, 0)
        content.add(tmpl_box)

        # Naming style: Use naming standard vs Keep original filename
        naming_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        naming_label = HeaderLabel(str(_("Naming style:")))
        naming_box.pack_start(naming_label, False, False, 0)
        self.radio_use_standard = Gtk.RadioButton.new_with_label_from_widget(
            None, str(_("Use naming standard"))
        )
        self.radio_keep_original = Gtk.RadioButton.new_with_label_from_widget(
            self.radio_use_standard, str(_("Keep original filename"))
        )
        self.radio_use_standard.set_active(True)
        self.radio_use_standard.connect("toggled", self.cb_naming_style_toggled)
        self.radio_keep_original.connect("toggled", self.cb_naming_style_toggled)
        naming_box.pack_start(self.radio_use_standard, False, False, 0)
        naming_box.pack_start(self.radio_keep_original, False, False, 0)
        content.add(naming_box)

        # File operation: Move files vs Make a copy
        op_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        op_label = HeaderLabel(str(_("File operation:")))
        op_box.pack_start(op_label, False, False, 0)
        self.radio_move = Gtk.RadioButton.new_with_label_from_widget(
            None, str(_("Move files"))
        )
        self.radio_copy = Gtk.RadioButton.new_with_label_from_widget(
            self.radio_move, str(_("Make a copy"))
        )
        self.radio_move.set_active(True)
        op_box.pack_start(self.radio_move, False, False, 0)
        op_box.pack_start(self.radio_copy, False, False, 0)
        content.add(op_box)

        # Records that point at the same file become ONE row: the file is
        # moved once and every record is repointed.  (Shared files used to
        # block this dialog entirely.)
        shared_groups: dict[str, list[Any]] = {}
        for media in dbstate.db.iter_media():
            raw_path = clean_path(str(media.get_path() or ""))
            if not raw_path:
                continue
            key = path_key(full_media_path(dbstate.db, raw_path))
            shared_groups.setdefault(key, []).append(media)

        self.shared_count = 0
        for members in shared_groups.values():
            members.sort(key=lambda m: namer_rank(dbstate.db, m))
            media = members[0]  # names the file
            raw_path = str(media.get_path() or "")
            hint_val = self._compute_hint(raw_path, media)
            if not any(
                self._needs_consolidation(str(m.get_path() or ""), hint_val)
                for m in members
            ):
                continue
            desc = str(media.get_description() or "")
            if len(members) > 1:
                self.shared_count += 1
                desc = _("%(desc)s (file shared by %(count)d records)") % {
                    "desc": desc or _("(unnamed)"),
                    "count": len(members),
                }
            self.rows.append(
                {
                    "handle": str(media.get_handle() or ""),
                    "handles": [str(m.get_handle() or "") for m in members],
                    "gramps_id": ", ".join(_gid_of(m) for m in members),
                    "desc": desc,
                    "raw_path": raw_path,
                    "src_full": full_media_path(dbstate.db, raw_path),
                    "suggested_path": hint_val,
                    "hint_text": hint_val,
                    "media": media,
                }
            )

        # Kept for callers/tests that look at it; no longer blocks anything.
        self.dup_files: list[dict[str, Any]] = []
        if self.shared_count:
            info_label = SelectableLabel(
                label=ngettext(
                    "%d file is used by several media records. It is moved once "
                    "and all of its records are updated.",
                    "%d files are used by several media records. Each is moved "
                    "once and all of its records are updated.",
                    self.shared_count,
                )
                % self.shared_count,
            )
            content.add(info_label)

        n_hints = sum(1 for r in self.rows if r.get("suggested_path"))
        self.accept_button = Gtk.Button(label=str(_("Accept hints (%d)")) % n_hints)
        self.accept_button.set_sensitive(n_hints > 0)
        self.accept_button.connect("clicked", self.cb_accept_hints)
        self.add_action_widget(self.accept_button, Gtk.ResponseType.NONE)

        self.apply_button = Gtk.Button(label=str(_("Apply")))
        self.apply_button.set_sensitive(len(self.rows) > 0)
        self.apply_button.connect("clicked", self.cb_apply)
        self.add_action_widget(self.apply_button, Gtk.ResponseType.NONE)

        self.add_button(str(_("_Close")), Gtk.ResponseType.CLOSE)

        if not self.rows:
            done = Gtk.Label(label=str(_("All media paths are already consolidated.")))
            done.set_halign(Gtk.Align.START)
            content.add(done)
            return

        count_label = Gtk.Label(
            label=str(_("Total unconsolidated media paths: %d") % len(self.rows))
        )
        count_label.set_halign(Gtk.Align.START)
        content.add(count_label)

        header_grid = create_table_grid(col_spacing=6, row_spacing=0)
        header_grid.set_vexpand(False)

        media_head = HeaderLabel(str(_("Media")))
        path_head = HeaderLabel(str(_("Current Path")))
        new_path_head = HeaderLabel(str(_("Consolidated Path")))
        new_path_head.set_hexpand(True)
        hint_head = HeaderLabel(str(_("Hint")))

        header_grid.attach(media_head, 0, 0, 1, 1)
        header_grid.attach(path_head, 1, 0, 1, 1)
        header_grid.attach(new_path_head, 2, 0, 1, 1)
        header_grid.attach(hint_head, 3, 0, 1, 1)
        content.add(header_grid)

        self.column_sizegroups = [
            Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL) for _ in range(4)
        ]
        self.column_sizegroups[0].add_widget(media_head)
        self.column_sizegroups[1].add_widget(path_head)
        self.column_sizegroups[2].add_widget(new_path_head)
        self.column_sizegroups[3].add_widget(hint_head)

        content.pack_start(self.build_rows(self.rows), True, True, 0)

    def build_rows(self, entries: list[dict[str, Any]]) -> Gtk.ScrolledWindow:
        """
        Build one table row (media, current path, new path, hint) per file.

        :param entries: The consolidation rows.
        :returns: A scrolled window holding the table.
        """
        grid = create_table_grid()

        row_index = 0
        for entry in entries:
            # Column 0: Media description & ID (25% wider)
            m_text = "%s (%s)" % (
                entry.get("desc") or _("(unnamed)"),
                entry.get("gramps_id", ""),
            )
            media_label = TableLabel(m_text, width_chars=33, width_request=250)
            grid.attach(media_label, 0, row_index, 1, 1)

            # Column 1: Current Path (50% wider)
            curr_label = TableLabel(
                entry.get("raw_path", ""), width_chars=48, width_request=360
            )
            grid.attach(curr_label, 1, row_index, 1, 1)

            # Column 2: Consolidated Path entry
            path_entry = Gtk.Entry()
            path_entry.set_width_chars(50)
            path_entry.set_hexpand(True)
            path_entry.set_text("")
            grid.attach(path_entry, 2, row_index, 1, 1)

            # Column 3: Hint label
            hint_label = TableLabel(
                entry.get("hint_text", ""), width_chars=48, width_request=360
            )
            hint_label.set_hexpand(True)
            grid.attach(hint_label, 3, row_index, 1, 1)

            if row_index == 0 and hasattr(self, "column_sizegroups"):
                self.column_sizegroups[0].add_widget(media_label)
                self.column_sizegroups[1].add_widget(curr_label)
                self.column_sizegroups[2].add_widget(path_entry)
                self.column_sizegroups[3].add_widget(hint_label)

            self.row_targets.append(
                {
                    "entry": entry,
                    "path_entry": path_entry,
                    "hint_label": hint_label,
                }
            )
            row_index += 1

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_min_content_height(280)
        scrolled.set_min_content_width(1280)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.add(grid)
        return scrolled

    def cb_set_mediapath(self, *obj: Any) -> None:
        """Track the base path typed by the user.

        The database is NOT modified here (it used to be, on every keystroke and
        with no undo); a changed base path is committed when Apply is pressed.
        """
        if not self.dbstate or not self.dbstate.db:
            return
        text = clean_path(self.path_entry.get_text())
        self._mediapath_text = text
        # Saved as None when emptied; resolved exactly as Gramps will.
        self.base_dir = expand_base_path(text or None, self.dbstate.db)
        if hasattr(self, "base_path_label"):
            self.base_path_label.set_markup(
                "<b>%s</b> %s"
                % (escape_markup(_("Media Base Path:")), escape_markup(self.base_dir))
            )
        self._recompute_hints()

    def cb_select_mediapath(self, *obj: Any) -> None:
        """Show dialog to choose media directory, matching Preferences Family Tree tab."""
        f = Gtk.FileChooserDialog(
            title=str(_("Select media directory")),
            transient_for=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            buttons=(
                str(_("_Cancel")),
                Gtk.ResponseType.CANCEL,
                str(_("_Apply")),
                Gtk.ResponseType.OK,
            ),
        )
        if hasattr(f, "set_default_size"):
            f.set_default_size(600, 400)
        mpath = media_path(self.dbstate.db) if self.dbstate and self.dbstate.db else ""
        if mpath and os.path.exists(mpath):
            f.set_current_folder(
                mpath if os.path.isdir(mpath) else os.path.dirname(mpath)
            )
        elif self.base_dir and os.path.exists(self.base_dir):
            f.set_current_folder(
                self.base_dir
                if os.path.isdir(self.base_dir)
                else os.path.dirname(self.base_dir)
            )

        status = f.run()
        if status == Gtk.ResponseType.OK:
            val = f.get_filename()
            if val:
                self.path_entry.set_text(val)
        f.destroy()

    def _needs_consolidation(self, raw_path: str, hint_val: str) -> bool:
        """
        Return True when a record is not yet at its consolidated location.

        The hint is an absolute path inside the base directory, while an
        already-consolidated record stores the matching *relative* path, so the
        two are compared in database form.  (Comparing the stored path with the
        absolute hint directly listed every record, every time.)

        :param raw_path: The path stored on the media record.
        :param hint_val: The suggested absolute path from :meth:`_compute_hint`.
        :returns: ``True`` if the record should be listed.
        """
        clean_raw = clean_path(raw_path)
        if not clean_raw:
            return False
        if is_absolute_path(clean_raw):
            return True
        target = to_db_path(hint_val, self.base_dir).replace("\\", "/")
        return clean_raw.replace("\\", "/") != target

    def _get_current_template(self) -> str:
        """
        Return the naming template chosen in the combo box (or the saved one).

        :returns: The filename template.
        """
        if hasattr(self, "tmpl_combo"):
            idx = self.tmpl_combo.get_active()
            if isinstance(idx, int) and 0 <= idx < len(FILENAME_PRESETS):
                return FILENAME_PRESETS[idx][0]
            entry = self.tmpl_combo.get_child()
            if hasattr(entry, "get_text"):
                val = entry.get_text()
                if isinstance(val, str) and val.strip():
                    return val.strip()
        return config.get(CONFIG_TEMPLATE_KEY) or DEFAULT_FILENAME_TEMPLATE

    def _compute_hint(self, raw_path: str, media: Any = None) -> str:
        """Compute hint path: base media path plus filename (using naming standard or original filename)."""
        if hasattr(self, "radio_keep_original") and bool(
            self.radio_keep_original.get_active()
        ):
            use_std = False
        elif hasattr(self, "radio_use_standard") and bool(
            self.radio_use_standard.get_active()
        ):
            use_std = True
        else:
            use_std = True
        curr_tmpl = self._get_current_template()
        if use_std:
            std = sanitize_standard_filename(
                raw_path,
                db=self.dbstate.db if self.dbstate else None,
                media=media,
                template=curr_tmpl,
                cache=getattr(self, "_ctx_cache", None),
            )
            fname = os.path.basename(std)
        else:
            fname = os.path.basename(raw_path)

        if hasattr(self, "base_dir") and self.base_dir:
            return os.path.join(self.base_dir, fname).replace("\\", "/")
        return fname.replace("\\", "/")

    def cb_template_changed(self, combo: Gtk.ComboBoxText) -> None:
        """
        Use a preset or typed template and recompute the hints.

        :param combo: The template combo box.
        """
        idx = combo.get_active()
        if isinstance(idx, int) and 0 <= idx < len(FILENAME_PRESETS):
            tmpl_str = FILENAME_PRESETS[idx][0]
            entry = combo.get_child()
            if hasattr(entry, "set_text"):
                entry.set_text(tmpl_str)
            self.apply_template(tmpl_str)
        else:
            entry = combo.get_child()
            if hasattr(entry, "get_text"):
                val = entry.get_text()
                if isinstance(val, str) and val.strip():
                    self.apply_template(val.strip())

    def cb_template_entry_activated(self, entry: Gtk.Entry) -> None:
        """
        Apply a typed template when Enter is pressed.

        :param entry: The combo box's text entry.
        """
        tmpl_str = entry.get_text().strip()
        if tmpl_str:
            self.apply_template(tmpl_str)

    def apply_template(self, tmpl_str: str) -> None:
        """
        Save the template and recompute every row's hint.

        :param tmpl_str: The filename template.
        """
        config.set(CONFIG_TEMPLATE_KEY, tmpl_str)
        self._recompute_hints()

    def cb_naming_style_toggled(self, _button: Gtk.RadioButton) -> None:
        """
        Recompute the hints when the naming style changes.

        :param _button: The radio button that was toggled.
        """
        self._recompute_hints()

    def _recompute_hints(self) -> None:
        """Recompute suggested paths when base directory, template, or naming style changes."""
        for target in self.row_targets:
            entry = target["entry"]
            raw_path = entry.get("raw_path", "")
            media = entry.get("media")
            hint_val = self._compute_hint(raw_path, media)
            entry["suggested_path"] = hint_val
            entry["hint_text"] = hint_val
            if "hint_label" in target:
                target["hint_label"].set_text(hint_val)

        n_hints = sum(
            1 for target in self.row_targets if target["entry"].get("suggested_path")
        )
        if hasattr(self, "accept_button"):
            self.accept_button.set_label(str(_("Accept hints (%d)")) % n_hints)
            self.accept_button.set_sensitive(n_hints > 0)

    def cb_accept_hints(self, _button: Gtk.Button) -> None:
        """
        Copy each row's suggested path into its "Consolidated Path" entry.

        :param _button: The button that was clicked.
        """
        count = 0
        for target in self.row_targets:
            sug = target["entry"].get("suggested_path", "")
            if sug:
                target["path_entry"].set_text(sug)
                count += 1
        OkDialog(
            str(_("Hints accepted")),
            str(
                _(
                    "Populated consolidated paths for %d media records. Review and press Apply."
                )
                % count
            ),
            parent=self,
        )

    def cb_apply(self, _button: Gtk.Button) -> None:
        """
        Move (or copy) each row's file once and repoint all of its records.

        Rows are grouped by source file, so a shared file is handled once for
        every record that uses it.  If the base media path was changed, other
        relative records are kept pointing at their files.
        """
        # Safety net: rows are grouped by source file, so two rows can only
        # share one if row_targets was built by hand.
        seen_srcs: dict[str, str] = {}
        for target in self.row_targets:
            new_p = clean_path(target["path_entry"].get_text())
            if not new_p:
                continue
            src_f = path_key(target["entry"].get("src_full", ""))
            if src_f in seen_srcs:
                OkDialog(
                    str(_("Duplicate Source Files Detected")),
                    str(
                        _(
                            "Multiple records in this consolidation list share the source file:\n'%s'\n\n"
                            "Moving this file would cause subsequent moves to fail and leave dangling references.\n\n"
                            "Please use 'Fix media references' first."
                        )
                        % target["entry"].get("raw_path", "")
                    ),
                    parent=self,
                )
                return
            seen_srcs[src_f] = target["entry"].get("gramps_id", "")

        db = self.dbstate.db
        applied = 0
        files_moved = 0
        files_copied = 0
        failures: list[str] = []
        claimed: set[str] = set()
        repointed: set[MediaHandle] = set()
        is_copy = hasattr(self, "radio_copy") and bool(self.radio_copy.get_active())
        base = self.base_dir

        # Commit a changed base path now (once), not on every keystroke, but
        # first note where every relative record's file really is.
        base_changed = self._mediapath_text != self._orig_mediapath
        snapshot = snapshot_resolved_paths(db) if base_changed else {}
        if base_changed:
            db.set_mediapath(self._mediapath_text or None)
            self._orig_mediapath = self._mediapath_text

        rebased = 0
        move_log = MoveLog(base, "Consolidate")
        with DbTxn(_("Consolidate Media Locations"), db) as trans:
            for target in self.row_targets:
                new_path = clean_path(target["path_entry"].get_text())
                if not new_path:
                    continue
                entry = target["entry"]
                gid = entry.get("gramps_id", "")
                records = []
                for handle in entry.get("handles") or [entry.get("handle")]:
                    try:
                        found = db.get_media_from_handle(handle)
                    except Exception:
                        found = None
                    if found is not None:
                        records.append(found)
                if not records:
                    continue

                src_full = entry.get("src_full", "")
                dest_full = (
                    new_path
                    if is_absolute_path(new_path)
                    else os.path.join(base, new_path)
                )
                if not src_full or not os.path.exists(src_full):
                    failures.append(
                        "[%s] %s: %s"
                        % (gid, entry.get("raw_path", ""), _("source file not found"))
                    )
                    continue

                dest_full = unique_destination(dest_full, claimed, src_full)
                ok, err = relocate_file(src_full, dest_full, copy=is_copy)
                if not ok:
                    LOG.warning("Failed to relocate '%s': %s", src_full, err)
                    failures.append(
                        "[%s] %s: %s" % (gid, entry.get("raw_path", ""), err)
                    )
                    continue
                if path_key(src_full) != path_key(dest_full):
                    if is_copy:
                        files_copied += 1
                    else:
                        files_moved += 1

                # Only now, with the file safely in place, repoint the records.
                new_rel = to_db_path(dest_full, base)
                if path_key(src_full) == path_key(dest_full):
                    action = "repoint"
                else:
                    action = "copy" if is_copy else "move"
                for media in records:
                    move_log.record(
                        action,
                        media,
                        clean_path(str(media.get_path() or "")),
                        new_rel,
                        src_full,
                        dest_full,
                    )
                    media.set_path(new_rel)
                    add_media_fixed_tag(db, media, txn=trans)
                    db.commit_media(media, trans)
                    repointed.add(media.get_handle())
                    applied += 1

            if snapshot:
                rebased = keep_records_pointing_at_files(db, snapshot, trans, repointed)

        if applied == 0 and not failures and not rebased:
            if base_changed:
                OkDialog(
                    str(_("Base media path saved")),
                    str(_("The base media path was saved. No records needed changes.")),
                    parent=self,
                )
                return
            OkDialog(
                str(_("Nothing to apply")),
                str(_("No paths entered. Press 'Accept hints' or enter paths first.")),
                parent=self,
            )
            return

        summary = str(_("Consolidated %d media file paths in the database.")) % applied
        if is_copy and files_copied > 0:
            summary += " " + str(_("Copied %d files to new locations.") % files_copied)
        elif not is_copy and files_moved > 0:
            summary += " " + str(_("Moved %d files to new locations.") % files_moved)
        extra = base_change_summary(rebased)
        if extra:
            summary += "\n\n" + extra
        summary += move_log_summary(move_log)

        if failures:
            summary += "\n\n" + str(_("Not changed (%d):")) % len(failures) + "\n"
            summary += "\n".join(failures[:10])
        OkDialog(
            str(_("Media Locations Consolidated")),
            summary,
            parent=self,
        )

    def show_dialog(self) -> None:
        """Show the dialog and run it until it is closed."""
        self.show_all()
        while True:
            resp = self.run()
            if resp in (
                Gtk.ResponseType.CLOSE,
                Gtk.ResponseType.CANCEL,
                Gtk.ResponseType.DELETE_EVENT,
            ):
                break
        self.destroy()


# ------------------------------------------------------------
#
# MediaFixReportDialog
#
# ------------------------------------------------------------
class MediaFixReportDialog(Gtk.Dialog):
    """Viewer dialog for the GWizard Media Fix report."""

    def __init__(
        self,
        report_text: str = "",
        dbstate: Any = None,
        title: str | None = None,
        transient_for: Gtk.Window | None = None,
    ) -> None:
        """Initialize the report viewer dialog."""
        dialog_title = title or str(_("GWizard Media Fix Report"))
        super().__init__(
            title=dialog_title,
            transient_for=transient_for,
            modal=True,
            destroy_with_parent=True,
        )
        self.dbstate = dbstate
        self.report_text = report_text
        self.set_default_size(800, 500)
        self.add_button(str(_("_Close")), Gtk.ResponseType.CLOSE)
        # Destroyed by the caller after run(); a response handler that also
        # destroyed it caused a second destroy on an already-destroyed dialog.

        content = self.get_content_area()
        content.set_border_width(12)
        content.set_spacing(6)

        self.base_dir = (
            get_media_base_path(dbstate.db)
            if dbstate and dbstate.db
            else get_media_base_path(None)
        )
        self.base_path_label = SelectableLabel(
            label="<b>%s</b> %s"
            % (escape_markup(_("Media Base Path:")), escape_markup(self.base_dir)),
            markup=True,
        )
        content.pack_start(self.base_path_label, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)

        self.textview = Gtk.TextView()
        self.textview.set_editable(False)
        self.textview.set_monospace(True)
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        self.textview.get_buffer().set_text(self.report_text)
        scrolled.add(self.textview)

        content.pack_start(scrolled, True, True, 0)


# ------------------------------------------------------------
#
# AcceptAllHintsReportDialog
#
# ------------------------------------------------------------
class AcceptAllHintsReportDialog(Gtk.Dialog):
    """Report dialog for Accept all hints using SelectableLabel for copyable text."""

    def __init__(
        self,
        report_text: str = "",
        title: str | None = None,
        transient_for: Gtk.Window | None = None,
    ) -> None:
        """
        Build the result dialog with selectable, copyable text.

        :param report_text: The report to show.
        :param title: Window title.
        :param transient_for: Parent window.
        """
        dialog_title = title or str(_("Accept All Hints Complete"))
        super().__init__(
            title=dialog_title,
            transient_for=transient_for,
            modal=True,
            destroy_with_parent=True,
        )
        self.report_text = report_text
        self.set_default_size(720, 480)
        self.add_button(str(_("_Close")), Gtk.ResponseType.CLOSE)

        content = self.get_content_area()
        content.set_border_width(12)
        content.set_spacing(6)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.report_label = SelectableLabel(
            label=report_text,
            selectable=True,
            wrap=True,
            can_focus=True,
        )
        scrolled.add(self.report_label)
        content.pack_start(scrolled, True, True, 0)

    def show_dialog(self) -> None:
        """Show the dialog and run it until it is closed."""
        self.show_all()
        while True:
            resp = self.run()
            if resp in (
                Gtk.ResponseType.CLOSE,
                Gtk.ResponseType.CANCEL,
                Gtk.ResponseType.DELETE_EVENT,
            ):
                break
        self.destroy()


def generate_media_fix_report(db: DbReadBase, progress_parent: Any = None) -> str:
    """Scan all media objects in database, check existence with os.path.exists(), and return formatted report."""
    base_dir = get_media_base_path(db) if db else get_media_base_path(None)
    curr_tmpl = config.get(CONFIG_TEMPLATE_KEY) or DEFAULT_FILENAME_TEMPLATE
    total = 0
    found = 0
    missing = 0
    permission_denied = 0
    absolute_paths = 0
    non_standard = 0
    in_default_path = 0
    outside_default_path = 0

    missing_list: list[tuple[str, str, str]] = []
    perm_denied_list: list[tuple[str, str, str, str]] = []
    abs_list: list[tuple[str, str, str]] = []
    non_std_list: list[tuple[str, str, str, str, str]] = []
    outside_default_list: list[tuple[str, str, str]] = []
    multi_ref_media: list[tuple[str, str, str, int, list[tuple[str, str]]]] = []
    zero_ref_media: list[tuple[str, str, str]] = []
    fixed_media: list[tuple[str, str, str]] = []

    # Detect duplicate media records pointing to the same file
    ctx_cache: dict[str, dict[str, str]] = {}
    dup_files = find_duplicate_media_references(db, ctx_cache)
    dup_media_count = sum(len(records) for records in dup_files.values())

    # Keep suggested names synchronized for duplicate file paths
    file_to_std_basename: dict[str, str] = {}

    n_media = db.get_number_of_media() if hasattr(db, "get_number_of_media") else 0
    prog = _Progress(str(_("Scanning media")), n_media, progress_parent)
    for media in db.iter_media():
        total += 1
        prog.step()
        m_handle = str(media.get_handle() or "")
        m_gid = str(media.get_gramps_id() or "")
        desc = str(media.get_description() or "")

        # Inspect backlinks from database elements
        backlinks: list[tuple[str, str]] = []
        if db and hasattr(db, "find_backlink_handles") and m_handle:
            try:
                backlinks = list(db.find_backlink_handles(m_handle))
            except Exception:
                backlinks = []

        # Inspect file path(s) using media.get_path() or media.get_file_list() if available
        raw_paths = [str(media.get_path() or "")]
        ctx = resolve_media_reference_context(db, media, ctx_cache)

        first_raw = raw_paths[0] if raw_paths else ""
        if has_media_fixed_tag(db, media):
            fixed_media.append((m_gid, desc, first_raw))

        if len(backlinks) > 1:
            multi_ref_media.append((m_gid, desc, first_raw, len(backlinks), backlinks))
        elif len(backlinks) == 0:
            zero_ref_media.append((m_gid, desc, first_raw))

        for raw_path in raw_paths:
            clean_raw = clean_path(raw_path)
            # Check default path location
            if is_in_default_path(clean_raw, base_dir):
                in_default_path += 1
            else:
                outside_default_path += 1
                outside_default_list.append((m_gid, desc, raw_path))

            # Check existence on filesystem
            try:
                full_path = media_path_full(db, clean_raw)
                norm_key = os.path.normcase(os.path.normpath(full_path))
            except Exception:
                full_path = clean_raw
                norm_key = os.path.normcase(os.path.normpath(clean_raw))

            exists = os.path.exists(full_path) or (
                is_absolute_path(clean_raw) and os.path.exists(clean_raw)
            )
            if exists:
                found += 1
            else:
                alt_path = (
                    os.path.join(base_dir, clean_raw)
                    if base_dir and not is_absolute_path(clean_raw)
                    else None
                )
                if alt_path and os.path.exists(alt_path):
                    found += 1
                else:
                    perm_issue, inaccess_dir = check_path_permission(full_path)
                    if not perm_issue and alt_path:
                        perm_issue, inaccess_dir = check_path_permission(alt_path)

                    if perm_issue and inaccess_dir:
                        permission_denied += 1
                        perm_denied_list.append((m_gid, desc, raw_path, inaccess_dir))
                    else:
                        missing += 1
                        missing_list.append((m_gid, desc, raw_path))

            # Check absolute path
            if is_absolute_path(clean_raw):
                absolute_paths += 1
                abs_list.append((m_gid, desc, raw_path))

            # Check filename standards
            if raw_path:
                assoc_str = ctx.get("assoc", "")
                dirname, _base = os.path.split(raw_path)

                if norm_key in file_to_std_basename:
                    std_basename = file_to_std_basename[norm_key]
                    std_path = (
                        os.path.join(dirname, std_basename) if dirname else std_basename
                    )
                else:
                    std_path = sanitize_standard_filename(
                        raw_path,
                        db=db,
                        media=media,
                        template=curr_tmpl,
                        cache=ctx_cache,
                    )
                    file_to_std_basename[norm_key] = os.path.basename(std_path)

                if path_key(std_path) != path_key(raw_path):
                    non_standard += 1
                    non_std_list.append((m_gid, desc, raw_path, std_path, assoc_str))

    prog.close()
    name_mismatches = find_name_mismatches(db)

    # Scan default path for unreferenced multimedia files
    # (skipped when no media base path is configured: the fallback is the user's
    # home folder, and every stray PDF/TXT there would be reported as "unreferenced")
    scan_stats: dict[str, Any] = {}
    base_configured = bool((db.get_mediapath() or "").strip()) if db else False
    unref_disk_files = (
        find_unreferenced_default_path_files(db, base_dir, stats=scan_stats)
        if base_configured
        else []
    )

    rule = "-" * 72
    unnamed = _("(unnamed)")

    def metric(label: str, value: Any) -> str:
        """Format one summary line, values aligned in column 29."""
        return "  %s%s" % (label.ljust(27), value)

    def heading(text: str) -> None:
        """Start a report section."""
        lines.extend([rule, text, rule])

    def field(label: str, value: Any, width: int = 0) -> str:
        """Format an indented "Label: value" line."""
        return (
            "    %s %s" % (label.ljust(width), value)
            if width
            else ("    %s %s" % (label, value))
        )

    if base_configured:
        unref_value = str(len(unref_disk_files))
    else:
        unref_value = _("n/a (no media base path set)")
    if scan_stats.get("truncated"):
        unref_value += " " + _("(scan truncated)")

    lines: list[str] = [
        "=" * 72,
        _("GWIZARD MEDIA FIX REPORT"),
        "=" * 72,
        "",
        _("SUMMARY METRICS:"),
        metric(_("Total media records:"), total),
        metric(_("Files in default path:"), in_default_path),
        metric(_("Files outside default path:"), outside_default_path),
        metric(_("Files found on disk:"), found),
        metric(_("Files missing on disk:"), missing),
        metric(_("Permission denied files:"), permission_denied),
        metric(_("Absolute file paths:"), absolute_paths),
        metric(_("Non-standard filenames:"), non_standard),
        metric(_("Unreferenced path files:"), unref_value),
        metric(_("Unreferenced image tags:"), len(zero_ref_media)),
        metric(
            _("Shared media records:"),
            _("%d (info)") % len(multi_ref_media),
        ),
        metric(_("Fixed media records:"), len(fixed_media)),
        metric(_("Name mismatches:"), len(name_mismatches)),
        metric(
            _("Duplicate file references:"),
            _("%(files)d files (%(records)d media records)")
            % {"files": len(dup_files), "records": dup_media_count},
        ),
        metric(_("Naming template:"), curr_tmpl),
        metric(_("Media Base Path:"), base_dir),
        "",
    ]

    if dup_files:
        heading(
            _("DUPLICATE FILE REFERENCES (%d files shared by multiple records):")
            % len(dup_files)
        )
        for records in dup_files.values():
            lines.append("  %s %s" % (_("File:"), records[0][2]))
            lines.append("    " + _("Referenced by %d media records:") % len(records))
            for gid, desc, _p, assoc_str in records:
                assoc_part = f" ({assoc_str})" if assoc_str else ""
                lines.append(f"      - [{gid}] {desc}{assoc_part}")
        lines.append("")

    if unref_disk_files:
        heading(
            _(
                "UNREFERENCED FILES IN DEFAULT PATH (%d files with no database "
                "connection):"
            )
            % len(unref_disk_files)
        )
        for rel_f in unref_disk_files[:100]:
            lines.append(f"  {rel_f}")
        if len(unref_disk_files) > 100:
            lines.append(
                "  " + _("... and %d more files.") % (len(unref_disk_files) - 100)
            )
        lines.append("")

    if multi_ref_media:
        heading(
            _(
                "SHARED MEDIA RECORDS - one file used from several places "
                "(%d items, informational):"
            )
            % len(multi_ref_media)
        )
        for gid, desc, path, r_count, blinks in multi_ref_media:
            type_counts: dict[str, int] = {}
            for cname, _h in blinks:
                type_counts[cname] = type_counts.get(cname, 0) + 1
            t_str = ", ".join(f"{k}: {v}" for k, v in sorted(type_counts.items()))
            lines.append(f"  [{gid}] {desc}")
            lines.append(field(_("Path:"), path, 11))
            lines.append(field(_("References:"), f"{r_count} ({t_str})", 11))
        lines.append("")

    if name_mismatches:
        heading(
            _("NAME MISMATCHES - description vs linked person (%d items):")
            % len(name_mismatches)
        )
        for gid, desc, in_desc, linked, kind in name_mismatches:
            lines.append(f"  [{gid}] {desc}")
            lines.append(field(_("Description says:"), in_desc, 17))
            lines.append(field(_("Linked person:"), f"{linked}  ({kind})", 17))
        lines.append("")

    heading(
        _(
            "UNREFERENCED IMAGE TAGS / MEDIA RECORDS (%d items with no data "
            "references):"
        )
        % len(zero_ref_media)
    )
    if zero_ref_media:
        for gid, desc, path in zero_ref_media:
            lines.append(f"  [{gid}] {desc or unnamed}")
            lines.append(field(_("Path:"), path))
    else:
        lines.append(
            "  "
            + _(
                "0 unreferenced image tags found. All media records have data "
                "references."
            )
        )
    lines.append("")

    if outside_default_list:
        heading(_("FILES OUTSIDE DEFAULT PATH (%d items):") % len(outside_default_list))
        for gid, desc, path in outside_default_list:
            lines.append(f"  [{gid}] {desc}")
            lines.append(field(_("Path:"), path))
        lines.append("")

    heading(
        _(
            "PERMISSION DENIED FILES (%d files inaccessible due to directory "
            "permissions):"
        )
        % len(perm_denied_list)
    )
    if perm_denied_list:
        for gid, desc, path, inaccess in perm_denied_list:
            lines.append(f"  [{gid}] {desc or unnamed}")
            lines.append(field(_("Path:"), path, 16))
            lines.append(field(_("Inaccessible at:"), inaccess, 16))
    else:
        lines.append(
            "  "
            + _(
                "0 permission errors encountered. All inspected directories are "
                "readable."
            )
        )
    lines.append("")

    if missing_list:
        heading(_("MISSING FILES (%d items):") % len(missing_list))
        for gid, desc, path in missing_list:
            lines.append(f"  [{gid}] {desc}")
            lines.append(field(_("Path:"), path))
        lines.append("")

    if abs_list:
        heading(_("ABSOLUTE PATHS (%d items):") % len(abs_list))
        for gid, desc, path in abs_list:
            lines.append(f"  [{gid}] {desc}")
            lines.append(field(_("Path:"), path))
        lines.append("")

    if non_std_list:
        heading(_("NON-STANDARD FILENAMES (%d items):") % len(non_std_list))
        for gid, desc, path, std_p, assoc_str in non_std_list:
            lines.append(f"  [{gid}] {desc}")
            if assoc_str:
                lines.append(field(_("Association:"), assoc_str, 12))
            lines.append(field(_("Current:"), path, 12))
            lines.append(field(_("Standard:"), std_p, 12))
        lines.append("")

    return "\n".join(lines)


# ------------------------------------------------------------
#
# GWizardMediaFix Window Controller
#
# ------------------------------------------------------------
class GWizardMediaFixOptions(tool.ToolOptions):
    """Tool options for GWizard Media Fix."""

    def __init__(self, name: str, person_id: str | None = None) -> None:
        """
        Set up the tool options.

        :param name: The tool's name.
        :param person_id: The active person's Gramps ID, if any.
        """
        super().__init__(name, person_id)


class GWizardMediaFix(tool.Tool, ManagedWindow):
    """Top-level GWizard Media Fix tool window."""

    def __init__(
        self,
        dbstate: Any,
        user: Any,
        options_class: Any,
        name: str,
        callback: Any = None,
    ) -> None:
        """
        Open the GWizard Media Fix window.

        :param dbstate: The Gramps database state.
        :param user: The Gramps user object (gives the UI state).
        :param options_class: The tool's options class.
        :param name: The tool's name.
        :param callback: Unused; part of the Gramps tool interface.
        """
        uistate = user.uistate
        tool.Tool.__init__(self, dbstate, options_class, name)
        ManagedWindow.__init__(self, uistate, [], self.__class__, modal=True)
        self.dbstate = dbstate
        self.report_path: str | None = None
        # GWizard tags are created when first applied; opening the tool no
        # longer writes to the tree (it used to add an undo entry).
        self._build_window(uistate)
        self.show()

    def _build_window(self, uistate: Any) -> None:
        """
        Build the main window with one button per step.

        :param uistate: The Gramps UI state.
        """
        dialog = Gtk.Dialog(
            title=str(_("GWizard Media Fix")),
            transient_for=uistate.window,
            modal=True,
            destroy_with_parent=True,
        )
        content = dialog.get_content_area()
        content.set_border_width(12)
        content.set_spacing(8)

        desc = Gtk.Label(
            label=str(
                _(
                    "Comprehensive utility to inspect media files across your database, find missing files, "
                    "consolidate storage locations into relative paths, and enforce standardized filename formats."
                )
            )
        )
        desc.set_line_wrap(True)
        desc.set_halign(Gtk.Align.START)
        content.add(desc)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.pack_start(vbox, True, True, 0)

        specs = [
            ("generate", str(_("Generate report"))),
            ("find_missing", str(_("Find missing media"))),
            ("fix_references", str(_("Fix media references"))),
            ("consolidate_location", str(_("Consolidate media location"))),
            ("clean_notes", str(_("Clean import notes"))),
            ("undo_moves", str(_("Undo last file moves"))),
        ]

        self.buttons: dict[str, Gtk.Button] = {}
        for key, label in specs:
            button = Gtk.Button(label=label)
            button.set_hexpand(True)
            button.connect("clicked", self.cb_button, key)
            vbox.pack_start(button, False, False, 0)
            self.buttons[key] = button

        # Action area buttons (Accept all hints placed to the left of Close)
        auto_all_btn = Gtk.Button(label=str(_("Accept all hints")))
        auto_all_btn.connect("clicked", self.cb_button, "auto_all")
        dialog.add_action_widget(auto_all_btn, Gtk.ResponseType.NONE)
        self.buttons["auto_all"] = auto_all_btn

        dialog.add_button(str(_("_Close")), Gtk.ResponseType.CLOSE)
        dialog.connect("response", self.cb_close)

        self.set_window(dialog, None, str(_("GWizard Media Fix")))
        self.setup_configs("interface.gwizardmediafix", 440, 330)
        dialog.show_all()

    def cb_close(self, dialog: Gtk.Dialog, response: int) -> None:
        """
        Close the tool window.

        :param dialog: The dialog.
        :param response: The response id.
        """
        self.close()

    def cb_generate_report(self) -> None:
        """Prompt file chooser for GWizardMediaFixReport.txt and write generated report."""
        chooser = Gtk.FileChooserDialog(
            title=str(_("Save Media Fix Report")),
            transient_for=self.window,
            action=Gtk.FileChooserAction.SAVE,
        )
        chooser.set_default_size(600, 400)
        chooser.add_buttons(
            str(_("_Cancel")),
            Gtk.ResponseType.CANCEL,
            str(_("_Save")),
            Gtk.ResponseType.OK,
        )
        chooser.set_current_name("GWizardMediaFixReport.txt")
        chooser.set_do_overwrite_confirmation(True)

        base_dir = (
            get_media_base_path(self.dbstate.db)
            if self.dbstate and self.dbstate.db
            else get_media_base_path(None)
        )
        if base_dir and os.path.isdir(base_dir):
            chooser.set_current_folder(base_dir)

        status = chooser.run()
        target_path = chooser.get_filename() if status == Gtk.ResponseType.OK else None
        chooser.destroy()

        if not target_path:
            return

        report_text = generate_media_fix_report(self.dbstate.db, self.window)
        try:
            with open(target_path, "w", encoding="utf-8") as handle:
                handle.write(report_text)
            self.report_path = target_path
            self.cb_view_report()
        except OSError as err:
            LOG.error("Failed to write report: %s", err)
            OkDialog(
                str(_("Report Not Written")),
                str(_("Could not write %(path)s: %(err)s"))
                % {"path": target_path, "err": err},
                parent=self.window,
            )

    def cb_view_report(self) -> None:
        """Open generated report in viewer dialog."""
        if not self.report_path or not os.path.exists(self.report_path):
            return

        try:
            with open(self.report_path, "r", encoding="utf-8") as handle:
                text = handle.read()
        except OSError:
            return

        dialog = MediaFixReportDialog(
            report_text=text,
            dbstate=self.dbstate,
            transient_for=self.window,
        )
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def cb_button(self, button: Gtk.Button, key: str) -> None:
        """
        Run the step behind a main-window button.

        :param button: The button that was clicked.
        :param key: The step's key, e.g. ``"find_missing"``.
        """
        if key == "generate":
            self.cb_generate_report()
        elif key == "find_missing":
            dlg = FindMissingMediaDialog(
                title=str(_("Find Missing Media")),
                dbstate=self.dbstate,
                transient_for=self.window,
            )
            dlg.show_dialog()
        elif key == "fix_references":
            dlg = FixMediaReferencesDialog(
                title=str(_("Fix Media References")),
                dbstate=self.dbstate,
                transient_for=self.window,
            )
            dlg.show_dialog()
        elif key == "consolidate_location":
            # Shared files are moved as a group inside the dialog, so they no
            # longer block it.
            dlg = ConsolidateMediaLocationDialog(
                title=str(_("Consolidate Media Location")),
                dbstate=self.dbstate,
                transient_for=self.window,
            )
            dlg.show_dialog()
        elif key == "auto_all":
            self.cb_auto_all()
        elif key == "clean_notes":
            self.cb_clean_notes()
        elif key == "undo_moves":
            self.cb_undo_moves()

    def _auto_find_missing(
        self, db: DbWriteBase
    ) -> tuple[int, list[tuple[str, str, str]], list[tuple[str, str, str, str]]]:
        """Auto find missing media files in the default media base path.

        :returns: (resolved_count, unresolved_missing_list, perm_denied_list)
        """
        base_dir = get_media_base_path(db) if db else ""
        resolved_count = 0
        unresolved: list[tuple[str, str, str]] = []
        perm_denied: list[tuple[str, str, str, str]] = []

        name_index = media_dir_index(db, base_dir)

        # Pass 1: work out every match without changing anything, so that a
        # file wanted by several different records can be held back.
        matches: list[tuple[Any, str, str, str, str]] = []  # media,gid,desc,raw,rel
        for media in list(db.iter_media()):
            m_gid = str(media.get_gramps_id() or "")
            desc = str(media.get_description() or "")
            raw_path = str(media.get_path() or "")
            clean_raw = clean_path(raw_path)
            if not clean_raw:
                continue

            try:
                full_path = media_path_full(db, clean_raw)
            except Exception:
                full_path = clean_raw

            exists = os.path.exists(full_path) or (
                is_absolute_path(clean_raw) and os.path.exists(clean_raw)
            )
            if exists:
                continue

            basename = os.path.basename(clean_raw.replace("\\", "/"))
            found_rel = find_in_media_dir(base_dir, basename, name_index)
            if found_rel:
                matches.append((media, m_gid, desc, raw_path, found_rel))
                continue
            perm_issue, inaccess_dir = check_path_permission(full_path)
            if not perm_issue and is_absolute_path(clean_raw):
                perm_issue, inaccess_dir = check_path_permission(clean_raw)
            if perm_issue and inaccess_dir:
                perm_denied.append((m_gid, desc, raw_path, inaccess_dir))
            else:
                unresolved.append((m_gid, desc, raw_path))

        unsafe = ambiguous_matches(
            [(m.get_handle(), raw, rel) for m, _g, _d, raw, rel in matches]
        )

        # Pass 2: repoint only the unambiguous matches.
        with DbTxn(_("Auto Find Missing Media"), db) as trans:
            for media, m_gid, desc, raw_path, found_rel in matches:
                if str(media.get_handle()) in unsafe:
                    unresolved.append((m_gid, desc, raw_path))
                    continue
                media.set_path(found_rel)
                add_media_fixed_tag(db, media, txn=trans)
                db.commit_media(media, trans)
                resolved_count += 1

        return resolved_count, unresolved, perm_denied

    def _auto_fix_references(self, db: DbWriteBase) -> tuple[int, int, list[str]]:
        """Auto resolve duplicate media references and purge unreferenced image tags.

        :returns: (merged_count, deleted_count, errors)
        """
        groups = find_duplicate_media_groups(db)
        merged_count = 0
        deleted_count = 0
        errors: list[str] = []

        from gramps.gen.merge.mergemediaquery import MergeMediaQuery

        for group in groups:
            g_type = group.get("type", "duplicate")
            if g_type == "unreferenced":
                h = group["keeper"]["handle"]
                try:
                    cand = db.get_media_from_handle(h)
                    if cand is None or not is_bare_media(cand):
                        errors.append(
                            "[%s] unreferenced, but has notes/attributes/tags/date - kept; review manually"
                            % group["keeper"].get("gramps_id", "")
                        )
                        continue
                    with DbTxn(_("Remove Unreferenced Media"), db) as trans:
                        db.remove_media(h, trans)
                        deleted_count += 1
                except Exception as err:
                    LOG.exception("Auto remove unreferenced media failed: %s", err)
                    errors.append(str(err))
            elif g_type == "duplicate":
                keeper = group["keeper"]
                keeper_media = db.get_media_from_handle(keeper["handle"])
                if not keeper_media:
                    continue
                for other in group["records"]:
                    if other["handle"] == keeper["handle"]:
                        continue
                    try:
                        other_media = db.get_media_from_handle(other["handle"])
                        if other_media:
                            query = MergeMediaQuery(
                                self.dbstate, keeper_media, other_media
                            )
                            query.execute()
                            add_media_fixed_tag(db, keeper_media, commit=True)
                            merged_count += 1
                    except Exception as err:
                        LOG.exception("Auto merge media record failed: %s", err)
                        errors.append(str(err))

        return merged_count, deleted_count, errors

    def _auto_consolidate_location(
        self, db: DbWriteBase
    ) -> tuple[int, list[tuple[str, str, str]]]:
        """Auto consolidate media file locations and apply standard filenames.

        Uses :func:`plan_consolidation_moves`, the same planner as the
        preview: a shared file is moved once and all of its records are
        repointed.

        :returns: (files_moved_or_renamed, not_consolidated)
        """
        base_dir = get_media_base_path(db) if db else ""
        if not base_dir:
            return 0, []
        if not (db.get_mediapath() or "").strip():
            # Without an explicit base path the fallback is the user's home
            # folder; never dump every media file there unattended.
            return 0, [
                (
                    "",
                    "",
                    "(halted: set the base media path in 'Consolidate media location' first)",
                )
            ]

        curr_tmpl = config.get(CONFIG_TEMPLATE_KEY) or DEFAULT_FILENAME_TEMPLATE
        consolidated_count = 0
        unconsolidated: list[tuple[str, str, str]] = []

        # Shared files are moved once with all their records.  Same planner
        # as the preview.
        moves = plan_consolidation_moves(db, base_dir, curr_tmpl)

        move_log = MoveLog(base_dir, "Accept all hints")
        with DbTxn(_("Auto Consolidate Media Locations"), db) as trans:
            for move in moves:
                ok, err = relocate_file(move["src_full"], move["dest_full"])
                if not ok:
                    unconsolidated.append(
                        (move["gids"], "", "%s (%s)" % (move["raw"], err))
                    )
                    continue
                new_rel = to_db_path(move["dest_full"], base_dir)
                action = (
                    "repoint"
                    if path_key(move["src_full"]) == path_key(move["dest_full"])
                    else "move"
                )
                for media in move["media"]:
                    move_log.record(
                        action,
                        media,
                        clean_path(str(media.get_path() or "")),
                        new_rel,
                        move["src_full"],
                        move["dest_full"],
                    )
                    media.set_path(new_rel)
                    add_media_fixed_tag(db, media, txn=trans)
                    db.commit_media(media, trans)
                consolidated_count += 1

        self.last_move_log_note = move_log_summary(move_log)
        return consolidated_count, unconsolidated

    def cb_undo_moves(self) -> None:
        """
        Reverse the most recent logged run of file moves, after confirmation.

        Files are moved back and records repointed; anything changed since the
        run is left alone and listed.
        """
        db = self.dbstate.db
        log_path = os.path.join(get_media_base_path(db), MOVE_LOG_NAME)
        run = last_logged_run(read_move_log(log_path))
        if not run:
            OkDialog(
                str(_("No file moves to undo")),
                str(_("No logged file moves were found in %s.")) % log_path,
                parent=self.window,
            )
            return
        n_files = len(
            {r["new_full"] for r in run if r.get("action") in ("move", "copy")}
        )
        confirm = QuestionDialog2(
            str(_("Undo last file moves")),
            _(
                "Reverse the file operations from %(time)s?\n\n"
                "Files moved: %(files)d (moved back; copies are kept)\n"
                "Media records: %(records)d (repointed)\n\n"
                "Records changed since then are left alone."
            )
            % {"time": run[0].get("time", ""), "files": n_files, "records": len(run)},
            str(_("_Undo moves")),
            str(_("_Cancel")),
            parent=self.window,
        )
        if not confirm.run():
            return
        files_back, records_back, problems = undo_logged_run(db, log_path)
        msg = _("Files moved back: %(files)d\nMedia records repointed: %(records)d") % {
            "files": files_back,
            "records": records_back,
        }
        if problems:
            msg += "\n\n" + str(_("Needs review (%d):")) % len(problems)
            msg += "\n" + "\n".join(problems[:15])
        OkDialog(str(_("File moves undone")), msg, parent=self.window)

    def cb_clean_notes(self) -> None:
        """Remove 'Records not imported into OBJE' notes whose problem is fixed."""
        db = self.dbstate.db
        items = find_stale_import_notes(db)
        if not items:
            OkDialog(
                str(_("No stale import notes")),
                str(
                    _(
                        "No 'Records not imported into OBJE' notes were found on media "
                        "whose file is now readable."
                    )
                ),
                parent=self.window,
            )
            return
        n_media = len({mh for mh, _g, _n, _ng in items})
        confirm = QuestionDialog2(
            str(_("Clean import notes")),
            ngettext(
                "Delete %(notes)d leftover import-failure note?",
                "Delete %(notes)d leftover import-failure notes?",
                len(items),
            )
            % {"notes": len(items)}
            + " "
            + _("(media records affected: %(media)d)") % {"media": n_media}
            + "\n\n"
            + _(
                "They describe files the importer could not find, but those files "
                "are readable now. This can be undone with Edit > Undo."
            ),
            str(_("_Delete")),
            str(_("_Cancel")),
            parent=self.window,
        )
        if not confirm.run():
            return
        removed = remove_import_notes(db, items)
        OkDialog(
            str(_("Import notes cleaned")),
            (
                ngettext(
                    "Removed %d note from media.",
                    "Removed %d notes from media.",
                    removed,
                )
                % removed
                + (
                    "\n\n"
                    + ngettext(
                        "%d note was left alone: its media record no longer exists.",
                        "%d notes were left alone: their media records no longer "
                        "exist.",
                        len(items) - removed,
                    )
                    % (len(items) - removed)
                    if removed < len(items)
                    else ""
                )
            ),
            parent=self.window,
        )

    def cb_auto_all(self) -> None:
        """Preview, then run, the default fixes across all media fix layers."""
        db = self.dbstate.db
        base_dir = get_media_base_path(db) if db else ""
        base_set = bool((db.get_mediapath() or "").strip())

        plan_progress = _Progress(str(_("Planning fixes")), 1, self.window)
        try:
            plan = build_accept_all_plan(db, base_dir, base_set)
        finally:
            plan_progress.close()

        if not plan_has_changes(plan):
            OkDialog(
                str(_("Nothing to change automatically")),
                format_plan(plan),
                parent=self.window,
            )
            return
        if not confirm_plan(self.window, format_plan(plan)):
            return

        prog = _Progress(str(_("Applying fixes")), 3, self.window)

        # Step 1: Find missing media
        missing_count, _unused_missing, _unused_denied = self._auto_find_missing(db)
        prog.step()

        # Step 2: Fix media references (must run before consolidation)
        merged_count, deleted_count, ref_errors = self._auto_fix_references(db)
        prog.step()

        # Step 3: Consolidate media locations
        self.last_move_log_note = ""
        consolidated_count, unconsolidated = self._auto_consolidate_location(db)
        prog.step()
        prog.close()

        # Final rescan: current state only, each file listed once with its real reason
        unresolved_missing, perm_denied = scan_unreadable_media(db)

        if base_set:
            consolidate_line = ngettext(
                "  • Consolidate media location: %(count)d file moved or renamed "
                "in '%(folder)s'.",
                "  • Consolidate media location: %(count)d files moved or renamed "
                "in '%(folder)s'.",
                consolidated_count,
            ) % {"count": consolidated_count, "folder": base_dir}
        else:
            consolidate_line = str(
                _("  • Consolidate media location: skipped (no base media path set).")
            )

        lines = [
            str(_("AUTOMATED CHANGES PERFORMED:")),
            ngettext(
                "  • Find missing media: %d missing path found in media directory "
                "and updated.",
                "  • Find missing media: %d missing paths found in media directory "
                "and updated.",
                missing_count,
            )
            % missing_count,
            _(
                "  • Fix media references: duplicate records merged: %(merged)d; "
                "unreferenced image tags deleted: %(deleted)d."
            )
            % {"merged": merged_count, "deleted": deleted_count},
            consolidate_line,
            "",
        ]
        if self.last_move_log_note:
            lines += [self.last_move_log_note.strip(), ""]

        manual_items: list[str] = []
        if unresolved_missing:
            manual_items.append(
                _(
                    "  • Missing files on disk (%(count)d): not found on disk. Locate "
                    "them with 'Find missing media' (searches '%(folder)s'):"
                )
                % {"count": len(unresolved_missing), "folder": base_dir}
            )
            for gid, desc, path in unresolved_missing[:5]:
                manual_items.append(f"      - [{gid}] {desc or _('(unnamed)')}: {path}")
            if len(unresolved_missing) > 5:
                manual_items.append(
                    ngettext(
                        "      - ... and %d more missing file",
                        "      - ... and %d more missing files",
                        len(unresolved_missing) - 5,
                    )
                    % (len(unresolved_missing) - 5)
                )

        if perm_denied:
            manual_items.append(
                str(
                    _(
                        "  • Permission denied files (%d): exist but cannot be read (often another Windows user profile). Copy them into a folder you own, set it as the base media path, then run this again:"
                    )
                )
                % len(perm_denied)
            )
            for gid, desc, path, inaccess in perm_denied[:5]:
                manual_items.append(f"      - [{gid}] {path} (blocked at: {inaccess})")
            if len(perm_denied) > 5:
                manual_items.append(
                    ngettext(
                        "      - ... and %d more inaccessible file",
                        "      - ... and %d more inaccessible files",
                        len(perm_denied) - 5,
                    )
                    % (len(perm_denied) - 5)
                )

        if ref_errors:
            manual_items.append(
                str(_("  • Reference items needing review (%d):") % len(ref_errors))
            )
            for err in ref_errors[:5]:
                manual_items.append(f"      - {err}")

        if unconsolidated:
            manual_items.append(
                str(_("  • Unconsolidated paths (%d): could not be relocated:"))
                % len(unconsolidated)
            )
            for gid, desc, path in unconsolidated[:5]:
                manual_items.append(f"      - [{gid}] {path}")
            if len(unconsolidated) > 5:
                manual_items.append(
                    ngettext(
                        "      - ... and %d more unconsolidated path",
                        "      - ... and %d more unconsolidated paths",
                        len(unconsolidated) - 5,
                    )
                    % (len(unconsolidated) - 5)
                )

        if manual_items:
            lines.append(str(_("CHANGES REQUIRING HUMAN INTERVENTION:")))
            lines.extend(manual_items)
        else:
            lines.append(
                str(
                    _(
                        "No human intervention required. All media files and references are fully resolved."
                    )
                )
            )

        stale_notes = find_stale_import_notes(db)
        if stale_notes:
            lines.append("")
            lines.append(
                ngettext(
                    "OPTIONAL CLEANUP: %d stale import note can be removed with "
                    "'Clean import notes'.",
                    "OPTIONAL CLEANUP: %d stale import notes can be removed with "
                    "'Clean import notes'.",
                    len(stale_notes),
                )
                % len(stale_notes)
            )

        dlg = AcceptAllHintsReportDialog(
            report_text="\n".join(lines),
            title=str(_("Accept All Hints Complete")),
            transient_for=self.window,
        )
        dlg.show_dialog()
