#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2007-2009  Douglas S. Blank <doug.blank@gmail.com>
# Copyright (C) 2011       Gary Burton
# Copyright (C) 2026       Brian McCullough
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

"""
Data Entry Gramplet: quick entry of people and their relatives.

The gramplet shows the active person in an editable block and a "New person"
block. The new person can be added to the tree on its own or as a parent,
spouse, sibling or child of the active person, together with up to four
events whose types are chosen from pop-up menus. A Source (by title) or an
existing Citation can be attached to everything that is created.
"""

# pylint: disable=too-many-lines
from __future__ import annotations

# ------------------------
# Python modules
# ------------------------
import contextlib
import logging
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

from gi.repository import GLib, Gtk, Pango

# ------------------------
# Gramps modules
# ------------------------
from gramps.gen.config import config as global_config
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.datehandler import get_date, parser
from gramps.gen.db import DbTxn
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.errors import ValidationError, WindowActiveError
from gramps.gen.lib import (
    ChildRef,
    Citation,
    Date,
    Event,
    EventRef,
    EventType,
    Family,
    FamilyRelType,
    Name,
    NameType,
    Person,
    Place,
    PlaceName,
    Source,
    Surname,
)
from gramps.gen.plug import Gramplet
from gramps.gen.utils.configmanager import ConfigManager
from gramps.gen.utils.db import get_birth_or_fallback, get_death_or_fallback
from gramps.gui import dialog as gramps_dialog
from gramps.gui import editors as gramps_editors
from gramps.gui import selectors as gramps_selectors

if TYPE_CHECKING:
    from gramps.gen.types import CitationHandle, PersonHandle

LOG = logging.getLogger(__name__)

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

# Must match id= in DataEntryGramplet.gpr.py. Written to the [meta] section
# of the .ini so the file identifies the addon it belongs to.
PLUGIN_ID = "Data Entry Gramplet"

# Bump if the keys below ever change shape (rename, type or meaning change),
# so a later version can tell an old-format .ini from a current one.
# 1: gramplet.event_type_1..4 held the bare EventType number.
# 2: gramplet.event_type_row1..4 hold "number:Name" (see event_type_token).
SCHEMA_VERSION = "2"

# Default types of the four event rows (used until the user picks others).
DEFAULT_EVENT_TYPES = (
    EventType.BIRTH,
    EventType.RESIDENCE,
    EventType.DEATH,
    EventType.BURIAL,
)

# .ini key for each event row's type menu (row numbers start at 1).
EVENT_TYPE_KEY = "gramplet.event_type_row%d"

# Space in pixels between the form and the left and right window edges.
FORM_MARGIN = 6


def event_type_token(value: int) -> str:
    """
    Return the string stored in the .ini for an event type.

    It is Gramps' number for the type plus its locale-independent name,
    e.g. ``"12:Birth"``.

    :param value: The EventType number.
    :returns: The ``number:Name`` token.
    """
    return f"{value}:{EventType(value).xml_str()}"


def parse_event_type_token(token: Any) -> int | None:
    """
    Return the EventType number for a stored ``number:Name`` token.

    The number AND the name must both match Gramps' current list of event
    types (that list can change between Gramps versions), otherwise the
    token is rejected.

    :param token: The value read from the .ini (normally a string).
    :returns: The EventType number, or ``None`` if the token is not valid.
    """
    try:
        number, name = token.split(":", 1)
        value = int(number)
    except (AttributeError, ValueError):
        return None
    if value in (EventType.UNKNOWN, EventType.CUSTOM):
        return None
    if value not in EventType().get_map():
        return None
    if EventType(value).xml_str() != name:
        return None
    return value


def _load_config() -> ConfigManager:
    """
    Register and load the addon's own .ini file.

    Gramps' ConfigManager puts it in this module's own folder
    (``use_plugins_path=False`` with no override), next to
    ``DataEntryGramplet.py``, and a ``[meta]`` block identifies the addon and
    the version of the .ini format.

    :returns: The registered ConfigManager.
    """
    config = global_config.register_manager("DataEntryGramplet", use_plugins_path=False)
    # ConfigManager writes any value equal to its registered default as a
    # ";;" comment line, so the [meta] keys are registered with "" defaults and
    # set below; that keeps them live (uncommented) in the file.
    config.register("meta.plugin_id", "")
    config.register("meta.schema_version", "")
    for number, default in enumerate(DEFAULT_EVENT_TYPES, 1):
        config.register(EVENT_TYPE_KEY % number, event_type_token(default))
    config.init()
    if (config.get("meta.plugin_id"), config.get("meta.schema_version")) != (
        PLUGIN_ID,
        SCHEMA_VERSION,
    ):
        # New file, or one from an older schema: migrate, then stamp it.
        # Schema 1 kept bare numbers under event_type_1..4 (unregistered keys
        # that ConfigManager keeps in its data dict, so remove them from there).
        for number in range(1, len(DEFAULT_EVENT_TYPES) + 1):
            old = config.data.get("gramplet", {}).pop(f"event_type_{number}", None)
            if isinstance(old, int) and parse_event_type_token(event_type_token(old)):
                config.set(EVENT_TYPE_KEY % number, event_type_token(old))
        config.set("meta.plugin_id", PLUGIN_ID)
        config.set("meta.schema_version", SCHEMA_VERSION)
        config.save()
    return config


CONFIG = _load_config()


@contextlib.contextmanager
def refusable_txn(txn: DbTxn) -> Iterator[DbTxn]:
    """
    Run a DbTxn like ``with txn:`` but let the body refuse to save anything.

    Raising :class:`~gramps.gen.errors.ValidationError` inside the body rolls
    the transaction back (DbTxn aborts on any exception) and shows the two
    arguments of the exception, a title and a message, in an error dialog.

    :param txn: The transaction to run.
    :returns: A context manager yielding the active transaction.
    """
    try:
        with txn as active_txn:
            yield active_txn
    except ValidationError as err:
        title = err.args[0] if err.args else ""
        body = err.args[1] if len(err.args) > 1 else ""
        gramps_dialog.ErrorDialog(title, body)


# ------------------------------------------------------------
#
# DataEntryGramplet
#
# ------------------------------------------------------------
# The Gramplet API builds the widgets in init() (not __init__) and hooks
# such as main() and db_changed() are called by the framework; the class is
# one form, so it has many widgets, attributes and callbacks:
# pylint: disable=attribute-defined-outside-init,too-many-instance-attributes
# pylint: disable=too-many-public-methods
class DataEntryGramplet(Gramplet):
    """
    Gramplet for quick entry of the active person and of new related people.
    """

    de_widgets: dict[str, Any]  # every widget of the form, by key
    trans: DbTxn  # the transaction of the Save / Add in progress
    show_source: bool
    _dirty_flag: bool
    _dirty_fields: list[str]
    _dirty_person: Person | None
    _dirty_family: Family | None
    _citation_handle: CitationHandle | None
    _event_choices: list[tuple[str, int]] | None
    _abandon_button: Gtk.Button
    _grid: Gtk.Grid
    _grid_row: int
    _field_group: Gtk.SizeGroup

    NO_REL = 0
    AS_PARENT = 1
    AS_MOTHER = 2
    AS_FATHER = 3
    AS_SPOUSE = 4
    AS_WIFE = 5
    AS_HUSBAND = 6
    AS_SIBLING = 7
    AS_CHILD = 8
    # Keys of the sourceable fields: each has an entry, a ":Label" and a
    # ":Citation" check button (see :meth:`make_source_field`).
    SOURCE_KEYS = [
        "NPSource",
        "NPEvent1Source",
        "NPEvent2Source",
        "NPEvent3Source",
        "NPEvent4Source",
        "APSource",
        "APBirthSource",
        "APDeathSource",
    ]
    # The four event rows of the New person section, each with a type menu.
    # The defaults are used until the user picks (then the picks persist).
    EVENT_PREFIXES = ("NPEvent1", "NPEvent2", "NPEvent3", "NPEvent4")
    EVENT_DEFAULTS = DEFAULT_EVENT_TYPES

    def init(self) -> None:  # pylint: disable=too-many-statements
        """
        Build the widgets (Gramplet API hook, called once by the framework).

        The whole form is ONE grid, so every row shares the same columns:
        labels and event menus, main field, "Source:" label, source field.
        The form scrolls in its own window while the Add / Copy / Clear
        buttons stay pinned to the bottom of the gramplet.
        """
        self._dirty = False
        self._dirty_person = None
        self._dirty_family = None
        self._citation_handle = None
        self.de_widgets = {}
        # The whole form is ONE grid so every row shares the same columns:
        #   0: labels / event-type menus   1: main field
        #   2: "Source:" label             3: source field
        # Columns 1 and 3 get the same width (size group), so the fields and
        # the "Source:" labels line up from row to row.
        self._grid = Gtk.Grid()
        self._grid.set_column_spacing(4)
        self._grid.set_row_spacing(4)
        # keep the fields (and the overlay scroll bar) off the window edges
        self._grid.set_margin_start(FORM_MARGIN)
        self._grid.set_margin_end(FORM_MARGIN)
        self._grid_row = 0
        self._field_group = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        # Row 1: Active person <name> [edit]            Family: [edit]
        self.make_row(
            "Active person",
            _("Active person"),
            None,
            True,
            [
                ("Edit person", "", "button", self.cb_edit_person),
                ("Edit family", _("Family:"), "button", self.cb_edit_family),
            ],
            False,
            0,
            None,
        )
        # Row 2:      ( ) Enter Sources  ( ) Select Citation  ( ) None [index]
        self.make_source_mode_row()
        genders = [_("female"), _("male"), _("unknown"), _("other")]
        self.make_row("APName", _("Surname, Given"), mark_dirty=True)
        self.make_row(
            "APGender",
            _("Gender"),
            genders,
            mark_dirty=True,
            default=2,
            source=(_("Source"), "APSource"),
        )
        self.make_row(
            "APBirth",
            _("Birth"),
            mark_dirty=True,
            source=(_("Source"), "APBirthSource"),
        )
        self.make_row(
            "APDeath",
            _("Death"),
            mark_dirty=True,
            source=(_("Source"), "APDeathSource"),
        )

        # Save and Abandon (a FlowBox, so they wrap when the window is narrow)
        button_bar, buttons = self.make_button_bar(
            [
                (_("Save"), self.cb_save_data_edit),
                (_("Abandon"), self.cb_abandon_data_edit),
            ]
        )
        self._abandon_button = buttons[1]
        self._init_dirty_style(self._abandon_button)
        self.attach_row(span_all=button_bar)

        self.make_row("New person", _("New person"), readonly=True)
        self.make_row(
            "NPRelation",
            _("Add relation"),
            [
                _("No relation to active person"),
                _("Add as a Parent"),
                _("Add as a Mother"),
                _("Add as a Father"),
                _("Add as a Spouse"),
                _("Add as a Wife"),
                _("Add as a Husband"),
                _("Add as a Sibling"),
                _("Add as a Child"),
            ],
        )
        self.make_row("NPName", _("Surname, Given"))
        self.make_row(
            "NPGender",
            _("Gender"),
            genders,
            default=2,
            source=(_("Source"), "NPSource"),
        )

        # Four event rows (default types: Birth, Residence, Death, Burial).
        # The type of each is chosen from a pop-up menu and remembered
        # between sessions (on_load / on_save).
        for prefix, default in zip(self.EVENT_PREFIXES, self.EVENT_DEFAULTS):
            self.make_event_row(prefix, default)

        # Layout: the form scrolls in its own ScrolledWindow while the Add /
        # Copy / Clear buttons stay pinned to the bottom of the gramplet.
        button_bar, buttons = self.make_button_bar(
            [
                (_("Add"), self.cb_add_data_entry),
                (_("Copy Active Data"), self.cb_copy_data_entry),
                (_("Clear"), self.cb_clear_data_entry),
            ]
        )
        button_bar.set_margin_start(FORM_MARGIN)
        button_bar.set_margin_end(FORM_MARGIN)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_shadow_type(Gtk.ShadowType.NONE)
        scroller.set_min_content_height(80)
        scroller.set_propagate_natural_height(True)
        scroller.add(self._grid)
        outer = Gtk.VBox()
        outer.pack_start(scroller, True, True, 0)
        outer.pack_start(Gtk.Separator(), False, False, 2)
        outer.pack_start(button_bar, False, False, 0)

        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(outer)
        outer.show_all()
        self.refresh_source_mode_widgets()
        self.cb_clear_data_entry(None)

    def main(self) -> None:
        """
        Fill the Active person block from the active person.

        Gramplet API hook, run by ``update()``. Nothing is refreshed while the
        user has unsaved edits in that block (the dirty flag is set).
        """
        # pylint: disable=too-many-statements
        if self._dirty:
            return
        self.de_widgets["Active person:Edit family"].hide()
        self.de_widgets["Active person:Edit family:Label"].hide()
        active_person = self.get_active_object("Person")
        self._dirty_person = active_person
        self._dirty_family = None
        if active_person:
            self.de_widgets["Active person:Edit person"].show()
            self.de_widgets["Active person:Edit family"].hide()
            self.de_widgets["Active person:Edit family:Label"].hide()
            # Fill in current person edits:
            name = name_displayer.display(active_person)
            self.de_widgets["Active person"].set_text(
                f"<i>{GLib.markup_escape_text(name)}</i> "
            )
            self.de_widgets["Active person"].set_use_markup(True)
            # Name:
            name_obj = active_person.get_primary_name()
            if name_obj:
                self.de_widgets["APName"].set_text(
                    f"{name_obj.get_surname()}, {name_obj.get_first_name()}"
                )
            self.de_widgets["APGender"].set_active(active_person.get_gender())  # gender
            # Birth:
            birth = get_birth_or_fallback(self.dbstate.db, active_person)
            birth_text = ""
            if birth:
                sdate = get_date(birth)
                birth_text += sdate + " "
                place_text = place_displayer.display_event(self.dbstate.db, birth)
                if place_text:
                    birth_text += _("in") + " " + place_text

            self.de_widgets["APBirth"].set_text(birth_text)
            # Death:
            death = get_death_or_fallback(self.dbstate.db, active_person)
            death_text = ""
            if death:
                sdate = get_date(death)
                death_text += sdate + " "
                place_text = place_displayer.display_event(self.dbstate.db, death)
                if place_text:
                    death_text += _("in") + " " + place_text
            self.de_widgets["APDeath"].set_text(death_text)
            family_list = active_person.get_family_handle_list()
            if len(family_list) > 0:
                self._dirty_family = self.dbstate.db.get_family_from_handle(
                    family_list[0]
                )
                self.de_widgets["Active person:Edit family"].show()
                self.de_widgets["Active person:Edit family:Label"].show()
            else:
                family_list = active_person.get_parent_family_handle_list()
                if len(family_list) > 0:
                    self._dirty_family = self.dbstate.db.get_family_from_handle(
                        family_list[0]
                    )
                    self.de_widgets["Active person:Edit family"].show()
                    self.de_widgets["Active person:Edit family:Label"].show()
            # lookup sources:
            self.de_widgets["APSource"].set_text(
                self.get_last_source_title(active_person)
            )
            self.de_widgets["APBirthSource"].set_text(self.get_last_source_title(birth))
            self.de_widgets["APDeathSource"].set_text(self.get_last_source_title(death))
            # "Use citation" is a one-shot action flag for the next Save,
            # not a persistent field value, so it does not survive a refresh:
            self.de_widgets["APSource:Citation"].set_active(False)
            self.de_widgets["APBirthSource:Citation"].set_active(False)
            self.de_widgets["APDeathSource:Citation"].set_active(False)
        else:
            self.clear_data_edit()
            self.de_widgets["Active person:Edit person"].hide()
            self.de_widgets["Active person:Edit family"].hide()
            self.de_widgets["Active person:Edit family:Label"].hide()
        self._dirty = False

    def make_button_bar(
        self, specs: list[tuple[str, Callable[..., None]]]
    ) -> tuple[Gtk.FlowBox, list[Gtk.Button]]:
        """
        Build a row of equal-width buttons that keeps to one line.

        Long labels are ellipsized (the full label is the tooltip) when the
        window gets narrow.

        :param specs: A list of ``(label, callback)`` tuples.
        :returns: The FlowBox and the list of its buttons.
        """
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_homogeneous(True)
        flow.set_min_children_per_line(len(specs))
        flow.set_max_children_per_line(len(specs))
        flow.set_column_spacing(4)
        flow.set_row_spacing(4)
        buttons = []
        for label, callback in specs:
            button = Gtk.Button(label=label)
            button.set_hexpand(True)
            button.set_tooltip_text(label)
            button.get_child().set_ellipsize(Pango.EllipsizeMode.END)
            button.connect("clicked", callback)
            flow.add(button)
            buttons.append(button)
        return flow, buttons

    def shrinkable(self, combo: Gtk.ComboBoxText) -> None:
        """
        Let a combo box shrink below the width of its longest item.

        The width it *requests* is capped so long menu items cannot widen its
        column; the combo still fills whatever space its column gets.

        :param combo: The combo box to adjust.
        """
        for cell in combo.get_cells():
            cell.set_property("ellipsize", Pango.EllipsizeMode.END)
            cell.set_property("max-width-chars", 6)

    def attach_row(
        self,
        first: Gtk.Widget | None = None,
        middle: Gtk.Widget | None = None,
        source_label: Gtk.Label | None = None,
        source_entry: Gtk.Entry | None = None,
        span_all: Gtk.Widget | None = None,
    ) -> None:
        """
        Add one row to the form grid.

        :param first: Column 0 (a label or an event type menu).
        :param middle: Column 1; it spans to the right edge unless there is a
            source field.
        :param source_label: Column 2, the "Source:" label.
        :param source_entry: Column 3, the source field. It always gets the
            same width as ``middle``.
        :param span_all: One widget across all four columns.
        """
        row = self._grid_row
        if span_all is not None:
            span_all.set_hexpand(True)
            self._grid.attach(span_all, 0, row, 4, 1)
        if first is not None:
            self._grid.attach(first, 0, row, 1, 1)
        if middle is not None:
            middle.set_hexpand(True)
            if source_entry is None:
                self._grid.attach(middle, 1, row, 3, 1)
            else:
                source_entry.set_hexpand(True)
                self._grid.attach(middle, 1, row, 1, 1)
                self._grid.attach(source_label, 2, row, 1, 1)
                self._grid.attach(source_entry, 3, row, 1, 1)
                # the two fields of a row always get the same width:
                self._field_group.add_widget(middle)
                self._field_group.add_widget(source_entry)
        self._grid_row += 1

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def make_row(  # pylint: disable=too-many-locals,too-many-statements
        self,
        pos: str,
        text: str,
        choices: list[str] | None = None,
        readonly: bool = False,
        callback_list: list[tuple[str, str, str, Callable[..., None]]] | None = None,
        mark_dirty: bool = False,
        default: int = 0,
        source: tuple[str, str] | None = None,
    ) -> None:
        """
        Create the widgets of one form row and add them to the grid.

        :param pos: Key under which the main widget is stored in ``de_widgets``.
        :param text: Row label.
        :param choices: Items of a pop-up menu; ``None`` makes a text entry.
        :param readonly: ``True`` for a section header (bold title, plus the
            name and edit buttons of ``callback_list``).
        :param callback_list: ``(key, label, kind, callback)`` edit buttons of
            a header row.
        :param mark_dirty: Whether editing the widgets marks the form dirty.
        :param default: Initially selected menu item.
        :param source: ``(label, key)`` of an optional Source field.
        """
        label = Gtk.Label()
        if readonly:
            # Section header: bold title in column 0; if there are edit
            # buttons, the name + buttons go across columns 1-3.
            label.set_text(f"<b>{GLib.markup_escape_text(text)}</b>")
            label.set_use_markup(True)
            label.set_alignment(0.0, 0.5)
            value = Gtk.Label()
            value.set_alignment(0.0, 0.5)
            value.set_use_markup(True)
            value.set_ellipsize(Pango.EllipsizeMode.END)
            self.de_widgets[pos] = value
            box = None
            if callback_list:
                box = Gtk.HBox()
                # the name keeps its natural width (ellipsized only when the
                # window is too narrow), so the edit icon sits right after it
                box.pack_start(value, False, False, 0)
                for index, (name, button_text, _kind, callback) in enumerate(
                    callback_list
                ):
                    if index == 1:
                        # the next control follows after a 4-space gap
                        box.pack_start(Gtk.Label(label="    "), False, False, 0)
                    if button_text:
                        text_label = Gtk.Label()
                        text_label.set_text(button_text)
                        self.de_widgets[pos + ":" + name + ":Label"] = text_label
                        box.pack_start(text_label, False, False, 0)
                    button = Gtk.Button()
                    image = Gtk.Image()
                    image.set_from_stock(Gtk.STOCK_EDIT, Gtk.IconSize.MENU)
                    button.add(image)
                    button.set_relief(Gtk.ReliefStyle.NONE)
                    button.connect("clicked", callback)
                    self.de_widgets[pos + ":" + name] = button
                    box.pack_start(button, False, False, 0)
            self.attach_row(first=label, middle=box)
            return
        label.set_text(f"{text}: ")
        label.set_alignment(1.0, 0.5)
        if choices is None:
            widget = Gtk.Entry()
            widget.set_width_chars(1)
        else:
            widget = Gtk.ComboBoxText()
            for add_type in choices:
                widget.append_text(add_type)
            self.shrinkable(widget)
            widget.set_active(default)
        self.de_widgets[pos] = widget
        if mark_dirty:
            widget.connect("changed", self.cb_mark_dirty)
        source_label = source_field = None
        if source:
            source_label, source_field = self.make_source_field(
                source[0], source[1], mark_dirty=mark_dirty
            )
        self.attach_row(
            first=label,
            middle=widget,
            source_label=source_label,
            source_entry=source_field,
        )

    def make_source_field(
        self, label_text: str, key: str, mark_dirty: bool = False
    ) -> tuple[Gtk.Label, Gtk.Widget]:
        """
        Build the "Source:" label and the field that occupies its column.

        The field is a wrapper holding a plain text entry (used in Enter
        Sources mode) and a "Use citation" check button (used in Select
        Citation mode); :meth:`refresh_source_mode_widgets` shows exactly
        one of the two, or neither in None mode. The entry is stored in
        ``de_widgets`` under ``key`` (as before, so ``.get_text()`` /
        ``.set_text()`` call sites keep working) and the check button under
        ``key + ":Citation"``.

        :param label_text: Text of the "Source:" label (always "Source" today).
        :param key: Key under which the entry is stored in ``de_widgets``.
        :param mark_dirty: Whether editing either widget marks the form dirty.
        :returns: The label and the wrapper widget to attach in its place.
        """
        label = Gtk.Label()
        label.set_text(f"{label_text}: ")
        label.set_alignment(1.0, 0.5)
        entry = Gtk.Entry()
        entry.set_width_chars(1)
        self.de_widgets[key + ":Label"] = label
        self.de_widgets[key] = entry
        checkbox = Gtk.CheckButton(label=_("Use citation"))
        checkbox.set_active(False)
        self.de_widgets[key + ":Citation"] = checkbox
        if mark_dirty:
            entry.connect("changed", self.cb_mark_dirty)
            checkbox.connect("toggled", self.cb_mark_dirty)
        wrapper = Gtk.HBox()
        wrapper.pack_start(entry, True, True, 0)
        wrapper.pack_start(checkbox, True, True, 0)
        return label, wrapper

    def make_source_mode_row(self) -> None:
        """
        Add the "( ) Enter Sources  ( ) Select Citation  ( ) None" row, plus a
        second row below it showing the citation chosen in Select Citation
        mode.

        The three options are a radio group, so exactly one is selected at a
        time; selecting one always deselects the others. Selecting Select
        Citation opens the Citation selector (see :meth:`cb_toggle_citation`).
        Selecting None sources nothing: no Source field is used and no
        citation is attached. None needs no callback of its own — selecting
        it deselects whichever of the other two was active, and their own
        ``toggled`` handlers already hide the Source fields and forget a
        chosen citation when that happens.
        """
        sources = Gtk.RadioButton.new_with_label(None, _("Enter Sources"))
        sources.set_active(True)
        sources.connect("toggled", self.cb_toggle_sources)
        self.de_widgets["Active person:Show sources"] = sources
        citation = Gtk.RadioButton.new_with_label_from_widget(
            sources, _("Select Citation")
        )
        citation.connect("toggled", self.cb_toggle_citation)
        self.de_widgets["Active person:Show citation"] = citation
        none = Gtk.RadioButton.new_with_label_from_widget(sources, _("None"))
        self.de_widgets["Active person:Show none"] = none
        row = Gtk.HBox()
        row.pack_start(sources, False, False, 0)
        row.pack_start(Gtk.Label(label="    "), False, False, 0)  # 4 spaces
        row.pack_start(citation, False, False, 0)
        row.pack_start(Gtk.Label(label="    "), False, False, 0)  # 4 spaces
        row.pack_start(none, False, False, 0)
        self.attach_row(middle=row)

        info = Gtk.Label()
        info.set_alignment(0.0, 0.5)
        info.set_margin_start(6)
        info.set_ellipsize(Pango.EllipsizeMode.END)
        self.de_widgets["Citation:Info"] = info
        self.attach_row(middle=info)

    def make_event_row(self, prefix: str, default_type: int) -> None:
        """
        Add one event row: ``[type menu] [date in place]  Source: [...]``.

        The widgets are stored in ``de_widgets`` as ``prefix + "Type"``,
        ``prefix`` and ``prefix + "Source"`` (+ ``":Label"``).

        :param prefix: Key prefix of the row, one of ``EVENT_PREFIXES``.
        :param default_type: EventType number selected until the user picks.
        """
        combo = Gtk.ComboBoxText()
        for name, _value in self.event_type_choices():
            combo.append_text(name)
        self.shrinkable(combo)
        self.de_widgets[prefix + "Type"] = combo
        self.select_event_type(prefix, default_type)
        entry = Gtk.Entry()
        entry.set_width_chars(1)
        self.de_widgets[prefix] = entry
        label, source_field = self.make_source_field(_("Source"), prefix + "Source")
        self.attach_row(
            first=combo, middle=entry, source_label=label, source_entry=source_field
        )

    def event_type_choices(self) -> list[tuple[str, int]]:
        """
        Return the event types offered by the type menus.

        :returns: A list of ``(translated name, EventType number)`` sorted by
            name; Unknown and Custom are left out.
        """
        choices: list[tuple[str, int]] | None = getattr(self, "_event_choices", None)
        if choices is None:
            skip = (EventType.UNKNOWN, EventType.CUSTOM)
            choices = [
                (str(EventType(value)), value)
                for value in EventType().get_map()
                if value not in skip
            ]
            choices.sort(key=lambda item: item[0].lower())
            self._event_choices = choices
        return choices

    def select_event_type(self, prefix: str, value: int) -> None:
        """
        Select an event type in the menu of an event row.

        :param prefix: Key prefix of the event row.
        :param value: EventType number; ignored if the menu does not offer it.
        """
        for index, (_name, choice) in enumerate(self.event_type_choices()):
            if choice == value:
                self.de_widgets[prefix + "Type"].set_active(index)
                return

    def selected_event_type(self, prefix: str) -> int:
        """
        Return the event type selected in the menu of an event row.

        :param prefix: Key prefix of the event row.
        :returns: The EventType number (Unknown if nothing is selected).
        """
        index = self.de_widgets[prefix + "Type"].get_active()
        choices = self.event_type_choices()
        if 0 <= index < len(choices):
            return choices[index][1]
        return EventType.UNKNOWN

    def event_row_for_type(self, value: int) -> str | None:
        """
        Find the first event row whose menu is set to a given type.

        :param value: EventType number.
        :returns: The row's key prefix, or ``None`` if no row has that type.
        """
        for prefix in self.EVENT_PREFIXES:
            if self.selected_event_type(prefix) == value:
                return prefix
        return None

    def on_load(self) -> None:
        """
        Restore the event types saved in ``DataEntryGramplet.ini``.

        A row whose stored ``number:Name`` no longer matches Gramps' list of
        event types (or is unreadable) falls back to that row's default.
        """
        for number, prefix in enumerate(self.EVENT_PREFIXES, 1):
            value = parse_event_type_token(CONFIG.get(EVENT_TYPE_KEY % number))
            if value is None:
                LOG.warning(
                    "%s: ignoring invalid %s; using the default",
                    CONFIG.filename,
                    EVENT_TYPE_KEY % number,
                )
                value = self.EVENT_DEFAULTS[number - 1]
            self.select_event_type(prefix, value)
        # Connect only now, so restoring does not trigger saves:
        for prefix in self.EVENT_PREFIXES:
            self.de_widgets[prefix + "Type"].connect(
                "changed", self.cb_event_type_changed
            )

    def save_event_types(self) -> None:
        """
        Write the four menu choices to ``DataEntryGramplet.ini``.
        """
        for number, prefix in enumerate(self.EVENT_PREFIXES, 1):
            CONFIG.set(
                EVENT_TYPE_KEY % number,
                event_type_token(self.selected_event_type(prefix)),
            )
        CONFIG.save()

    def cb_event_type_changed(self, _combo: Gtk.ComboBoxText) -> None:
        """
        Save the event types as soon as one of the menus changes.

        :param _combo: The menu that changed (unused).
        """
        self.save_event_types()

    def on_save(self) -> None:
        """
        Save the event types (Gramplet API hook, called when the view closes).
        """
        self.gui.data = []  # drop anything an older version kept there
        self.save_event_types()

    # --- dirty-state flag -------------------------------------------------
    # _dirty is a property so that every existing "self._dirty = ..."
    # assignment also refreshes the Abandon button (red + tooltip).
    @property
    def _dirty(self) -> bool:
        """Whether the Active person block has unsaved edits."""
        return getattr(self, "_dirty_flag", False)

    @_dirty.setter
    def _dirty(self, value: bool) -> None:
        """
        Set or clear the dirty flag and refresh the Abandon button.

        :param value: The new state; clearing it also forgets which fields
            were edited.
        """
        self._dirty_flag = bool(value)
        if not self._dirty_flag:
            self._dirty_fields = []
        self._refresh_dirty_style()

    def _init_dirty_style(self, button: Gtk.Button) -> None:
        """
        Attach a CSS provider so the ``de-dirty`` class turns the button red.

        :param button: The Abandon button.
        """

        provider = Gtk.CssProvider()
        provider.load_from_data(
            b"button.de-dirty { background-image: none;"
            b" background-color: #c01c28; color: #ffffff; }"
        )
        button.get_style_context().add_provider(
            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        button.set_tooltip_text(_("Nothing to abandon."))

    def _dirty_label(self, key: str) -> str:
        """
        Return the user-visible name of an Active person field.

        :param key: Key of the widget in ``de_widgets``.
        :returns: The translated field name (the key itself if unknown).
        """
        labels = {
            "APName": _("Name"),
            "APGender": _("Gender"),
            "APBirth": _("Birth"),
            "APDeath": _("Death"),
            "APSource": _("Person source"),
            "APBirthSource": _("Birth source"),
            "APDeathSource": _("Death source"),
        }
        return labels.get(key, key)

    def _dirty_tooltip(self) -> str:
        """
        Return the Abandon button's tooltip: what is unsaved, and whose it is.
        """
        fields = ", ".join(
            self._dirty_label(key) for key in getattr(self, "_dirty_fields", [])
        )
        text = _("Unsaved changes: %s") % (fields or _("(unknown)"))
        person = getattr(self, "_dirty_person", None)
        if person:
            text += "\n" + _("Person being edited: %s") % name_displayer.display(person)
        return text + "\n" + _("Click to discard them and reload.")

    def _refresh_dirty_style(self) -> None:
        """
        Make the Abandon button red (with a tooltip) while the form is dirty.
        """
        button = getattr(self, "_abandon_button", None)
        if button is None:
            return
        context = button.get_style_context()
        if self._dirty:
            context.add_class("de-dirty")
            button.set_tooltip_text(self._dirty_tooltip())
        else:
            context.remove_class("de-dirty")
            button.set_tooltip_text(_("Nothing to abandon."))

    def cb_mark_dirty(self, obj: Gtk.Widget) -> None:
        """
        Note that the user changed an Active person field.

        :param obj: The widget that changed.
        """
        fields = getattr(self, "_dirty_fields", [])
        for key, widget in self.de_widgets.items():
            if widget is obj and key not in fields:
                fields.append(key)
                break
        self._dirty_fields = fields
        self._dirty = True

    def cb_abandon_data_edit(self, _obj: Gtk.Button | None = None) -> None:
        """
        Discard the unsaved edits and reload the Active person block.

        :param _obj: The button that was clicked (unused).
        """
        self._dirty = False
        self.update()

    def cb_edit_done(self, _person: Person) -> None:
        """
        Reload after the person editor was closed.

        :param _person: The edited person (unused).
        """
        self._dirty = False
        self.update()

    def cb_edit_person(self, _obj: Gtk.Button | None = None) -> None:
        """
        Open the Edit Person dialog for the active person.

        :param _obj: The button that was clicked (unused).
        """
        if not self._dirty_person:
            return
        try:
            gramps_editors.EditPerson(
                self.gui.dbstate,
                self.gui.uistate,
                [],
                self._dirty_person,
                callback=self.cb_edit_done,
            )
        except WindowActiveError:
            pass

    def cb_edit_family(self, _obj: Gtk.Button | None = None) -> None:
        """
        Open the Edit Family dialog for the active person's family.

        :param _obj: The button that was clicked (unused).
        """
        if not self._dirty_family:
            return
        try:
            gramps_editors.EditFamily(
                self.gui.dbstate, self.gui.uistate, [], self._dirty_family
            )
        except WindowActiveError:
            pass

    def process_dateplace(self, text: str) -> tuple[Date | None, Place | None]:
        """
        Split ``date in place`` text, parse the date and find or create the place.

        :param text: What the user typed, e.g. ``1855-06-21 in Great Falls``.
        :returns: A ``(Date, Place)`` tuple; either may be ``None``.
        """
        if text == "":
            return None, None
        prep_in = _("in")  # word or phrase that separates date from place
        text = text.strip()
        date_text, place_text = text, ""
        if f" {prep_in} " in text:
            date_text, place_text = text.split(f" {prep_in} ", 1)
        elif text.startswith(f"{prep_in} "):
            date_text, place_text = text.split(f"{prep_in} ", 1)
        date = parser.parse(date_text.strip()) if date_text.strip() else None
        place = None
        if place_text.strip():
            place = self.get_or_create_place(place_text.strip())[1]
        return date, place

    def get_or_create_place(self, place_name: str) -> tuple[int, Place | None]:
        """
        Find a place by its displayed title, or create it.

        :param place_name: The place title.
        :returns: ``(-1, None)`` for an empty name, ``(0, place)`` if found,
            ``(1, place)`` if created.
        """
        if place_name == "":
            return (-1, None)
        place_list = self.dbstate.db.get_place_handles()
        for place_handle in place_list:
            place = self.dbstate.db.get_place_from_handle(place_handle)
            place_title = place_displayer.display(self.dbstate.db, place)
            if place_title.strip() == place_name:
                return (0, place)  # (old, object)
        place = Place()
        place.set_title(place_name)
        place.set_name(PlaceName(value=place_name))
        self.dbstate.db.add_place(place, self.trans)
        return (1, place)  # (new, object)

    def get_or_create_event(
        self, obj: Person, event_type: int, date: Date | None, place: Place | None
    ) -> tuple[int, Event | None]:
        """
        Update the person's event of a type, or create one.

        :param obj: The person.
        :param event_type: EventType number.
        :param date: The date to set, or ``None``.
        :param place: The place to set, or ``None``.
        :returns: ``(-1, None)`` if there is nothing to store, ``(0, event)``
            if an existing event was updated, ``(1, event)`` if created.
        """
        if date is None and place is None:
            return (-1, None)
        # first, see if it exists
        ref_list = obj.get_event_ref_list()
        # look for a match, and possible correction
        for ref in ref_list:
            event = self.dbstate.db.get_event_from_handle(ref.ref)
            if event is not None:
                if int(event.get_type()) == event_type:
                    # Match! Let's update
                    if date:
                        event.set_date_object(date)
                    if place:
                        event.set_place_handle(place.get_handle())
                    self.dbstate.db.commit_event(event, self.trans)
                    return (0, event)
        # else create it:
        event = Event()
        if event_type:
            event.set_type(EventType(event_type))
        if date:
            event.set_date_object(date)
        if place:
            event.set_place_handle(place.get_handle())
        self.dbstate.db.add_event(event, self.trans)
        return (1, event)

    def get_or_create_source(self, source_text: str) -> tuple[int, Source]:
        """
        Find a source by its title, or create it.

        :param source_text: The source title.
        :returns: ``(0, source)`` if found, ``(1, source)`` if created.
        """
        source_list = self.dbstate.db.get_source_handles()
        for source_handle in source_list:
            source = self.dbstate.db.get_source_from_handle(source_handle)
            if source.get_title() == source_text:
                return (0, source)
        source = Source()
        source.set_title(source_text)
        self.dbstate.db.add_source(source, self.trans)
        return (1, source)

    def get_last_source_title(self, obj: Person | Event | None) -> str:
        """
        Return the title of the source of the object's last citation.

        :param obj: A person or event, or ``None``.
        :returns: The source title, or an empty string.
        """
        if obj:
            citation_list = obj.get_citation_list()
            if len(citation_list) > 0:
                citation_handle = citation_list[-1]
                citation = self.dbstate.db.get_citation_from_handle(citation_handle)
                if citation:
                    source = self.dbstate.db.get_source_from_handle(
                        citation.get_reference_handle()
                    )
                    if source:
                        return source.get_title()
        return ""

    def make_event(
        self, event_type: int, date: Date | None, place: Place | None
    ) -> Event | None:
        """
        Create and add an event to the database.

        :param event_type: EventType number.
        :param date: The date, or ``None``.
        :param place: The place, or ``None``.
        :returns: The new event, or ``None`` if both date and place are empty.
        """
        if date is None and place is None:
            return None
        event = Event()
        event.set_type(EventType(event_type))
        if date:
            event.set_date_object(date)
        if place:
            event.set_place_handle(place.get_handle())
        self.dbstate.db.add_event(event, self.trans)
        return event

    def make_person(self, firstname: str, surname: str, gender: int) -> Person:
        """
        Create a Person object (not yet added to the database).

        :param firstname: Given name.
        :param surname: Surname.
        :param gender: Person gender constant.
        :returns: The new person.
        """
        person = Person()
        name = Name()
        name.set_type(NameType(NameType.BIRTH))
        name.set_first_name(firstname)
        surname_obj = Surname()
        surname_obj.set_surname(surname)
        name.set_surname_list([surname_obj])
        name.set_primary_surname(0)
        person.set_primary_name(name)
        person.set_gender(gender)
        return person

    # pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
    def cb_save_data_edit(self, _obj: Gtk.Button | None = None) -> None:
        """
        Save the edits made in the Active person block.

        Does nothing if there are no unsaved edits.

        :param _obj: The button that was clicked (unused).
        """
        if self._dirty:
            if not self.dbstate.is_open():
                gramps_dialog.ErrorDialog(
                    _("No Family Tree is open."),
                    _("Please open a Family Tree to edit data."),
                )
                return
            # Save the edits ----------------------------------
            person = self._dirty_person
            # First, get the data:
            gender = self.de_widgets["APGender"].get_active()
            if "," in self.de_widgets["APName"].get_text():
                surname, firstname = self.de_widgets["APName"].get_text().split(",", 1)
            else:
                surname, firstname = self.de_widgets["APName"].get_text(), ""
            surname = surname.strip()
            firstname = firstname.strip()
            if person:
                name = person.get_primary_name()
            else:
                return
            # Now, edit it:
            with DbTxn(
                _("Gramplet Data Edit: %s") % name_displayer.display(person),
                self.dbstate.db,
            ) as self.trans:
                surname_obj = name.get_primary_surname()
                surname_obj.set_surname(surname)
                name.set_first_name(firstname)
                person.set_gender(gender)
                birthdate, birthplace = self.process_dateplace(
                    self.de_widgets["APBirth"].get_text().strip()
                )
                _new, birthevent = self.get_or_create_event(
                    person, EventType.BIRTH, birthdate, birthplace
                )
                # reference it, if need be:
                birthref = person.get_birth_ref()
                if birthevent:
                    if birthref is None:
                        # need new
                        birthref = EventRef()
                    birthref.set_reference_handle(birthevent.get_handle())
                    person.set_birth_ref(birthref)
                    # Only add if there is an event:
                    source_text = self.de_widgets["APBirthSource"].get_text().strip()
                    if (
                        source_text
                        and self.de_widgets["Active person:Show sources"].get_active()
                    ):
                        _new, source = self.get_or_create_source(source_text)
                        self.add_source(birthevent, source)
                        self.dbstate.db.commit_event(birthevent, self.trans)
                    if self.add_selected_citation(
                        birthevent, "APBirthSource:Citation"
                    ):
                        self.dbstate.db.commit_event(birthevent, self.trans)
                deathdate, deathplace = self.process_dateplace(
                    self.de_widgets["APDeath"].get_text().strip()
                )
                _new, deathevent = self.get_or_create_event(
                    person, EventType.DEATH, deathdate, deathplace
                )
                # reference it, if need be:
                deathref = person.get_death_ref()
                if deathevent:
                    if deathref is None:
                        # need new
                        deathref = EventRef()
                    deathref.set_reference_handle(deathevent.get_handle())
                    person.set_death_ref(deathref)
                    # Only add if there is an event:
                    source_text = self.de_widgets["APDeathSource"].get_text().strip()
                    if (
                        source_text
                        and self.de_widgets["Active person:Show sources"].get_active()
                    ):
                        _new, source = self.get_or_create_source(source_text)
                        self.add_source(deathevent, source)
                        self.dbstate.db.commit_event(deathevent, self.trans)
                    if self.add_selected_citation(
                        deathevent, "APDeathSource:Citation"
                    ):
                        self.dbstate.db.commit_event(deathevent, self.trans)
                source_text = self.de_widgets["APSource"].get_text().strip()
                if (
                    source_text
                    and self.de_widgets["Active person:Show sources"].get_active()
                ):
                    _new, source = self.get_or_create_source(source_text)
                    self.add_source(person, source)
                self.add_selected_citation(person, "APSource:Citation")
                self.dbstate.db.commit_person(person, self.trans)
        self._dirty = False
        self.update()

    def add_source(self, obj: Person | Event, source: Source) -> None:
        """
        Cite a source on an object, reusing an existing citation of it.

        :param obj: The person or event to cite it on.
        :param source: The source.
        """
        found = 0
        for handle in obj.get_citation_list():
            citation = self.dbstate.db.get_citation_from_handle(handle)
            if citation.get_reference_handle() == source.get_handle():
                found = 1
                break
        if not found:
            citation = Citation()
            citation.set_reference_handle(source.get_handle())
            self.dbstate.db.add_citation(citation, self.trans)
        obj.add_citation(citation.get_handle())

    def cb_add_data_entry(self, _obj: Gtk.Button | None = None) -> None:
        """
        Add the New person (and its events) to the tree.

        The person is added on its own or as the parent, spouse, sibling or
        child of the active person, depending on the "Add relation" menu.
        Everything is saved in one transaction; if a check fails inside it
        (for example both partners have the same gender) the transaction is
        rolled back, so nothing is left behind, and the error is shown.

        :param _obj: The button that was clicked (unused).
        """
        # The relation handling below is long-standing code that is kept as it is:
        # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        # pylint: disable=too-many-return-statements,too-many-nested-blocks
        # pylint: disable=no-else-return,no-else-break,no-else-raise
        if not self.dbstate.is_open():
            gramps_dialog.ErrorDialog(
                _("No Family Tree is open."),
                _("Please open a Family Tree before adding a person."),
            )
            return
        # First, get the data:
        if "," in self.de_widgets["NPName"].get_text():
            surname, firstname = self.de_widgets["NPName"].get_text().split(",", 1)
        else:
            surname, firstname = self.de_widgets["NPName"].get_text(), ""
        surname = surname.strip()
        firstname = firstname.strip()
        gender = self.de_widgets["NPGender"].get_active()
        current_person: Any  # validated per relation below, before any writes
        if self._dirty:
            current_person = self._dirty_person
        else:
            current_person = self.get_active_object("Person")
        # Pre-check to make sure everything is ok: -------------------------------------------
        if surname == "" and firstname == "":
            gramps_dialog.ErrorDialog(
                _("Please provide a name."), _("Can't add new person.")
            )
            return
        if self.de_widgets["NPRelation"].get_active() == self.NO_REL:
            # "No relation to active person"
            pass
        elif self.de_widgets["NPRelation"].get_active() == self.AS_PARENT:
            # "Add as a Parent"
            if current_person is None:
                gramps_dialog.ErrorDialog(
                    _("Please set an active person."),
                    _("Can't add new person as a parent."),
                )
                return
            elif gender == Person.UNKNOWN:  # unknown
                gramps_dialog.ErrorDialog(
                    _("Please set the new person's gender."),
                    _("Can't add new person as a parent."),
                )
                return
        elif self.de_widgets["NPRelation"].get_active() == self.AS_MOTHER:
            # "Add as a Mother"
            if current_person is None:
                gramps_dialog.ErrorDialog(
                    _("Please set an active person."),
                    _("Can't add new person as a mother."),
                )
                return
        elif self.de_widgets["NPRelation"].get_active() == self.AS_FATHER:
            # "Add as a Father"
            if current_person is None:
                gramps_dialog.ErrorDialog(
                    _("Please set an active person."),
                    _("Can't add new person as a father."),
                )
                return
        elif self.de_widgets["NPRelation"].get_active() == self.AS_SPOUSE:
            # "Add as a Spouse"
            if current_person is None:
                gramps_dialog.ErrorDialog(
                    _("Please set an active person."),
                    _("Can't add new person as a spouse."),
                )
                return
            elif (
                gender == Person.UNKNOWN
                and current_person.get_gender() == Person.UNKNOWN
            ):  # both genders unknown
                gramps_dialog.ErrorDialog(
                    _("Please set the new person's gender."),
                    _("Can't add new person as a spouse."),
                )
                return
        elif self.de_widgets["NPRelation"].get_active() == self.AS_WIFE:
            # "Add as a Wife"
            if current_person is None:
                gramps_dialog.ErrorDialog(
                    _("Please set an active person."),
                    _("Can't add new person as a wife."),
                )
                return
        elif self.de_widgets["NPRelation"].get_active() == self.AS_HUSBAND:
            # "Add as a Husband"
            if current_person is None:
                gramps_dialog.ErrorDialog(
                    _("Please set an active person."),
                    _("Can't add new person as a husband."),
                )
                return
        elif self.de_widgets["NPRelation"].get_active() == self.AS_SIBLING:
            # "Add as a Sibling"
            if current_person is None:
                gramps_dialog.ErrorDialog(
                    _("Please set an active person."),
                    _("Can't add new person as a sibling."),
                )
                return
        elif self.de_widgets["NPRelation"].get_active() == self.AS_CHILD:
            # "Add as a Child"
            if current_person is None:
                gramps_dialog.ErrorDialog(
                    _("Please set an active person."),
                    _("Can't add new person as a child."),
                )
                return
        # Start the transaction: ------------------------------------------------------------
        person = self.make_person(firstname, surname, gender)
        with refusable_txn(
            DbTxn(
                _("Gramplet Data Edit: %s") % name_displayer.display(person),
                self.dbstate.db,
            )
        ) as self.trans:
            # New person --------------------------------------------------
            # The four event rows; each type comes from its pop-up menu.
            # A Birth (Death) event becomes the person's birth (death)
            # reference - the first one only; all others are plain events.
            birth_designated = death_designated = False
            for prefix in self.EVENT_PREFIXES:
                ev_type = self.selected_event_type(prefix)
                ev_date, ev_place = self.process_dateplace(
                    self.de_widgets[prefix].get_text().strip()
                )
                event = self.make_event(ev_type, ev_date, ev_place)
                if not event:
                    continue  # Only add if there is an event
                source_text = self.de_widgets[prefix + "Source"].get_text().strip()
                if (
                    source_text
                    and self.de_widgets["Active person:Show sources"].get_active()
                ):
                    _new, source = self.get_or_create_source(source_text)
                    self.add_source(event, source)
                    self.dbstate.db.commit_event(event, self.trans)
                if self.add_selected_citation(event, prefix + "Source:Citation"):
                    self.dbstate.db.commit_event(event, self.trans)
                event_ref = EventRef()
                event_ref.set_reference_handle(event.get_handle())
                if ev_type == EventType.BIRTH and not birth_designated:
                    person.set_birth_ref(event_ref)
                    birth_designated = True
                elif ev_type == EventType.DEATH and not death_designated:
                    person.set_death_ref(event_ref)
                    death_designated = True
                else:
                    person.add_event_ref(event_ref)
            # Need to add here to get a handle:
            self.dbstate.db.add_person(person, self.trans)
            # All error checking done; just add relation:
            if self.de_widgets["NPRelation"].get_active() == self.NO_REL:
                # "No relation to active person"
                current_person = None
            elif self.de_widgets["NPRelation"].get_active() == self.AS_PARENT:
                # "Add as a Parent"
                # Go through current_person parent families
                added = False
                for family_handle in current_person.get_parent_family_handle_list():
                    family = self.dbstate.db.get_family_from_handle(family_handle)
                    if family:
                        # find one that person would fit as a parent
                        fam_husband_handle = family.get_father_handle()
                        fam_wife_handle = family.get_mother_handle()
                        # can we add person as wife?
                        if (
                            fam_wife_handle is None
                            and person.get_gender() == Person.FEMALE
                        ):
                            # add the person
                            family.set_mother_handle(person.get_handle())
                            family.set_relationship(FamilyRelType.MARRIED)
                            person.add_family_handle(family.get_handle())
                            added = True
                            break
                        elif (
                            fam_husband_handle is None
                            and person.get_gender() == Person.MALE
                        ):
                            # add the person
                            family.set_father_handle(person.get_handle())
                            family.set_relationship(FamilyRelType.MARRIED)
                            person.add_family_handle(family.get_handle())
                            added = True
                            break
                if added:
                    self.dbstate.db.commit_family(family, self.trans)
                else:
                    family = Family()
                    self.dbstate.db.add_family(family, self.trans)
                    if person.get_gender() == Person.MALE:
                        family.set_father_handle(person.get_handle())
                    elif person.get_gender() == Person.FEMALE:
                        family.set_mother_handle(person.get_handle())
                    family.set_relationship(FamilyRelType.MARRIED)
                    # add curent_person as child
                    childref = ChildRef()
                    childref.set_reference_handle(current_person.get_handle())
                    family.add_child_ref(childref)
                    current_person.add_parent_family_handle(family.get_handle())
                    # finalize
                    person.add_family_handle(family.get_handle())
                    self.dbstate.db.commit_family(family, self.trans)
            elif self.de_widgets["NPRelation"].get_active() == self.AS_MOTHER:
                # "Add as a Mother"
                # Go through current_person parent families
                added = False
                for family_handle in current_person.get_parent_family_handle_list():
                    family = self.dbstate.db.get_family_from_handle(family_handle)
                    if family:
                        fam_wife_handle = family.get_mother_handle()
                        # can we add person as mother?
                        if fam_wife_handle is None:
                            # add the person
                            family.set_mother_handle(person.get_handle())
                            family.set_relationship(FamilyRelType.MARRIED)
                            person.add_family_handle(family.get_handle())
                            added = True
                            break
                if added:
                    self.dbstate.db.commit_family(family, self.trans)
                else:
                    family = Family()
                    self.dbstate.db.add_family(family, self.trans)
                    family.set_mother_handle(person.get_handle())
                    family.set_relationship(FamilyRelType.MARRIED)
                    # add curent_person as child
                    childref = ChildRef()
                    childref.set_reference_handle(current_person.get_handle())
                    family.add_child_ref(childref)
                    current_person.add_parent_family_handle(family.get_handle())
                    # finalize
                    person.add_family_handle(family.get_handle())
                    self.dbstate.db.commit_family(family, self.trans)
            elif self.de_widgets["NPRelation"].get_active() == self.AS_FATHER:
                # "Add as a Father"
                # Go through current_person parent families
                added = False
                for family_handle in current_person.get_parent_family_handle_list():
                    family = self.dbstate.db.get_family_from_handle(family_handle)
                    if family:
                        fam_husband_handle = family.get_father_handle()
                        # can we add person as father?
                        if fam_husband_handle is None:
                            # add the person
                            family.set_father_handle(person.get_handle())
                            family.set_relationship(FamilyRelType.MARRIED)
                            person.add_family_handle(family.get_handle())
                            added = True
                            break
                if added:
                    self.dbstate.db.commit_family(family, self.trans)
                else:
                    family = Family()
                    self.dbstate.db.add_family(family, self.trans)
                    family.set_father_handle(person.get_handle())
                    family.set_relationship(FamilyRelType.MARRIED)
                    # add curent_person as child
                    childref = ChildRef()
                    childref.set_reference_handle(current_person.get_handle())
                    family.add_child_ref(childref)
                    current_person.add_parent_family_handle(family.get_handle())
                    # finalize
                    person.add_family_handle(family.get_handle())
                    self.dbstate.db.commit_family(family, self.trans)
            elif self.de_widgets["NPRelation"].get_active() == self.AS_SPOUSE:
                # "Add as a Spouse"
                added = False
                family = None
                for family_handle in current_person.get_family_handle_list():
                    family = self.dbstate.db.get_family_from_handle(family_handle)
                    if family:
                        fam_husband_handle = family.get_father_handle()
                        fam_wife_handle = family.get_mother_handle()
                        if current_person.get_handle() == fam_husband_handle:
                            # can we add person as wife?
                            if fam_wife_handle is None:
                                if person.get_gender() == Person.FEMALE:
                                    # add the person
                                    family.set_mother_handle(person.get_handle())
                                    family.set_relationship(FamilyRelType.MARRIED)
                                    person.add_family_handle(family.get_handle())
                                    added = True
                                    break
                                elif person.get_gender() == Person.UNKNOWN:
                                    family.set_mother_handle(person.get_handle())
                                    family.set_relationship(FamilyRelType.MARRIED)
                                    person.set_gender(Person.FEMALE)
                                    self.de_widgets["NPGender"].set_active(
                                        Person.FEMALE
                                    )
                                    person.add_family_handle(family.get_handle())
                                    added = True
                                    break
                        elif current_person.get_handle() == fam_wife_handle:
                            # can we add person as husband?
                            if fam_husband_handle is None:
                                if person.get_gender() == Person.MALE:
                                    # add the person
                                    family.set_father_handle(person.get_handle())
                                    family.set_relationship(FamilyRelType.MARRIED)
                                    person.add_family_handle(family.get_handle())
                                    added = True
                                    break
                                elif person.get_gender() == Person.UNKNOWN:
                                    family.set_father_handle(person.get_handle())
                                    family.set_relationship(FamilyRelType.MARRIED)
                                    person.add_family_handle(family.get_handle())
                                    person.set_gender(Person.MALE)
                                    self.de_widgets["NPGender"].set_active(Person.MALE)
                                    added = True
                                    break
                if added:
                    self.dbstate.db.commit_family(family, self.trans)
                else:
                    if person.get_gender() == Person.UNKNOWN:
                        if current_person is None:
                            raise ValidationError(
                                _("Please set Active person."),
                                _("Can't add new person as a spouse to no one."),
                            )
                        elif current_person.get_gender() == Person.UNKNOWN:
                            raise ValidationError(
                                _("Please set gender on Active or new person."),
                                _("Can't add new person as a spouse."),
                            )
                        elif current_person.get_gender() == Person.MALE:
                            family = Family()
                            self.dbstate.db.add_family(family, self.trans)
                            family.set_father_handle(current_person.get_handle())
                            family.set_mother_handle(person.get_handle())
                            family.set_relationship(FamilyRelType.MARRIED)
                            person.set_gender(Person.FEMALE)
                            self.de_widgets["NPGender"].set_active(Person.FEMALE)
                            person.add_family_handle(family.get_handle())
                            current_person.add_family_handle(family.get_handle())
                            self.dbstate.db.commit_family(family, self.trans)
                        elif current_person.get_gender() == Person.FEMALE:
                            family = Family()
                            self.dbstate.db.add_family(family, self.trans)
                            family.set_father_handle(person.get_handle())
                            family.set_mother_handle(current_person.get_handle())
                            family.set_relationship(FamilyRelType.MARRIED)
                            person.set_gender(Person.MALE)
                            self.de_widgets["NPGender"].set_active(Person.MALE)
                            person.add_family_handle(family.get_handle())
                            current_person.add_family_handle(family.get_handle())
                            self.dbstate.db.commit_family(family, self.trans)
                    elif person.get_gender() == Person.MALE:
                        if current_person.get_gender() == Person.UNKNOWN:
                            family = Family()
                            self.dbstate.db.add_family(family, self.trans)
                            family.set_father_handle(person.get_handle())
                            family.set_mother_handle(current_person.get_handle())
                            family.set_relationship(FamilyRelType.MARRIED)
                            current_person.set_gender(Person.FEMALE)
                            person.add_family_handle(family.get_handle())
                            current_person.add_family_handle(family.get_handle())
                            self.dbstate.db.commit_family(family, self.trans)
                        elif current_person.get_gender() == Person.MALE:
                            raise ValidationError(
                                _("Same genders on Active and new person."),
                                _("Can't add new person as a spouse."),
                            )
                        elif current_person.get_gender() == Person.FEMALE:
                            family = Family()
                            self.dbstate.db.add_family(family, self.trans)
                            family.set_father_handle(person.get_handle())
                            family.set_mother_handle(current_person.get_handle())
                            family.set_relationship(FamilyRelType.MARRIED)
                            person.add_family_handle(family.get_handle())
                            current_person.add_family_handle(family.get_handle())
                            self.dbstate.db.commit_family(family, self.trans)
                    elif person.get_gender() == Person.FEMALE:
                        if current_person.get_gender() == Person.UNKNOWN:
                            family = Family()
                            self.dbstate.db.add_family(family, self.trans)
                            family.set_father_handle(current_person.get_handle())
                            family.set_mother_handle(person.get_handle())
                            family.set_relationship(FamilyRelType.MARRIED)
                            current_person.set_gender(Person.MALE)
                            person.add_family_handle(family.get_handle())
                            current_person.add_family_handle(family.get_handle())
                            self.dbstate.db.commit_family(family, self.trans)
                        elif current_person.get_gender() == Person.MALE:
                            family = Family()
                            self.dbstate.db.add_family(family, self.trans)
                            family.set_father_handle(current_person.get_handle())
                            family.set_mother_handle(person.get_handle())
                            family.set_relationship(FamilyRelType.MARRIED)
                            person.add_family_handle(family.get_handle())
                            current_person.add_family_handle(family.get_handle())
                            self.dbstate.db.commit_family(family, self.trans)
                        elif current_person.get_gender() == Person.FEMALE:
                            raise ValidationError(
                                _("Same genders on Active and new person."),
                                _("Can't add new person as a spouse."),
                            )
            elif self.de_widgets["NPRelation"].get_active() == self.AS_WIFE:
                # "Add as a Wife"
                added = False
                family = None
                for family_handle in current_person.get_family_handle_list():
                    family = self.dbstate.db.get_family_from_handle(family_handle)
                    if family:
                        fam_wife_handle = family.get_mother_handle()
                        # can we add person as wife?
                        if fam_wife_handle is None:
                            # add the person
                            family.set_mother_handle(person.get_handle())
                            family.set_relationship(FamilyRelType.MARRIED)
                            person.add_family_handle(family.get_handle())
                            added = True
                            break
                if added:
                    self.dbstate.db.commit_family(family, self.trans)
                else:
                    family = Family()
                    self.dbstate.db.add_family(family, self.trans)
                    family.set_mother_handle(person.get_handle())
                    family.set_father_handle(current_person.get_handle())
                    family.set_relationship(FamilyRelType.MARRIED)
                    person.add_family_handle(family.get_handle())
                    current_person.add_family_handle(family.get_handle())
                    self.dbstate.db.commit_family(family, self.trans)
            elif self.de_widgets["NPRelation"].get_active() == self.AS_HUSBAND:
                # "Add as a Husband"
                added = False
                family = None
                for family_handle in current_person.get_family_handle_list():
                    family = self.dbstate.db.get_family_from_handle(family_handle)
                    if family:
                        fam_husband_handle = family.get_father_handle()
                        # can we add person as husband?
                        if fam_husband_handle is None:
                            # add the person
                            family.set_father_handle(person.get_handle())
                            family.set_relationship(FamilyRelType.MARRIED)
                            person.add_family_handle(family.get_handle())
                            added = True
                            break
                if added:
                    self.dbstate.db.commit_family(family, self.trans)
                else:
                    family = Family()
                    self.dbstate.db.add_family(family, self.trans)
                    family.set_father_handle(person.get_handle())
                    family.set_mother_handle(current_person.get_handle())
                    family.set_relationship(FamilyRelType.MARRIED)
                    person.add_family_handle(family.get_handle())
                    current_person.add_family_handle(family.get_handle())
                    self.dbstate.db.commit_family(family, self.trans)
            elif (
                self.de_widgets["NPRelation"].get_active() == self.AS_SIBLING
                and current_person is not None
            ):
                # "Add as a Sibling"
                added = False
                for family_handle in current_person.get_parent_family_handle_list():
                    family = self.dbstate.db.get_family_from_handle(family_handle)
                    if family:
                        childref = ChildRef()
                        childref.set_reference_handle(person.get_handle())
                        family.add_child_ref(childref)
                        person.add_parent_family_handle(family.get_handle())
                        added = True
                        break
                if added:
                    self.dbstate.db.commit_family(family, self.trans)
                else:
                    family = Family()
                    self.dbstate.db.add_family(family, self.trans)
                    childref = ChildRef()
                    childref.set_reference_handle(person.get_handle())
                    family.add_child_ref(childref)
                    childref = ChildRef()
                    childref.set_reference_handle(current_person.get_handle())
                    family.add_child_ref(childref)
                    person.add_parent_family_handle(family.get_handle())
                    current_person.add_parent_family_handle(family.get_handle())
                    self.dbstate.db.commit_family(family, self.trans)
            elif (
                self.de_widgets["NPRelation"].get_active() == self.AS_CHILD
                and current_person is not None
            ):
                # "Add as a Child"
                added = False
                family = None
                for family_handle in current_person.get_family_handle_list():
                    family = self.dbstate.db.get_family_from_handle(family_handle)
                    if family:
                        childref = ChildRef()
                        childref.set_reference_handle(person.get_handle())
                        family.add_child_ref(childref)
                        person.add_parent_family_handle(family.get_handle())
                        added = True
                        break
                if added:
                    self.dbstate.db.commit_family(family, self.trans)
                else:
                    if current_person.get_gender() == Person.UNKNOWN:
                        raise ValidationError(
                            _("Please set gender on Active person."),
                            _("Can't add new person as a child."),
                        )
                    else:
                        family = Family()
                        self.dbstate.db.add_family(family, self.trans)
                        childref = ChildRef()
                        childref.set_reference_handle(person.get_handle())
                        family.add_child_ref(childref)
                        person.add_parent_family_handle(family.get_handle())
                        current_person.add_family_handle(family.get_handle())
                        if current_person.get_gender() == Person.FEMALE:
                            family.set_mother_handle(current_person.get_handle())
                        else:
                            family.set_father_handle(current_person.get_handle())
                        self.dbstate.db.commit_family(family, self.trans)
            # Commit changes -------------------------------------------------
            if current_person:  # if related to current person
                self.dbstate.db.commit_person(current_person, self.trans)
            if person:
                source_text = self.de_widgets["NPSource"].get_text().strip()
                if (
                    source_text
                    and self.de_widgets["Active person:Show sources"].get_active()
                ):
                    _new, source = self.get_or_create_source(source_text)
                    self.add_source(person, source)
                self.add_selected_citation(person, "NPSource:Citation")
                self.dbstate.db.commit_person(person, self.trans)

    def cb_copy_data_entry(self, _obj: Gtk.Button | None = None) -> None:
        """
        Copy the Active person's data into the New person block.

        Birth and Death go to the event rows whose menus are set to those
        types. If a citation is chosen, its date goes to the Residence row.

        :param _obj: The button that was clicked (unused).
        """
        self.de_widgets["NPName"].set_text(self.de_widgets["APName"].get_text())
        self.de_widgets["NPGender"].set_active(self.de_widgets["APGender"].get_active())
        self.de_widgets["NPSource"].set_text(self.de_widgets["APSource"].get_text())
        # Birth and Death go to the event row whose menu is set to that type:
        for ev_type, ap_key in (
            (EventType.BIRTH, "APBirth"),
            (EventType.DEATH, "APDeath"),
        ):
            prefix = self.event_row_for_type(ev_type)
            if prefix:
                self.de_widgets[prefix].set_text(self.de_widgets[ap_key].get_text())
                self.de_widgets[prefix + "Source"].set_text(
                    self.de_widgets[ap_key + "Source"].get_text()
                )
        # A chosen citation's date becomes the Residence date (e.g. a census):
        if self.de_widgets["Active person:Show citation"].get_active():
            citation = self.selected_citation()
            date_text = get_date(citation) if citation else ""
            prefix = self.event_row_for_type(EventType.RESIDENCE)
            if date_text and prefix:
                self.de_widgets[prefix].set_text(date_text)
        # FIXME: put cursor in add surname

    def clear_data_edit(self) -> None:
        """
        Empty the Active person block.
        """
        self.de_widgets["Active person"].set_text("")
        self.de_widgets["APName"].set_text("")
        self.de_widgets["APBirth"].set_text("")
        self.de_widgets["APDeath"].set_text("")
        self.de_widgets["APGender"].set_active(Person.UNKNOWN)
        self.de_widgets["APSource"].set_text("")
        self.de_widgets["APBirthSource"].set_text("")
        self.de_widgets["APDeathSource"].set_text("")
        self.de_widgets["APSource:Citation"].set_active(False)
        self.de_widgets["APBirthSource:Citation"].set_active(False)
        self.de_widgets["APDeathSource:Citation"].set_active(False)

    def cb_clear_data_entry(self, _obj: Gtk.Button | None = None) -> None:
        """
        Empty the New person block (the event types are kept).

        :param _obj: The button that was clicked (unused).
        """
        self.de_widgets["NPName"].set_text("")
        self.de_widgets["NPRelation"].set_active(self.NO_REL)
        self.de_widgets["NPGender"].set_active(Person.UNKNOWN)
        self.de_widgets["NPSource"].set_text("")
        self.de_widgets["NPSource:Citation"].set_active(False)
        for prefix in self.EVENT_PREFIXES:
            self.de_widgets[prefix].set_text("")
            self.de_widgets[prefix + "Source"].set_text("")
            self.de_widgets[prefix + "Source:Citation"].set_active(False)

    def db_changed(self) -> None:
        """
        Follow database changes (Gramplet API hook).

        If a person or family changes, the relatives of the active person
        might have changed. A chosen citation only makes sense in one tree,
        so it is forgotten when the tree changes.
        """
        self.connect(self.dbstate.db, "person-add", self.update)
        self.connect(self.dbstate.db, "person-delete", self.update)
        self.connect(self.dbstate.db, "person-update", self.update)
        self.connect(self.dbstate.db, "family-add", self.update)
        self.connect(self.dbstate.db, "family-delete", self.update)
        self.connect(self.dbstate.db, "person-rebuild", self.update)
        self.connect(self.dbstate.db, "family-rebuild", self.update)
        self._dirty = False
        self._dirty_person = None
        self.connect(self.dbstate.db, "citation-delete", self.cb_citation_deleted)
        self.connect(self.dbstate.db, "citation-update", self.cb_citation_updated)
        self._citation_handle = None
        self.select_sources_mode()
        self.update_citation_display()
        self.cb_clear_data_entry(None)

    def active_changed(self, handle: PersonHandle) -> None:
        """
        Refresh when the active person changes (Gramplet API hook).

        :param handle: Handle of the new active person.
        """
        self.update()

    def select_sources_mode(self) -> None:
        """
        Select Enter Sources (only if not already selected).

        Selecting it deselects Select Citation through the radio group,
        which (via :meth:`cb_toggle_citation`) also forgets any chosen
        citation.
        """
        widget = self.de_widgets["Active person:Show sources"]
        if not widget.get_active():
            widget.set_active(True)

    def refresh_source_mode_widgets(self) -> None:
        """
        Show the right field for each sourceable row, hide the rest.

        Enter Sources shows the entry and its "Source:" label; Select
        Citation shows the "Use citation" check button instead; None hides
        both.
        """
        sources_on = self.de_widgets["Active person:Show sources"].get_active()
        citation_on = self.de_widgets["Active person:Show citation"].get_active()
        for key in self.SOURCE_KEYS:
            for name, visible in (
                (key, sources_on),
                (key + ":Label", sources_on),
                (key + ":Citation", citation_on),
            ):
                widget = self.de_widgets.get(name)
                if widget is not None:
                    widget.set_visible(visible)

    def cb_toggle_sources(self, _widget: Gtk.RadioButton) -> None:
        """
        Handle the Enter Sources radio button.

        The radio group keeps this mutually exclusive with Select Citation
        and None.

        :param _widget: The Enter Sources radio button (unused; its state
            is read directly by :meth:`refresh_source_mode_widgets`).
        """
        self.refresh_source_mode_widgets()

    def cb_toggle_citation(self, widget: Gtk.RadioButton) -> None:
        """
        Handle the Select Citation radio button.

        Selecting it opens the Citation selector and (through the radio
        group) deselects Enter Sources. If no valid citation is chosen,
        selection reverts to Enter Sources, which re-enters this callback
        (now deselected) to forget the citation.

        :param widget: The Select Citation radio button.
        """
        if widget.get_active():
            if not self.pick_citation():
                self.select_sources_mode()
                return  # the revert re-enters here, deselected, to tidy up
        else:
            self._citation_handle = None
        self.update_citation_display()
        self.refresh_source_mode_widgets()

    def pick_citation(self) -> bool:
        """
        Open the Citation selector.

        :returns: ``True`` if a Citation was chosen (cancelling, or picking a
            Source row, gives ``False``).
        """
        if not self.dbstate.is_open():
            return False
        selector = gramps_selectors.SelectorFactory("Citation")(
            self.dbstate, self.uistate, self.track
        )
        picked = selector.run()
        if not isinstance(picked, Citation):  # cancelled, or a Source row
            return False
        self._citation_handle = picked.get_handle()
        return True

    def selected_citation(self) -> Citation | None:
        """
        Return the chosen Citation, or ``None`` (none chosen, or deleted).
        """
        if not self._citation_handle:
            return None
        return self.dbstate.db.get_citation_from_handle(self._citation_handle)

    def describe_citation(self) -> str | None:
        """
        Describe the chosen citation for the user.

        :returns: ``Date; Volume/Page; Source title`` (empty parts left out),
            or ``None`` if no citation is chosen.
        """
        citation = self.selected_citation()
        if citation is None:
            return None
        source = self.dbstate.db.get_source_from_handle(citation.get_reference_handle())
        parts = [
            get_date(citation),
            citation.get_page(),
            source.get_title() if source else "",
        ]
        return "; ".join(part for part in parts if part)

    def update_citation_display(self) -> None:
        """
        Show the chosen citation next to the Select Citation radio button.
        """
        text = self.describe_citation() or ""
        info = self.de_widgets["Citation:Info"]
        info.set_text(text)
        info.set_tooltip_text(text or None)
        self.de_widgets["Active person:Show citation"].set_tooltip_text(
            _("Choose a citation to attach to the new records (instead of Sources).")
        )

    def cb_citation_deleted(self, handle_list: list[CitationHandle]) -> None:
        """
        Select Enter Sources if the chosen citation was deleted.

        :param handle_list: Handles of the deleted citations.
        """
        if self._citation_handle in handle_list:
            self.select_sources_mode()

    def cb_citation_updated(self, handle_list: list[CitationHandle]) -> None:
        """
        Refresh the citation display if the chosen citation was edited.

        :param handle_list: Handles of the updated citations.
        """
        if self._citation_handle in handle_list:
            self.update_citation_display()

    def add_selected_citation(self, obj: Person | Event, checkbox_key: str) -> bool:
        """
        Attach the chosen citation to an object, field by field.

        Citation mode alone is not enough: the field's own "Use citation"
        check button (see :meth:`make_source_field`) must also be checked,
        the same way a Source field's text governs Enter Sources mode.

        :param obj: The person or event to attach it to.
        :param checkbox_key: Key of that field's "Use citation" check button.
        :returns: ``True`` if ``obj`` was changed, so the caller must commit it.
        """
        if (
            self.de_widgets["Active person:Show citation"].get_active()
            and self.de_widgets[checkbox_key].get_active()
            and self.selected_citation() is not None
        ):
            obj.add_citation(self._citation_handle)
            return True
        return False
