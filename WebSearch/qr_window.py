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
Provides a GTK window to display a QR code for a given URL in the WebSearch Gramplet.
"""

import sys

import gi

gi.require_version("Gtk", "3.0")  # pylint: disable=wrong-import-position
gi.require_version("GdkPixbuf", "2.0")  # pylint: disable=wrong-import-position
from gi.repository import GdkPixbuf, Gtk

try:
    import qrcode
except ImportError:
    print(
        "❌ Error. QR codes are disabled. Install it using: `pip install qrcode[pil]`.",
        file=sys.stderr,
    )

try:
    import qrcode

    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False
    print(
        "❌ Error. QR codes are disabled. Install it using: `pip install qrcode[pil]`.",
        file=sys.stderr,
    )

from translation_helper import _


class QRCodeWindow(Gtk.Window):
    """
    A GTK window for generating and displaying a QR code for a given URL.

    This class provides a simple interface to generate a QR code from a URL
    and display it in a separate GTK window. If QR code generation fails,
    the window will display an error message instead.

    Features:
    - Uses the `qrcode` library to generate QR codes.
    - Displays the generated QR code as an image inside the window.
    - Shows an error message if QR code generation fails.
    - Supports localization for error messages in Gramps.

    Attributes:
        url (str): The URL for which the QR code is generated.

    Methods:
        generate_qr(url):
            Generates a QR code image for the given URL.
            Returns a GdkPixbuf image if successful or an error message if it fails.
    """

    def __init__(self, url):
        """
        Initialize the QRCodeWindow with a QR code or an error message.

        Args:
            url (str): The URL to generate a QR code for. The resulting QR code
                       or an error message will be displayed in the window.
        """
        super().__init__(title=_("QR-code"))
        self.set_default_size(300, 300)
        self.set_position(Gtk.WindowPosition.CENTER)

        qr_image, error_message = self.generate_qr(url)

        if qr_image:
            image_widget = Gtk.Image.new_from_pixbuf(qr_image)
            self.add(image_widget)
        else:
            error_label = Gtk.Label(label=error_message)
            error_label.set_justify(Gtk.Justification.CENTER)
            error_label.set_margin_top(20)
            error_label.set_margin_bottom(20)
            error_label.set_margin_start(10)
            error_label.set_margin_end(10)
            self.add(error_label)

    def generate_qr(self, url):
        """
        Generate a QR code image for the given URL.

        Args:
            url (str): The URL to encode as a QR code.

        Returns:
            tuple: (GdkPixbuf.Pixbuf, None) if successful,
                   (None, str) with error message otherwise.
        """

        if not QR_AVAILABLE:
            return None, _('⚠ Missing dependency "qrcode"')

        if not hasattr(qrcode, "make"):
            return None, _('⚠ Missing dependency "qrcode"')

        try:
            qr = qrcode.make(url)
            qr.save("/tmp/qrcode.png")
            return (
                GdkPixbuf.Pixbuf.new_from_file_at_size("/tmp/qrcode.png", 250, 250),
                None,
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            error_message = _(
                "⚠ Error generating QR code:\nOriginal error: “{}”"
            ).format(e)
            print(error_message, file=sys.stderr)
            return None, error_message
