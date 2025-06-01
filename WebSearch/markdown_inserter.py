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
MarkdownInserter module.

Provides functionality to insert styled text into a Gtk.TextView,
supporting a subset of Markdown-like syntax for bold, italic, underline,
colored text, links, and headings (H1–H6).

Supported formatting syntax:
------------------------------------
- # Heading 1
- ## Heading 2
- ### Heading 3
- #### Heading 4
- ##### Heading 5
- ###### Heading 6

- **bold text**
- *italic text*
- __underlined text__

- {red|colored text}  — supports colors: red, blue, green, orange, purple, yellow, gray, black

- [link text](https://example.com)  — clickable links

- {small|small text} — smaller text (scale 0.8)
- {small_bold|small bold text} — smaller bold text (scale 0.8 + bold)

Notes:
- Empty inline tags like {small|} or {red|} will be automatically skipped
  and removed from the output.
------------------------------------
"""

import re

# --------------------------
# Third-party libraries
# --------------------------
import gi

gi.require_version("Gtk", "3.0")  # pylint: disable=wrong-import-position
gi.require_version("Gdk", "3.0")  # pylint: disable=wrong-import-position
from gi.repository import Gtk, Gdk, Pango


class MarkdownInserter:
    """
    Class for inserting formatted text into a Gtk.TextView using simple Markdown-like syntax.
    Supports bold, italic, underline, colors, links, and headings (H1–H6).
    """

    def __init__(self, textview):
        """
        Initialize the MarkdownInserter with the target Gtk.TextView.

        Args:
            textview (Gtk.TextView): The text view widget to insert formatted text into.
        """
        self.textview = textview
        self.buffer = textview.get_buffer()
        self.setup_tags()

    def setup_tags(self):
        """
        Create and initialize text tags for different Markdown elements (bold, italic, etc.).
        """
        self.bold_tag = self.buffer.create_tag("bold", weight=Pango.Weight.BOLD)
        self.italic_tag = self.buffer.create_tag("italic", style=Pango.Style.ITALIC)
        self.underline_tag = self.buffer.create_tag(
            "underline", underline=Pango.Underline.SINGLE
        )
        self.small_tag = self.buffer.create_tag("small", scale=0.8)
        self.small_bold_tag = self.buffer.create_tag(
            "small_bold", scale=0.8, weight=Pango.Weight.BOLD
        )

        self.color_tags = {
            "red": self.buffer.create_tag("red", foreground="red"),
            "blue": self.buffer.create_tag("blue", foreground="blue"),
            "green": self.buffer.create_tag("green", foreground="green"),
            "orange": self.buffer.create_tag("orange", foreground="orange"),
            "purple": self.buffer.create_tag("purple", foreground="purple"),
            "yellow": self.buffer.create_tag("yellow", foreground="yellow"),
            "gray": self.buffer.create_tag("gray", foreground="gray"),
            "black": self.buffer.create_tag("black", foreground="black"),
        }

        self.hover_color_tag = self.buffer.create_tag("hover_link", foreground="green")

        self.heading_tags = {
            1: self.buffer.create_tag("h1", weight=Pango.Weight.BOLD, scale=2.0),
            2: self.buffer.create_tag("h2", weight=Pango.Weight.BOLD, scale=1.8),
            3: self.buffer.create_tag("h3", weight=Pango.Weight.BOLD, scale=1.6),
            4: self.buffer.create_tag("h4", weight=Pango.Weight.BOLD, scale=1.4),
            5: self.buffer.create_tag("h5", weight=Pango.Weight.BOLD, scale=1.2),
            6: self.buffer.create_tag("h6", weight=Pango.Weight.BOLD, scale=1.0),
        }

        self.link_tag_template = self.buffer.create_tag(
            "link",
            foreground="blue",
            underline=Pango.Underline.SINGLE,
        )

        self.link_hover_tag = self.buffer.create_tag(
            "link_hover",
            foreground="green",
            underline=Pango.Underline.SINGLE,
        )

    def insert_markdown(self, text: str):
        """
        Parse and insert the given text with Markdown-like formatting into the text buffer.
        Removes empty tags automatically.

        Args:
            text (str): The input text containing Markdown-like formatting.
        """
        self.buffer.set_text("")

        # Remove empty tags like {small|}, {red|}, {small_bold|}, etc.
        text = re.sub(r"\{[a-z_]+\|\}", "", text)

        patterns = [
            (re.compile(r"^###### (.+)", re.MULTILINE), "h6"),
            (re.compile(r"^##### (.+)", re.MULTILINE), "h5"),
            (re.compile(r"^#### (.+)", re.MULTILINE), "h4"),
            (re.compile(r"^### (.+)", re.MULTILINE), "h3"),
            (re.compile(r"^## (.+)", re.MULTILINE), "h2"),
            (re.compile(r"^# (.+)", re.MULTILINE), "h1"),
            (re.compile(r"\*\*(.+?)\*\*", re.DOTALL), "bold"),
            (re.compile(r"__(.+?)__", re.DOTALL), "underline"),
            (re.compile(r"\{dir\|(.+?)\}", re.DOTALL), "dir"),
            (re.compile(r"\{small_bold\|(.+?)\}", re.DOTALL), "small_bold"),
            (re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", re.DOTALL), "italic"),
            (
                re.compile(
                    r"\{(red|blue|green|orange|purple|yellow|gray|black)\|(.+?)\}",
                    re.DOTALL,
                ),
                "color",
            ),
            (re.compile(r"\{small\|(.+?)\}", re.DOTALL), "small"),
            (re.compile(r"\[([^\[\]]+?)\]\((https?://[^\s)]+)\)", re.DOTALL), "link"),
        ]

        matches = []
        for pattern, tag in patterns:
            for match in pattern.finditer(text):
                matches.append((match.start(), match.end(), match, tag))

        matches.sort(key=lambda x: x[0])

        last_pos = 0
        for start, end, match, tag in matches:
            if start < last_pos:
                continue

            if last_pos < start:
                self.buffer.insert(self.buffer.get_end_iter(), text[last_pos:start])

            # Clean text before inserting
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                content = match.group(1).strip()
                if content:
                    level = int(tag[1])
                    heading_tag = self.heading_tags.get(level)
                    if heading_tag:
                        self.buffer.insert_with_tags(
                            self.buffer.get_end_iter(), content + "\n", heading_tag
                        )

            elif tag == "color":
                color, colored_text = match.group(1), match.group(2).strip()
                if colored_text:
                    tag_obj = self.color_tags.get(color.lower())
                    if tag_obj:
                        self.buffer.insert_with_tags(
                            self.buffer.get_end_iter(), colored_text, tag_obj
                        )
                    else:
                        self.buffer.insert(self.buffer.get_end_iter(), colored_text)

            elif tag == "small_bold":
                content = match.group(1).strip()
                if content:
                    self.buffer.insert_with_tags(
                        self.buffer.get_end_iter(), content, self.small_bold_tag
                    )

            elif tag == "small":
                content = match.group(1).strip()
                if content:
                    self.buffer.insert_with_tags(
                        self.buffer.get_end_iter(), content, self.small_tag
                    )

            elif tag == "link":
                link_text = match.group(1).strip()
                link_url = match.group(2).strip()
                if link_text and link_url:
                    self.insert_link(link_text, link_url)

            elif tag == "dir":
                path = match.group(1).strip()
                if path:
                    self.insert_directory_link(path)

            else:
                content = match.group(1).strip()
                if content:
                    tag_obj = getattr(self, f"{tag}_tag")
                    self.buffer.insert_with_tags(
                        self.buffer.get_end_iter(), content, tag_obj
                    )

            last_pos = end

        if last_pos < len(text):
            self.buffer.insert(self.buffer.get_end_iter(), text[last_pos:])

    def insert_link(self, link_text, url):
        """
        Insert a clickable hyperlink into the buffer.

        Args:
            link_text (str): The display text for the link.
            url (str): The URL to open when the link is clicked.
        """
        tag_name = f"link_{abs(hash(url))}"

        # Create a new tag only if one with the same name does not already exist
        tag_table = self.buffer.get_tag_table()
        link_tag = tag_table.lookup(tag_name)
        if link_tag is None:
            link_tag = self.buffer.create_tag(
                tag_name,
                foreground="blue",
                underline=Pango.Underline.SINGLE,
            )
            setattr(link_tag, "url", url)
            setattr(link_tag, "link_id", hash(url))

        start_iter = self.buffer.get_end_iter()
        self.buffer.insert_with_tags(start_iter, link_text, link_tag)

    def insert_directory_link(self, path):
        """
        Insert a clickable directory path into the buffer.
        """
        url = f"file://{path}"
        tag_name = f"dir_{abs(hash(url))}"

        tag_table = self.buffer.get_tag_table()
        dir_tag = tag_table.lookup(tag_name)
        if dir_tag is None:
            dir_tag = self.buffer.create_tag(
                tag_name,
                foreground="purple",
                underline=Pango.Underline.SINGLE,
            )
            setattr(dir_tag, "url", url)
            setattr(dir_tag, "link_id", hash(url))
            setattr(dir_tag, "dir", True)

        self.buffer.insert_with_tags(self.buffer.get_end_iter(), path, dir_tag)

    def on_hover_link(self, widget, event):
        """
        Handles the hover event on a link in a Gtk.TextView. Changes the cursor to a "pointer"
        when hovering over a link and modifies the link color to green. Restores the normal cursor
        and removes color changes when the cursor is no longer over the link.
        """
        x, y = event.x, event.y
        success, iter_ = widget.get_iter_at_location(x, y)
        if success:
            tags = iter_.get_tags()
            for tag in tags:
                if hasattr(tag, "url"):
                    widget.get_window(Gtk.TextWindowType.TEXT).set_cursor(
                        Gdk.Cursor.new(Gdk.CursorType.HAND1)
                    )

                    start_iter = iter_.copy()
                    start_iter.backward_to_tag_toggle(tag)

                    end_iter = iter_.copy()
                    end_iter.forward_to_tag_toggle(tag)

                    self.buffer.apply_tag(self.link_hover_tag, start_iter, end_iter)
                    return

        widget.get_window(Gtk.TextWindowType.TEXT).set_cursor(
            Gdk.Cursor.new(Gdk.CursorType.ARROW)
        )
        start_iter = self.buffer.get_start_iter()
        end_iter = self.buffer.get_end_iter()
        self.buffer.remove_tag(self.link_hover_tag, start_iter, end_iter)
