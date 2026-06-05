# -*- coding: utf-8 -*-
"""
tests/compat_mocks.py

Compatibility stubs for Gramps library imports used in tests.
This module provides a unified mocking setup for headless testing.
"""

import sys
from unittest.mock import MagicMock


class Person:
    """Fallback stub for gramps.gen.lib.Person."""

    MALE = 0
    FEMALE = 1
    UNKNOWN = 2
    OTHER = 3


class NameType:
    UNKNOWN = -1
    CUSTOM = 0
    AKA = 1
    BIRTH = 2
    MARRIED = 3


class NameOriginType:
    UNKNOWN = 0
    CUSTOM = 1
    PATRONYMIC = 5


class Surname:
    def __init__(self, surname_str="", origin=NameOriginType.UNKNOWN):
        self._surname = surname_str
        self._origin = origin

    def get_surname(self) -> str:
        return self._surname

    def get_origintype(self):
        return self._origin

    def set_surname(self, val):
        self._surname = val

    def set_origintype(self, val):
        self._origin = val

    def set_primary(self, val):
        pass


class Name:
    def __init__(self):
        self._first_name = ""
        self._type = None
        self._surnames = []

    def get_first_name(self):
        return self._first_name

    def set_first_name(self, name_str):
        self._first_name = name_str

    def get_regular_name(self):
        return self._first_name

    def get_type(self):
        return self._type

    def set_type(self, val):
        self._type = val

    def get_surname_list(self):
        return self._surnames

    def add_surname(self, surname):
        self._surnames.append(surname)

    def set_surname_list(self, list_):
        self._surnames = list_

    def serialize(self):
        return {}

    def unserialize(self, data):
        pass


def mock_gramps():
    """Injects Gramps and GTK mocks into sys.modules."""
    # GTK Mocks
    gi_mock = MagicMock()
    gi_repository_mock = MagicMock()
    sys.modules["gi"] = gi_mock
    sys.modules["gi.repository"] = gi_repository_mock
    sys.modules["gi.repository.Gtk"] = MagicMock()
    sys.modules["gi.repository.GLib"] = MagicMock()

    # Gramps Mocks
    gramps_mock = MagicMock()
    gramps_gen_mock = MagicMock()
    gramps_gen_lib_mock = MagicMock()
    gramps_gen_db_mock = MagicMock()
    gramps_gen_const_mock = MagicMock()
    gramps_gen_errors_mock = MagicMock()
    gramps_gen_display_mock = MagicMock()
    gramps_gui_mock = MagicMock()
    gramps_gui_plug_mock = MagicMock()
    gramps_gui_dialog_mock = MagicMock()
    gramps_gui_editors_mock = MagicMock()

    # Configure lib mock
    gramps_gen_lib_mock.Person = Person
    gramps_gen_lib_mock.Name = Name
    gramps_gen_lib_mock.Surname = Surname
    gramps_gen_lib_mock.NameType = NameType
    gramps_gen_lib_mock.NameOriginType = NameOriginType

    # Configure const mock
    gramps_gen_const_mock.GRAMPS_LOCALE.translation.gettext = lambda x: x

    # Configure error mock
    class WindowActiveError(Exception):
        pass

    gramps_gen_errors_mock.WindowActiveError = WindowActiveError

    # Configure tool mock
    class MockTool:
        def __init__(self, *args, **kwargs):
            pass

    class MockToolOptions:
        def __init__(self, *args, **kwargs):
            pass

    gramps_gui_plug_mock.tool.Tool = MockTool
    gramps_gui_plug_mock.tool.ToolOptions = MockToolOptions

    # Inject into sys.modules
    sys.modules["gramps"] = gramps_mock
    sys.modules["gramps.gen"] = gramps_gen_mock
    sys.modules["gramps.gen.lib"] = gramps_gen_lib_mock
    sys.modules["gramps.gen.db"] = gramps_gen_db_mock
    sys.modules["gramps.gen.const"] = gramps_gen_const_mock
    sys.modules["gramps.gen.errors"] = gramps_gen_errors_mock
    sys.modules["gramps.gen.display"] = gramps_gen_display_mock
    sys.modules["gramps.gen.display.name"] = MagicMock()
    sys.modules["gramps.gui"] = gramps_gui_mock
    sys.modules["gramps.gui.plug"] = gramps_gui_plug_mock
    sys.modules["gramps.gui.dialog"] = gramps_gui_dialog_mock
    sys.modules["gramps.gui.editors"] = gramps_gui_editors_mock

    return gramps_gen_lib_mock
