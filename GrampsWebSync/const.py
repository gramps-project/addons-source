# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021-2024       David Straub
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


"""Constants for Gramps Web Sync."""

from __future__ import annotations

from gramps.gen.lib.primaryobj import BasicPrimaryObject as GrampsObject


# types
Action = tuple[str, str, str, GrampsObject | None, GrampsObject | None]
Actions = list[Action]


# changed: added, deleteed, updated - local/remote/both
C_ADD_LOC = "added_local"
C_ADD_REM = "added_remote"
C_DEL_LOC = "deleted_local"
C_DEL_REM = "deleted_remote"
C_UPD_LOC = "updated_local"
C_UPD_REM = "updated_remote"
C_UPD_BOTH = "updated_both"

# actions: add, delete, update, merge - local/remote
A_ADD_LOC = "add_local"
A_ADD_REM = "add_remote"
A_DEL_LOC = "del_local"
A_DEL_REM = "del_remote"
A_UPD_LOC = "upd_local"
A_UPD_REM = "upd_remote"
A_MRG_REM = "mrg_remote"


OBJ_LST = [
    "Family",
    "Person",
    "Citation",
    "Event",
    "Media",
    "Note",
    "Place",
    "Repository",
    "Source",
    "Tag",
]

# sync modes
MODE_BIDIRECTIONAL = 0
MODE_RESET_TO_LOCAL = 1
MODE_RESET_TO_REMOTE = 2
