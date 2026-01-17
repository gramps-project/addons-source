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
Displays the WebSearch information panel with dependency status and usage instructions.

This module creates a Markdown-based info panel in the Gramplet that reports:
- missing Python dependencies,
- local file paths (user data),
- instructions for safe customization,
- support and contact information.
"""

from translation_helper import _

from constants import (
    CONFIGS_DIR,
    CSV_DIR,
    USER_DATA_CSV_DIR,
    USER_DATA_JSON_DIR,
)
from markdown_inserter import MarkdownInserter

# Dependency flags
OPENAI_AVAILABLE = False
REQUESTS_AVAILABLE = False
QR_AVAILABLE = False

# Check for openai
try:
    import openai  # pylint: disable=import-outside-toplevel

    if hasattr(openai, "OpenAI"):
        OPENAI_AVAILABLE = True
except ImportError:
    pass

# Check for requests
try:
    import requests  # pylint: disable=import-outside-toplevel

    if hasattr(requests, "post"):
        REQUESTS_AVAILABLE = True
except ImportError:
    pass

# Check for qrcode
try:
    import qrcode  # pylint: disable=import-outside-toplevel

    if hasattr(qrcode, "make"):
        QR_AVAILABLE = True
except ImportError:
    pass


class InfoPanel:
    """Provides a Markdown-rendered info panel with system and user data status."""

    def __init__(self, ui, version):
        """Initialize the InfoPanel with the given UI namespace and version info."""
        self.ui = ui
        self.buffer = self.ui.info_textview.get_buffer()
        self.version = version
        self.markdown = MarkdownInserter(self.ui.info_textview)
        self.build()

    def build(self):
        """Build the full info panel with Markdown-formatted system information."""
        self.ui.notebook.set_tab_label_text(self.ui.textarea_container_info, "ℹ️")

        self.ui.info_textview.set_editable(False)
        self.ui.info_textview.set_cursor_visible(False)
        self.ui.info_textview.set_can_focus(True)
        self.ui.info_textview.set_focus_on_click(True)
        self.ui.info_textview.set_accepts_tab(False)
        self.ui.info_textview.set_left_margin(10)
        self.ui.info_textview.set_right_margin(10)
        self.ui.info_textview.set_top_margin(5)
        self.ui.info_textview.set_bottom_margin(5)

        self.ui.info_textview.connect(
            "motion-notify-event", self.markdown.on_hover_link
        )

        markdown_parts = []

        # --- About section
        markdown_parts.append(_("## 🧩 About WebSearch"))
        markdown_parts.append(
            _(
                "WebSearch is a Gramplet for Gramps that helps you search "
                "genealogy-related websites."
            )
        )
        markdown_parts.append(
            _(
                "It supports CSV-based link templates, AI-assisted site discovery, and "
                "direct integration with notes and attributes."
            )
        )
        markdown_parts.append("")

        # --- System info
        if not QR_AVAILABLE or not OPENAI_AVAILABLE or not REQUESTS_AVAILABLE:
            markdown_parts.append(_("## ⚙️ System Information"))

            if not QR_AVAILABLE:
                markdown_parts.append(_("🔻 **Missing:** `qrcode`"))
                markdown_parts.append(
                    _("ℹ️ This Python library is not available in your system.")
                )
                markdown_parts.append(
                    _("Without it, QR code generation will not work.")
                )
                markdown_parts.append(
                    _("💡 Usually installed with: `pip install qrcode[pil]`")
                )
                markdown_parts.append(
                    _(
                        "*Note: Some operating systems or environments may require alternative "
                        "installation methods.*"
                    )
                )
                markdown_parts.append("")

            if not OPENAI_AVAILABLE:
                markdown_parts.append(_("🔻 **Missing:** `openai`"))
                markdown_parts.append(
                    _("ℹ️ This library is required for accessing OpenAI-based features.")
                )
                markdown_parts.append(
                    _(
                        "Without it, AI-generated site suggestions and place history "
                        "will be disabled."
                    )
                )
                markdown_parts.append(
                    _("💡 Usually installed with: `pip install openai`")
                )
                markdown_parts.append(
                    _(
                        "*Note: Some operating systems or environments may require alternative "
                        "installation methods.*"
                    )
                )
                markdown_parts.append("")

            if not REQUESTS_AVAILABLE:
                markdown_parts.append(_("🔻 **Missing:** `requests`"))
                markdown_parts.append(
                    _("ℹ️ This library is used to communicate with web APIs.")
                )
                markdown_parts.append(
                    _("Without it, external data sources may not be accessible.")
                )
                markdown_parts.append(
                    _("💡 Usually installed with: `pip install requests`")
                )
                markdown_parts.append(
                    _(
                        "*Note: Some operating systems or environments may require alternative "
                        "installation methods.*"
                    )
                )
                markdown_parts.append("")

        # --- File paths section
        markdown_parts.append(_("## 📂 Data File Locations"))
        markdown_parts.append(
            _(
                "Below are the paths to system and user-defined data files used by WebSearch."
            )
        )
        markdown_parts.append("")
        markdown_parts.append(_("#### CSV File Paths"))
        markdown_parts.append(
            _("- **System path:** `{dir|%s}` – contains the built-in CSV files")
            % CSV_DIR
        )
        markdown_parts.append(
            _("- **User-defined path:** `{dir|%s}` – for custom user-defined CSV files")
            % USER_DATA_CSV_DIR
        )
        markdown_parts.append("")
        markdown_parts.append(_("#### JSON File Paths"))
        markdown_parts.append(
            _(
                "- **System path:** `{dir|%s}` – contains the built-in attribute_mapping.json file"
            )
            % CONFIGS_DIR
        )
        markdown_parts.append(
            _(
                "- **User-defined path:** `{dir|%s}` – for custom user-defined "
                "attribute_mapping.json file"
            )
            % USER_DATA_JSON_DIR
        )
        markdown_parts.append("")
        markdown_parts.append(
            _("  💡 *Tip: click any path above to open it in your file manager.*")
        )
        markdown_parts.append(
            _("📖 View detailed usage in: ")
            + "[Section 3.2. attribute_mapping.json](https://github.com/jurchello/WebSearch/"
            "blob/main/README.md#232-attribute_mappingjson--attribute-mapping-rules), "
            "[Section 6.2. User-defined CSV Files](https://github.com/jurchello/WebSearch/"
            "blob/main/README.md#262-user-defined-csv-files)"
        )
        markdown_parts.append("")

        # --- Support section
        markdown_parts.append(_("## 💬 Support"))
        markdown_parts.append(_("👤 Created and maintained by Yurii Liubymyi"))
        markdown_parts.append(
            _(
                "💬 For help or feedback, feel free to mention `@Urchello` on the Gramps forum:"
            )
        )
        markdown_parts.append(
            f"[{_('Gramps Forum (Discourse)')}](https://gramps.discourse.group/)"
        )
        markdown_parts.append("")
        markdown_parts.append(
            _("✅ Bug reports and feature requests are completely **free of charge**.")
        )
        markdown_parts.append("")
        markdown_parts.append(
            f"- [{_('GitHub Issues')}](https://github.com/jurchello/WebSearch/issues)"
        )
        markdown_parts.append(
            f"- [{_('Gramps Bug Tracker')}](https://gramps-project.org/bugs)"
        )
        markdown_parts.append("")
        markdown_parts.append(_("🧩 WebSearch Gramplet version: `%s`") % self.version)

        full_markdown = "\n".join(markdown_parts)
        self.markdown.insert_markdown(full_markdown)
