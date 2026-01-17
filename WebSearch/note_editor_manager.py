#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Yurii Liubymyi <jurchello@gmail.com>
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

# ----------------------------------------------------------------------------


"""
Module to launch the GTK note editor in Gramps for various supported object types.

This utility supports editing notes for multiple entity types such as:
- People
- Families
- Events
- Media
- Sources
- Citations

Depending on the provided information (object or handle, note object),
the launcher resolves the correct Gramps object and note, opens the editor,
and handles saving the edited note back to the parent entity.

Designed to be compatible with both Gramps 6.0 and 5.2.
"""

from functools import partial
from gettext import gettext as _
from types import SimpleNamespace

from gramps.gui.editors.editnote import EditNote
from gramps.gen.db import DbTxn
from constants import ActivityType
from helpers import get_handle_lookup


class NoteEditorManager:
    """
    A utility class to launch the GTK note editor for supported Gramps objects.

    Provides methods depending on how object and note are passed in:
    - By object handle and note object
    - By object and note object
    """

    def __init__(self, dbstate, uistate, activities_model):
        self.dbstate = dbstate
        self.uistate = uistate
        self.activities_model = activities_model

    def edit_by_obj_handle_and_note_handle(self, ctx: SimpleNamespace):
        """Edit a note by object handle and note handle."""
        if not ctx.note_handle:
            raise NoteNotFoundError(f"Note with handle: '{ctx.note_handle}'  not found")
        obj = self._get_object_by_handle(ctx.nav_type, ctx.obj_handle)
        if obj is None:
            return False
        note_obj = self._get_object_by_handle("Notes", ctx.note_handle)
        if note_obj is None:
            raise NoteNotFoundError(f"Note with handle: '{ctx.note_handle}'  not found")
        self._edit(ctx, obj, note_obj)
        return True

    def edit_by_obj_and_note_handle(self, ctx: SimpleNamespace):
        """Edit a note by object instance and note handle."""
        if not ctx.note_handle:
            raise NoteNotFoundError(f"Note with handle: '{ctx.note_handle}'  not found")
        note_obj = self._get_object_by_handle("Notes", ctx.note_handle)
        if note_obj is None:
            raise NoteNotFoundError(f"Note with handle: '{ctx.note_handle}'  not found")

        self._edit(ctx, ctx.obj, note_obj)
        return True

    def edit_by_obj_handle_and_note_obj(self, ctx: SimpleNamespace):
        """Edit note by object handle and note object."""
        obj = self._get_object_by_handle(ctx.nav_type, ctx.obj_handle)
        if obj is None:
            print(f"Warning. Object by handle '{ctx.obj_handle}' not found")
            return False
        self._edit(ctx, obj, ctx.note_obj)
        return True

    def edit_by_obj_and_note_obj(self, ctx: SimpleNamespace):
        """Edit note by object and note object."""
        self._edit(ctx, ctx.obj, ctx.note_obj)
        return True

    def _get_object_by_handle(self, nav_type, obj_handle):
        """Resolve the Gramps object by navigation type and obj_handle."""
        lookup = get_handle_lookup(self.dbstate.db)
        if nav_type not in lookup:
            raise ValueError(f"Unsupported nav_type: {nav_type}")
        result = lookup[nav_type](obj_handle)

        return result

    def _edit(self, ctx: SimpleNamespace, obj, note_obj):
        """Launch the GTK editor to edit the given note object."""

        EditNote(
            self.dbstate,
            self.uistate,
            [],
            note_obj,
            callback=partial(
                self._on_note_edited,
                ctx,
                obj,
                note_obj,
            ),
        )

    def _on_note_edited(self, ctx, obj, note_obj, unused_note_handle):
        """Save the updated note back to the object and commit to the database."""

        self.activities_model.create(
            {
                "nav_type": ctx.nav_type,
                "activity_type": ActivityType.NOTE_EDIT.value,
                "obj_handle": obj.get_handle(),
                "obj_gramps_id": obj.get_gramps_id(),
            }
        )

        with DbTxn("Edit Note", self.dbstate.db) as trans:
            self.dbstate.db.commit_note(note_obj, trans)

        if ctx.callback:
            ctx.callback()


class NoteNotFoundError(Exception):
    """Raised when an expected note is no longer present in the object."""
