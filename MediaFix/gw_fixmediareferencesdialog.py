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

"""Fix Media References dialog for resolving duplicate and shared media references."""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
from __future__ import annotations
import logging
import os
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
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.db import DbReadBase, DbTxn
from gramps.gen.merge.mergemediaquery import MergeMediaQuery
from gramps.gen.utils.file import media_path_full
from gramps.gui.dialog import OkDialog

try:
    from gwizard_common import (
        TableLabel,
        HeaderLabel,
        create_table_grid,
        MoveLog,
        clean_path,
        full_media_path,
        is_bare_media,
        path_key,
        unique_destination,
        relocate_file,
        is_media_locked,
        add_media_fixed_tag,
    )
except (ImportError, ValueError):
    from gwizard_common import (  # type: ignore[import-not-found,no-redef]
        TableLabel,
        HeaderLabel,
        create_table_grid,
        MoveLog,
        clean_path,
        full_media_path,
        is_bare_media,
        path_key,
        unique_destination,
        relocate_file,
        is_media_locked,
        add_media_fixed_tag,
    )

_ = glocale.translation.sgettext
ngettext = glocale.translation.ngettext
LOG = logging.getLogger(__name__)


def media_base_path(db: DbReadBase) -> str:
    """
    Return the base media folder (where the file-move log is kept).

    :param db: The database.
    :returns: The folder, resolved as Gramps does.
    """
    try:
        from gwizardmediafix import get_media_base_path
    except (ImportError, ValueError):
        from gwizardmediafix import (  # type: ignore[import-not-found,no-redef]
            get_media_base_path,
        )
    return get_media_base_path(db)


def find_duplicate_media_groups(
    db: DbReadBase | None, cache: dict[str, dict[str, str]] | None = None
) -> list[dict[str, Any]]:
    """Scan database for media files referenced by multiple media records.

    Returns a list of dicts describing each shared file and its referencing media records.
    """
    if not db:
        return []

    try:
        from gwizardmediafix import (
            resolve_media_reference_context,
            check_path_permission,
        )
    except (ImportError, ValueError):
        from gwizardmediafix import (  # type: ignore[import-not-found,no-redef]
            resolve_media_reference_context,
            check_path_permission,
        )

    path_map: dict[str, list[dict[str, Any]]] = {}

    for media in db.iter_media():
        m_handle = str(media.get_handle() or "")
        m_gid = str(media.get_gramps_id() or "")
        desc = str(media.get_description() or "")
        raw_path = clean_path(str(media.get_path() or ""))
        if not raw_path:
            continue

        # full_media_path never raises, so full_path is always bound (it used
        # to be left unset when media_path_full() failed -> UnboundLocalError).
        full_path = full_media_path(db, raw_path)
        key = path_key(full_path)

        assoc_str = ""
        try:
            ctx = resolve_media_reference_context(db, media, cache)
            assoc_str = ctx.get("assoc", "")
        except Exception:
            pass

        # The permission walk lists every parent folder and reads the file, so
        # only run it for files that are missing or unreadable (os.access is
        # one cheap system call).
        perm_issue, inaccess_dir = False, None
        if not os.access(full_path, os.R_OK):
            perm_issue, inaccess_dir = check_path_permission(full_path)
            if not perm_issue and os.path.isabs(raw_path):
                perm_issue, inaccess_dir = check_path_permission(raw_path)

        backlinks = []
        if hasattr(db, "find_backlink_handles") and m_handle:
            try:
                backlinks = list(db.find_backlink_handles(m_handle))
            except Exception:
                backlinks = []

        if key not in path_map:
            path_map[key] = []

        path_map[key].append(
            {
                "handle": m_handle,
                "gramps_id": m_gid,
                "desc": desc,
                "raw_path": raw_path,
                "full_path": key,
                "backlink_count": len(backlinks),
                "assoc": assoc_str,
                "perm_issue": perm_issue,
                "inaccess_dir": inaccess_dir,
                "media": media,
                "bare": is_bare_media(media),
            }
        )

    groups: list[dict[str, Any]] = []
    # 1. Duplicate file references (multiple media records sharing the same file)
    for file_key, records in path_map.items():
        if len(records) > 1:
            records.sort(
                key=lambda rec: (
                    -rec["backlink_count"],
                    not rec["assoc"],
                    not rec["desc"],
                    rec["gramps_id"],
                )
            )
            keeper = records[0]
            groups.append(
                {
                    "type": "duplicate",
                    "file_key": file_key,
                    "records": records,
                    "keeper": keeper,
                    "raw_path": records[0]["raw_path"],
                    "perm_issue": any(rec.get("perm_issue") for rec in records),
                    "inaccess_dir": next(
                        (
                            rec["inaccess_dir"]
                            for rec in records
                            if rec.get("inaccess_dir")
                        ),
                        None,
                    ),
                }
            )

    # 2. Unreferenced media records (image tags with 0 data references)
    for records in path_map.values():
        if len(records) == 1 and records[0]["backlink_count"] == 0:
            rec = records[0]
            groups.append(
                {
                    "type": "unreferenced",
                    "file_key": rec["full_path"],
                    "records": [rec],
                    "keeper": rec,
                    "raw_path": rec["raw_path"],
                    "perm_issue": rec.get("perm_issue", False),
                    "inaccess_dir": rec.get("inaccess_dir"),
                }
            )

    return groups


# ------------------------------------------------------------
#
# FixMediaReferencesDialog
#
# ------------------------------------------------------------
class FixMediaReferencesDialog(Gtk.Dialog):
    """Review and resolve duplicate references where a single media file is used for multiple references, or unreferenced image tags."""

    def __init__(
        self,
        title: str | None = None,
        dbstate: Any = None,
        transient_for: Gtk.Window | None = None,
    ) -> None:
        """
        Scan the tree and build the review table.

        :param title: Window title (defaults to "Fix Media References").
        :param dbstate: The Gramps database state.
        :param transient_for: Parent window.
        """
        dialog_title = title or str(_("Fix Media References"))
        super().__init__(
            title=dialog_title,
            transient_for=transient_for,
            modal=True,
            destroy_with_parent=True,
        )
        self.dbstate = dbstate
        self.groups: list[dict[str, Any]] = []
        self.rows: list[dict[str, Any]] = []
        self.row_targets: list[dict[str, Any]] = []
        self.set_default_size(1360, 520)

        if dbstate and dbstate.db:
            self.groups = find_duplicate_media_groups(dbstate.db)
            self.rows = self.groups

        n_hints = len(self.groups)
        self.accept_button = Gtk.Button(label=str(_("Accept hints (%d)")) % n_hints)
        self.accept_button.set_sensitive(n_hints > 0)
        self.accept_button.connect("clicked", self.cb_accept_hints)
        self.add_action_widget(self.accept_button, Gtk.ResponseType.NONE)

        self.apply_button = Gtk.Button(label=str(_("Apply")))
        self.apply_button.set_sensitive(len(self.groups) > 0)
        self.apply_button.connect("clicked", self.cb_apply)
        self.add_action_widget(self.apply_button, Gtk.ResponseType.NONE)

        self.add_button(str(_("_Close")), Gtk.ResponseType.CLOSE)

        content = self.get_content_area()
        content.set_border_width(12)
        content.set_spacing(6)

        info = Gtk.Label(
            label=str(
                _(
                    "Review duplicate references where a single media file is shared by multiple records, "
                    "or image tags with no data references in the database. "
                    "You can merge duplicate media records into a single keeper, create separate file copies, "
                    "or delete unreferenced records."
                )
            )
        )
        info.set_line_wrap(True)
        info.set_halign(Gtk.Align.START)
        content.add(info)

        if not self.groups:
            done = Gtk.Label(
                label=str(_("No duplicate or unreferenced media records found."))
            )
            done.set_halign(Gtk.Align.START)
            content.add(done)
            return

        dup_count = sum(1 for g in self.groups if g.get("type") == "duplicate")
        unref_count = sum(1 for g in self.groups if g.get("type") == "unreferenced")
        count_label = Gtk.Label(
            label=str(
                _(
                    "Total items to fix: %(total)d (duplicate file groups: "
                    "%(dups)d, unreferenced image tags: %(unref)d)"
                )
                % {"total": len(self.groups), "dups": dup_count, "unref": unref_count}
            )
        )
        count_label.set_halign(Gtk.Align.START)
        content.add(count_label)

        header_grid = create_table_grid(col_spacing=6, row_spacing=0)
        header_grid.set_vexpand(False)

        file_head = HeaderLabel(str(_("File / Media Records")))
        ref_head = HeaderLabel(str(_("References")))
        action_head = HeaderLabel(str(_("Resolution")))
        action_head.set_hexpand(True)
        hint_head = HeaderLabel(str(_("Hint")))
        hint_head.set_hexpand(True)

        header_grid.attach(file_head, 0, 0, 1, 1)
        header_grid.attach(ref_head, 1, 0, 1, 1)
        header_grid.attach(action_head, 2, 0, 1, 1)
        header_grid.attach(hint_head, 3, 0, 1, 1)
        content.add(header_grid)

        self.column_sizegroups = [
            Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL) for _ in range(4)
        ]
        self.column_sizegroups[0].add_widget(file_head)
        self.column_sizegroups[1].add_widget(ref_head)
        self.column_sizegroups[2].add_widget(action_head)
        self.column_sizegroups[3].add_widget(hint_head)

        content.pack_start(self.build_rows(self.groups), True, True, 0)

    def build_rows(self, groups: list[dict[str, Any]]) -> Gtk.ScrolledWindow:
        """
        Build one table row (description, references, action, hint) per group.

        :param groups: Result of :func:`find_duplicate_media_groups`.
        :returns: A scrolled window holding the table.
        """
        grid = create_table_grid()
        row_index = 0

        for group in groups:
            records = group["records"]
            keeper = group["keeper"]
            g_type = group.get("type", "duplicate")

            if g_type == "unreferenced":
                # Column 0: File path and records summary
                desc_lines = [
                    group["raw_path"],
                    f"  • [{keeper['gramps_id']}] {keeper['desc'] or _('(unnamed)')} ("
                    + str(_("Unreferenced"))
                    + ")",
                ]
                file_label = TableLabel(
                    "\n".join(desc_lines), width_chars=40, width_request=320
                )
                grid.attach(file_label, 0, row_index, 1, 1)

                # Column 1: References summary
                ref_label = TableLabel(
                    f"[{keeper['gramps_id']}]: "
                    + str(_("0 data references (unreferenced image tag)")),
                    width_chars=40,
                    width_request=300,
                )
                grid.attach(ref_label, 1, row_index, 1, 1)

                # Column 2: Action ComboBox
                action_combo = Gtk.ComboBoxText()
                action_combo.append_text(str(_("Delete unreferenced record")))
                action_combo.append_text(str(_("Keep unreferenced (no change)")))
                action_combo.set_active(1)  # never delete by default
                action_combo.set_hexpand(True)
                grid.attach(action_combo, 2, row_index, 1, 1)

                # Column 3: Hint label
                # Only suggest deleting a record that carries nothing worth
                # keeping (no notes, attributes, tags, citations or date).
                bare = bool(keeper.get("bare"))
                suggested_action = 0 if bare else 1
                if bare:
                    hint_str = str(
                        _("Unreferenced media object with no notes or other data")
                    )
                else:
                    hint_str = str(
                        _(
                            "Unreferenced, but has notes, attributes, tags, "
                            "citations or a date: keep, or review manually"
                        )
                    )
                if group.get("perm_issue") and group.get("inaccess_dir"):
                    hint_str = (
                        str(_("Permission denied at '%s'")) % group["inaccess_dir"]
                    )
                hint_label = TableLabel(
                    hint_str,
                    width_chars=36,
                    width_request=280,
                )
                hint_label.set_hexpand(True)
                grid.attach(hint_label, 3, row_index, 1, 1)

            else:
                # Column 0: File path and records summary
                desc_lines = [group["raw_path"]]
                if group.get("perm_issue") and group.get("inaccess_dir"):
                    desc_lines.append(
                        "  ⚠ "
                        + str(_("Permission denied at: %s")) % group["inaccess_dir"]
                    )
                for rec in records:
                    rec_desc = rec["desc"] or _("(unnamed)")
                    desc_lines.append(f"  • [{rec['gramps_id']}] {rec_desc}")
                file_label = TableLabel(
                    "\n".join(desc_lines), width_chars=40, width_request=320
                )
                grid.attach(file_label, 0, row_index, 1, 1)

                # Column 1: References summary
                ref_parts = []
                for rec in records:
                    assoc = rec.get("assoc") or rec.get("desc") or _("(unnamed)")
                    ref_parts.append(f"[{rec['gramps_id']}]: {assoc}")
                ref_label = TableLabel(
                    "\n".join(ref_parts), width_chars=40, width_request=300
                )
                grid.attach(ref_label, 1, row_index, 1, 1)

                # Column 2: Action ComboBox
                action_combo = Gtk.ComboBoxText()
                action_combo.append_text(
                    str(_("Merge into keeper [%s]")) % keeper["gramps_id"]
                )
                action_combo.append_text(str(_("Create separate file copies")))
                action_combo.append_text(str(_("Keep shared (no change)")))
                action_combo.set_active(0)
                action_combo.set_hexpand(True)
                grid.attach(action_combo, 2, row_index, 1, 1)
                suggested_action = 0

                # Column 3: Hint label
                hint_str = str(_("Merge duplicate records into keeper [%(gid)s]")) % {
                    "gid": keeper["gramps_id"],
                }
                hint_label = TableLabel(hint_str, width_chars=36, width_request=280)
                hint_label.set_hexpand(True)
                grid.attach(hint_label, 3, row_index, 1, 1)

            if row_index == 0 and hasattr(self, "column_sizegroups"):
                self.column_sizegroups[0].add_widget(file_label)
                self.column_sizegroups[1].add_widget(ref_label)
                self.column_sizegroups[2].add_widget(action_combo)
                self.column_sizegroups[3].add_widget(hint_label)

            self.row_targets.append(
                {
                    "group": group,
                    "action_combo": action_combo,
                    "hint_label": hint_label,
                    "suggested_action": suggested_action,
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

    def cb_accept_hints(self, _button: Gtk.Button) -> None:
        """
        Set every row's action to its suggestion.

        Unreferenced records are only set to *Delete* when they carry no data.

        :param _button: The button that was clicked.
        """
        count = 0
        for target in self.row_targets:
            combo = target["action_combo"]
            if hasattr(combo, "set_active"):
                combo.set_active(target["suggested_action"])
                count += 1
        OkDialog(
            str(_("Hints accepted")),
            str(
                ngettext(
                    "Set the suggested action for %d row. Review and press Apply.",
                    "Set the suggested action for %d rows. Review and press Apply.",
                    count,
                )
                % count
            ),
            parent=self,
        )

    def cb_apply(self, _button: Gtk.Button) -> None:
        """
        Merge, split or delete according to each row's chosen action.

        Locked records are never changed; failures are listed in the result.

        :param _button: The button that was clicked.
        """
        merged_count = 0
        copied_count = 0
        deleted_count = 0
        errors: list[str] = []

        for target in self.row_targets:
            combo = target["action_combo"]
            choice = 0
            if hasattr(combo, "get_active"):
                raw_choice = combo.get_active()
                try:
                    choice = int(raw_choice)
                except (TypeError, ValueError):
                    choice = 0
            group = target["group"]
            g_type = group.get("type", "duplicate")

            if g_type == "unreferenced":
                if choice == 0:
                    handle = group["keeper"]["handle"]
                    cand = self.dbstate.db.get_media_from_handle(handle)
                    if cand and is_media_locked(self.dbstate.db, cand):
                        errors.append(
                            "[%s] %s"
                            % (
                                group["keeper"].get("gramps_id", ""),
                                _("media is locked; cannot delete"),
                            )
                        )
                        continue
                    try:
                        with DbTxn(
                            _("Remove Unreferenced Media"), self.dbstate.db
                        ) as trans:
                            self.dbstate.db.remove_media(handle, trans)
                            deleted_count += 1
                    except Exception as err:
                        LOG.exception("Failed to remove unreferenced media: %s", err)
                        errors.append(str(err))
                continue

            if choice == 2:  # Keep shared (no change)
                continue

            records = group["records"]
            keeper = group["keeper"]

            if choice == 0:
                # Merge duplicate records into keeper
                keeper_media = self.dbstate.db.get_media_from_handle(keeper["handle"])
                if not keeper_media:
                    continue
                if is_media_locked(self.dbstate.db, keeper_media):
                    errors.append(
                        "[%s] %s"
                        % (
                            keeper.get("gramps_id", ""),
                            _("keeper media is locked; cannot merge"),
                        )
                    )
                    continue
                for other in records:
                    if other["handle"] == keeper["handle"]:
                        continue
                    try:
                        other_media = self.dbstate.db.get_media_from_handle(
                            other["handle"]
                        )
                        if other_media:
                            if is_media_locked(self.dbstate.db, other_media):
                                errors.append(
                                    "[%s] %s"
                                    % (
                                        other.get("gramps_id", ""),
                                        _("media is locked; cannot merge"),
                                    )
                                )
                                continue
                            query = MergeMediaQuery(
                                self.dbstate, keeper_media, other_media
                            )
                            query.execute()
                            add_media_fixed_tag(
                                self.dbstate.db, keeper_media, commit=True
                            )
                            merged_count += 1
                    except Exception as err:
                        LOG.exception("Failed to merge media record: %s", err)
                        errors.append(str(err))

            elif choice == 1:
                # Create separate file copies for each duplicate record
                src_path = clean_path(group["raw_path"])
                try:
                    src_full = clean_path(media_path_full(self.dbstate.db, src_path))
                except Exception:
                    src_full = src_path

                base, ext = os.path.splitext(src_path)
                claimed: set[str] = set()
                move_log = MoveLog(media_base_path(self.dbstate.db), "Split media")
                with DbTxn(_("Split Media References"), self.dbstate.db) as trans:
                    for rec in records[1:]:
                        other_media = self.dbstate.db.get_media_from_handle(
                            rec["handle"]
                        )
                        if other_media and is_media_locked(
                            self.dbstate.db, other_media
                        ):
                            errors.append(
                                "[%s] %s"
                                % (
                                    rec.get("gramps_id", ""),
                                    _("media is locked; cannot modify path"),
                                )
                            )
                            continue
                        new_rel = f"{base}_{rec['gramps_id']}{ext}"
                        try:
                            expected = media_path_full(self.dbstate.db, new_rel)
                        except Exception:
                            expected = new_rel
                        if not os.path.exists(src_full):
                            errors.append(
                                "[%s] source file not found: %s"
                                % (rec["gramps_id"], src_full)
                            )
                            continue
                        dest_full = unique_destination(expected, claimed, src_full)
                        if dest_full != expected:  # keep DB path and disk name in step
                            extra = os.path.splitext(dest_full)[0][
                                len(os.path.splitext(expected)[0]) :
                            ]
                            new_rel = f"{base}_{rec['gramps_id']}{extra}{ext}"
                        copied_ok, copy_err = relocate_file(
                            src_full, dest_full, copy=True
                        )
                        if not copied_ok:
                            LOG.warning("Failed to copy media file: %s", copy_err)
                            errors.append("[%s] %s" % (rec["gramps_id"], copy_err))
                            continue
                        copied_count += 1
                        if other_media:
                            move_log.record(
                                "copy",
                                other_media,
                                clean_path(str(other_media.get_path() or "")),
                                new_rel,
                                src_full,
                                dest_full,
                            )
                            other_media.set_path(new_rel)
                            add_media_fixed_tag(self.dbstate.db, other_media, txn=trans)
                            self.dbstate.db.commit_media(other_media, trans)
                if len(move_log):
                    log_err = move_log.write()
                    if log_err:
                        errors.append(
                            str(_("The file-move log could not be written: %s"))
                            % log_err
                        )

        if merged_count == 0 and copied_count == 0 and deleted_count == 0:
            if errors:
                # Every selected action failed (e.g. all locked): say why,
                # instead of claiming nothing was selected.
                OkDialog(
                    str(_("Nothing was changed")),
                    "\n".join(errors),
                    parent=self,
                )
                return
            OkDialog(
                str(_("Nothing to apply")),
                str(
                    _(
                        "No actions selected. Choose 'Merge', 'Create copies', or 'Delete' for one or more records first."
                    )
                ),
                parent=self,
            )
            return

        summary = []
        if merged_count > 0:
            summary.append(str(_("Merged %d duplicate media records.")) % merged_count)
        if copied_count > 0:
            summary.append(str(_("Created %d separate media files.")) % copied_count)
        if deleted_count > 0:
            summary.append(
                str(_("Deleted %d unreferenced media records.")) % deleted_count
            )

        msg = " ".join(summary)
        if errors:
            msg += "\n\n" + "\n".join(errors)
        OkDialog(
            str(_("Media References Resolved")),
            msg + "\n\n" + str(_("Close and reopen this dialog to rescan.")),
            parent=self,
        )

        # Update button sensitivities and group records after applying
        self.groups = []
        self.row_targets = []
        if hasattr(self, "apply_button"):
            self.apply_button.set_sensitive(False)
        if hasattr(self, "accept_button"):
            self.accept_button.set_sensitive(False)

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
