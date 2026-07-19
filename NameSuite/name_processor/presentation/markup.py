#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Dmitry Bryndin
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

"""GTK-free Pango markup and formatting helpers."""


def pango_escape(text: str) -> str:
    """Escapes XML special characters to prevent GTK Pango parsing crashes."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generate_pango_diff(old_str: str, new_str: str) -> str:
    """
    Generates a simple before/after diff in Pango markup.
    Format: <current> -> <suggested>
    Example: Иванович -> Ивановна
    """
    old_esc = pango_escape(old_str)
    new_esc = pango_escape(new_str)

    if not old_esc and not new_esc:
        return ""
    if not old_esc:
        return f"<span weight='bold'>{new_esc}</span>"
    if not new_esc:
        return f"{old_esc}"

    return f"{old_esc} → <span weight='bold'>{new_esc}</span>"


def format_confidence(score: float) -> str:
    """Formats a confidence score (0.0-1.0) as a percentage string."""
    return f"{int(score * 100)}%"
