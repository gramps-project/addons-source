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

"""Shared UI widgets and utilities for GWizard tools."""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
from __future__ import annotations
import csv
import html
import logging
import os
import re
import shutil
import sys
from datetime import datetime
from typing import Any

# -------------------------------------------------------------------------
#
# GTK modules
#
# -------------------------------------------------------------------------
from gi.repository import Gtk, Pango

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.db import DbReadBase, DbTxn, DbWriteBase
from gramps.gen.lib import Tag
from gramps.gen.utils.file import media_path_full

_ = glocale.translation.sgettext
LOG = logging.getLogger(__name__)

# "C:\..." or "C:/..." - a Windows drive path, recognised on every platform
_WIN_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def escape_markup(text: Any) -> str:
    """
    Escape text for use inside Pango markup.

    Paths and translated strings can contain ``&`` or ``<`` (e.g. a folder
    called "Smith & Jones"), which otherwise makes GTK reject the markup and
    show an empty label.

    :param text: Any value; it is converted to ``str`` first.
    :returns: The escaped text.
    """
    return html.escape(str(text), quote=False)


# ------------------------------------------------------------
#
# SelectableLabel
#
# ------------------------------------------------------------
class SelectableLabel(Gtk.Label):
    """Gtk.Label subclass that is selectable, left-aligned, and wrappable by default."""

    def __init__(
        self,
        label: str = "",
        selectable: bool = True,
        wrap: bool = True,
        xalign: float = 0.0,
        markup: bool = False,
        can_focus: bool = False,
        max_width_chars: int | None = None,
        size_request: tuple[int, int] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the selectable label with standard formatting defaults."""
        super().__init__(**kwargs)
        if markup:
            self.set_markup(label)
        else:
            self.set_text(label)

        self.set_selectable(selectable)
        self.set_halign(Gtk.Align.START)
        self.set_xalign(xalign)
        self.set_can_focus(can_focus)

        if wrap:
            self.set_line_wrap(True)
            self.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        if max_width_chars is not None:
            self.set_max_width_chars(max_width_chars)

        if size_request is not None:
            self.set_size_request(*size_request)


# ------------------------------------------------------------
#
# TableLabel
#
# ------------------------------------------------------------
class TableLabel(SelectableLabel):
    """Selectable label tailored for table and grid data cells."""

    def __init__(
        self,
        label: str = "",
        width_chars: int | None = None,
        width_request: int | None = None,
        selectable: bool = True,
        wrap: bool = True,
        markup: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize a table cell label with standard alignment, wrapping, and width constraints."""
        size_req = (width_request, -1) if width_request is not None else None
        super().__init__(
            label=label,
            selectable=selectable,
            wrap=wrap,
            xalign=0.0,
            markup=markup,
            can_focus=False,
            max_width_chars=width_chars,
            size_request=size_req,
            **kwargs,
        )


# ------------------------------------------------------------
#
# HeaderLabel
#
# ------------------------------------------------------------
class HeaderLabel(SelectableLabel):
    """Header label displaying bold markup text for table column headers."""

    def __init__(self, title: str = "", **kwargs: Any) -> None:
        """Initialize a header label with bold markup."""
        super().__init__(
            label="<b>%s</b>" % escape_markup(title),
            selectable=True,
            wrap=False,
            xalign=0.0,
            markup=True,
            can_focus=False,
            **kwargs,
        )


# ------------------------------------------------------------
#
# Table Grid helper
#
# ------------------------------------------------------------
def create_table_grid(col_spacing: int = 6, row_spacing: int = 6) -> Gtk.Grid:
    """Return a standard Gtk.Grid configured for wizard tables."""
    grid = Gtk.Grid()
    grid.set_column_spacing(col_spacing)
    grid.set_row_spacing(row_spacing)
    grid.set_hexpand(True)
    grid.set_vexpand(True)
    return grid


# ------------------------------------------------------------
#
# Pure path helpers (no GTK / Gramps dependency; unit-testable)
#
# ------------------------------------------------------------
def clean_path(path: str | None) -> str:
    """Strip whitespace and surrounding quotes from a path string.

    Matched pairs of quotes are removed.  An unmatched double quote is removed
    (never valid in a Windows filename), but an unmatched apostrophe is kept
    because it can legitimately end a folder name ("Grandma's").
    """
    if not path:
        return ""
    text = str(path).strip()
    while len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    if text.startswith('"'):
        text = text[1:].strip()
    if text.endswith('"'):
        text = text[:-1].strip()
    return text


def is_absolute_path(path: str | None) -> bool:
    """Return True for drive-absolute AND rooted drive-less paths.

    Python 3.13+ on Windows no longer treats "/Users/x" as absolute, but GEDCOM
    imports commonly produce exactly such paths (drive letter stripped).  Treat
    them as absolute so they are not mistaken for paths relative to the media
    base directory.
    """
    text = clean_path(path)
    if not text:
        return False
    return (
        os.path.isabs(text) or text[0] in ("/", "\\") or bool(_WIN_DRIVE_RE.match(text))
    )


def is_windows_style_path(path: str | None) -> bool:
    """Return True for a drive path ("C:\\x", "C:/x") or a UNC path ("\\\\srv\\x").

    Such paths come from Windows (often via a GEDCOM import) and are compared
    case-insensitively on every platform.
    """
    text = clean_path(path)
    return bool(_WIN_DRIVE_RE.match(text)) or text.startswith("\\\\")


def path_key(path: str) -> str:
    """Normalised key for comparing two paths.

    Backslashes are treated as separators on every platform.  Case is folded
    where the file system is case-insensitive (Windows, macOS default) and for
    Windows-style paths everywhere, so "C:\\Pic.JPG" and "c:/pic.jpg" match on
    Linux and macOS too.
    """
    text = clean_path(path)
    fold = is_windows_style_path(text) or sys.platform == "darwin"
    key = os.path.normcase(os.path.normpath(text.replace("\\", "/")))
    return key.casefold() if fold else key


def full_media_path(db: DbReadBase, raw_path: str | None) -> str:
    """Return the on-disk path for a stored media path ("" for an empty path).

    Absolute paths (including Windows drive paths on Linux/macOS) are returned
    as-is; relative paths are resolved against the media base path.  Never
    raises.
    """
    text = clean_path(raw_path)
    if not text:
        return ""
    if is_absolute_path(text):
        return text
    try:
        return media_path_full(db, text)
    except Exception:  # noqa: BLE001 - fall back to the stored path
        return text


def is_bare_media(media: Any) -> bool:
    """Return True when a media record carries nothing worth keeping.

    A record with notes, attributes, tags, citations or a date is not bare and
    must never be deleted automatically.
    """

    def _has(name: str) -> bool:
        """Return True if the record's ``name`` method returns anything."""
        method = getattr(media, name, None)
        return bool(method()) if callable(method) else False

    date = media.get_date_object() if hasattr(media, "get_date_object") else None
    return not (
        _has("get_note_list")
        or _has("get_attribute_list")
        or _has("get_tag_list")
        or _has("get_citation_list")
        or (date is not None and not date.is_empty())
    )


def to_db_path(full_path: str, base_dir: str) -> str:
    """Return full_path relative to base_dir (forward slashes) when inside it.

    Paths outside base_dir (or on another drive) are returned unchanged.
    """
    if not full_path or not base_dir:
        return full_path
    try:
        abs_full = os.path.abspath(full_path)
        abs_base = os.path.abspath(base_dir)
        norm_full = os.path.normcase(os.path.normpath(abs_full))
        norm_base = os.path.normcase(os.path.normpath(abs_base))
        if (
            norm_full == norm_base
            or os.path.commonpath([norm_full, norm_base]) != norm_base
        ):
            return full_path
        return os.path.relpath(abs_full, abs_base).replace("\\", "/")
    except (ValueError, OSError):
        return full_path


def unique_destination(dest: str, claimed: set[str], src: str | None = None) -> str:
    """Return dest, or dest with _2, _3 ... appended to the stem, such that the
    result neither exists on disk (unless it is src itself) nor was already
    claimed by another record in the current batch.  The result is claimed."""

    def taken(candidate: str) -> bool:
        """Return True if *p* is claimed in this batch or is another existing file."""
        if path_key(candidate) in claimed:
            return True
        if os.path.exists(candidate):
            try:
                if src and os.path.exists(src) and os.path.samefile(src, candidate):
                    return False
            except OSError:
                pass
            return True
        return False

    stem, ext = os.path.splitext(dest)
    cand, n = dest, 2
    while taken(cand):
        cand = f"{stem}_{n}{ext}"
        n += 1
    claimed.add(path_key(cand))
    return cand


def relocate_file(src: str, dest: str, copy: bool = False) -> tuple[bool, str]:
    """Move or copy src to dest WITHOUT ever overwriting an existing file.

    Returns (ok, error_message).  ok is also True when dest already is the
    same file as src.
    """
    try:
        if os.path.exists(dest):
            try:
                same = os.path.samefile(src, dest)
            except OSError:
                same = False
            if not same:
                return False, "destination already exists"
            if not copy and os.path.basename(src) != os.path.basename(dest):
                os.rename(src, dest)  # case-only rename on a case-insensitive FS
            return True, ""
        parent = os.path.dirname(dest)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if copy:
            shutil.copy2(src, dest)
        else:
            shutil.move(src, dest)
        return True, ""
    except Exception as err:  # noqa: BLE001 - report any OS/shutil error
        return False, str(err)


def build_basename_index(base_dir: str, limit: int = 50000) -> dict[str, list[str]]:
    """Map lower-cased file name -> full paths for every file below base_dir."""
    index: dict[str, list[str]] = {}
    seen = 0
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            if fname.startswith("."):
                continue
            index.setdefault(fname.lower(), []).append(os.path.join(root, fname))
            seen += 1
            if seen >= limit:
                return index
    return index


# ------------------------------------------------------------
#
# GWizard Standard Tags and Locking Helpers
#
# ------------------------------------------------------------
#
# These helpers work on ANY Gramps object that carries tags (Media, Citation,
# Source, Repository, Note, Person, Family, Event, Place), so every GWizard tool
# (Media Fix, Citation Fix, ...) shares one definition of "locked".
#
# A lock is the tag named TAG_LOCKED.  It is looked up by NAME, so renaming
# the tag in Organize Tags silently unlocks everything that carries it (and the
# next lock creates a new tag with the standard name).  Tell users to leave the
# GWizard tag names alone.
#
# Tags are created lazily, the first time an object is tagged; checking
# whether something is locked never changes the database.
#
TAG_MEDIA_FIXED = "GWizard: MediaFixed"
TAG_MEDIA_FIXED_COLOR = "#2E8B57"

TAG_LOCKED = "GWizard: Locked"
TAG_LOCKED_COLOR = "#B22222"


def create_gwizard_tag(name: str, color: str = "") -> Tag:
    """
    Create a new (unsaved) Tag with the given name and colour.

    :param name: The tag name.
    :param color: Optional colour, e.g. ``"#B22222"``.
    :returns: The new tag.
    """
    tag = Tag()
    tag.set_name(name)
    if color:
        tag.set_color(color)
    return tag


def ensure_tag(
    db: DbWriteBase | None,
    name: str,
    color: str = "",
    txn: Any = None,
) -> Tag | None:
    """
    Return the tag called *name*, creating it if it does not exist.

    Pass *txn* when a transaction is already open: without it a new
    transaction is started, and Gramps does not allow nested transactions.

    :param db: The database.
    :param name: The tag name.
    :param color: Colour used when the tag has to be created.
    :param txn: An open transaction, or ``None``.
    :returns: The tag, or ``None`` if it could not be created.
    """
    if not db or not hasattr(db, "get_tag_from_name"):
        return None
    try:
        tag = db.get_tag_from_name(name)
        if tag:
            return tag
    except Exception:
        pass

    if not hasattr(db, "add_tag"):
        return None

    tag = create_gwizard_tag(name, color)
    if hasattr(db, "get_number_of_tags"):
        try:
            tag.set_priority(db.get_number_of_tags())
        except Exception:
            pass

    # add_tag() already commits the tag; a second commit_tag() was redundant.
    try:
        if txn is not None:
            db.add_tag(tag, txn)
        else:
            with DbTxn(_("Create GWizard Tag"), db) as trans:
                db.add_tag(tag, trans)
        return tag
    except Exception as err:
        LOG.warning("Failed to create tag '%s': %s", name, err)
        return None


def ensure_gwizard_tags(
    db: DbWriteBase, txn: Any = None
) -> tuple[Tag | None, Tag | None]:
    """
    Ensure both standard GWizard tags exist.

    Not needed for normal use (tags are created when first applied); kept for
    callers that want the tags visible up front.

    :param db: The database.
    :param txn: An open transaction, or ``None``.
    :returns: ``(MediaFixed tag, Locked tag)``.
    """
    t_fixed = ensure_tag(db, TAG_MEDIA_FIXED, TAG_MEDIA_FIXED_COLOR, txn=txn)
    t_locked = ensure_tag(db, TAG_LOCKED, TAG_LOCKED_COLOR, txn=txn)
    return t_fixed, t_locked


def find_tag_handle(db: DbReadBase | None, name: str) -> str | None:
    """
    Return the handle of the tag called *name* without creating it.

    :param db: The database.
    :param name: The tag name.
    :returns: The tag handle, or ``None`` if there is no such tag.
    """
    if not db or not hasattr(db, "get_tag_from_name"):
        return None
    try:
        tag = db.get_tag_from_name(name)
    except Exception:
        return None
    return tag.get_handle() if tag else None


def has_tag(db: DbReadBase, obj: Any, name: str) -> bool:
    """
    Return True if *obj* carries the tag called *name*.

    :param db: The database.
    :param obj: Any tagged Gramps object (or ``None``).
    :param name: The tag name.
    :returns: Whether the object has the tag.
    """
    if not obj or not hasattr(obj, "get_tag_list"):
        return False
    tag_list = obj.get_tag_list()
    if not tag_list:
        return False
    handle = find_tag_handle(db, name)
    return bool(handle) and handle in tag_list


def commit_object(db: DbWriteBase, obj: Any, txn: Any) -> None:
    """
    Commit any primary object with the matching ``commit_<type>`` method.

    :param db: The database.
    :param obj: A Media, Citation, Source, Repository, Note, ... object.
    :param txn: The open transaction.
    :raises TypeError: If the database has no commit method for the type.
    """
    commit = getattr(db, "commit_%s" % type(obj).__name__.lower(), None)
    if commit is None:
        raise TypeError("cannot commit object of type %s" % type(obj).__name__)
    commit(obj, txn)


def _commit_now(db: DbWriteBase, obj: Any, txn: Any, label: str) -> None:
    """
    Commit *obj* in *txn*, or in a transaction of its own when *txn* is None.

    :param db: The database.
    :param obj: The object to commit.
    :param txn: An open transaction, or ``None``.
    :param label: Undo label for a new transaction.
    """
    if txn is not None:
        commit_object(db, obj, txn)
    else:
        with DbTxn(label, db) as trans:
            commit_object(db, obj, trans)


def add_tag_to(
    db: DbWriteBase | None,
    obj: Any,
    name: str,
    color: str = "",
    txn: Any = None,
    commit: bool = False,
) -> bool:
    """
    Add the tag called *name* to *obj* (creating the tag if needed).

    :param db: The database.
    :param obj: Any tagged Gramps object.
    :param name: The tag name.
    :param color: Colour used if the tag has to be created.
    :param txn: An open transaction, or ``None``.
    :param commit: Also commit *obj* (in *txn*, or a new transaction).
    :returns: True if the tag was newly added.
    """
    if not db or not obj or not hasattr(obj, "add_tag"):
        return False
    tag = ensure_tag(db, name, color, txn=txn)
    if not tag or not tag.get_handle():
        return False
    if tag.get_handle() in (obj.get_tag_list() or []):
        return False
    obj.add_tag(tag.get_handle())
    if commit:
        _commit_now(db, obj, txn, _("Tag %s") % name)
    return True


def remove_tag_from(
    db: DbWriteBase | None,
    obj: Any,
    name: str,
    txn: Any = None,
    commit: bool = False,
) -> bool:
    """
    Remove the tag called *name* from *obj*.

    :param db: The database.
    :param obj: Any tagged Gramps object.
    :param name: The tag name.
    :param txn: An open transaction, or ``None``.
    :param commit: Also commit *obj* (in *txn*, or a new transaction).
    :returns: True if the tag was removed.
    """
    if not db or not obj or not hasattr(obj, "remove_tag"):
        return False
    handle = find_tag_handle(db, name)
    if not handle or handle not in (obj.get_tag_list() or []):
        return False
    obj.remove_tag(handle)
    if commit:
        _commit_now(db, obj, txn, _("Untag %s") % name)
    return True


def is_locked(db: DbReadBase, obj: Any) -> bool:
    """
    Return True if *obj* carries the shared ``GWizard: Locked`` tag.

    Every GWizard tool must check this before changing an object.

    :param db: The database.
    :param obj: Any tagged Gramps object (or ``None``).
    :returns: Whether the object is locked.
    """
    return has_tag(db, obj, TAG_LOCKED)


def lock_object(
    db: DbWriteBase, obj: Any, txn: Any = None, commit: bool = False
) -> bool:
    """
    Lock *obj* against changes by GWizard tools.

    :param db: The database.
    :param obj: Any tagged Gramps object.
    :param txn: An open transaction, or ``None``.
    :param commit: Also commit *obj*.
    :returns: True if the object was newly locked.
    """
    return add_tag_to(db, obj, TAG_LOCKED, TAG_LOCKED_COLOR, txn=txn, commit=commit)


def unlock_object(
    db: DbWriteBase, obj: Any, txn: Any = None, commit: bool = False
) -> bool:
    """
    Remove the GWizard lock from *obj*.

    :param db: The database.
    :param obj: Any tagged Gramps object.
    :param txn: An open transaction, or ``None``.
    :param commit: Also commit *obj*.
    :returns: True if the lock was removed.
    """
    return remove_tag_from(db, obj, TAG_LOCKED, txn=txn, commit=commit)


def add_fixed_tag(
    db: DbWriteBase,
    obj: Any,
    name: str = TAG_MEDIA_FIXED,
    color: str = TAG_MEDIA_FIXED_COLOR,
    txn: Any = None,
    commit: bool = False,
) -> bool:
    """
    Mark *obj* as repaired by a GWizard tool.

    Each tool can pass its own tag name (Media Fix uses ``GWizard: MediaFixed``).

    :param db: The database.
    :param obj: Any tagged Gramps object.
    :param name: The "fixed" tag name for the calling tool.
    :param color: Colour used if the tag has to be created.
    :param txn: An open transaction, or ``None``.
    :param commit: Also commit *obj*.
    :returns: True if the tag was newly added.
    """
    return add_tag_to(db, obj, name, color, txn=txn, commit=commit)


# Media-specific names, kept so existing callers and tests keep working.
def is_media_locked(db: DbReadBase, media: Any) -> bool:
    """Return True if *media* has the ``GWizard: Locked`` tag (see is_locked)."""
    return is_locked(db, media)


def has_media_fixed_tag(db: DbReadBase, media: Any) -> bool:
    """Return True if *media* has the ``GWizard: MediaFixed`` tag."""
    return has_tag(db, media, TAG_MEDIA_FIXED)


def add_media_fixed_tag(
    db: DbWriteBase,
    media: Any,
    txn: Any = None,
    commit: bool = False,
) -> bool:
    """Add the ``GWizard: MediaFixed`` tag to *media* (see add_fixed_tag)."""
    return add_fixed_tag(db, media, txn=txn, commit=commit)


def lock_media(
    db: DbWriteBase,
    media: Any,
    txn: Any = None,
    commit: bool = False,
) -> bool:
    """Lock *media* (see lock_object)."""
    return lock_object(db, media, txn=txn, commit=commit)


def unlock_media(
    db: DbWriteBase,
    media: Any,
    txn: Any = None,
    commit: bool = False,
) -> bool:
    """Unlock *media* (see unlock_object)."""
    return unlock_object(db, media, txn=txn, commit=commit)


# ------------------------------------------------------------
#
# File-move log and "Undo last file moves"
#
# Edit > Undo reverts database changes only.  After files have been moved,
# undoing the database leaves every moved record pointing at the old location,
# where the file no longer is.  Every file operation is therefore logged, and
# undo_logged_run() moves the files back *and* repoints the records.
#
# ------------------------------------------------------------
MOVE_LOG_NAME = "GWizardMediaFix-moves.csv"
MOVE_LOG_FIELDS = [
    "run_id",
    "time",
    "action",
    "handle",
    "gramps_id",
    "old_db_path",
    "new_db_path",
    "old_full",
    "new_full",
]
# action values: "move", "copy", "repoint" (same file, new stored path) and
# "undone" (a marker row: gramps_id holds the run_id that was reversed).


# ------------------------------------------------------------
#
# MoveLog
#
# ------------------------------------------------------------
class MoveLog:
    """Collects the file operations of one run and appends them to the CSV log."""

    def __init__(self, log_dir: str, label: str = "") -> None:
        """
        Start a new run.

        :param log_dir: Folder for the log (the base media folder).
        :param label: Short description of the run, e.g. "Consolidate".
        """
        self.path = os.path.join(log_dir, MOVE_LOG_NAME)
        self.label = label
        self.run_id = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        self.rows: list[dict[str, str]] = []

    def __len__(self) -> int:
        """Return the number of logged record changes."""
        return len(self.rows)

    def record(
        self,
        action: str,
        media: Any,
        old_db_path: str,
        new_db_path: str,
        old_full: str,
        new_full: str,
    ) -> None:
        """
        Log one record's change.

        :param action: ``"move"``, ``"copy"`` or ``"repoint"``.
        :param media: The media record.
        :param old_db_path: The stored path before the change.
        :param new_db_path: The stored path after the change.
        :param old_full: The file's full path before the change.
        :param new_full: The file's full path after the change.
        """
        self.rows.append(
            {
                "run_id": self.run_id,
                "time": datetime.now().isoformat(timespec="seconds"),
                "action": action,
                "handle": str(media.get_handle() or ""),
                "gramps_id": str(media.get_gramps_id() or ""),
                "old_db_path": old_db_path,
                "new_db_path": new_db_path,
                "old_full": old_full,
                "new_full": new_full,
            }
        )

    def write(self) -> str:
        """
        Append the run to the log file.

        :returns: ``""`` on success, otherwise an error message.
        """
        if not self.rows:
            return ""
        return _append_log_rows(self.path, self.rows)


def _append_log_rows(path: str, rows: list[dict[str, str]]) -> str:
    """
    Append rows to the CSV log, writing the header for a new file.

    :param path: The log file.
    :param rows: Rows keyed by :data:`MOVE_LOG_FIELDS`.
    :returns: ``""`` on success, otherwise an error message.
    """
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        new_file = not os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=MOVE_LOG_FIELDS)
            if new_file:
                writer.writeheader()
            writer.writerows(rows)
        return ""
    except OSError as err:
        LOG.warning("Could not write move log %s: %s", path, err)
        return str(err)


def read_move_log(path: str) -> list[dict[str, str]]:
    """
    Read the CSV move log.

    :param path: The log file.
    :returns: All rows, oldest first (empty if the file is missing).
    """
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def last_logged_run(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    Return the rows of the most recent run that has not been undone.

    :param rows: Result of :func:`read_move_log`.
    :returns: That run's rows, oldest first (empty if there is none).
    """
    undone = {r["gramps_id"] for r in rows if r.get("action") == "undone"}
    runs: list[str] = []
    for row in rows:
        rid = row.get("run_id", "")
        if row.get("action") != "undone" and rid not in undone and rid not in runs:
            runs.append(rid)
    if not runs:
        return []
    last = runs[-1]
    return [r for r in rows if r.get("run_id") == last and r.get("action") != "undone"]


def _move_back(
    gid: str, new_full: str, old_full: str, problems: list[str]
) -> tuple[bool, bool]:
    """
    Move one logged file back to its old location, never overwriting.

    :param gid: Gramps ID for messages.
    :param new_full: Where the run put the file.
    :param old_full: Where the file was before the run.
    :param problems: Messages are appended here.
    :returns: ``(file is now at old_full, this call moved it)``.
    """
    new_there = os.path.exists(new_full)
    old_there = os.path.exists(old_full)
    same = False
    if new_there and old_there:
        try:
            same = os.path.samefile(new_full, old_full)  # case-only rename
        except OSError:
            same = False
    if new_there and (not old_there or same):
        ok, err = relocate_file(new_full, old_full)
        if not ok:
            problems.append("[%s] %s: %s" % (gid, new_full, err))
        return ok, ok
    if old_there and not new_there:
        return True, False  # already moved back by hand
    if old_there:
        problems.append(
            "[%s] %s"
            % (
                gid,
                _("another file is now at %(old)s; left at %(new)s")
                % {"old": old_full, "new": new_full},
            )
        )
    else:
        problems.append(
            "[%s] %s" % (gid, _("file is in neither location: %s") % new_full)
        )
    return False, False


def undo_logged_run(db: DbWriteBase, log_path: str) -> tuple[int, int, list[str]]:
    """
    Reverse the most recent logged run: move files back, repoint records.

    Safe by design:

    - a moved file is moved back only if it is still at its new location and
      nothing has taken its old one; a file is never overwritten or deleted
      (copies are left in place; only the records are repointed);
    - a record is repointed only if its path is still the one the run stored
      (or already the old one, e.g. after Edit > Undo); a record changed
      since, or locked, is left alone and reported.

    The run is then marked as undone in the log, so the next call reverses
    the run before it.

    :param db: The database.
    :param log_path: The move log file.
    :returns: ``(files moved back, records repointed, problems)``.
    """
    run = last_logged_run(read_move_log(log_path))
    if not run:
        return 0, 0, []
    files_back = 0
    records_back = 0
    problems: list[str] = []
    # For each moved file: is it (back) at its old location?  A record is only
    # repointed to the old location when its file is really there.
    file_back: dict[str, bool] = {}
    with DbTxn(_("Undo GWizard file moves"), db) as trans:
        for row in reversed(run):
            gid = row.get("gramps_id", "")
            old_full, new_full = row.get("old_full", ""), row.get("new_full", "")
            is_move = row.get("action") == "move"
            key = path_key(new_full)
            if is_move and key not in file_back:
                file_back[key], moved = _move_back(gid, new_full, old_full, problems)
                files_back += int(moved)
            if is_move and not file_back.get(key, False):
                continue  # keep the record on the file's actual location
            try:
                media = db.get_media_from_handle(row.get("handle", ""))
            except Exception:
                media = None
            if media is None:
                problems.append("[%s] %s" % (gid, _("record no longer exists")))
                continue
            current = clean_path(str(media.get_path() or ""))
            old_db = row.get("old_db_path", "")
            if path_key(current) == path_key(old_db):
                continue  # already back (e.g. Edit > Undo was used)
            if path_key(current) != path_key(row.get("new_db_path", "")):
                problems.append("[%s] %s" % (gid, _("path changed since; left alone")))
                continue
            if is_locked(db, media):
                problems.append("[%s] %s" % (gid, _("locked; left alone")))
                continue
            media.set_path(old_db)
            commit_object(db, media, trans)
            records_back += 1
    marker = {field: "" for field in MOVE_LOG_FIELDS}
    marker.update(
        {
            "run_id": datetime.now().strftime("%Y%m%dT%H%M%S%f"),
            "time": datetime.now().isoformat(timespec="seconds"),
            "action": "undone",
            "gramps_id": run[0].get("run_id", ""),
        }
    )
    err = _append_log_rows(log_path, [marker])
    if err:
        problems.append(_("could not mark the run as undone in the log: %s") % err)
    return files_back, records_back, problems
