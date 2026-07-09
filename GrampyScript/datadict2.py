#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025       Doug Blank
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

# ------------------------------------------------------------------------
#
# Python modules
#
# ------------------------------------------------------------------------

from __future__ import annotations

from gramps.gen.lib.json_utils import data_to_object, object_to_dict
from gramps.gen.lib import PrimaryObject, GrampsType
from gramps.gen.config import config

NoneType = type(None)

# *Ref._class -> the table its `ref` handle points into, for the `reference`
# property below.
REFERENCE_TABLES = {
    "ChildRef": "Person",
    "EventRef": "Event",
    "MediaRef": "Media",
    "PersonRef": "Person",
    "PlaceRef": "Place",
    "RepoRef": "Repository",
}
invalid_date_format = config.get("preferences.invalid-date-format")
age_precision = config.get("preferences.age-display-precision")
age_after_death = config.get("preferences.age-after-death")


def flatten(lst):
    result = []
    for item in lst:
        if isinstance(item, list):
            result.extend(flatten(item))  # Recursive call for sublists
        else:
            result.append(item)
    return result


class NoneData:

    # def __setattr__(self, attr, value):
    #    if attr == "root":
    #        self.root = value
    #    elif attr == "path":
    #        self.path = value
    #    else:
    #        pass

    def __getattr__(self, attr):
        return NoneData()

    def __str__(self):
        return ""

    def __bool__(self):
        return False

    def __call__(self, *args, **kwargs):
        # print(args, kwargs)
        return ""

    def __iter__(self):
        return iter([])


class DataDict2(dict):
    """
    A wrapper around a data dict that also provides an
    object interface.
    """

    def __init__(self, data=None, root=None, path=None, callback=None):
        """
        Wrap a data dict (raw data) or object
        with an attribute API. If data is an object,
        we use it to get the attributes.
        """
        self.root = root if root is not None else self
        self.path = path if path is not None else []
        self.callback = callback
        if isinstance(data, dict):
            super().__init__(data)
        else:
            super().__init__()
            if data:
                # Data is actually a Gramps object
                self.update(object_to_dict(data))

    @property
    def gender(self):
        return sa.gender(self._object)

    @property
    def age(self):
        birth_event = self.birth
        death_event = self.death
        if birth_event and death_event:
            birth_date = birth_event.get_date_object()
            death_date = death_event.get_date_object()
            return death_date - birth_date
        else:
            return ""

    @property
    def birth(self):
        ref = self._object.get_birth_ref()
        if ref:
            event_handle = ref.get_reference_handle()
            if event_handle is not None:
                event = sa.dbase.get_event_from_handle(event_handle)
                if event is not None:
                    return DataDict2(event, callback=self.callback)

        return NoneData()

    @property
    def place(self):
        place_handle = self._object.place
        if place_handle:
            place = sa.dbase.get_place_from_handle(place_handle)
            if place is not None:
                return DataDict2(place, callback=self.callback)

        return NoneData()

    @property
    def death(self):
        ref = self._object.get_death_ref()
        if ref:
            event_handle = ref.get_reference_handle()
            if event_handle is not None:
                event = sa.dbase.get_event_from_handle(event_handle)
                if event is not None:
                    return DataDict2(event, callback=self.callback)

        return NoneData()

    @property
    def parents(self):
        parents = []
        father = sa.father(self._object)
        if father is not None:
            parents.append(DataDict2(father, callback=self.callback))
        mother = sa.mother(self._object)
        if mother is not None:
            parents.append(DataDict2(mother, callback=self.callback))
        return DataList2(parents)

    @property
    def father(self):
        father = sa.father(self._object)
        if father is not None:
            return DataDict2(father, callback=self.callback)
        else:
            return NoneData()

    @property
    def mother(self):
        mother = sa.mother(self._object)
        if mother is not None:
            return DataDict2(mother, callback=self.callback)
        else:
            return NoneData()

    @property
    def spouse(self):
        spouse = sa.spouse(self._object)
        if spouse is not None:
            return DataDict2(spouse, callback=self.callback)
        else:
            return NoneData()

    @property
    def source(self):
        source_handle = self["source_handle"]
        source = sa.dbase.get_source_from_handle(source_handle)
        if source is not None:
            return DataDict2(source, callback=self.callback)
        else:
            return NoneData()

    @property
    def families(self):
        return DataList2(
            [
                DataDict2(family, callback=self.callback)
                for family in sa.parent_in(self._object)
            ],
        )

    @property
    def parent_families(self):
        return DataList2(
            [
                DataDict2(family, callback=self.callback)
                for family in sa.child_in(self._object)
            ],
        )

    @property
    def children(self):
        return DataList2(
            [
                DataDict2(person, callback=self.callback)
                for person in sa.children(self._object)
            ],
        )

    @property
    def notes(self):
        return DataList2(
            [
                DataDict2(sa.dbase.get_raw_note_data(handle), callback=self.callback)
                for handle in self.note_list
            ],
        )

    @property
    def tags(self):
        return DataList2(
            [
                DataDict2(sa.dbase.get_raw_tag_data(handle), callback=self.callback)
                for handle in self.tag_list
            ],
        )

    @property
    def citations(self):
        return DataList2(
            [
                DataDict2(
                    sa.dbase.get_raw_citation_data(handle), callback=self.callback
                )
                for handle in self.citation_list
            ],
        )

    @property
    def media(self):
        return self.media_list

    @property
    def events(self):
        return DataList2(
            [
                DataDict2(sa.dbase.get_raw_event_data(handle), callback=self.callback)
                for handle in self.event_list
            ],
        )

    @property
    def reference(self):
        # self is one of the *Ref wrapper types (PersonRef, EventRef, ...);
        # `ref` is a handle into whichever table its own _class points at,
        # not always Person.
        table = REFERENCE_TABLES.get(self["_class"])
        if table is None:
            return NoneData()
        getter = sa.dbase.method("get_raw_%s_data", table)
        data = getter(self.ref) if getter else None
        if data is None:
            return NoneData()
        return DataDict2(data, callback=self.callback)

    @property
    def attributes(self):
        return self.attribute_list

    @property
    def addresses(self):
        return self.address_list

    @property
    def lds_ords(self):
        return self.lds_ord_list

    @property
    def references(self):
        return self.person_ref_list

    @property
    def back_references(self):
        retval = []
        for obj_type, ohandle in sa.dbase.find_backlink_handles(self.handle):
            obj = sa.dbase.method("get_%s_from_handle", obj_type)(ohandle)
            retval.append(DataDict2(obj, callback=self.callback))
        return DataList2(retval)

    @property
    def back_references_recursively(self):
        retval = []
        for obj_type, ohandle in self._object.get_referenced_handles_recursively():
            obj = sa.dbase.method("get_%s_from_handle", obj_type)(ohandle)
            retval.append(DataDict2(obj, callback=self.callback))
        return DataList2(retval)

    @property
    def name(self):
        if self["_class"] == "Person":
            return self.primary_name
        return self["name"] if "name" in self else NoneData()

    @property
    def surname(self):
        if self["_class"] == "Person":
            return self.primary_name.surname_list[0]
        return self["surname"] if "surname" in self else NoneData()

    @property
    def names(self):
        return DataList2([self.primary_name] + self.alternate_names)

    @property
    def string(self):
        # The raw "string" field only holds the *custom*-type override text
        # for GrampsType-based values (NameOriginType, NameType, EventType,
        # ...); for predefined values (the common case) it is always "".
        # Route to the real object's `.string` property instead, which
        # computes the actual (translated) label. Raising AttributeError
        # for anything without a "string" field falls back to the normal
        # __getattr__ lookup, so this doesn't change behavior elsewhere.
        if "string" not in self:
            raise AttributeError("string")
        if isinstance(self._object, GrampsType):
            return str(self._object)
        return self["string"]

    def _real_object(self):
        """Walk from the root's real object down self.path to find the
        actual (not reconstructed) object that this wrapper represents."""
        obj = self.root._object
        for part in self.path:
            if isinstance(part, int):
                obj = obj[part]
            else:
                obj = getattr(obj, part)
        return obj

    def __setattr__(self, attr, value):
        if attr in ["root", "path", "callback"]:
            return super().__setattr__(attr, value)
        else:
            # Set it in the real _object:
            setattr(self._real_object(), attr, value)
            # Update the top-level dict:
            self.root.update(object_to_dict(self.root._object))
            # Call the callback
            if self.root.callback is not None:
                self.root.callback("set", self.root)

    # def __str__(self):
    #    return str(self._object)

    def __dir__(self):
        # Merge real class attributes with the dynamic dict keys, so that
        # introspection tools (e.g. jedi-based completion) can see fields
        # like `primary_name` that only exist via __getattr__.
        return sorted(set(super().__dir__()) | set(self.keys()))

    def __getattr__(self, key):
        if key == "_object":
            if "_object" not in self:
                # A nested wrapper (non-empty path) must resolve to the
                # actual sub-object inside the root's real object tree,
                # not a standalone copy reconstructed from its own dict
                # slice -- otherwise set_*() calls below mutate a clone
                # that is discarded instead of the real, committed object.
                if self.path:
                    self["_object"] = self._real_object()
                else:
                    self["_object"] = data_to_object(self)
            return self["_object"]
        elif key.startswith("_"):
            raise AttributeError(
                "this method cannot be used to access hidden attributes"
            )

        if key in self:
            value = self[key]
            if isinstance(value, dict):
                return DataDict2(value, root=self.root, path=self.path + [key])
            elif isinstance(value, list):
                return DataList2(value, root=self.root, path=self.path + [key])
            else:
                return value
        else:
            # Some method or attribute not available
            # otherwise.
            try:
                attr = getattr(self._object, key)
                if key.startswith("set_"):
                    return self.set_wrapper(attr)
                else:
                    return attr
            except Exception:
                return NoneData()

    def set_wrapper(self, method):
        def wrapper(*args, **kwargs):
            value = method(*args, **kwargs)
            # Update the toplevel dict:
            self.root.update(object_to_dict(self.root._object))
            # Call the callback
            if self.root.callback is not None:
                self.root.callback("set", self.root)
            return value

        return wrapper


class DataList2(list):
    """
    A wrapper around a data list.
    """

    def __init__(self, data, root=None, path=None):
        self.root = root
        self.path = path if path is not None else []
        super().__init__(data)

    def __setitem__(self, position, value):
        raise Exception("Setting a DataList2 item is not allowed")

    def __getattr__(self, attr):
        if attr.startswith("set_"):
            # Fan the call (same args) out to every item, rather than
            # collecting each item's set_*() wrapper closure unevaluated
            # (which isn't callable itself and silently did nothing).
            def wrapper(*args, **kwargs):
                return DataList2([getattr(x, attr)(*args, **kwargs) for x in self])

            return wrapper
        return DataList2(flatten([getattr(x, attr) for x in self]))

    def __getitem__(self, position, root=None, path=""):
        try:
            value = super().__getitem__(position)
        except Exception:
            return NoneData()
        # Items can already be fully-wrapped (e.g. after `+`/`__radd__`
        # concatenates lists whose elements are DataDict2/DataList2). Since
        # both subclass dict/list, re-wrapping them here would discard their
        # real root/path and replace it with this list's (often unrelated)
        # root, corrupting later attribute assignment.
        if isinstance(value, (DataDict2, DataList2)):
            return value
        elif isinstance(value, dict):
            return DataDict2(value, root=self.root, path=self.path + [position])
        elif isinstance(value, list):
            return DataList2(value, root=self.root, path=self.path + [position])
        else:
            return value

    def __iter__(self):
        self.index = 0
        return self

    def __next__(self):
        if self.index >= len(self):
            raise StopIteration

        result = self[self.index]
        self.index += 1
        return result

    def __add__(self, value):
        return DataList2([x for x in self] + [x for x in value])

    def __radd__(self, value):
        # self is the right-hand operand here (Python calls b.__radd__(a)
        # for `a + b`), so the result must be `value + self`, not `self +
        # value` -- otherwise `plain_list + data_list2` comes out reversed.
        return DataList2([x for x in value] + [x for x in self])


sa = None


def set_sa(new_sa):
    """Set SimpleAccess"""
    global sa
    sa = new_sa
