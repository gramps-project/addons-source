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
Module to launch the GTK attribute editor in Gramps for various supported object types.

This utility supports editing attributes for multiple entity types such as:
- People
- Families
- Events
- Media
- Sources
- Citations

Depending on the provided information (object or handle, attribute object or name),
the launcher resolves the correct Gramps object and attribute, opens the editor,
and handles saving the edited attribute back to the parent entity.

Designed to be compatible with both Gramps 6.0 and 5.2.
"""

from functools import partial
from gettext import gettext as _
from types import SimpleNamespace

from gramps.gui.editors.editattribute import EditAttribute
from gramps.gen.db import DbTxn
from constants import ActivityType
from helpers import get_attribute_name, get_handle_lookup


class AttributeEditorManager:
    """
    A utility class to launch the GTK attribute editor for supported Gramps objects.

    Provides four methods depending on how object and attribute are passed in:
    - By object handle and attribute name
    - By object handle and attribute object
    - By object and attribute name
    - By object and attribute object
    """

    def __init__(self, dbstate, uistate, activities_model):
        self.dbstate = dbstate
        self.uistate = uistate
        self.activities_model = activities_model

    def edit_by_obj_handle_and_attr_name(self, ctx: SimpleNamespace):
        """Edit attribute by object handle and attribute name (via context object)."""
        obj = self._get_object_by_handle(ctx.nav_type, ctx.obj_handle)
        if obj is None:
            print(f"❌ Error. Object by handle '{ctx.obj_handle}' not found")
            return False
        matches = self._find_attributes_by_name(obj, ctx.attr_type, ctx.attr_value)
        for index, attr_obj in matches:
            self._edit(ctx, obj, attr_obj, index)
        return True

    def edit_by_obj_handle_and_attr_obj(self, ctx: SimpleNamespace, attr_obj):
        """Edit attribute by object handle and attribute object."""
        obj = self._get_object_by_handle(ctx.nav_type, ctx.obj_handle)
        if obj is None:
            print(f"❌ Error. Object by handle '{ctx.obj_handle}' not found")
            return False
        index = self._find_attribute_index(obj, attr_obj)
        self._edit(ctx, obj, attr_obj, index)
        return True

    def edit_by_obj_and_attr_name(self, ctx: SimpleNamespace, obj):
        """Edit attribute by object and attribute name."""
        matches = self._find_attributes_by_name(obj, ctx.attr_type, ctx.attr_value)
        for index, attr_obj in matches:
            self._edit(ctx, obj, attr_obj, index)
        return True

    def edit_by_obj_and_attr_obj(self, ctx: SimpleNamespace, obj, attr_obj):
        """Edit attribute by object and attribute object."""
        index = self._find_attribute_index(obj, attr_obj)
        self._edit(ctx, obj, attr_obj, index)
        return True

    def _find_attribute_index(self, obj, target_attr):
        """Find the index of a specific attribute object within an object's attribute list."""
        for i, attr in enumerate(obj.get_attribute_list()):
            if attr is target_attr:
                return i
        raise AttributeNotFoundError("Attribute not found")

    def _get_object_by_handle(self, nav_type, obj_handle):
        """Resolve the Gramps object by navigation type and obj_handle."""
        lookup = get_handle_lookup(self.dbstate.db)
        if nav_type not in lookup:
            raise ValueError(f"Unsupported nav_type: {nav_type}")
        return lookup[nav_type](obj_handle)

    def _find_attributes_by_name(self, obj, attr_name, attr_value=None):
        """Find attribute objects by their type (attr_name), optionally filtering by value."""
        matches = [
            (i, attr)
            for i, attr in enumerate(obj.get_attribute_list())
            if attr.get_type() == attr_name
            and (attr_value is None or attr.get_value() == attr_value)
        ]

        if not matches:
            raise AttributeNotFoundError(
                f"Attribute {attr_name} with value {attr_value} not found"
            )

        return matches

    def _edit(self, ctx: SimpleNamespace, obj, attr, index):
        old_attr_name = get_attribute_name(attr.get_type())
        old_attr_value = attr.get_value()

        EditAttribute(
            self.dbstate,
            self.uistate,
            [],
            attr,
            (
                obj.get_primary_name().get_name()
                if hasattr(obj, "get_primary_name")
                else ""
            ),
            self.dbstate.db.get_person_attribute_types(),
            callback=partial(
                self._on_attribute_edited,
                ctx,
                obj,
                index,
                old_attr_name,
                old_attr_value,
            ),
        )

    def _on_attribute_edited(
        self, ctx, obj, index, old_attr_name, old_attr_value, updated_attr
    ):
        """Save the updated attribute back to the object and commit to the database."""
        if not updated_attr:
            return

        self.activities_model.create(
            {
                "nav_type": ctx.nav_type,
                "activity_type": ActivityType.ATTRIBUTE_EDIT.value,
                "obj_handle": obj.get_handle(),
                "obj_gramps_id": obj.get_gramps_id(),
                "old_attr_name": old_attr_name,
                "old_attr_value": old_attr_value,
                "updated_attr_name": get_attribute_name(updated_attr.get_type()),
                "updated_attr_value": updated_attr.get_value(),
            }
        )

        attr_list = obj.get_attribute_list()
        attr_list[index] = updated_attr

        with DbTxn("Edit Attribute", self.dbstate.db) as trans:
            obj.set_attribute_list(attr_list)
            commit_map = {
                "People": self.dbstate.db.commit_person,
                "Families": self.dbstate.db.commit_family,
                "Events": self.dbstate.db.commit_event,
                "Media": self.dbstate.db.commit_media,
                "Sources": self.dbstate.db.commit_source,
                "Citations": self.dbstate.db.commit_citation,
                "Person": self.dbstate.db.commit_person,
                "Family": self.dbstate.db.commit_family,
                "Event": self.dbstate.db.commit_event,
                "Source": self.dbstate.db.commit_source,
                "Citation": self.dbstate.db.commit_citation,
            }
            if ctx.nav_type in commit_map:
                commit_map[ctx.nav_type](obj, trans)

        refreshed_attr = obj.get_attribute_list()[index]
        name = get_attribute_name(refreshed_attr.get_type())
        value = refreshed_attr.get_value()

        if ctx.callback:
            ctx.callback((refreshed_attr, name, value))


class AttributeNotFoundError(Exception):
    """Raised when an expected attribute is no longer present in the object."""
