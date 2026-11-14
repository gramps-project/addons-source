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

"""Shared GTK test doubles for the GWizard tool tests.

The GWizard dialogs subclass Gtk classes and build widgets, which needs a
display.  These lightweight fakes stand in for the few widgets the tests
inspect.  Every GWizard test module calls :func:`install` *before* importing
a GWizard module (so the dialog classes subclass the fakes) and again in
``setUpModule``, and :func:`uninstall` in ``tearDownModule``, so the real
``Gtk`` module is not left patched for other Gramps tests in the same run.

This module is not named ``*_test.py`` and so is not collected as a test.
"""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
from __future__ import annotations
import sys
from typing import Any
from unittest.mock import MagicMock


# ------------------------------------------------------------
#
# Fake widgets
#
# ------------------------------------------------------------
class _FakeDialog:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.response: Any = None

    def get_content_area(self) -> MagicMock:
        return MagicMock()

    def add_button(self, *args: Any, **kwargs: Any) -> None:
        pass

    def add_action_widget(self, *args: Any, **kwargs: Any) -> None:
        pass

    def connect(self, *args: Any, **kwargs: Any) -> None:
        pass

    def set_default_size(self, *args: Any, **kwargs: Any) -> None:
        pass

    def show_all(self) -> None:
        pass

    def destroy(self) -> None:
        pass

    def run(self) -> Any:
        if self.response is not None:
            return self.response
        from gi.repository import Gtk

        return Gtk.ResponseType.OK


class _FakeLabel:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.selectable = False
        self.can_focus = True
        self.line_wrap = False
        self.text = ""
        self.markup = ""
        self.max_width_chars: int | None = None
        self.size_request: tuple[int, int] | None = None
        self.xalign = 0.5
        self.halign: Any = None

    def set_text(self, val: str) -> None:
        self.text = val

    def set_markup(self, val: str) -> None:
        self.markup = val

    def set_use_markup(self, val: bool) -> None:
        pass

    def set_selectable(self, val: bool) -> None:
        self.selectable = val

    def set_can_focus(self, val: bool) -> None:
        self.can_focus = val

    def set_line_wrap(self, val: bool) -> None:
        self.line_wrap = val

    def set_line_wrap_mode(self, val: Any) -> None:
        pass

    def set_halign(self, val: Any) -> None:
        self.halign = val

    def set_xalign(self, val: float) -> None:
        self.xalign = val

    def set_max_width_chars(self, val: int) -> None:
        self.max_width_chars = val

    def set_size_request(self, w: int, h: int) -> None:
        self.size_request = (w, h)

    def set_hexpand(self, val: bool) -> None:
        self.hexpand = val

    def set_vexpand(self, val: bool) -> None:
        self.vexpand = val


class _FakeGrid:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.col_spacing = 0
        self.row_spacing = 0
        self.hexpand = False
        self.vexpand = False

    def set_column_spacing(self, val: int) -> None:
        self.col_spacing = val

    def set_row_spacing(self, val: int) -> None:
        self.row_spacing = val

    def set_hexpand(self, val: bool) -> None:
        self.hexpand = val

    def set_vexpand(self, val: bool) -> None:
        self.vexpand = val

    def attach(self, *args: Any, **kwargs: Any) -> None:
        pass


class _FakeEntry:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._text = ""
        self._callbacks: list[Any] = []

    def set_text(self, val: str) -> None:
        self._text = val
        for cb in self._callbacks:
            try:
                cb()
            except Exception:
                pass

    def get_text(self) -> str:
        return self._text

    def set_width_chars(self, val: int) -> None:
        pass

    def set_hexpand(self, val: bool) -> None:
        pass

    def set_sensitive(self, val: bool) -> None:
        self._sensitive = val

    def connect(self, signal: str, callback: Any, *args: Any) -> None:
        if signal == "changed":
            self._callbacks.append(callback)


class _FakeRadioButton:
    def __init__(self, group: Any = None, label: str = "") -> None:
        self._active = False
        self.group = group if group is not None else self
        self._peers = [self]
        if group is not None and hasattr(group, "_peers"):
            group._peers.append(self)
            self._peers = group._peers
        self.label = label
        self._callbacks: list[Any] = []

    @classmethod
    def new_with_label_from_widget(
        cls, group: Any = None, label: str = ""
    ) -> _FakeRadioButton:
        btn = cls(group, label)
        if group is None:
            btn._active = True
        return btn

    def set_active(self, val: bool) -> None:
        self._active = val
        if val:
            for peer in self._peers:
                if peer is not self:
                    peer._active = False
        for cb in self._callbacks:
            try:
                cb(self)
            except Exception:
                pass

    def get_active(self) -> bool:
        return self._active

    def connect(self, signal: str, callback: Any, *args: Any) -> None:
        if signal == "toggled":
            self._callbacks.append(callback)


class _FakeComboBoxText:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._active = 0
        self._items: list[str] = []
        self._child = _FakeEntry()

    @classmethod
    def new_with_entry(cls) -> _FakeComboBoxText:
        return cls()

    def get_child(self) -> _FakeEntry:
        return self._child

    def append_text(self, text: str) -> None:
        self._items.append(text)

    def set_active(self, val: int) -> None:
        self._active = val

    def get_active(self) -> int:
        return self._active

    def set_hexpand(self, val: bool) -> None:
        pass

    def connect(self, *args: Any, **kwargs: Any) -> None:
        pass


class _FakeButton:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._label = kwargs.get("label", "")
        if args and isinstance(args[0], str):
            self._label = args[0]
        self._sensitive = True
        self._tooltip = ""
        self._clicked: list[tuple[Any, tuple[Any, ...]]] = []

    def set_label(self, val: str) -> None:
        self._label = val

    def get_label(self) -> str:
        return self._label

    def set_sensitive(self, val: bool) -> None:
        self._sensitive = val

    def get_sensitive(self) -> bool:
        return self._sensitive

    def set_hexpand(self, val: bool) -> None:
        pass

    def set_tooltip_text(self, val: str) -> None:
        self._tooltip = val

    def get_tooltip_text(self) -> str:
        return self._tooltip

    def connect(self, signal: str, callback: Any, *args: Any) -> None:
        if signal == "clicked":
            self._clicked.append((callback, args))

    def clicked(self) -> None:
        """Run the "clicked" handlers, as pressing the button would."""
        for callback, args in self._clicked:
            callback(self, *args)

    def add(self, *args: Any, **kwargs: Any) -> None:
        pass


_FAKES: dict[str, Any] = {
    "Dialog": _FakeDialog,
    "Label": _FakeLabel,
    "Grid": _FakeGrid,
    "Entry": _FakeEntry,
    "RadioButton": _FakeRadioButton,
    "ComboBoxText": _FakeComboBoxText,
    "Button": _FakeButton,
}
_originals: dict[str, Any] = {}


def gtk() -> Any:
    """
    Return the ``Gtk`` module, mocking PyGObject when it has not been loaded.

    :returns: The (real or mock) ``Gtk`` module.
    """
    if "gi" not in sys.modules:
        gi_mock = MagicMock()
        sys.modules["gi"] = gi_mock
        sys.modules["gi.repository"] = gi_mock.repository
    from gi.repository import Gtk  # pylint: disable=import-outside-toplevel

    return Gtk


def install() -> Any:
    """
    Put the fake widgets on ``Gtk`` (idempotent).

    :returns: The ``Gtk`` module.
    """
    module = gtk()
    for name, fake in _FAKES.items():
        current = getattr(module, name, None)
        if current is not fake:
            _originals.setdefault(name, current)
            setattr(module, name, fake)
    return module


def uninstall() -> None:
    """Restore the ``Gtk`` attributes that :func:`install` replaced."""
    module = gtk()
    for name, original in _originals.items():
        setattr(module, name, original)
    _originals.clear()
