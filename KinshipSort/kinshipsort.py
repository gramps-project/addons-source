# -*- coding: utf-8 -*-
#
# KinshipSort - biological kinship sorting for Gramps
# Copyright (C) 2026 Jacek Kuznia <jacek.kuznia@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <https://www.gnu.org/licenses/>.
#
# The grouped-view actions and add-person behavior are adapted from
# gramps/plugins/view/persontreeview.py:
# Copyright (C) 2000-2007 Donald N. Allingham
# Copyright (C) 2008 Gary Burton
# Copyright (C) 2009 Nick Hall
# Copyright (C) 2010 Benny Malengier
# See ATTRIBUTION.md for provenance.
#

"""Kinship-sorted People views for Gramps 6.0.x.

This experimental addon adds two presentation variants of the People
view: a flat list and a surname-grouped tree.  It does not write calculated
kinship degrees to the genealogy database.

Kinship degree is the minimum number of biological parent/child steps along
a path going up to a common ancestor and then down to a relative. It is
calculated relative to the database Home Person, not the active selection.
Flat-list ties are ordered by generation, then the normal Gramps name key.
Grouped-view ties use the normal name key. Other columns retain their normal
Gramps sort. Only birth relations are counted. People with no established
biological relationship have a blank degree and follow relatives in ascending
order. Descending order reverses the entire list, including blank degrees.
The inherited Gramps editing actions remain available.
"""

# ------------------------------------------------------------------------
# Standard Python modules
# ------------------------------------------------------------------------
from collections import defaultdict

# ------------------------------------------------------------------------
# GTK/Gnome modules
# ------------------------------------------------------------------------
from gi.repository import Gtk

# ------------------------------------------------------------------------
# Gramps modules
# ------------------------------------------------------------------------
from gramps.gen.config import config
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.lib import ChildRefType, Name, Person, Surname
from gramps.gen.errors import WindowActiveError
from gramps.gen.utils.db import preset_name
from gramps.gui.editors import EditPerson
from gramps.gui.views.listview import TEXT
from gramps.gui.views.treemodels.flatbasemodel import FlatBaseModel
from gramps.gui.views.treemodels.treebasemodel import TreeBaseModel
from gramps.gui.views.treemodels.peoplemodel import PeopleBaseModel
from gramps.plugins.lib.libpersonview import BasePersonView

# ------------------------------------------------------------------------
# Addon modules
# ------------------------------------------------------------------------
from kinship_calculation import calculate_kinship_from_relations

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# The standard People model has columns 0..14 visible/configurable and model
# column 15 reserved for the hidden tag-colour value.  We insert our visible
# column at 15 and move the hidden tag-colour value to 16.
KINSHIP_COL = 15
TAG_COLOR_COL = 16
NO_SURNAME = config.get("preferences.no-surname-text")


def _biological_relations(db):
    """Return biological parent and child maps.

    The result is ``(parents, children)`` where both mappings contain only
    birth relations from Gramps ChildRef objects.  Keeping the two directions
    separate is important: a valid biological kinship path may go from the
    Home Person upward to a common ancestor and then downward to a relative,
    but it must never go downward first and then upward through the other
    parent of a shared child.  The latter would incorrectly classify spouses
    as biological relatives.
    """
    parents = defaultdict(set)
    children = defaultdict(set)

    for family_handle in db.get_family_handles():
        family = db.get_family_from_handle(family_handle)
        if family is None:
            continue

        father_handle = family.get_father_handle()
        mother_handle = family.get_mother_handle()

        for child_ref in family.get_child_ref_list():
            child_handle = child_ref.ref
            if not child_handle:
                continue

            if (
                father_handle
                and child_ref.get_father_relation() == ChildRefType.BIRTH
            ):
                parents[child_handle].add(father_handle)
                children[father_handle].add(child_handle)

            if (
                mother_handle
                and child_ref.get_mother_relation() == ChildRefType.BIRTH
            ):
                parents[child_handle].add(mother_handle)
                children[mother_handle].add(child_handle)

    return parents, children


def calculate_kinship_info(db):
    """Return ``(degrees, generations, home_handle)``.

    Biological kinship is defined through a common biological ancestor.
    A valid path has exactly this shape::

        Home Person -> parent -> ... -> common ancestor
        common ancestor -> child -> ... -> relative

    Either part may have length 0.  This covers direct ancestors, direct
    descendants and collateral relatives such as siblings and cousins.

    The calculation uses one multi-source downward traversal from all
    biological ancestors of Home.  This keeps the result identical to the
    previous common-ancestor definition while avoiding repeated scans of the
    same descendant branches.

    ``degrees`` stores the minimum number of biological parent/child steps in
    any valid common-ancestor path.  ``generations`` stores the relative
    generation level for the selected shortest path.
    """
    if db is None or not db.is_open():
        return {}, {}, None

    home_handle = db.get_default_handle()
    if not home_handle or not db.has_person_handle(home_handle):
        return {}, {}, None

    home = db.get_person_from_handle(home_handle)
    if home is None:
        return {}, {}, None

    parents, children = _biological_relations(db)
    degrees, generations = calculate_kinship_from_relations(
        home_handle, parents, children
    )

    return degrees, generations, home_handle


def _kinship_sort_key(data, degrees, generations=None):
    """Return a stable kinship sort key.

    Related people sort first by degree.  When ``generations`` is supplied,
    ties are split by generation level with ancestors first, then the same
    generation, then descendants.  Remaining ties are alphabetical.

    People with no established relationship follow relatives in ascending
    order. Gramps reverses the entire order for descending sorts.
    """
    sorted_name = name_displayer.raw_sorted_name(data.primary_name)
    degree = degrees.get(data.handle)

    if degree is None:
        return "1\x1f" + sorted_name

    if generations is None:
        return f"0\x1f{degree:012d}\x1f{sorted_name}"

    generation = generations.get(data.handle, 0)

    # At a fixed degree, valid generation levels run from +degree down to
    # -degree.  ``degree - generation`` therefore gives 0, 2, 4... for the
    # desired order: ancestors -> same generation -> descendants.
    generation_rank = degree - generation

    return (
        f"0\x1f{degree:012d}\x1f{generation_rank:012d}\x1f{sorted_name}"
    )


class KinshipColumnsMixin:
    """Add the calculated kinship column to a standard People model."""

    def _init_kinship(self, db):
        (
            self.kinship_degrees,
            self.generation_levels,
            self.home_handle,
        ) = calculate_kinship_info(db)

    def _extend_people_columns(self):
        self.fmap.insert(KINSHIP_COL, self.column_kinship_degree)
        self.smap.insert(KINSHIP_COL, self.sort_kinship_degree)

    def color_column(self):
        return TAG_COLOR_COL

    def column_kinship_degree(self, data):
        degree = self.kinship_degrees.get(data.handle)
        return "" if degree is None else str(degree)

    def sort_kinship_degree(self, data):
        return _kinship_sort_key(
            data, self.kinship_degrees, self.generation_levels
        )


class KinshipPersonListModel(KinshipColumnsMixin, PeopleBaseModel, FlatBaseModel):
    """Flat People model with calculated kinship degree."""

    def __init__(
        self,
        db,
        uistate,
        scol=0,
        order=Gtk.SortType.ASCENDING,
        search=None,
        skip=set(),
        sort_map=None,
    ):
        PeopleBaseModel.__init__(self, db)
        self._init_kinship(db)
        self._extend_people_columns()

        FlatBaseModel.__init__(
            self,
            db,
            uistate,
            scol=scol,
            order=order,
            search=search,
            skip=skip,
            sort_map=sort_map,
        )

    def destroy(self):
        self.kinship_degrees = None
        self.generation_levels = None
        self.home_handle = None
        PeopleBaseModel.destroy(self)
        FlatBaseModel.destroy(self)


class KinshipPersonTreeModel(KinshipColumnsMixin, PeopleBaseModel, TreeBaseModel):
    """Surname-grouped People model ordered by nearest related group member."""

    def __init__(
        self,
        db,
        uistate,
        scol=0,
        order=Gtk.SortType.ASCENDING,
        search=None,
        skip=set(),
        sort_map=None,
    ):
        PeopleBaseModel.__init__(self, db)
        self._init_kinship(db)
        self._extend_people_columns()
        self.group_degrees = {}

        TreeBaseModel.__init__(
            self,
            db,
            uistate,
            search=search,
            skip=skip,
            scol=scol,
            order=order,
            sort_map=sort_map,
        )

    def _set_base_data(self):
        # PeopleBaseModel already set gen_cursor, map, fmap and smap.
        self.number_items = self.db.get_number_of_people

    def rebuild_data(self, data_filter=None, data_filter2=None, skip=[]):
        """Refresh surname-group degrees before rebuilding the tree."""
        self.group_degrees = self._calculate_group_degrees(self.db)
        return TreeBaseModel.rebuild_data(
            self, data_filter=data_filter, data_filter2=data_filter2, skip=skip
        )

    def _calculate_group_degrees(self, db):
        """Return the lowest kinship degree present in each surname group."""
        group_degrees = {}
        ngn = name_displayer.name_grouping_data

        # During Gramps startup a view can be created before a genealogy
        # database is open.  In that state get_person_cursor() can return an
        # empty list rather than a cursor/context manager.
        if db is None or not db.is_open():
            return group_degrees

        cursor_obj = db.get_person_cursor()

        def consume(cursor):
            for handle, data in cursor:
                group_name = ngn(db, data.primary_name)
                degree = self.kinship_degrees.get(handle)
                if degree is None:
                    continue

                old_degree = group_degrees.get(group_name)
                if old_degree is None or degree < old_degree:
                    group_degrees[group_name] = degree

        # Depending on database/startup state Gramps may return either a
        # cursor context manager or a plain iterable.  Support both.
        if hasattr(cursor_obj, "__enter__") and hasattr(cursor_obj, "__exit__"):
            with cursor_obj as cursor:
                consume(cursor)
        else:
            consume(cursor_obj)

        return group_degrees

    def _group_sort_key(self, group_name):
        """Return the group key for the currently selected sort column.

        When sorting by kinship, surname groups are ordered by the nearest
        related person in the group and then alphabetically.  For every other
        selected column the groups themselves stay in normal alphabetical
        surname order, while people inside each group are sorted by the clicked
        column.
        """
        alpha = group_name or NO_SURNAME

        if self.sort_col != KINSHIP_COL:
            return alpha

        degree = self.group_degrees.get(group_name)

        # TreeBaseModel.Node applies locale collation to this string.
        # Zero-padding preserves numeric degree order.
        if degree is None:
            return "1\x1f" + alpha
        return f"0\x1f{degree:012d}\x1f{alpha}"

    def get_tree_levels(self):
        return [_('Group As'), _('Name')]

    def column_header(self, node):
        # Group nodes use a hidden kinship-aware sort key as node.name.
        # The original surname group is stored in node.ref and is what should
        # be shown to the user.
        return node.ref if node.ref else NO_SURNAME

    def sort_kinship_degree(self, data):
        """Keep grouped surname rows sorted by degree, then alphabetically."""
        return _kinship_sort_key(data, self.kinship_degrees)

    def add_row(self, handle, data):
        """Add a person under a surname group with kinship-aware ordering."""
        ngn = name_displayer.name_grouping_data
        group_name = ngn(self.db, data.primary_name)

        if group_name not in self.tree:
            self.add_node(
                None,
                group_name,
                self._group_sort_key(group_name),
                None,
                add_parent=False,
            )

        self.add_node(
            group_name,
            handle,
            self.sort_func(data),
            handle,
            add_parent=False,
        )

    def destroy(self):
        self.kinship_degrees = None
        self.generation_levels = None
        self.group_degrees = None
        self.home_handle = None
        PeopleBaseModel.destroy(self)
        self.number_items = None
        TreeBaseModel.destroy(self)


class KinshipBaseView(BasePersonView):
    """Shared UI definition for both kinship People views."""

    COL_KINSHIP = KINSHIP_COL
    _COLUMN_CONFIG_VERSION = 1
    _KINSHIP_DEFAULT_WIDTH = 110

    COLUMNS = BasePersonView.COLUMNS[:] + [
        (_("Kinship degree"), TEXT, None),
    ]

    _BASE_RANK = [
        BasePersonView.COL_NAME,
        BasePersonView.COL_ID,
        BasePersonView.COL_GEN,
        BasePersonView.COL_BDAT,
        BasePersonView.COL_BPLAC,
        BasePersonView.COL_DDAT,
        BasePersonView.COL_DPLAC,
        BasePersonView.COL_SPOUSE,
        BasePersonView.COL_PARENTS,
        BasePersonView.COL_MARRIAGES,
        BasePersonView.COL_CHILDREN,
        BasePersonView.COL_TODO,
        BasePersonView.COL_PRIV,
        BasePersonView.COL_TAGS,
        BasePersonView.COL_CHAN,
    ]

    # "Name" stays first by default, while the calculated column is second.
    # The configuration dialog can later move or hide the kinship column.
    _DEFAULT_RANK = [BasePersonView.COL_NAME, COL_KINSHIP] + [
        col for col in _BASE_RANK if col != BasePersonView.COL_NAME
    ]

    _BASE_WIDTH_BY_COL = {
        col: width
        for col, width in zip(
            _BASE_RANK,
            [250, 75, 75, 100, 175, 100, 175, 100, 30, 30, 30, 30, 30, 100, 100],
        )
    }
    # Do not use a comprehension here.  Comprehensions executed in a class
    # body have their own scope and therefore cannot see class attributes such
    # as COL_KINSHIP or _KINSHIP_DEFAULT_WIDTH.
    _DEFAULT_SIZES = []
    for _col in _DEFAULT_RANK:
        if _col == COL_KINSHIP:
            _DEFAULT_SIZES.append(_KINSHIP_DEFAULT_WIDTH)
        else:
            _DEFAULT_SIZES.append(_BASE_WIDTH_BY_COL[_col])
    del _col

    CONFIGSETTINGS = (
        (
            "columns.visible",
            [
                BasePersonView.COL_NAME,
                COL_KINSHIP,
                BasePersonView.COL_ID,
                BasePersonView.COL_GEN,
                BasePersonView.COL_BDAT,
                BasePersonView.COL_DDAT,
            ],
        ),
        ("columns.rank", _DEFAULT_RANK),
        ("columns.size", _DEFAULT_SIZES),
        ("kinship.column-config-version", 0),
    )

    def _ensure_kinship_column_config(self):
        """Migrate older addon settings to a real configurable column.

        Versions 0.1.x/0.2.0/0.2.1 may have left a 15-column configuration
        behind.  Gramps' ColumnOrder dialog builds its rows from
        ``columns.rank`` and ``columns.size``, so the calculated column must be
        present in those settings, not only in ``COLUMNS``.
        """
        cfg = self._config
        version = cfg.get("kinship.column-config-version")
        rank = list(cfg.get("columns.rank") or [])
        sizes = list(cfg.get("columns.size") or [])
        visible = list(cfg.get("columns.visible") or [])

        # Preserve existing widths by model-column id wherever possible.
        size_by_col = {}
        for col, width in zip(rank, sizes):
            if isinstance(col, int) and 0 <= col <= self.COL_KINSHIP:
                size_by_col[col] = width

        # Keep each known model column exactly once.
        clean_rank = []
        for col in rank:
            if (
                isinstance(col, int)
                and 0 <= col <= self.COL_KINSHIP
                and col not in clean_rank
            ):
                clean_rank.append(col)
        for col in range(self.COL_KINSHIP + 1):
            if col not in clean_rank:
                clean_rank.append(col)

        if version < self._COLUMN_CONFIG_VERSION:
            # First migration: make Name first and kinship second.  Afterwards
            # the user's own order is preserved across restarts.
            clean_rank = [
                BasePersonView.COL_NAME,
                self.COL_KINSHIP,
            ] + [
                col
                for col in clean_rank
                if col not in (BasePersonView.COL_NAME, self.COL_KINSHIP)
            ]
            if BasePersonView.COL_NAME not in visible:
                visible.insert(0, BasePersonView.COL_NAME)
            if self.COL_KINSHIP not in visible:
                # Visible by default on first migration.  If the user hides it
                # later, version==1 prevents us from turning it back on.
                insert_at = 1 if BasePersonView.COL_NAME in visible else 0
                visible.insert(insert_at, self.COL_KINSHIP)

        valid_visible = []
        for col in visible:
            if (
                isinstance(col, int)
                and col in clean_rank
                and col not in valid_visible
            ):
                valid_visible.append(col)

        clean_sizes = []
        for col in clean_rank:
            if col == self.COL_KINSHIP:
                clean_sizes.append(size_by_col.get(col, self._KINSHIP_DEFAULT_WIDTH))
            else:
                clean_sizes.append(
                    size_by_col.get(col, self._BASE_WIDTH_BY_COL.get(col, 100))
                )

        cfg.set("columns.rank", clean_rank)
        cfg.set("columns.size", clean_sizes)
        cfg.set("columns.visible", valid_visible)
        cfg.set("kinship.column-config-version", self._COLUMN_CONFIG_VERSION)
        cfg.save()

    def _set_initial_sort_to_kinship(self):
        """Use kinship as the initial sort when its column is visible.

        ``ListView.sort_col`` is the index among visible GUI columns, not the
        underlying model-column id.  The kinship column can be moved in the
        configuration dialog, so its current visible position has to be found
        dynamically.  Once the view is open, normal Gramps header clicks take
        over and the user can sort by any visible column.
        """
        visible_columns = [pair for pair in self.column_order() if pair[0]]
        for index, pair in enumerate(visible_columns):
            if pair[1] == self.COL_KINSHIP:
                self.sort_col = index
                self.sort_order = Gtk.SortType.ASCENDING
                return

        # If the user hid the kinship column, fall back to Gramps' normal
        # first-visible-column sort.
        self.sort_col = 0
        self.sort_order = Gtk.SortType.ASCENDING

    def _after_init(self):
        # A family deletion/rebuild can change the biological graph globally.
        self.callman.add_db_signal("family-delete", self.object_build)
        self.callman.add_db_signal("family-rebuild", self.object_build)

    def set_default_person(self, *obj):
        """Set Home Person and immediately recalculate kinship ordering."""
        super().set_default_person(*obj)
        self.dirty = True
        if self.active:
            self.build_tree()

    def set_active(self):
        """Recalculate if Home Person changed while this view was inactive."""
        current_home = (
            self.dbstate.db.get_default_handle() if self.dbstate.is_open() else None
        )
        if self.model is not None and self.model.home_handle != current_home:
            self.dirty = True

        super().set_active()

        if self.dirty:
            self.build_tree()

    # Kinship can change for many people after a person/family edit.  For this
    # first prototype correctness is preferred over incremental optimisation.
    def row_add(self, handle_list):
        self.object_build()

    def row_update(self, handle_list):
        self.object_build()

    def row_delete(self, handle_list):
        self.object_build()

    def related_update(self, handle_list):
        self.object_build()


class KinshipSortListView(KinshipBaseView):
    """Flat list of all people with user-selectable column sorting."""

    def __init__(self, pdata, dbstate, uistate, nav_group=0):
        BasePersonView.__init__(
            self,
            pdata,
            dbstate,
            uistate,
            _("People by kinship degree"),
            KinshipPersonListModel,
            nav_group=nav_group,
        )
        self._ensure_kinship_column_config()
        self._set_initial_sort_to_kinship()
        self._after_init()

    def get_config_name(self):
        return __name__ + ".flat"


class KinshipSortTreeView(KinshipBaseView):
    """Surname-grouped list with user-selectable column sorting."""

    def __init__(self, pdata, dbstate, uistate, nav_group=0):
        BasePersonView.__init__(
            self,
            pdata,
            dbstate,
            uistate,
            _("People by kinship, grouped"),
            KinshipPersonTreeModel,
            nav_group=nav_group,
        )
        self._ensure_kinship_column_config()
        self._set_initial_sort_to_kinship()
        self._after_init()

    def get_viewtype_stock(self):
        return "gramps-tree-group"

    def define_actions(self):
        BasePersonView.define_actions(self)
        self.action_list.extend(
            [
                ("OpenAllNodes", self.open_all_nodes),
                ("CloseAllNodes", self.close_all_nodes),
            ]
        )

    additional_ui = BasePersonView.additional_ui[:]
    additional_ui.append(
        """
      <section id="PopUpTree">
        <item>
          <attribute name="action">win.OpenAllNodes</attribute>
          <attribute name="label" translatable="yes">Expand all Nodes</attribute>
        </item>
        <item>
          <attribute name="action">win.CloseAllNodes</attribute>
          <attribute name="label" translatable="yes">Collapse all Nodes</attribute>
        </item>
      </section>
    """
    )

    def add(self, *obj):
        """Match the standard grouped People view when adding a person."""
        person = Person()
        model, pathlist = self.selection.get_selected_rows()
        name = Name()
        name.add_surname(Surname())
        name.set_primary_surname(0)
        basepers = None

        if len(pathlist) == 1:
            path = pathlist[0]
            pathids = path.get_indices()
            if len(pathids) == 1:
                path = Gtk.TreePath((pathids[0], 0))
            iter_ = model.get_iter(path)
            handle = model.get_handle_from_iter(iter_)
            if handle:
                basepers = self.dbstate.db.get_person_from_handle(handle)

        if basepers:
            preset_name(basepers, name)
        person.set_primary_name(name)

        try:
            EditPerson(self.dbstate, self.uistate, [], person)
        except WindowActiveError:
            pass

    def get_config_name(self):
        return __name__ + ".grouped"
