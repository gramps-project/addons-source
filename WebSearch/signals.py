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
Defines a custom GObject signal emitter for asynchronous events in the WebSearch Gramplet.
"""

import gi

gi.require_version("Gtk", "3.0")  # pylint: disable=wrong-import-position
from gi.repository import GObject


class WebSearchSignalEmitter(GObject.GObject):
    """
    WebSearchSignalEmitter class for emitting custom signals in the WebSearch gramplet.

    This class extends GObject to provide a custom signal mechanism for asynchronous
    operations. It allows the WebSearch gramplet to emit signals when specific actions,
    such as fetching sites, are completed.

    Key Features:
    - Defines a "sites-fetched" signal that carries a list of fetched sites as its payload.
    - Used for event-driven updates in the WebSearch gramplet.

    Attributes:
    - None

    Methods:
    - None (inherits from GObject.GObject)

    Signals:
    - "sites-fetched": Emitted when a site-fetching operation completes, passing
      the results as an object.
    """

    __gsignals__ = {"sites-fetched": (GObject.SignalFlags.RUN_FIRST, None, (object,))}

    def __init__(self):
        """
        Initialize the WebSearchSignalEmitter.

        Sets up the custom GObject signal infrastructure for use in WebSearch.
        """
        GObject.GObject.__init__(self)
