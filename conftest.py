#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Eduard Ralph
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
Root conftest.py — registers custom pytest markers and provides
auto-skip for GUI-dependent tests on headless environments.
"""

import pytest


def _has_gtk():
    """Check if GTK is available at import time."""
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk  # noqa: F401

        return True
    except (ImportError, ValueError):
        return False


HAS_GTK = _has_gtk()


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "gui: mark test as requiring GTK/GUI (deselected with -m 'not gui')",
    )


def pytest_collection_modifyitems(config, items):
    """Auto-skip tests marked @pytest.mark.gui when GTK is not available."""
    if HAS_GTK:
        return
    skip_gui = pytest.mark.skip(
        reason="GTK not available (headless environment)"
    )
    for item in items:
        if "gui" in item.keywords:
            item.add_marker(skip_gui)
