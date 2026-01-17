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
WebSearch - a Gramplet for searching genealogical websites.

Allows searching for genealogical resources based on the active person's, place's,
or source's data. Integrates multiple regional websites into a single sidebar tool
with customizable URL templates.
"""

# pylint: disable=invalid-name

# --------------------------
# Standard Python libraries
# --------------------------
from functools import partial
import json
import random
import os
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from enum import IntEnum
from types import SimpleNamespace


# --------------------------
# Third-party libraries
# --------------------------
import gi

gi.require_version("Gtk", "3.0")  # pylint: disable=wrong-import-position
from gi.repository import Gdk, GdkPixbuf, GObject, Gtk

# --------------------------
# GRAMPS API
# --------------------------
from gramps.gen.db import DbTxn
from gramps.gen.lib import Attribute, Note, NoteType, SrcAttribute
from gramps.gen.plug import Gramplet
from gramps.gui.display import display_url
from gramps.gui.editors import EditObject
from gramps.gen.errors import HandleError

# --------------------------
# Own project imports
# --------------------------
from attribute_links_loader import AttributeLinksLoader
from attribute_mapping_loader import AttributeMappingLoader
from config_ini_manager import ConfigINIManager
from constants import (
    ALL_COLUMNS_LOCALIZED,
    ALL_ICONS_LOCALIZED,
    CONFIGS_DIR,
    DB_FILE_TABLE_DIR,
    DEFAULT_AI_PROVIDER,
    DEFAULT_COLUMNS_ORDER,
    DEFAULT_DISPLAY_COLUMNS,
    DEFAULT_DISPLAY_ICONS,
    DEFAULT_ENABLED_FILES,
    DEFAULT_MIDDLE_NAME_HANDLING,
    DEFAULT_SHOW_ATTRIBUTE_LINKS,
    DEFAULT_SHOW_INTERNET_LINKS,
    DEFAULT_SHOW_NOTE_LINKS,
    DEFAULT_SHOW_SHORT_URL,
    DEFAULT_URL_COMPACTNESS_LEVEL,
    DEFAULT_URL_PREFIX_REPLACEMENT,
    DEFAULT_ENABLED_PLACE_HISTORY,
    DEFAULT_CUSTOM_COUNTRY_CODE_FOR_AI_NOTES,
    ICON_SAVED_PATH,
    ICON_SIZE,
    ICON_VISITED_PATH,
    INTERFACE_FILE_PATH,
    MIGRATIONS_DIR,
    RIGHT_MOUSE_BUTTON,
    STYLE_CSS_PATH,
    URL_SAFE_CHARS,
    USER_DATA_CSV_DIR,
    USER_DATA_JSON_DIR,
    ADMINISTRATIVE_DIVISIONS_DIR,
    VIEW_IDS_MAPPING,
    AIProviders,
    MiddleNameHandling,
    SupportedNavTypes,
    URLCompactnessLevel,
    SourceTypes,
    DBFileTables,
    HiddenLinksScope,
    SavedTo,
    ActivityType,
    DomainSuggestionStatus,
    DomainSuggestionValidationStatus,
    DomainType,
)
from models import (
    AIUrlData,
    LinkContext,
    AIDomainData,
    PlaceHistoryRequestData,
    DBFileTableConfig,
)
from entity_data_builder import EntityDataBuilder
from helpers import get_system_locale
from internet_links_loader import InternetLinksLoader
from model_row_generator import ModelRowGenerator
from note_links_loader import NoteLinksLoader
from notification import Notification
from qr_window import QRCodeWindow
from settings_ui_manager import SettingsUIManager
from signals import WebSearchSignalEmitter
from url_formatter import UrlFormatter
from website_loader import WebsiteLoader
from gramplet_version_extractor import GrampletVersionExtractor
from translation_helper import _
from markdown_inserter import MarkdownInserter
from markdown_place_history_formatter import MarkdownPlaceHistoryFormatter
from place_history_storage import PlaceHistoryStorage
from db_file_table import DBFileTable
from migration_manager import MigrationManager
from info_panel import InfoPanel
from activity_row_generator import ActivityRowGenerator
from attribute_editor_manager import AttributeEditorManager, AttributeNotFoundError
from note_editor_manager import NoteEditorManager, NoteNotFoundError

# ai/
from ai.openai_ai_client import OpenaiAIClient
from ai.mistral_ai_client import MistralAIClient
from ai.site_prompt_builder import SitePromptBuilder
from ai.site_prompt_request import SitePromptRequest
from ai.place_history_prompt_builder import PlaceHistoryPromptBuilder
from ai.place_history_request import PlaceHistoryRequest
from ai.community_prompt_builder import CommunityPromptBuilder
from ai.community_prompt_request import CommunityPromptRequest

MODEL_SCHEMA = [
    ("icon_name", str),
    ("title", str),
    ("final_url", str),
    ("comment", str),
    ("url_pattern", str),
    ("keys_json", str),
    ("formatted_url", str),
    ("visited_icon", GdkPixbuf.Pixbuf),
    ("saved_icon", GdkPixbuf.Pixbuf),
    ("nav_type", str),
    ("visited_icon_visible", bool),
    ("saved_icon_visible", bool),
    ("obj_handle", str),
    ("obj_gramps_id", str),
    ("replaced_keys_count", int),
    ("total_keys_count", int),
    ("keys_color", str),
    ("user_data_icon", GdkPixbuf.Pixbuf),
    ("user_data_icon_visible", bool),
    ("display_keys_count", bool),
    ("file_identifier_text", str),
    ("file_identifier_text_visible", bool),
    ("file_identifier_icon", GdkPixbuf.Pixbuf),
    ("file_identifier_icon_visible", bool),
    ("file_identifier_sort", str),
    ("source_type", str),
    ("country_code", str),
    ("source_file_path", str),
    ("saved_record_id", int),
    ("saved_attribute_type", str),
    ("saved_attribute_value", str),
    ("saved_to", str),
    ("visited_record_id", int),
]

ModelColumns = IntEnum(
    "ModelColumns", {name.upper(): idx for idx, (name, _) in enumerate(MODEL_SCHEMA)}
)
MODEL_TYPES = [type_ for _, type_ in MODEL_SCHEMA]

ACTIVITY_MODEL_SCHEMA = [
    ("activity_type", str),
    ("created_at", str),
    ("details", str),
]

ActivityColumns = IntEnum(
    "ActivityColumns",
    {name.upper(): idx for idx, (name, _) in enumerate(ACTIVITY_MODEL_SCHEMA)},
)
ACTIVITY_MODEL_TYPES = [type_ for _, type_ in ACTIVITY_MODEL_SCHEMA]


class WebSearch(Gramplet):
    """
    WebSearch is a Gramplet for Gramps that provides an interface to search
    genealogy-related websites. It integrates with various online resources,
    formats search URLs based on genealogical data, and allows users to track
    visited and saved links.

    Features:
    - Fetches recommended genealogy websites based on provided data.
    - Supports both predefined CSV-based links and AI-suggested links.
    - Tracks visited and saved links with icons.
    - Allows users to add links as notes or attributes in Gramps.
    - Provides a graphical interface using GTK.
    """

    def __init__(self, gui):
        """
        Initialize the WebSearch Gramplet.

        Sets up all required components, directories, signal emitters, and configuration managers.
        Also initializes the Gramplet GUI and internal context for tracking active Gramps objects.
        """
        self.finder = None
        self.entity_data_builder = None
        self.model_row_generator = None
        self.note_links_loader = None
        self._display_columns = []
        self.attribute_editor_manager = None
        self.note_editor_manager = None
        MigrationManager().migrate()
        self.version = GrampletVersionExtractor().get()
        self.make_directories()
        self.init_database_models()
        self._context = SimpleNamespace(
            person=None,
            family=None,
            place=None,
            source=None,
            active_url=None,
            active_tree_path=None,
            last_active_entity_handle=None,
            last_active_entity_type=None,
            previous_ai_site_provider=None,
            previous_ai_place_history_provider=None,
            active_place_latitude=None,
            active_place_longitude=None,
        )
        self.system_locale = get_system_locale()
        self.gui = gui

        self.builder = Gtk.Builder()
        self.builder.add_from_file(INTERFACE_FILE_PATH)
        self.ui = SimpleNamespace(
            boxes=SimpleNamespace(
                main=self.builder.get_object("main_box"),
                badges=SimpleNamespace(
                    box=self.builder.get_object("badges_box"),
                    container=self.builder.get_object("badge_container"),
                ),
            ),
            ai_recommendations_label=self.builder.get_object(
                "ai_recommendations_label"
            ),
            tree_view=self.builder.get_object("treeview"),
            activity_treeview=self.builder.get_object("activity_treeview"),
            context_menus=SimpleNamespace(
                main=SimpleNamespace(
                    menu=self.builder.get_object("main_context_menu"),
                    items=SimpleNamespace(
                        add_note=self.builder.get_object("add_note"),
                        add_attribute=self.builder.get_object("add_attribute"),
                        show_qr=self.builder.get_object("show_qr"),
                        copy_link=self.builder.get_object("copy_link"),
                        hide_selected=self.builder.get_object("hide_selected"),
                        hide_all=self.builder.get_object("hide_all"),
                        edit_attribute=self.builder.get_object("edit_attribute"),
                        edit_note=self.builder.get_object("edit_note"),
                    ),
                ),
            ),
            text_renderers=SimpleNamespace(
                file_identifier=self.builder.get_object(
                    "file_identifier_text_renderer"
                ),
                keys_replaced=self.builder.get_object("keys_replaced_renderer"),
                slash=self.builder.get_object("slash_renderer"),
                keys_total=self.builder.get_object("keys_total_renderer"),
                title=self.builder.get_object("title_renderer"),
                url=self.builder.get_object("url_renderer"),
                comment=self.builder.get_object("comment_renderer"),
                activity_type=self.builder.get_object("activity_type_renderer"),
                activity_date=self.builder.get_object("activity_date_renderer"),
                activity_details=self.builder.get_object("activity_details_renderer"),
            ),
            icon_renderers=SimpleNamespace(
                category=self.builder.get_object("category_icon_renderer"),
                visited=self.builder.get_object("visited_icon_renderer"),
                saved=self.builder.get_object("saved_icon_renderer"),
                user_data=self.builder.get_object("user_data_icon_renderer"),
                file_identifier=self.builder.get_object(
                    "file_identifier_icon_renderer"
                ),
            ),
            columns=SimpleNamespace(
                icons=self.builder.get_object("icons_column"),
                file_identifier=self.builder.get_object("file_identifier_column"),
                keys=self.builder.get_object("keys_column"),
                title=self.builder.get_object("title_column"),
                url=self.builder.get_object("url_column"),
                comment=self.builder.get_object("comment_column"),
                activity_type=self.builder.get_object("activity_type_column"),
                activity_date=self.builder.get_object("activity_date_column"),
                activity_details=self.builder.get_object("activity_details_column"),
            ),
            notebook=self.builder.get_object("notebook"),
            notes_textview=self.builder.get_object("notes_textview"),
            info_textview=self.builder.get_object("info_textview"),
            pages=SimpleNamespace(
                treeview_page=self.builder.get_object("treeview_page"),
                textarea_container=self.builder.get_object("textarea_container"),
                activity_container=self.builder.get_object("activity_container"),
                textarea_container_info=self.builder.get_object(
                    "textarea_container_info"
                ),
            ),
        )
        InfoPanel(
            SimpleNamespace(
                notebook=self.ui.notebook,
                info_textview=self.ui.info_textview,
                textarea_container_info=self.ui.pages.textarea_container_info,
            ),
            self.version,
        )

        self._columns_order = []

        self.model = Gtk.ListStore(*MODEL_TYPES)
        self.activity_model = Gtk.ListStore(*ACTIVITY_MODEL_TYPES)
        self.signal_emitter = WebSearchSignalEmitter()
        self.attribute_loader = AttributeMappingLoader()
        self.attribute_links_loader = AttributeLinksLoader()
        self.internet_links_loader = InternetLinksLoader()
        self.config_ini_manager = ConfigINIManager()
        self.settings_ui_manager = SettingsUIManager(self.config_ini_manager)
        self.website_loader = WebsiteLoader()
        self.url_formatter = UrlFormatter(self.config_ini_manager)
        Gramplet.__init__(self, gui)
        self.activity_row_generator = ActivityRowGenerator(self.activities_model)
        self.refresh_activities_tab()

    def init_database_models(self):
        """Init database models"""
        self.place_history_model = DBFileTable(
            DBFileTableConfig(
                filename=DBFileTables.PLACE_HISTORY_REQUESTS.value,
                unique_fields=["id"],
                required_fields=[
                    "event_gramps_id",
                    "event_handle",
                    "file_path",
                    "place_name",
                    "place_type",
                ],
                set_updated_at=False,
            )
        )
        self.visits_model = DBFileTable(
            DBFileTableConfig(
                filename=DBFileTables.VISITS.value,
                unique_fields=["id"],
                required_fields=[
                    "link",
                    "nav_type",
                    "obj_handle",
                    "obj_gramps_id",
                ],
            )
        )
        self.saves_model = DBFileTable(
            DBFileTableConfig(
                filename=DBFileTables.SAVES.value,
                unique_fields=["id"],
                required_fields=[
                    "link",
                    "nav_type",
                    "obj_handle",
                    "obj_gramps_id",
                    "saved_to",
                ],
            )
        )

        self.hidden_links_model = DBFileTable(
            DBFileTableConfig(
                filename=DBFileTables.HIDDEN_LINKS.value,
                unique_fields=["id"],
                required_fields=["url_pattern", "nav_type", "scope"],
            )
        )

        self.domain_suggestions_model = DBFileTable(
            DBFileTableConfig(
                filename=DBFileTables.DOMAIN_SUGGESTIONS.value,
                unique_fields=["id"],
                required_fields=["domain", "status", "validation_status"],
            )
        )

        self.activities_model = DBFileTable(
            DBFileTableConfig(
                filename=DBFileTables.ACTIVITIES.value,
                unique_fields=["id"],
                required_fields=["activity_type"],
            )
        )

    def init(self):
        """Initializes and attaches the main GTK interface to the gramplet container."""
        self.gui.WIDGET = self.build_gui()
        container = self.gui.get_container_widget()
        if self.gui.textview in container.get_children():
            container.remove(self.gui.textview)
        container.add(self.gui.WIDGET)
        self.gui.WIDGET.show_all()

    def post_init(self):
        """Initializes GUI signals and refreshes the AI section."""
        self.signal_emitter.connect("sites-fetched", self.on_sites_fetched)
        self.signal_emitter.connect(
            "place-history-fetched", self.on_place_history_fetched
        )
        self.ui.notes_textview.set_editable(False)
        self.ui.notes_textview.set_cursor_visible(False)
        self.ui.notes_textview.set_can_focus(True)
        self.ui.notes_textview.set_focus_on_click(True)
        self.ui.notes_textview.set_accepts_tab(False)
        self.ui.notes_textview.set_left_margin(10)
        self.ui.notes_textview.set_right_margin(10)
        self.ui.notes_textview.set_top_margin(5)
        self.ui.notes_textview.set_bottom_margin(5)

        self.markdown_inserter = MarkdownInserter(self.ui.notes_textview)
        self.ui.notes_textview.connect("event-after", self.on_textview_click)
        self.ui.notes_textview.connect(
            "motion-notify-event", self.markdown_inserter.on_hover_link
        )
        self.ui.notes_textview.connect("populate-popup", self.on_populate_popup, None)

        self.ui.info_textview.connect("event-after", self.on_textview_click)

        self.refresh_ai_section()

    def on_populate_popup(self, _widget, popup, _user_data):
        """Handle the populate-popup signal to add custom menu items."""
        if isinstance(popup, Gtk.Menu):
            save_coordinates_item = Gtk.MenuItem(
                label=_("Save Coordinates to the Place")
            )
            save_coordinates_item.connect("activate", self.on_save_coordinates_to_place)
            popup.append(save_coordinates_item)
            save_coordinates_item.show()

    def on_textview_click(self, widget, event):
        """Handle mouse click events on the textview"""
        if event.type == Gdk.EventType.BUTTON_RELEASE:
            x, y = int(event.x), int(event.y)
            success, text_iter = widget.get_iter_at_location(x, y)

            if not success:
                return False

            tags = text_iter.get_tags()
            for tag in tags:
                url = getattr(tag, "url", None)
                if url:
                    if event.button.button == 1:
                        if url.startswith("file://"):
                            self.open_dir(url[7:])
                        else:
                            webbrowser.open(url)
                        return True
        return False

    def open_dir(self, path):
        """Open a directory in the default file manager based on the OS."""
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])  # pylint: disable=consider-using-with
        else:
            subprocess.Popen(["xdg-open", path])  # pylint: disable=consider-using-with

    def on_save_coordinates_to_place(self, _widget):
        """
        Save the coordinates of the selected place (URL) to the place data.
        """
        if (
            self._context.active_place_latitude
            and self._context.active_place_longitude
            and self._context.place
        ):
            with DbTxn("Save coordinates to place", self.dbstate.db) as trans:
                self._context.place.set_latitude(self._context.active_place_latitude)
                self._context.place.set_longitude(self._context.active_place_longitude)
                self.dbstate.db.commit_place(self._context.place, trans)

    def refresh_ai_section(self):
        """Updates AI provider settings and fetches AI-recommended sites if necessary."""
        ai_domain_data = self.website_loader.get_domains_data(self.config_ini_manager)
        ai_url_data = self.website_loader.get_urls_data(self.config_ini_manager)

        self.toggle_badges_visibility()

        pending_domains = self.getShuffledPendingDomains()
        if len(pending_domains) >= 10:
            GObject.idle_add(
                self.signal_emitter.emit, "sites-fetched", json.dumps(pending_domains)
            )
            return

        if self._ai_provider == AIProviders.DISABLED.value:
            return

        if not self._ai_api_key:
            print("❌ Error. No AI API Key found.", file=sys.stderr)
            return

        if self._context.previous_ai_site_provider == self._ai_provider:
            return
        self._context.previous_ai_site_provider = self._ai_provider

        if self._ai_provider == AIProviders.OPENAI.value:
            self.finder = OpenaiAIClient(self._ai_api_key, self._ai_model)
        elif self._ai_provider == AIProviders.MISTRAL.value:
            self.finder = MistralAIClient(self._ai_api_key, self._ai_model)
        else:
            print(f"❌ Error. Unknown AI provider: {self._ai_provider}", file=sys.stderr)
            return

        threading.Thread(
            target=self.fetch_sites_in_background,
            args=(
                ai_domain_data,
                ai_url_data,
            ),
            daemon=True,
        ).start()

    def getShuffledPendingDomains(self):
        """
        Return up to 10 pending domain suggestions with non-empty domain and URL, in random order.
        """
        records = (
            self.domain_suggestions_model.query()
            .where("status", DomainSuggestionStatus.PENDING.value)
            .get()
        )

        pending_domains = []
        for r in records:
            domain = r.get("domain")
            url = r.get("url")
            domain_type = r.get("domain_type")
            if domain and url and domain_type:
                pending_domains.append(
                    {
                        "domain": domain.strip(),
                        "url": url.strip(),
                        "domain_type": domain_type,
                    }
                )

        random.shuffle(pending_domains)
        return pending_domains[:10]

    def refresh_place_history_section(self, place_history_request_data):
        """Refreshes the section displaying the historical administrative data for a place."""

        place_history_record = self.place_history_model.first_by_field(
            "event_handle", place_history_request_data.handle
        )
        if place_history_record:
            results = PlaceHistoryStorage().load_results_from_file(place_history_record)
            if results and results != {}:
                (
                    self._context.active_place_latitude,
                    self._context.active_place_longitude,
                ) = self.get_coordinates(results)
                formatted_text = MarkdownPlaceHistoryFormatter().format(
                    results, place_history_request_data, place_history_record
                )
                GObject.idle_add(
                    self.signal_emitter.emit, "place-history-fetched", formatted_text
                )
                return

        if self._ai_provider == AIProviders.DISABLED.value:
            self.update_message_in_ai_notes(_("AI provider is disabled"))
            return

        if not self._ai_api_key:
            self.update_message_in_ai_notes(_("No AI API key provided"))
            print("❌ Error. No AI API Key found.", file=sys.stderr)
            return

        if not self._enabled_place_history:
            self.update_message_in_ai_notes(
                _("AI-generated historical place data is currently disabled")
            )
            return

        if self._ai_provider == AIProviders.OPENAI.value:
            self.finder = OpenaiAIClient(self._ai_api_key, self._ai_model)
        elif self._ai_provider == AIProviders.MISTRAL.value:
            self.finder = MistralAIClient(self._ai_api_key, self._ai_model)
        else:
            error_message = _(
                "AI provider is unknown. Please check your AI provider settings."
            )
            self.update_message_in_ai_notes(error_message)
            print(
                f"⚠ Unknown AI provider: {self._ai_provider}. {error_message}",
                file=sys.stderr,
            )
            return

        self.show_loading_message_in_notes()

        threading.Thread(
            target=self.fetch_place_history_in_background,
            args=(place_history_request_data,),
            daemon=True,
        ).start()

    def show_loading_message_in_notes(self):
        """Displays a loading message in the notes text view."""
        self.update_message_in_ai_notes(
            _("⏳ Generating historical place data, please wait...")
        )

    def update_message_in_ai_notes(self, text):
        """Updates the message displayed in the AI notes section of the UI."""
        buffer = self.ui.notes_textview.get_buffer()
        buffer.set_text(text)

    def make_directories(self):
        """Creates necessary directories for storing configurations and user data."""
        for directory in [
            CONFIGS_DIR,
            USER_DATA_CSV_DIR,
            USER_DATA_JSON_DIR,
            ADMINISTRATIVE_DIVISIONS_DIR,
            DB_FILE_TABLE_DIR,
            MIGRATIONS_DIR,
            ADMINISTRATIVE_DIVISIONS_DIR,
        ]:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)

    def fetch_sites_in_background(
        self, ai_domain_data: AIDomainData, ai_url_data: AIUrlData
    ):
        """Fetches AI-recommended genealogy sites in a background thread."""
        try:
            ai_domain_data.skipped_domains = set(
                self.domain_suggestions_model.query()
                .where("domain_type", DomainType.RESOURCE.value)
                .all_values_list("domain")
            )
            site_prompt_builder = SitePromptBuilder()
            site_request = SitePromptRequest(ai_domain_data, site_prompt_builder)
            site_results = self.finder.request(site_request)
            self.save_ai_domain_suggestions(site_results, DomainType.RESOURCE.value)
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"❌ Error fetching RESOURCE sites: {e}", file=sys.stderr)

        try:
            ai_url_data.skipped_urls = set(
                self.domain_suggestions_model.query()
                .where("domain_type", DomainType.COMMUNITY.value)
                .all_values_list("url")
            )
            community_prompt_builder = CommunityPromptBuilder()
            community_request = CommunityPromptRequest(
                ai_url_data, community_prompt_builder
            )
            community_results = self.finder.request(community_request)
            self.save_ai_domain_suggestions(
                community_results, DomainType.COMMUNITY.value
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"❌ Error fetching COMMUNITY sites: {e}", file=sys.stderr)

        pending_domains = self.getShuffledPendingDomains()
        if len(pending_domains) == 0:
            return

        GObject.idle_add(
            self.signal_emitter.emit, "sites-fetched", json.dumps(pending_domains)
        )

    def save_ai_domain_suggestions(self, results, domain_type):
        """Save AI-generated domain suggestions to the table with PENDING status."""
        saved_results = []

        existing_domains = {
            d.lower()
            for d in self.domain_suggestions_model.query().all_values_list("domain")
        }

        for r in results:
            domain = r.get("domain", "").strip().lower()
            url = r.get("url", "").strip()

            if not domain or not url:
                continue

            if domain in existing_domains:
                continue

            self.domain_suggestions_model.create(
                {
                    "domain": domain,
                    "url": url,
                    "status": DomainSuggestionStatus.PENDING.value,
                    "validation_status": DomainSuggestionValidationStatus.NOT_CHECKED.value,
                    "domain_type": domain_type,
                }
            )
            saved_results.append({"domain": domain, "url": url})

        return saved_results

    def fetch_place_history_in_background(self, place_history_request_data):
        """Fetches historical place data using AI in a background thread."""
        try:
            prompt_builder = PlaceHistoryPromptBuilder()
            request = PlaceHistoryRequest(place_history_request_data, prompt_builder)
            results = self.finder.request(request)
            if results and results != {}:

                (
                    self._context.active_place_latitude,
                    self._context.active_place_longitude,
                ) = self.get_coordinates(results)
                filename = (
                    f"{place_history_request_data.gramps_id}_"
                    f"{place_history_request_data.handle}.json"
                )
                place_history_record = self.place_history_model.create(
                    {
                        "event_gramps_id": place_history_request_data.gramps_id,
                        "event_handle": place_history_request_data.handle,
                        "file_path": os.path.join(
                            ADMINISTRATIVE_DIVISIONS_DIR, filename
                        ),
                        "place_name": place_history_request_data.name,
                        "place_type": results.get("place_type", None),
                        "latitude": self._context.active_place_latitude,
                        "longitude": self._context.active_place_longitude,
                    }
                )

                self.activities_model.create(
                    {
                        "event_gramps_id": place_history_request_data.gramps_id,
                        "event_handle": place_history_request_data.handle,
                        "file_path": os.path.join(
                            ADMINISTRATIVE_DIVISIONS_DIR, filename
                        ),
                        "activity_type": ActivityType.PLACE_HISTORY_LOAD.value,
                    }
                )
                self.refresh_activities_tab()

                PlaceHistoryStorage().save_results_to_file(
                    place_history_record, results
                )
                formatted_text = MarkdownPlaceHistoryFormatter().format(
                    results, place_history_request_data, place_history_record
                )
                GObject.idle_add(
                    self.signal_emitter.emit, "place-history-fetched", formatted_text
                )

        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"❌ Error fetching place history: {e}", file=sys.stderr)
            GObject.idle_add(
                self.signal_emitter.emit,
                "place-history-fetched",
                "⚠ Error while generating AI content.",
            )

    def get_coordinates(self, results):
        """
        Extracts latitude and longitude from the provided results.
        """
        location_info = results.get("location_info", None)

        if location_info is None:
            return None, None

        latitude = location_info.get("latitude")
        longitude = location_info.get("longitude")

        if latitude in [None, ""]:
            latitude = None
        if longitude in [None, ""]:
            longitude = None

        return latitude, longitude

    def on_place_history_fetched(self, unused_gramplet, text: str):
        """
        Handles the 'place-history-fetched' signal and updates the notes view.
        """
        self.update_notes_textview(text)

    def update_notes_textview(self, text: str):
        """Updates the notes textview in the UI thread."""
        self.markdown_inserter.insert_markdown(text)

    def on_sites_fetched(self, unused_gramplet, results):
        """
        Handles the 'sites-fetched' signal and populates badges if valid results are received.
        """
        if results:
            try:
                sites = json.loads(results)
                if not isinstance(sites, list):
                    return
                pending_domains = [
                    (
                        site.get("domain", "").strip(),
                        site.get("url", "").strip(),
                        site.get("domain_type", DomainType.RESOURCE.value),
                    )
                    for site in sites
                    if site.get("domain") and site.get("url")
                ]
                if pending_domains:
                    self.populate_badges(pending_domains)
            except json.JSONDecodeError as e:
                print(f"❌ Error. JSON Decode Error: {e}", file=sys.stderr)
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"❌ Error. Error processing sites: {e}", file=sys.stderr)

    def db_changed(self):
        """Responds to changes in the database and updates the active context accordingly."""
        self.attribute_editor_manager = AttributeEditorManager(
            self.dbstate, self.gui.uistate, self.activities_model
        )
        self.note_editor_manager = NoteEditorManager(
            self.dbstate, self.gui.uistate, self.activities_model
        )
        self.entity_data_builder = EntityDataBuilder(
            self.dbstate, self.config_ini_manager
        )
        self.model_row_generator = ModelRowGenerator(
            SimpleNamespace(
                website_loader=self.website_loader,
                url_formatter=self.url_formatter,
                attribute_loader=self.attribute_loader,
                config_ini_manager=self.config_ini_manager,
                visits_model=self.visits_model,
                saves_model=self.saves_model,
                hidden_links_model=self.hidden_links_model,
                activities_model=self.activities_model,
            )
        )
        self.note_links_loader = NoteLinksLoader(self.dbstate.db)

        # Connect signals for all supported types
        for key, handler in {
            "Person": self.active_person_changed,
            "Place": self.active_place_changed,
            "Source": self.active_source_changed,
            "Family": self.active_family_changed,
            "Event": self.active_event_changed,
            "Citation": self.active_citation_changed,
            "Media": self.active_media_changed,
            "Note": self.active_note_changed,
            "Repository": self.active_repository_changed,
        }.items():
            self.connect_signal(key, handler)

        # Determine which handle is currently active
        handle_map = {
            SupportedNavTypes.PEOPLE.value: self.gui.uistate.get_active("Person"),
            SupportedNavTypes.PLACES.value: self.gui.uistate.get_active("Place"),
            SupportedNavTypes.SOURCES.value: self.gui.uistate.get_active("Source"),
            SupportedNavTypes.FAMILIES.value: self.gui.uistate.get_active("Family"),
            SupportedNavTypes.EVENTS.value: self.gui.uistate.get_active("Event"),
            SupportedNavTypes.CITATIONS.value: self.gui.uistate.get_active("Citation"),
            SupportedNavTypes.MEDIA.value: self.gui.uistate.get_active("Media"),
            SupportedNavTypes.NOTES.value: self.gui.uistate.get_active("Note"),
            SupportedNavTypes.REPOSITORIES.value: self.gui.uistate.get_active(
                "Repository"
            ),
        }

        for nav_type, handle in handle_map.items():
            if handle:
                self.refresh_main_treeview_tab(nav_type, handle)
                break

        notebook = self.gui.uistate.viewmanager.notebook
        if notebook:
            notebook.connect("switch-page", self.on_category_changed)

    def refresh_main_treeview_tab(self, nav_type, obj_handle):
        """Dispatch refresh logic depending on entity type."""
        dispatcher = {
            SupportedNavTypes.PEOPLE.value: self.active_person_changed,
            SupportedNavTypes.PLACES.value: self.active_place_changed,
            SupportedNavTypes.SOURCES.value: self.active_source_changed,
            SupportedNavTypes.FAMILIES.value: self.active_family_changed,
            SupportedNavTypes.EVENTS.value: self.active_event_changed,
            SupportedNavTypes.CITATIONS.value: self.active_citation_changed,
            SupportedNavTypes.MEDIA.value: self.active_media_changed,
            SupportedNavTypes.NOTES.value: self.active_note_changed,
            SupportedNavTypes.REPOSITORIES.value: self.active_repository_changed,
        }

        handler = dispatcher.get(nav_type)
        if handler:
            handler(obj_handle)

    def on_category_changed(self, unused_notebook, unused_page, page_num, *unused_args):
        """Handle changes in the selected category and update the context."""
        try:
            page_lookup = self.gui.uistate.viewmanager.page_lookup
            for (cat_num, view_num), p_num in page_lookup.items():
                if p_num == page_num:
                    views = self.gui.uistate.viewmanager.views
                    view_id = views[cat_num][view_num][0].id
                    nav_type = VIEW_IDS_MAPPING.get(view_id, None)
                    if nav_type:
                        self._context.last_active_entity_type = nav_type
                        self._context.last_active_entity_handle = (
                            self.gui.uistate.get_active(nav_type)
                        )
                        self.call_entity_changed_method()
                    else:
                        self.model.clear()
                    break
        except Exception:  # pylint: disable=broad-exception-caught
            self.model.clear()

    def populate_links(self, core_keys, attribute_keys, nav_type, obj):
        """Populates the list model with formatted website links relevant to the current entity."""
        self.model.clear()

        context = LinkContext(
            core_keys=core_keys,
            attribute_keys=attribute_keys,
            nav_type=nav_type,
            obj=obj,
        )

        websites = self.collect_all_websites(context)
        self.insert_websites_into_model(websites, context)

    def refresh_activities_tab(self):
        """Refreshes the activity log model with the latest 1000 activity records."""
        self.activity_model.clear()

        records = self.activity_row_generator.generate_rows()
        for model_row in records:
            if model_row:
                self.activity_model.append(
                    [model_row[name] for name, _ in ACTIVITY_MODEL_SCHEMA]
                )

    def collect_all_websites(self, ctx):
        """Returns a combined list of all applicable websites for the given entity context."""
        websites = self.website_loader.load_websites(self.config_ini_manager)

        if self._show_attribute_links:
            websites += self.attribute_links_loader.get_links_from_attributes(
                ctx.obj, ctx.nav_type
            )

        if self._show_internet_links and ctx.nav_type in [
            SupportedNavTypes.PEOPLE.value,
            SupportedNavTypes.PLACES.value,
            SupportedNavTypes.REPOSITORIES.value,
        ]:
            websites += self.internet_links_loader.get_links_from_internet_objects(
                ctx.obj, ctx.nav_type
            )

        if self._show_note_links:
            websites += self.note_links_loader.get_links_from_notes(
                ctx.obj, ctx.nav_type
            )

        return websites

    def insert_websites_into_model(self, websites, link_context: LinkContext):
        """Formats each website entry and appends it to the Gtk model."""
        for website_data in websites:
            model_row = self.model_row_generator.generate(link_context, website_data)
            if model_row:
                self.model.append([model_row[name] for name, _ in MODEL_SCHEMA])

    def on_link_clicked(self, unused_tree_view, path, unused_column):
        """Handles the event when a URL is clicked in the tree view and opens the link."""
        tree_iter = self.model.get_iter(path)
        url = self.model.get_value(tree_iter, ModelColumns.FINAL_URL.value)

        if url.startswith("gramps://"):
            self.open_internal_link(url)
        else:
            encoded_url = urllib.parse.quote(url, safe=URL_SAFE_CHARS)
            display_url(encoded_url)

        self.add_icon_event(
            SimpleNamespace(
                icon_path=ICON_VISITED_PATH,
                tree_iter=tree_iter,
                model_icon_pos=ModelColumns.VISITED_ICON.value,
                model_visibility_pos=ModelColumns.VISITED_ICON_VISIBLE.value,
                model=self.visits_model,
                saved_to=None,
            )
        )

    def open_internal_link(self, url):
        """Opens internal Gramps link using EditObject."""
        try:
            if url.startswith("gramps://"):
                obj_class, prop, value = url[9:].split("/")
                EditObject(self.dbstate, self.gui.uistate, [], obj_class, prop, value)
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"❌ Error when open the internal link: {url} - {e}")

    def add_icon_event(self, settings):
        """Adds a visual icon to the model and saves the hash when a link is clicked."""
        icon_path = settings.icon_path
        tree_iter = settings.tree_iter
        model = settings.model
        model_icon_pos = settings.model_icon_pos
        model_visibility_pos = settings.model_visibility_pos
        saved_to = settings.saved_to
        url = self.model.get_value(tree_iter, ModelColumns.FINAL_URL.value)
        nav_type = self.model.get_value(tree_iter, ModelColumns.NAV_TYPE.value)
        obj_handle = self.model.get_value(tree_iter, ModelColumns.OBJ_HANDLE.value)
        obj_gramps_id = self.model.get_value(
            tree_iter, ModelColumns.OBJ_GRAMPS_ID.value
        )
        source_file_path = self.model.get_value(
            tree_iter, ModelColumns.SOURCE_FILE_PATH.value
        )

        if (
            not model.query()
            .where("link", url)
            .where("obj_handle", obj_handle)
            .exists()
        ):

            data = {
                "link": url,
                "nav_type": nav_type,
                "obj_handle": obj_handle,
                "obj_gramps_id": obj_gramps_id,
                "source_file_path": source_file_path,
            }

            if saved_to:

                activity_data = dict(data)
                data["saved_to"] = saved_to

                if saved_to == SavedTo.NOTE.value:
                    activity_data["activity_type"] = (
                        ActivityType.LINK_SAVE_TO_NOTE.value
                    )
                    activity_data["note_gramps_id"] = settings.note_gramps_id
                    activity_data["note_handle"] = settings.note_handle
                    data["note_gramps_id"] = settings.note_gramps_id
                    data["note_handle"] = settings.note_handle
                elif saved_to == SavedTo.ATTRIBUTE.value:
                    activity_data["activity_type"] = (
                        ActivityType.LINK_SAVE_TO_ATTRIBUTE.value
                    )
                    data["attribute_type"] = settings.attribute_type
                    data["attribute_value"] = settings.attribute_value
                    activity_data["attribute_type"] = settings.attribute_type
                    activity_data["attribute_value"] = settings.attribute_value

                record = model.create(data)
                activity_data["saves_record_id"] = record.get("id")
                self.activities_model.create(activity_data)
                self.refresh_activities_tab()

            else:
                record = model.create(data)
                activity_data = dict(data)
                activity_data["activity_type"] = ActivityType.LINK_VISIT.value
                activity_data["visits_record_id"] = record.get("id")
                self.activities_model.create(activity_data)
                self.refresh_activities_tab()

            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    icon_path, ICON_SIZE, ICON_SIZE
                )
                self.model.set_value(tree_iter, model_icon_pos, pixbuf)
                self.model.set_value(tree_iter, model_visibility_pos, True)
                self.ui.columns.icons.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
                self.ui.columns.icons.set_fixed_width(-1)
                self.ui.columns.icons.queue_resize()
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"❌ Error loading icon: {e}", file=sys.stderr)

    def active_person_changed(self, handle):
        """Handles updates when the active person changes in the GUI."""
        self._context.last_active_entity_handle = handle
        self._context.last_active_entity_type = "Person"
        self.close_main_context_menu()

        if handle is None:
            self.model.clear()
            return

        person = self.dbstate.db.get_person_from_handle(handle)
        self._context.person = person
        if not person:
            self.model.clear()
            return

        person_data, attribute_keys = self.entity_data_builder.get_person_data(person)
        self.populate_links(
            person_data, attribute_keys, SupportedNavTypes.PEOPLE.value, person
        )
        self.update()

    def active_event_changed(self, handle):
        """Handles updates when the active event changes in the GUI."""
        self._context.last_active_entity_handle = handle
        self._context.last_active_entity_type = "Event"
        self.close_main_context_menu()

        if handle is None:
            self.model.clear()
            return

        event = self.dbstate.db.get_event_from_handle(handle)
        self._context.event = event
        if not event:
            self.model.clear()
            return

        self.populate_links({}, {}, SupportedNavTypes.EVENTS.value, event)
        self.update()

    def active_citation_changed(self, handle):
        """Handles updates when the active citation changes in the GUI."""
        self._context.last_active_entity_handle = handle
        self._context.last_active_entity_type = "Citation"
        self.close_main_context_menu()

        if handle is None:
            self.model.clear()
            return

        citation = self.dbstate.db.get_citation_from_handle(handle)
        self._context.citation = citation
        if not citation:
            self.model.clear()
            return

        self.populate_links({}, {}, SupportedNavTypes.CITATIONS.value, citation)
        self.update()

    def active_media_changed(self, handle):
        """Handles updates when the active media changes in the GUI."""
        self._context.last_active_entity_handle = handle
        self._context.last_active_entity_type = "Media"
        self.close_main_context_menu()

        if handle is None:
            self.model.clear()
            return

        media = self.dbstate.db.get_media_from_handle(handle)
        self._context.media = media
        if not media:
            self.model.clear()
            return

        self.populate_links({}, {}, SupportedNavTypes.MEDIA.value, media)
        self.update()

    def active_note_changed(self, handle):
        """Handles updates when the active note changes in the GUI."""
        self._context.last_active_entity_handle = handle
        self._context.last_active_entity_type = "Note"
        self.close_main_context_menu()

        if handle is None:
            self.model.clear()
            return

        note = self.dbstate.db.get_note_from_handle(handle)
        self._context.note = note
        if not note:
            self.model.clear()
            return

        self.populate_links({}, {}, SupportedNavTypes.NOTES.value, note)
        self.update()

    def active_repository_changed(self, handle):
        """Handles updates when the active repository changes in the GUI."""
        self._context.last_active_entity_handle = handle
        self._context.last_active_entity_type = "Repository"
        self.close_main_context_menu()

        if handle is None:
            self.model.clear()
            return

        repository = self.dbstate.db.get_repository_from_handle(handle)
        self._context.repository = repository
        if not repository:
            self.model.clear()
            return

        self.populate_links({}, {}, SupportedNavTypes.REPOSITORIES.value, repository)
        self.update()

    def active_place_changed(self, handle):
        """Handles updates when the active place changes in the GUI."""
        self._context.last_active_entity_handle = handle
        self._context.last_active_entity_type = "Place"

        if handle is None:
            self.model.clear()
            return

        place = self.dbstate.db.get_place_from_handle(handle)
        self._context.place = place
        if not place:
            self.model.clear()
            return

        place_data = self.entity_data_builder.get_place_data(place)
        self.populate_links(place_data, {}, SupportedNavTypes.PLACES.value, place)
        self.update()

        self.refresh_place_history_section(
            PlaceHistoryRequestData(
                name=place_data["place"],
                full_hierarchy=place_data["title"],
                language=self._custom_country_code_for_ai_notes or place_data["locale"],
                latitude=place_data["latitude"],
                longitude=place_data["longitude"],
                handle=handle,
                gramps_id=place.get_gramps_id(),
            )
        )

    def active_source_changed(self, handle):
        """Handles updates when the active source changes in the GUI."""
        self._context.last_active_entity_handle = handle
        self._context.last_active_entity_type = "Source"

        if handle is None:
            self.model.clear()
            return

        source = self.dbstate.db.get_source_from_handle(handle)
        self._context.source = source
        if not source:
            self.model.clear()
            return

        source_data = self.entity_data_builder.get_source_data(source)
        self.populate_links(source_data, {}, SupportedNavTypes.SOURCES.value, source)
        self.update()

    def active_family_changed(self, handle):
        """Handles updates when the active family changes in the GUI."""
        self._context.last_active_entity_handle = handle
        self._context.last_active_entity_type = "Family"

        if handle is None:
            self.model.clear()
            return

        family = self.dbstate.db.get_family_from_handle(handle)
        self._context.family = family
        if not family:
            self.model.clear()
            return

        family_data = self.entity_data_builder.get_family_data(family)
        self.populate_links(family_data, {}, SupportedNavTypes.FAMILIES.value, family)
        self.update()

    def close_main_context_menu(self):
        """Closes the main context menu if it is currently visible."""
        if (
            self.ui.context_menus.main.menu
            and self.ui.context_menus.main.menu.get_visible()
        ):
            self.ui.context_menus.main.menu.hide()

    def build_gui(self):
        """Constructs and returns the full GTK UI for the WebSearch Gramplet."""

        self.builder.connect_signals(self)

        # Create and set the ListStore model
        self.ui.tree_view.set_model(self.model)
        self.ui.tree_view.set_has_tooltip(True)

        # Get selection object
        selection = self.ui.tree_view.get_selection()
        selection.set_mode(Gtk.SelectionMode.SINGLE)

        # Connect signals
        self.ui.tree_view.connect("row-activated", self.on_link_clicked)
        self.ui.tree_view.connect("query-tooltip", self.on_query_tooltip)
        self.ui.tree_view.connect("button-press-event", self.on_button_press)
        self.ui.tree_view.connect("columns-changed", self.on_column_changed)

        # Columns reordering
        for column in self.ui.tree_view.get_columns():
            column.set_reorderable(True)

        # Columns sorting
        self.add_sorting(
            self.ui.columns.file_identifier, ModelColumns.FILE_IDENTIFIER_SORT.value
        )
        self.add_sorting(self.ui.columns.title, ModelColumns.TITLE.value)
        self.add_sorting(self.ui.columns.url, ModelColumns.FORMATTED_URL.value)
        self.add_sorting(self.ui.columns.comment, ModelColumns.COMMENT.value)

        # Columns rendering
        self.ui.columns.icons.add_attribute(
            self.ui.icon_renderers.category, "icon-name", ModelColumns.ICON_NAME.value
        )
        self.ui.columns.icons.add_attribute(
            self.ui.icon_renderers.visited, "pixbuf", ModelColumns.VISITED_ICON.value
        )
        self.ui.columns.icons.add_attribute(
            self.ui.icon_renderers.visited,
            "visible",
            ModelColumns.VISITED_ICON_VISIBLE.value,
        )
        self.ui.columns.icons.add_attribute(
            self.ui.icon_renderers.saved, "pixbuf", ModelColumns.SAVED_ICON.value
        )
        self.ui.columns.icons.add_attribute(
            self.ui.icon_renderers.saved,
            "visible",
            ModelColumns.SAVED_ICON_VISIBLE.value,
        )
        self.ui.columns.icons.add_attribute(
            self.ui.icon_renderers.user_data,
            "pixbuf",
            ModelColumns.USER_DATA_ICON.value,
        )
        self.ui.columns.icons.add_attribute(
            self.ui.icon_renderers.user_data,
            "visible",
            ModelColumns.USER_DATA_ICON_VISIBLE.value,
        )
        self.ui.columns.keys.add_attribute(
            self.ui.text_renderers.keys_replaced,
            "text",
            ModelColumns.REPLACED_KEYS_COUNT.value,
        )
        self.ui.columns.keys.add_attribute(
            self.ui.text_renderers.keys_total,
            "text",
            ModelColumns.TOTAL_KEYS_COUNT.value,
        )
        self.ui.columns.keys.add_attribute(
            self.ui.text_renderers.keys_replaced,
            "foreground",
            ModelColumns.KEYS_COLOR.value,
        )
        self.ui.columns.keys.add_attribute(
            self.ui.text_renderers.keys_replaced,
            "visible",
            ModelColumns.DISPLAY_KEYS_COUNT.value,
        )
        self.ui.columns.keys.add_attribute(
            self.ui.text_renderers.keys_total,
            "visible",
            ModelColumns.DISPLAY_KEYS_COUNT.value,
        )
        self.ui.columns.keys.add_attribute(
            self.ui.text_renderers.slash,
            "visible",
            ModelColumns.DISPLAY_KEYS_COUNT.value,
        )
        self.ui.text_renderers.keys_total.set_property("foreground", "green")
        self.ui.columns.file_identifier.add_attribute(
            self.ui.text_renderers.file_identifier,
            "text",
            ModelColumns.FILE_IDENTIFIER_TEXT.value,
        )
        self.ui.columns.file_identifier.add_attribute(
            self.ui.text_renderers.file_identifier,
            "visible",
            ModelColumns.FILE_IDENTIFIER_TEXT_VISIBLE.value,
        )
        self.ui.columns.file_identifier.add_attribute(
            self.ui.icon_renderers.file_identifier,
            "pixbuf",
            ModelColumns.FILE_IDENTIFIER_ICON.value,
        )
        self.ui.columns.file_identifier.add_attribute(
            self.ui.icon_renderers.file_identifier,
            "visible",
            ModelColumns.FILE_IDENTIFIER_ICON_VISIBLE.value,
        )
        self.ui.columns.title.add_attribute(
            self.ui.text_renderers.title, "text", ModelColumns.TITLE.value
        )
        self.ui.columns.url.add_attribute(
            self.ui.text_renderers.url, "text", ModelColumns.FORMATTED_URL.value
        )
        self.ui.columns.comment.add_attribute(
            self.ui.text_renderers.comment, "text", ModelColumns.COMMENT.value
        )

        # CSS styles, translate, update
        self.apply_styles()
        self.translate()
        self.update_columns_visibility()
        self.reorder_columns()

        # Setup activity log view
        self.ui.activity_treeview.set_model(self.activity_model)
        self.ui.activity_treeview.set_headers_visible(True)

        self.ui.columns.activity_type.add_attribute(
            self.ui.text_renderers.activity_type,
            "text",
            ActivityColumns.ACTIVITY_TYPE.value,
        )
        self.ui.columns.activity_date.add_attribute(
            self.ui.text_renderers.activity_date,
            "text",
            ActivityColumns.CREATED_AT.value,
        )
        self.ui.columns.activity_details.add_attribute(
            self.ui.text_renderers.activity_details,
            "text",
            ActivityColumns.DETAILS.value,
        )

        self.ui.notebook.set_tab_label_text(self.ui.pages.activity_container, "📜")

        return self.ui.boxes.main

    def reorder_columns(self):
        """Reorders the treeview columns based on user configuration."""
        self._columns_order = self.config_ini_manager.get_list(
            "websearch.columns_order", DEFAULT_COLUMNS_ORDER
        )

        columns_map = self.ui.columns
        previous_column = None

        for column_id in self._columns_order:
            column = getattr(columns_map, column_id, None)
            if column:
                current_pos = self.ui.tree_view.get_columns().index(column)
                expected_pos = self._columns_order.index(column_id)
                if current_pos != expected_pos:
                    self.ui.tree_view.move_column_after(column, previous_column)
                previous_column = column

    def on_column_changed(self, tree_view):
        """Saves the current order of columns when changed by the user."""
        columns = tree_view.get_columns()
        column_map = {v: k for k, v in self.ui.columns.__dict__.items()}
        columns_order = [column_map[col] for col in columns]
        self.config_ini_manager.set_list("websearch.columns_order", columns_order)

    def update_columns_visibility(self):
        """Updates columns visibility."""
        self._display_columns = self.config_ini_manager.get_list(
            "websearch.display_columns", DEFAULT_DISPLAY_COLUMNS
        )
        self.ui.columns.icons.set_visible("icons" in self._display_columns)
        self.ui.columns.file_identifier.set_visible(
            "file_identifier" in self._display_columns
        )
        self.ui.columns.keys.set_visible("keys" in self._display_columns)
        self.ui.columns.title.set_visible("title" in self._display_columns)
        self.ui.columns.url.set_visible("url" in self._display_columns)
        self.ui.columns.comment.set_visible("comment" in self._display_columns)

    def translate(self):
        """Sets translated text for UI elements and context menu."""
        self.ui.notebook.set_tab_label_text(self.ui.pages.treeview_page, "🔗")
        self.ui.notebook.set_tab_label_text(self.ui.pages.textarea_container, "🧠")

        self.ui.columns.file_identifier.set_title("")
        self.ui.columns.keys.set_title(_("Keys"))
        self.ui.columns.title.set_title(_("Title"))
        self.ui.columns.url.set_title(_("Website URL"))
        self.ui.columns.comment.set_title(_("Comment"))

        self.ui.context_menus.main.items.add_note.set_label(_("Add link to note"))
        self.ui.context_menus.main.items.add_attribute.set_label(
            _("Add link to attribute")
        )
        self.ui.context_menus.main.items.show_qr.set_label(_("Show QR-code"))
        self.ui.context_menus.main.items.copy_link.set_label(
            _("Copy link to clipboard")
        )
        self.ui.context_menus.main.items.hide_selected.set_label(
            _("Hide link for selected item")
        )
        self.ui.context_menus.main.items.hide_all.set_label(
            _("Hide link for all items")
        )

        self.ui.context_menus.main.items.edit_attribute.set_label(
            _("Edit Attribute with the Link")
        )

        self.ui.context_menus.main.items.edit_note.set_label(
            _("Edit Note with the Link")
        )

        self.ui.ai_recommendations_label.set_text(_("🔍 AI Suggestions"))

    def toggle_badges_visibility(self):
        """Shows or hides the badge container based on OpenAI usage."""
        if self._ai_provider != AIProviders.DISABLED.value:
            self.ui.boxes.badges.box.show()
        else:
            self.ui.boxes.badges.box.hide()

    def add_sorting(self, column, index):
        """Enables sorting for the specified column."""
        column.set_sort_column_id(index)
        self.model.set_sort_column_id(index, Gtk.SortType.ASCENDING)

    def apply_styles(self):
        """Applies custom CSS styling to the WebSearch interface."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_path(STYLE_CSS_PATH)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def populate_badges(self, pending_domains):
        """Displays AI-suggested site badges in the interface."""
        self.ui.boxes.badges.container.foreach(self.remove_widget)
        for domain, url, domain_type in pending_domains:
            badge = self.create_badge(domain, url, domain_type)
            self.ui.boxes.badges.container.add(badge)
        self.ui.boxes.badges.container.show_all()

    def remove_widget(self, widget):
        """Removes a widget from the container."""
        self.ui.boxes.badges.container.remove(widget)

    def create_badge(self, domain, url, domain_type):
        """Creates a clickable badge widget for an AI-suggested domain."""
        badge_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        badge_box.get_style_context().add_class("badge")

        if domain_type == DomainType.COMMUNITY.value:
            badge_box.get_style_context().add_class("badge-community")
        elif domain_type == DomainType.RESOURCE.value:
            badge_box.get_style_context().add_class("badge-resource")

        label = Gtk.Label(label=domain)
        label.get_style_context().add_class("badge-label")

        close_button = Gtk.Button(label="×")
        close_button.set_relief(Gtk.ReliefStyle.NONE)
        close_button.set_focus_on_click(False)
        close_button.set_size_request(16, 16)
        close_button.get_style_context().add_class("badge-close")
        close_button.connect("clicked", self.on_remove_badge, badge_box)

        event_box = Gtk.EventBox()
        event_box.add(label)
        event_box.connect("button-press-event", self.on_button_press_event, url)

        badge_box.pack_start(event_box, True, True, 0)
        badge_box.pack_start(close_button, False, False, 0)

        return badge_box

    def on_button_press_event(self, unused_widget, unused_event, url):
        """Handles button press event to open a URL."""
        self.open_url(url)

    def open_url(self, url):
        """Opens the given URL in the default web browser."""
        webbrowser.open(urllib.parse.quote(url, safe=URL_SAFE_CHARS))

    def on_remove_badge(self, unused_button, badge):
        """Handles removing a badge and saving its domain to skipped list."""
        domain_label = None
        for child in badge.get_children():
            if isinstance(child, Gtk.EventBox):
                for sub_child in child.get_children():
                    if isinstance(sub_child, Gtk.Label):
                        domain_label = sub_child.get_text().strip()
                        break
        if domain_label:
            self.mark_domain_as_skipped(domain_label)

            self.refresh_activities_tab()
        self.ui.boxes.badges.container.remove(badge)

    def mark_domain_as_skipped(self, domain: str):
        """Mark an existing domain suggestion as skipped, if it exists."""
        records = self.domain_suggestions_model.query().where("domain", domain).get()

        if not records:
            return

        for record in records:

            if record.get("status") == DomainSuggestionStatus.SKIPPED.value:
                continue

            self.domain_suggestions_model.update(
                record["id"], {"status": DomainSuggestionStatus.SKIPPED.value}
            )

            self.activities_model.create(
                {
                    "domain": domain,
                    "activity_type": ActivityType.DOMAIN_SKIP.value,
                }
            )

    def on_button_press(self, widget, event):
        """Handles right-click context menu activation in the treeview."""
        if event.button == RIGHT_MOUSE_BUTTON:
            path_info = widget.get_path_at_pos(event.x, event.y)
            if path_info:
                path, unused_column, unused_cell_x, unused_cell_y = path_info
                tree_iter = self.model.get_iter(path)
                if not tree_iter or not self.model.iter_is_valid(tree_iter):
                    return
                url = self.model.get_value(tree_iter, ModelColumns.FINAL_URL.value)
                nav_type = self.model.get_value(tree_iter, ModelColumns.NAV_TYPE.value)
                source_type = self.model.get_value(
                    tree_iter, ModelColumns.SOURCE_TYPE.value
                )
                saved_icon_visible = self.model.get_value(
                    tree_iter, ModelColumns.SAVED_ICON_VISIBLE.value
                )

                self._context.active_tree_path = path
                self._context.active_url = url
                self.ui.context_menus.main.menu.show_all()

                if (
                    nav_type
                    in [
                        SupportedNavTypes.PEOPLE.value,
                        SupportedNavTypes.FAMILIES.value,
                        SupportedNavTypes.EVENTS.value,
                        SupportedNavTypes.MEDIA.value,
                        SupportedNavTypes.SOURCES.value,
                        SupportedNavTypes.CITATIONS.value,
                        SupportedNavTypes.REPOSITORIES.value,
                        SupportedNavTypes.PLACES.value,
                    ]
                    and source_type != SourceTypes.NOTE.value
                    and not saved_icon_visible
                ):
                    self.ui.context_menus.main.items.add_note.show()
                else:
                    self.ui.context_menus.main.items.add_note.hide()

                if (
                    nav_type
                    in [
                        SupportedNavTypes.PEOPLE.value,
                        SupportedNavTypes.FAMILIES.value,
                        SupportedNavTypes.EVENTS.value,
                        SupportedNavTypes.MEDIA.value,
                        SupportedNavTypes.SOURCES.value,
                        SupportedNavTypes.CITATIONS.value,
                    ]
                    and source_type != SourceTypes.ATTRIBUTE.value
                    and not saved_icon_visible
                ):
                    self.ui.context_menus.main.items.add_attribute.show()
                else:
                    self.ui.context_menus.main.items.add_attribute.hide()

                # attributes
                saved_type = self.model.get_value(
                    tree_iter, ModelColumns.SAVED_ATTRIBUTE_TYPE.value
                )
                saved_value = self.model.get_value(
                    tree_iter, ModelColumns.SAVED_ATTRIBUTE_VALUE.value
                )
                if saved_type and saved_value:
                    self.ui.context_menus.main.items.edit_attribute.show()
                else:
                    self.ui.context_menus.main.items.edit_attribute.hide()

                # notes
                saved_to = self.model.get_value(tree_iter, ModelColumns.SAVED_TO.value)
                if saved_to == SavedTo.NOTE.value:
                    self.ui.context_menus.main.items.edit_note.show()
                else:
                    self.ui.context_menus.main.items.edit_note.hide()

                self.ui.context_menus.main.menu.popup_at_pointer(event)

    def on_edit_attribute(self, unused_widget):
        """Opens the attribute editor for the saved attribute."""
        path = self._context.active_tree_path
        tree_iter = self.get_active_tree_iter(path)
        nav_type = self.model.get_value(tree_iter, ModelColumns.NAV_TYPE.value)
        obj_handle = self.model.get_value(tree_iter, ModelColumns.OBJ_HANDLE.value)
        saved_record_id = self.model.get_value(
            tree_iter, ModelColumns.SAVED_RECORD_ID.value
        )
        attr_type = self.model.get_value(
            tree_iter, ModelColumns.SAVED_ATTRIBUTE_TYPE.value
        )
        attr_value = self.model.get_value(
            tree_iter, ModelColumns.SAVED_ATTRIBUTE_VALUE.value
        )
        try:
            self.attribute_editor_manager.edit_by_obj_handle_and_attr_name(
                SimpleNamespace(
                    nav_type=nav_type,
                    obj_handle=obj_handle,
                    attr_type=attr_type,
                    attr_value=attr_value,
                    callback=partial(
                        self.on_attribute_updated_via_editor_manager, saved_record_id
                    ),
                )
            )
        except AttributeNotFoundError:
            self.show_notification(
                _("Attribute no longer exists. The extra icon is removed")
            )
            if saved_record_id:
                self.saves_model.query().where("id", saved_record_id).delete()
            self.refresh_main_treeview_tab(nav_type, obj_handle)

    def on_attribute_updated_via_editor_manager(self, saved_record_id, result):
        """
        Callback method invoked after the attribute editor is closed and an attribute is updated.
        """
        unused_attr_obj, name, value = result
        if saved_record_id:
            record = self.saves_model.read_by_id(saved_record_id)
            record["attribute_type"] = name
            record["attribute_value"] = value
            self.saves_model.update(saved_record_id, record)
            nav_type = record.get("nav_type")
            obj_handle = record.get("obj_handle")
            self.refresh_main_treeview_tab(nav_type, obj_handle)
            self.refresh_activities_tab()

    def on_edit_note(self, unused_widget):
        """Opens the note editor for the saved note."""
        path = self._context.active_tree_path
        tree_iter = self.get_active_tree_iter(path)
        nav_type = self.model.get_value(tree_iter, ModelColumns.NAV_TYPE.value)
        obj_handle = self.model.get_value(tree_iter, ModelColumns.OBJ_HANDLE.value)
        saved_record_id = self.model.get_value(
            tree_iter, ModelColumns.SAVED_RECORD_ID.value
        )
        record = self.saves_model.read_by_id(saved_record_id)
        if not record:
            return
        try:
            self.note_editor_manager.edit_by_obj_handle_and_note_handle(
                SimpleNamespace(
                    nav_type=nav_type,
                    obj_handle=obj_handle,
                    note_handle=record.get("note_handle", ""),
                    callback=partial(
                        self.on_note_updated_via_editor_manager, saved_record_id
                    ),
                )
            )
        except NoteNotFoundError:
            self.show_notification(
                _("Note no longer exists. The extra icon is removed")
            )
            if saved_record_id:
                self.saves_model.query().where("id", saved_record_id).delete()
            self.refresh_main_treeview_tab(nav_type, obj_handle)

    def on_note_updated_via_editor_manager(self, saved_record_id):
        """
        Callback method invoked after the note editor is closed and a note is updated.
        """
        if saved_record_id:
            record = self.saves_model.read_by_id(saved_record_id)
            self.saves_model.update(saved_record_id, record)
            self.refresh_activities_tab()

    def on_add_note(self, unused_widget):
        """Adds the current selected URL as a note to the person record."""
        if not self._context.active_tree_path:
            print("❌ Error: No saved path to the iterator!", file=sys.stderr)
            return

        note = Note()
        tree_iter = self.get_active_tree_iter(self._context.active_tree_path)
        note.set(
            _(
                "📌 This '{title}' web link was archived for future reference by the "
                "WebSearch gramplet (v. {version}):\n\n"
                "🔗 {url}\n\n"
                "You can use this link to revisit the source and verify the information "
                "related to this entity."
            ).format(
                title=self.model.get_value(tree_iter, ModelColumns.TITLE.value),
                version=self.version,
                url=self._context.active_url,
            )
        )

        note.set_privacy(True)
        nav_type = self.model.get_value(tree_iter, ModelColumns.NAV_TYPE.value)
        note_handle = None

        with DbTxn("Add Web Link Note", self.dbstate.db) as trans:
            if nav_type == SupportedNavTypes.PEOPLE.value:
                note.set_type(NoteType.PERSON)
                note_handle = self.dbstate.db.add_note(note, trans)
                self._context.person.add_note(note_handle)
                self.dbstate.db.commit_person(self._context.person, trans)

            elif nav_type == SupportedNavTypes.FAMILIES.value:
                note.set_type(NoteType.FAMILY)
                note_handle = self.dbstate.db.add_note(note, trans)
                self._context.family.add_note(note_handle)
                self.dbstate.db.commit_family(self._context.family, trans)

            elif nav_type == SupportedNavTypes.EVENTS.value:
                note.set_type(NoteType.EVENT)
                note_handle = self.dbstate.db.add_note(note, trans)
                self._context.event.add_note(note_handle)
                self.dbstate.db.commit_event(self._context.event, trans)

            elif nav_type == SupportedNavTypes.PLACES.value:
                note.set_type(NoteType.PLACE)
                note_handle = self.dbstate.db.add_note(note, trans)
                self._context.place.add_note(note_handle)
                self.dbstate.db.commit_place(self._context.place, trans)

            elif nav_type == SupportedNavTypes.SOURCES.value:
                note.set_type(NoteType.SOURCE)
                note_handle = self.dbstate.db.add_note(note, trans)
                self._context.source.add_note(note_handle)
                self.dbstate.db.commit_source(self._context.source, trans)

            elif nav_type == SupportedNavTypes.CITATIONS.value:
                note.set_type(NoteType.CITATION)
                note_handle = self.dbstate.db.add_note(note, trans)
                self._context.citation.add_note(note_handle)
                self.dbstate.db.commit_citation(self._context.citation, trans)

            elif nav_type == SupportedNavTypes.REPOSITORIES.value:
                note.set_type(NoteType.REPO)
                note_handle = self.dbstate.db.add_note(note, trans)
                self._context.repository.add_note(note_handle)
                self.dbstate.db.commit_repository(self._context.repository, trans)

            elif nav_type == SupportedNavTypes.MEDIA.value:
                note.set_type(NoteType.MEDIA)
                note_handle = self.dbstate.db.add_note(note, trans)
                self._context.media.add_note(note_handle)
                self.dbstate.db.commit_media(self._context.media, trans)

        tree_iter = self.get_active_tree_iter(self._context.active_tree_path)
        self.add_icon_event(
            SimpleNamespace(
                icon_path=ICON_SAVED_PATH,
                tree_iter=tree_iter,
                model_icon_pos=ModelColumns.SAVED_ICON.value,
                model_visibility_pos=ModelColumns.SAVED_ICON_VISIBLE.value,
                model=self.saves_model,
                note_handle=note_handle,
                note_gramps_id=note.get_gramps_id(),
                saved_to=SavedTo.NOTE.value,
            )
        )

        handle = self.model.get_value(tree_iter, ModelColumns.OBJ_HANDLE.value)
        self.refresh_main_treeview_tab(nav_type, handle)

        try:
            note_obj = self.dbstate.db.get_note_from_handle(note_handle)
            note_gramps_id = note_obj.get_gramps_id()
            self.show_notification(
                _("Note #%(id)s has been successfully added") % {"id": note_gramps_id}
            )
        except Exception:  # pylint: disable=broad-exception-caught
            self.show_notification(_("Error creating note"))

    def on_show_qr_code(self, unused_widget):
        """Opens a window showing the QR code for the selected URL."""
        selection = self.ui.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            url = model[tree_iter][ModelColumns.FINAL_URL.value]
            qr_window = QRCodeWindow(url)
            qr_window.show_all()

    def on_copy_url_to_clipboard(self, unused_widget):
        """Copies the selected URL to the system clipboard."""
        selection = self.ui.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            url = model[tree_iter][ModelColumns.FINAL_URL.value]
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(url, -1)
            clipboard.store()
            self.show_notification(_("URL is copied to the Clipboard"))

    def on_hide_link_for_selected_item(self, unused_widget):
        """Hides the selected link only for the current Gramps object."""
        selection = self.ui.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            url_pattern = model[tree_iter][ModelColumns.URL_PATTERN.value]
            obj_handle = model[tree_iter][ModelColumns.OBJ_HANDLE.value]
            obj_gramps_id = model[tree_iter][ModelColumns.OBJ_GRAMPS_ID.value]
            nav_type = model[tree_iter][ModelColumns.NAV_TYPE.value]
            if not (  # pylint: disable=duplicate-code
                self.hidden_links_model.query()
                .where("url_pattern", url_pattern)
                .where("obj_handle", obj_handle)
                .where("nav_type", nav_type)
                .where("scope", HiddenLinksScope.OBJECT.value)
                .exists()
            ):
                self.hidden_links_model.create(
                    {
                        "url_pattern": url_pattern,
                        "obj_handle": obj_handle,
                        "obj_gramps_id": obj_gramps_id,
                        "nav_type": nav_type,
                        "scope": HiddenLinksScope.OBJECT.value,
                    }
                )
                self.activities_model.create(
                    {
                        "url_pattern": url_pattern,
                        "nav_type": nav_type,
                        "obj_handle": obj_handle,
                        "obj_gramps_id": obj_gramps_id,
                        "activity_type": ActivityType.HIDE_LINK_FOR_OBJECT.value,
                    }
                )
                self.refresh_activities_tab()
            model.remove(tree_iter)

    def on_hide_link_for_all_items(self, unused_widget):
        """Hides the selected link for all Gramps objects."""
        selection = self.ui.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            url_pattern = model[tree_iter][ModelColumns.URL_PATTERN.value]
            nav_type = model[tree_iter][ModelColumns.NAV_TYPE.value]
            if not (  # pylint: disable=duplicate-code
                self.hidden_links_model.query()
                .where("url_pattern", url_pattern)
                .where("nav_type", nav_type)
                .where("scope", HiddenLinksScope.ALL.value)
                .exists()
            ):
                self.hidden_links_model.create(
                    {
                        "url_pattern": url_pattern,
                        "obj_handle": None,
                        "nav_type": nav_type,
                        "scope": HiddenLinksScope.ALL.value,
                    }
                )
                self.activities_model.create(
                    {
                        "url_pattern": url_pattern,
                        "nav_type": nav_type,
                        "activity_type": ActivityType.HIDE_LINK_FOR_ALL.value,
                    }
                )
                self.refresh_activities_tab()
            model.remove(tree_iter)

    def show_notification(self, message):
        """Displays a floating notification with the given message."""
        notification = Notification(message)
        notification.show_all()
        return notification

    def get_active_tree_iter(self, path):
        """Returns the tree iter for the given tree path."""
        path_str = str(path)
        try:
            tree_path = Gtk.TreePath.new_from_string(path_str)
            self.ui.tree_view.get_selection().select_path(tree_path)
            self.ui.tree_view.set_cursor(tree_path)
            tree_iter = self.model.get_iter(tree_path)
            return tree_iter
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"❌ Error in get_active_tree_iter: {e}", file=sys.stderr)
            return None

    def on_add_attribute(self, unused_widget):
        """(Unused) Adds the selected URL as an attribute to the person."""
        if not self._context.active_tree_path:
            print("❌ Error. No saved path to the iterator!", file=sys.stderr)
            return

        tree_iter = self.get_active_tree_iter(self._context.active_tree_path)
        nav_type = self.model.get_value(tree_iter, ModelColumns.NAV_TYPE.value)

        attribute = None

        if nav_type in [
            SupportedNavTypes.PEOPLE.value,
            SupportedNavTypes.FAMILIES.value,
            SupportedNavTypes.EVENTS.value,
            SupportedNavTypes.MEDIA.value,
        ]:
            attribute = Attribute()

        if nav_type in [
            SupportedNavTypes.SOURCES.value,
            SupportedNavTypes.CITATIONS.value,
        ]:
            attribute = SrcAttribute()

        if not attribute:
            return

        attribute_type = _("WebSearch Link")
        attribute_value = self._context.active_url
        attribute.set_type(attribute_type)
        attribute.set_value(attribute_value)
        attribute.set_privacy(True)

        with DbTxn("Add Web Link Attribute", self.dbstate.db) as trans:
            if nav_type == SupportedNavTypes.PEOPLE.value:
                self._context.person.add_attribute(attribute)
                self.dbstate.db.commit_person(self._context.person, trans)
            elif nav_type == SupportedNavTypes.FAMILIES.value:
                self._context.family.add_attribute(attribute)
                self.dbstate.db.commit_family(self._context.family, trans)
            elif nav_type == SupportedNavTypes.EVENTS.value:
                self._context.event.add_attribute(attribute)
                self.dbstate.db.commit_event(self._context.event, trans)
            elif nav_type == SupportedNavTypes.MEDIA.value:
                self._context.media.add_attribute(attribute)
                self.dbstate.db.commit_media(self._context.media, trans)
            elif nav_type == SupportedNavTypes.SOURCES.value:
                self._context.source.add_attribute(attribute)
                self.dbstate.db.commit_source(self._context.source, trans)
            elif nav_type == SupportedNavTypes.CITATIONS.value:
                self._context.citation.add_attribute(attribute)
                self.dbstate.db.commit_citation(self._context.citation, trans)
            else:
                return

        tree_iter = self.get_active_tree_iter(self._context.active_tree_path)
        self.add_icon_event(
            SimpleNamespace(
                icon_path=ICON_SAVED_PATH,
                tree_iter=tree_iter,
                model_icon_pos=ModelColumns.SAVED_ICON.value,
                model_visibility_pos=ModelColumns.SAVED_ICON_VISIBLE.value,
                model=self.saves_model,
                saved_to=SavedTo.ATTRIBUTE.value,
                attribute_type=attribute_type,
                attribute_value=attribute_value,
            )
        )

        self.show_notification(_("Attribute has been successfully added"))

        handle = self.model.get_value(tree_iter, ModelColumns.OBJ_HANDLE.value)
        self.refresh_main_treeview_tab(nav_type, handle)

    def on_query_tooltip(self, widget, x, y, unused_keyboard_mode, tooltip):
        """Displays a tooltip with key and comment information."""
        bin_x, bin_y = widget.convert_widget_to_bin_window_coords(x, y)
        path_info = widget.get_path_at_pos(bin_x, bin_y)

        if path_info:
            path, *_ = path_info
            tree_iter = self.model.get_iter(path)
            tooltip_text = self._build_tooltip_text(tree_iter)
            tooltip.set_text(tooltip_text)
            return True
        return False

    def _build_tooltip_text(self, tree_iter):
        """Builds the tooltip text from a model row."""
        title = self.model.get_value(tree_iter, ModelColumns.TITLE.value)
        comment = self.model.get_value(tree_iter, ModelColumns.COMMENT.value) or ""
        keys_json = self.model.get_value(tree_iter, ModelColumns.KEYS_JSON.value)
        keys = json.loads(keys_json)

        replaced_keys = [
            f"{key}={value}"
            for var in keys["replaced_keys"]
            for key, value in var.items()
        ]
        empty_keys = list(keys["empty_keys"])

        tooltip_lines = [_("Title: {title}").format(title=title)]

        if replaced_keys:
            tooltip_lines.append(
                _("Replaced: {keys}").format(keys=", ".join(replaced_keys))
            )
        if empty_keys:
            tooltip_lines.append(_("Empty: {keys}").format(keys=", ".join(empty_keys)))
        if comment:
            tooltip_lines.append(_("Comment: {comment}").format(comment=comment))

        return "\n".join(tooltip_lines)

    def build_options(self):
        """Builds the list of configurable options for the Gramplet."""
        self.opts = self.settings_ui_manager.build_options()
        list(map(self.add_option, self.opts))

    def save_options(self):
        """Saves the current state of the configuration options."""
        self.config_ini_manager.set_boolean_list(
            "websearch.enabled_files", self.opts[0].get_selected()
        )
        self.config_ini_manager.set_enum(
            "websearch.middle_name_handling", self.opts[1].get_value()
        )
        self.config_ini_manager.set_boolean_option(
            "websearch.show_short_url", self.opts[2].get_value()
        )
        self.config_ini_manager.set_enum(
            "websearch.url_compactness_level", self.opts[3].get_value()
        )
        self.config_ini_manager.set_string(
            "websearch.url_prefix_replacement", self.opts[4].get_value()
        )
        self.config_ini_manager.set_enum(
            "websearch.ai_provider", self.opts[5].get_value()
        )
        self.config_ini_manager.set_string(
            "websearch.openai_api_key", self.opts[6].get_value()
        )
        self.config_ini_manager.set_string(
            "websearch.openai_model", self.opts[7].get_value()
        )
        self.config_ini_manager.set_string(
            "websearch.mistral_api_key", self.opts[8].get_value()
        )
        self.config_ini_manager.set_string(
            "websearch.mistral_model", self.opts[9].get_value()
        )
        self.config_ini_manager.set_boolean_option(
            "websearch.show_attribute_links", self.opts[10].get_value()
        )
        self.config_ini_manager.set_boolean_option(
            "websearch.show_internet_links", self.opts[11].get_value()
        )
        self.config_ini_manager.set_boolean_option(
            "websearch.show_note_links", self.opts[12].get_value()
        )

        selected_labels = self.opts[13].get_selected()
        selected_columns = [
            key
            for key, label in ALL_COLUMNS_LOCALIZED.items()
            if label in selected_labels
        ]
        self.config_ini_manager.set_boolean_list(
            "websearch.display_columns", selected_columns
        )

        selected_labels = self.opts[14].get_selected()
        selected_icons = [
            key
            for key, label in ALL_ICONS_LOCALIZED.items()
            if label in selected_labels
        ]
        self.config_ini_manager.set_boolean_list(
            "websearch.display_icons", selected_icons
        )

        self.config_ini_manager.set_boolean_option(
            "websearch.enabled_place_history", self.opts[15].get_value()
        )
        self.config_ini_manager.set_string(
            "websearch.custom_country_code_for_ai_notes", self.opts[16].get_value()
        )

        self.config_ini_manager.save()

    def save_update_options(self, obj):
        """Saves configuration options and refreshes the Gramplet view."""
        self.save_options()
        self.update()
        self.on_load()
        self.update_columns_visibility()
        self.call_entity_changed_method()
        self.refresh_ai_section()

    def call_entity_changed_method(self):
        """Calls the entity changed method based on the last active entity type."""
        entity_type = self._context.last_active_entity_type.lower()
        method_name = f"active_{entity_type}_changed"
        method = getattr(self, method_name, None)
        if self._context.last_active_entity_handle is None:
            return
        if method is not None and callable(method):
            try:
                method(self._context.last_active_entity_handle)  # pylint: disable=E1102
            except HandleError as e:
                print(f"❌ Error. {e}")
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"❌ Error. {e}", file=sys.stderr)
        else:
            print(f"❌ Method '{method_name}' not found or not callable")

    def on_load(self):
        """Loads all persistent WebSearch configuration settings."""
        self._enabled_files = self.config_ini_manager.get_list(
            "websearch.enabled_files", DEFAULT_ENABLED_FILES
        )
        self._ai_provider = self.load_ai_provider()

        self._openai_api_key = self.config_ini_manager.get_string(
            "websearch.openai_api_key", ""
        )
        self._openai_model = self.config_ini_manager.get_string(
            "websearch.openai_model", ""
        )

        self._mistral_api_key = self.config_ini_manager.get_string(
            "websearch.mistral_api_key", ""
        )
        self._mistral_model = self.config_ini_manager.get_string(
            "websearch.mistral_model", ""
        )

        if self._ai_provider == AIProviders.OPENAI.value:
            self._ai_api_key = self._openai_api_key
            self._ai_model = self._openai_model
        if self._ai_provider == AIProviders.MISTRAL.value:
            self._ai_api_key = self._mistral_api_key
            self._ai_model = self._mistral_model
        elif self._ai_provider == AIProviders.DISABLED.value:
            self._ai_api_key = ""
            self._ai_model = ""

        self._middle_name_handling = self.config_ini_manager.get_enum(
            "websearch.middle_name_handling",
            MiddleNameHandling,
            DEFAULT_MIDDLE_NAME_HANDLING,
        )
        self._show_short_url = self.config_ini_manager.get_boolean_option(
            "websearch.show_short_url", DEFAULT_SHOW_SHORT_URL
        )
        self._url_compactness_level = self.config_ini_manager.get_enum(
            "websearch.url_compactness_level",
            URLCompactnessLevel,
            DEFAULT_URL_COMPACTNESS_LEVEL,
        )
        self._url_prefix_replacement = self.config_ini_manager.get_string(
            "websearch.url_prefix_replacement", DEFAULT_URL_PREFIX_REPLACEMENT
        )
        self._show_attribute_links = self.config_ini_manager.get_boolean_option(
            "websearch.show_attribute_links", DEFAULT_SHOW_ATTRIBUTE_LINKS
        )
        self._show_internet_links = self.config_ini_manager.get_boolean_option(
            "websearch.show_internet_links", DEFAULT_SHOW_INTERNET_LINKS
        )
        self._show_note_links = self.config_ini_manager.get_boolean_option(
            "websearch.show_note_links", DEFAULT_SHOW_NOTE_LINKS
        )
        self._columns_order = self.config_ini_manager.get_list(
            "websearch.columns_order", DEFAULT_COLUMNS_ORDER
        )
        self._display_columns = self.config_ini_manager.get_list(
            "websearch.display_columns", DEFAULT_DISPLAY_COLUMNS
        )
        self._display_icons = self.config_ini_manager.get_list(
            "websearch.display_icons", DEFAULT_DISPLAY_ICONS
        )
        self._enabled_place_history = self.config_ini_manager.get_boolean_option(
            "websearch.enabled_place_history", DEFAULT_ENABLED_PLACE_HISTORY
        )
        self._custom_country_code_for_ai_notes = self.config_ini_manager.get_string(
            "websearch.custom_country_code_for_ai_notes",
            DEFAULT_CUSTOM_COUNTRY_CODE_FOR_AI_NOTES,
        )

    def load_ai_provider(self):
        """Load the configured AI provider from the settings."""
        return self.config_ini_manager.get_enum(
            "websearch.ai_provider",
            AIProviders,
            DEFAULT_AI_PROVIDER,
        )
