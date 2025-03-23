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

# Standard Python libraries
import os
import sys
import json
import traceback
import threading
import webbrowser
import urllib.parse
from enum import IntEnum
from types import SimpleNamespace

# Third-party libraries
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GObject

# GRAMPS API
from gramps.gen.plug import Gramplet
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gui.display import display_url
from gramps.gen.lib import Note, Attribute, Date
from gramps.gen.db import DbTxn
from gramps.gen.lib.eventtype import EventType
from gramps.gen.lib.placetype import PlaceType

# Own project imports
from qr_window import QRCodeWindow
from site_finder import SiteFinder
from config_ini_manager import ConfigINIManager
from settings_ui_manager import SettingsUIManager
from website_loader import WebsiteLoader
from notification import Notification
from signals import WebSearchSignalEmitter
from url_formatter import UrlFormatter
from attribute_mapping_loader import AttributeMappingLoader
from attribute_links_loader import AttributeLinksLoader
from constants import (
    DEFAULT_SHOW_SHORT_URL,
    DEFAULT_URL_COMPACTNESS_LEVEL,
    DEFAULT_URL_PREFIX_REPLACEMENT,
    DEFAULT_USE_OPEN_AI,
    CATEGORY_ICON,
    DEFAULT_CATEGORY_ICON,
    HIDDEN_HASH_FILE_PATH,
    USER_DATA_CSV_DIR,
    USER_DATA_JSON_DIR,
    DATA_DIR,
    CONFIGS_DIR,
    DEFAULT_ENABLED_FILES,
    DEFAULT_MIDDLE_NAME_HANDLING,
    ICON_EARTH_PATH,
    ICON_PIN_PATH,
    ICON_CHAIN_PATH,
    ICON_UID_PATH,
    UID_ICON_WIDTH,
    UID_ICON_HEIGHT,
    ICON_USER_DATA_PATH,
    ICON_VISITED_PATH,
    ICON_SAVED_PATH,
    FLAGS_DIR,
    VISITED_HASH_FILE_PATH,
    SAVED_HASH_FILE_PATH,
    URL_SAFE_CHARS,
    ICON_SIZE,
    INTERFACE_FILE_PATH,
    RIGHT_MOUSE_BUTTON,
    STYLE_CSS_PATH,
    DEFAULT_COLUMNS_ORDER,
    DEFAULT_SHOW_URL_COLUMN,
    DEFAULT_SHOW_VARS_COLUMN,
    DEFAULT_SHOW_USER_DATA_ICON,
    DEFAULT_SHOW_FLAG_ICONS,
    DEFAULT_SHOW_ATTRIBUTE_LINKS,
    URLCompactnessLevel,
    MiddleNameHandling,
    PersonDataKeys,
    FamilyDataKeys,
    PlaceDataKeys,
    SourceDataKeys,
    SupportedNavTypes,
)

MODEL_SCHEMA = [
    ("icon_name", str),
    ("locale_text", str),
    ("title", str),
    ("final_url", str),
    ("comment", str),
    ("url_pattern", str),
    ("variables_json", str),
    ("formatted_url", str),
    ("visited_icon", GdkPixbuf.Pixbuf),
    ("saved_icon", GdkPixbuf.Pixbuf),
    ("uid_icon", GdkPixbuf.Pixbuf),
    ("uid_visible", bool),
    ("nav_type", str),
    ("visited_icon_visible", bool),
    ("saved_icon_visible", bool),
    ("obj_handle", str),
    ("replaced_vars_count", int),
    ("total_vars_count", int),
    ("vars_color", str),
    ("user_data_icon", GdkPixbuf.Pixbuf),
    ("user_data_icon_visible", bool),
    ("locale_icon", GdkPixbuf.Pixbuf),
    ("locale_icon_visible", bool),
    ("locale_text_visible", bool),
]

ModelColumns = IntEnum(
    "ModelColumns", {name.upper(): idx for idx, (name, _) in enumerate(MODEL_SCHEMA)}
)
MODEL_TYPES = [type_ for _, type_ in MODEL_SCHEMA]

from translation_helper import _


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

    __gsignals__ = {"sites-fetched": (GObject.SignalFlags.RUN_FIRST, None, (object,))}

    def __init__(self, gui):
        """
        Initialize the WebSearch Gramplet.

        Sets up all required components, directories, signal emitters, and configuration managers.
        Also initializes the Gramplet GUI and internal context for tracking active Gramps objects.
        """
        self._context = SimpleNamespace(
            person=None,
            family=None,
            place=None,
            source=None,
            active_url=None,
            active_tree_path=None,
        )
        self.system_locale = (
            glocale.language[0]
            if isinstance(glocale.language, list)
            else glocale.language
        )
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
            context_menu=self.builder.get_object("context_menu"),
            context_menu_items=SimpleNamespace(
                add_note=self.builder.get_object("add_note"),
                show_qr=self.builder.get_object("show_qr"),
                copy_link=self.builder.get_object("copy_link"),
                hide_selected=self.builder.get_object("hide_selected"),
                hide_all=self.builder.get_object("hide_all"),
            ),
            text_renderers=SimpleNamespace(
                locale=self.builder.get_object("locale_text_renderer"),
                vars_replaced=self.builder.get_object("vars_replaced_renderer"),
                slash=self.builder.get_object("slash_renderer"),
                vars_total=self.builder.get_object("vars_total_renderer"),
                title=self.builder.get_object("title_renderer"),
                url=self.builder.get_object("url_renderer"),
                comment=self.builder.get_object("comment_renderer"),
            ),
            icon_renderers=SimpleNamespace(
                category=self.builder.get_object("category_icon_renderer"),
                visited=self.builder.get_object("visited_icon_renderer"),
                saved=self.builder.get_object("saved_icon_renderer"),
                uid=self.builder.get_object("uid_icon_renderer"),
                user_data=self.builder.get_object("user_data_icon_renderer"),
                locale=self.builder.get_object("locale_icon_renderer"),
            ),
            columns=SimpleNamespace(
                icons=self.builder.get_object("icons_column"),
                locale=self.builder.get_object("locale_column"),
                vars=self.builder.get_object("vars_column"),
                title=self.builder.get_object("title_column"),
                url=self.builder.get_object("url_column"),
                comment=self.builder.get_object("comment_column"),
            ),
        )

        self._columns_order = []
        self._show_url_column = False
        self._show_vars_column = False

        self.model = Gtk.ListStore(*MODEL_TYPES)

        self.make_directories()
        self.signal_emitter = WebSearchSignalEmitter()
        self.attribute_loader = AttributeMappingLoader()
        self.attribute_links_loader = AttributeLinksLoader()
        self.config_ini_manager = ConfigINIManager()
        self.settings_ui_manager = SettingsUIManager(self.config_ini_manager)
        self.website_loader = WebsiteLoader()
        self.url_formatter = UrlFormatter(self.config_ini_manager)
        Gramplet.__init__(self, gui)

    def init(self):
        """Initializes and attaches the main GTK interface to the gramplet container."""
        self.gui.WIDGET = self.build_gui()
        container = self.gui.get_container_widget()
        if self.gui.textview in container.get_children():
            container.remove(self.gui.textview)
        container.add(self.gui.WIDGET)
        self.gui.WIDGET.show_all()

    def post_init(self):
        """
        Performs additional setup after the GUI is initialized, including optional
        AI site fetching.
        """
        self.signal_emitter.connect("sites-fetched", self.on_sites_fetched)
        locales, domains, include_global = self.website_loader.get_domains_data(
            self.config_ini_manager
        )
        if not self._use_openai:
            self.toggle_badges_visibility()
            return
        if not self._openai_api_key:
            print("❌ ERROR: No OpenAI API Key found.", file=sys.stderr)
            self.toggle_badges_visibility()
            return
        self.finder = SiteFinder(self._openai_api_key)
        threading.Thread(
            target=self.fetch_sites_in_background,
            args=(domains, locales, include_global),
            daemon=True,
        ).start()

    def make_directories(self):
        """Creates necessary directories for storing configurations and user data."""
        for directory in [DATA_DIR, CONFIGS_DIR, USER_DATA_CSV_DIR, USER_DATA_JSON_DIR]:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)

    def fetch_sites_in_background(self, csv_domains, locales, include_global):
        """Fetches AI-recommended genealogy sites in a background thread."""
        skipped_domains = self.website_loader.load_skipped_domains()
        all_excluded_domains = csv_domains.union(skipped_domains)
        try:
            results = self.finder.find_sites(
                all_excluded_domains, locales, include_global
            )
            GObject.idle_add(self.signal_emitter.emit, "sites-fetched", results)
        except Exception as e:
            print(f"❌ Error fetching sites: {e}", file=sys.stderr)
            GObject.idle_add(self.signal_emitter.emit, "sites-fetched", None)

    def on_sites_fetched(self, gramplet, results):
        """
        Handles the 'sites-fetched' signal and populates badges if valid results are received.
        """
        if results:
            try:
                sites = json.loads(results)
                if not isinstance(sites, list):
                    return
                domain_url_pairs = [
                    (site.get("domain", "").strip(), site.get("url", "").strip())
                    for site in sites
                    if site.get("domain") and site.get("url")
                ]
                if domain_url_pairs:
                    self.populate_badges(domain_url_pairs)
            except json.JSONDecodeError as e:
                print(f"❌ JSON Decode Error: {e}", file=sys.stderr)
            except Exception as e:
                print(f"❌ Error processing sites: {e}", file=sys.stderr)

    def db_changed(self):
        """Responds to changes in the database and updates the active context accordingly."""
        self.connect_signal("Person", self.active_person_changed)
        self.connect_signal("Place", self.active_place_changed)
        self.connect_signal("Source", self.active_source_changed)
        self.connect_signal("Family", self.active_family_changed)
        self.connect_signal("Event", self.active_event_changed)
        self.connect_signal("Citation", self.active_citation_changed)
        self.connect_signal("Media", self.active_media_changed)

        active_person_handle = self.gui.uistate.get_active("Person")
        active_place_handle = self.gui.uistate.get_active("Place")
        active_source_handle = self.gui.uistate.get_active("Source")
        active_family_handle = self.gui.uistate.get_active("Family")
        active_event_handle = self.gui.uistate.get_active("Event")
        active_citation_handle = self.gui.uistate.get_active("Citation")
        active_media_handle = self.gui.uistate.get_active("Media")

        if active_person_handle:
            self.active_person_changed(active_person_handle)
        elif active_place_handle:
            self.active_place_changed(active_place_handle)
        elif active_source_handle:
            self.active_source_changed(active_source_handle)
        elif active_family_handle:
            self.active_family_changed(active_family_handle)
        elif active_event_handle:
            self.active_event_changed(active_event_handle)
        elif active_citation_handle:
            self.active_citation_changed(active_citation_handle)
        elif active_media_handle:
            self.active_media_changed(active_media_handle)

    def is_true(self, value):
        """Checks whether a given string value represents a boolean 'true'."""
        return str(value).strip().lower() in {"1", "true", "yes", "y"}

    def populate_links(self, entity_data, uids_data, nav_type, obj):
        """Populates the list model with formatted website links relevant to the current entity."""
        self.model.clear()
        websites = self.website_loader.load_websites(self.config_ini_manager)
        obj_handle = obj.get_handle()

        if self._show_attribute_links:
            attr_links = self.attribute_links_loader.get_links_from_attributes(
                obj, nav_type
            )
            websites += attr_links

        for nav, locale, title, is_enabled, url_pattern, comment, is_custom in websites:

            if self.website_loader.has_string_in_file(
                f"{url_pattern}|{obj_handle}|{nav_type}", HIDDEN_HASH_FILE_PATH
            ) or self.website_loader.has_string_in_file(
                f"{url_pattern}|{nav_type}", HIDDEN_HASH_FILE_PATH
            ):
                continue

            if nav == nav_type and self.is_true(is_enabled):
                try:

                    if locale in ["STATIC", "ATTR"]:
                        final_url = url_pattern
                        formatted_url = url_pattern
                        uid_icon = None
                        uid_visible = False
                        variables = {
                            "replaced_variables": [],
                            "not_found_variables": [],
                            "empty_variables": [],
                        }
                        variables_json = json.dumps(variables)
                        replaced_vars_count = 0
                        total_vars_count = 0
                    else:
                        filtered_uids_data = (
                            self.attribute_loader.add_matching_variables_to_data(
                                uids_data, url_pattern
                            )
                        )
                        data = entity_data.copy()
                        data.update(filtered_uids_data)

                        variables = self.url_formatter.check_pattern_variables(
                            url_pattern, data
                        )
                        variables_json = json.dumps(variables)

                        final_url = url_pattern % data
                        formatted_url = self.url_formatter.format(final_url, variables)
                        uid_icon, uid_visible = self.get_uid_icon_data(
                            variables["replaced_variables"], filtered_uids_data
                        )

                    icon_name = CATEGORY_ICON.get(nav_type, DEFAULT_CATEGORY_ICON)
                    hash_value = self.website_loader.generate_hash(
                        f"{final_url}|{obj_handle}"
                    )
                    visited_icon, visited_icon_visible = self.get_visited_icon_data(
                        hash_value
                    )
                    saved_icon, saved_icon_visible = self.get_saved_icon_data(
                        hash_value
                    )
                    user_data_icon, user_data_icon_visible = (
                        self.get_user_data_icon_data(is_custom)
                    )
                    locale_icon, locale_icon_visible = self.get_locale_icon_data(locale)

                    replaced_vars_count = len(variables["replaced_variables"])
                    total_vars_count = (
                        len(variables["not_found_variables"])
                        + len(variables["replaced_variables"])
                        + len(variables["empty_variables"])
                    )

                    vars_color = "black"
                    if replaced_vars_count == total_vars_count:
                        vars_color = "green"
                    elif replaced_vars_count not in (total_vars_count, 0):
                        vars_color = "orange"
                    elif replaced_vars_count == 0:
                        vars_color = "red"

                    locale_text = locale
                    if locale_text in ["COMMON", "UID", "STATIC"]:
                        locale_text = ""

                    data_dict = {
                        "icon_name": icon_name,
                        "locale_text": locale_text,
                        "title": title,
                        "final_url": final_url,
                        "comment": comment,
                        "url_pattern": url_pattern,
                        "variables_json": variables_json,
                        "formatted_url": formatted_url,
                        "visited_icon": visited_icon,
                        "saved_icon": saved_icon,
                        "uid_icon": uid_icon,
                        "uid_visible": uid_visible,
                        "nav_type": nav_type,
                        "visited_icon_visible": visited_icon_visible,
                        "saved_icon_visible": saved_icon_visible,
                        "obj_handle": obj_handle,
                        "replaced_vars_count": replaced_vars_count,
                        "total_vars_count": total_vars_count,
                        "vars_color": vars_color,
                        "user_data_icon": user_data_icon,
                        "user_data_icon_visible": user_data_icon_visible,
                        "locale_icon": locale_icon,
                        "locale_icon_visible": locale_icon_visible,
                        "locale_text_visible": not locale_icon_visible,
                    }

                    self.model.append([data_dict[name] for name, _ in MODEL_SCHEMA])
                except KeyError:
                    pass

    def get_locale_icon_data(self, locale):
        """Returns an appropriate flag or icon based on the locale identifier."""
        locale_icon = None
        locale_icon_visible = False

        if locale == "COMMON":
            locale_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(
                ICON_EARTH_PATH, ICON_SIZE, ICON_SIZE
            )
            locale_icon_visible = True
            return locale_icon, locale_icon_visible
        if locale == "STATIC":
            locale_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(
                ICON_PIN_PATH, ICON_SIZE, ICON_SIZE
            )
            locale_icon_visible = True
            return locale_icon, locale_icon_visible
        if locale == "ATTR":
            locale_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(
                ICON_CHAIN_PATH, ICON_SIZE, ICON_SIZE
            )
            locale_icon_visible = True
            return locale_icon, locale_icon_visible
        if locale == "UID":
            return locale_icon, locale_icon_visible

        if not locale or not self._show_flag_icons:
            return locale_icon, locale_icon_visible

        locale = locale.lower()
        flag_filename = f"{locale}.png"
        flag_path = os.path.join(FLAGS_DIR, flag_filename)

        if os.path.exists(flag_path):
            try:
                locale_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    flag_path, ICON_SIZE, ICON_SIZE
                )
                locale_icon_visible = True
            except Exception as e:
                print(f"❌ Error loading flag icon '{flag_path}': {e}", file=sys.stderr)

        return locale_icon, locale_icon_visible

    def get_user_data_icon_data(self, is_custom):
        """Returns the user data icon if the entry is from a user-defined source."""
        user_data_icon = None
        user_data_icon_visible = False

        if not self._show_user_data_icon:
            return user_data_icon, user_data_icon_visible

        if is_custom:
            try:
                user_data_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    ICON_USER_DATA_PATH, ICON_SIZE, ICON_SIZE
                )
                user_data_icon_visible = True
            except Exception as e:
                print(f"❌ Error loading icon: {e}", file=sys.stderr)
        return user_data_icon, user_data_icon_visible

    def get_visited_icon_data(self, hash_value):
        """Returns the visited icon if the URL hash exists in the visited list."""
        visited_icon = None
        visited_icon_visible = False
        if self.website_loader.has_hash_in_file(hash_value, VISITED_HASH_FILE_PATH):
            try:
                visited_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    ICON_VISITED_PATH, ICON_SIZE, ICON_SIZE
                )
                visited_icon_visible = True
            except Exception as e:
                print(f"❌ Error loading icon: {e}", file=sys.stderr)
        return visited_icon, visited_icon_visible

    def get_saved_icon_data(self, hash_value):
        """Returns the saved icon if the URL hash exists in the saved list."""
        saved_icon = None
        saved_icon_visible = False
        if self.website_loader.has_hash_in_file(hash_value, SAVED_HASH_FILE_PATH):
            try:
                saved_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    ICON_SAVED_PATH, ICON_SIZE, ICON_SIZE
                )
                saved_icon_visible = True
            except Exception as e:
                print(f"❌ Error loading icon: {e}", file=sys.stderr)
        return saved_icon, saved_icon_visible

    def get_uid_icon_data(self, replaced_variables, filtered_uids_data):
        """Returns the UID icon if a matching variable from UID data was used."""
        uid_icon = None
        uid_visible = False

        try:
            replaced_vars_set = {list(var.keys())[0] for var in replaced_variables}
            if any(var in replaced_vars_set for var in filtered_uids_data.keys()):
                uid_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    ICON_UID_PATH, UID_ICON_WIDTH, UID_ICON_HEIGHT
                )
                uid_visible = True
        except Exception as e:
            print(f"❌ Error loading UID icon: {e}", file=sys.stderr)

        return uid_icon, uid_visible

    def on_link_clicked(self, tree_view, path, column):
        """Handles the event when a URL is clicked in the tree view and opens the link."""
        tree_iter = self.model.get_iter(path)
        url = self.model.get_value(tree_iter, ModelColumns.FINAL_URL.value)
        encoded_url = urllib.parse.quote(url, safe=URL_SAFE_CHARS)
        self.add_icon_event(
            SimpleNamespace(
                file_path=VISITED_HASH_FILE_PATH,
                icon_path=ICON_VISITED_PATH,
                tree_iter=tree_iter,
                model_icon_pos=ModelColumns.VISITED_ICON.value,
                model_visibility_pos=ModelColumns.VISITED_ICON_VISIBLE.value,
            )
        )
        display_url(encoded_url)

    def add_icon_event(self, settings):
        """Adds a visual icon to the model and saves the hash when a link is clicked."""
        file_path = settings.file_path
        icon_path = settings.icon_path
        tree_iter = settings.tree_iter
        model_icon_pos = settings.model_icon_pos
        model_visibility_pos = settings.model_visibility_pos
        url = self.model.get_value(tree_iter, ModelColumns.FINAL_URL.value)
        obj_handle = self.model.get_value(tree_iter, ModelColumns.OBJ_HANDLE.value)
        hash_value = self.website_loader.generate_hash(f"{url}|{obj_handle}")
        if not self.website_loader.has_hash_in_file(hash_value, file_path):
            self.website_loader.save_hash_to_file(hash_value, file_path)
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    icon_path, ICON_SIZE, ICON_SIZE
                )
                self.model.set_value(tree_iter, model_icon_pos, pixbuf)
                self.model.set_value(tree_iter, model_visibility_pos, True)
                self.ui.columns.icons.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
                self.ui.columns.icons.set_fixed_width(-1)
                self.ui.columns.icons.queue_resize()
            except Exception as e:
                print(f"❌ Error loading icon: {e}", file=sys.stderr)

    def active_person_changed(self, handle):
        """Handles updates when the active person changes in the GUI."""
        self.close_context_menu()

        person = self.dbstate.db.get_person_from_handle(handle)
        self._context.person = person
        if not person:
            return

        person_data, uids_data = self.get_person_data(person)
        self.populate_links(
            person_data, uids_data, SupportedNavTypes.PEOPLE.value, person
        )
        self.update()

    def active_event_changed(self, handle):
        """Handles updates when the active event changes in the GUI."""
        self.close_context_menu()

        event = self.dbstate.db.get_event_from_handle(handle)
        self._context.event = event
        if not event:
            return

        self.populate_links({}, {}, SupportedNavTypes.EVENTS.value, event)
        self.update()

    def active_citation_changed(self, handle):
        """Handles updates when the active citation changes in the GUI."""
        self.close_context_menu()

        citation = self.dbstate.db.get_citation_from_handle(handle)
        self._context.citation = citation
        if not citation:
            return

        self.populate_links({}, {}, SupportedNavTypes.CITATIONS.value, citation)
        self.update()

    def active_media_changed(self, handle):
        """Handles updates when the active media changes in the GUI."""
        self.close_context_menu()

        media = self.dbstate.db.get_media_from_handle(handle)
        self._context.media = media
        if not media:
            return

        self.populate_links({}, {}, SupportedNavTypes.MEDIA.value, media)
        self.update()

    def close_context_menu(self):
        """Closes the context menu if it is currently visible."""
        if self.ui.context_menu and self.ui.context_menu.get_visible():
            self.ui.context_menu.hide()

    def active_place_changed(self, handle):
        """Handles updates when the active place changes in the GUI."""
        try:
            place = self.dbstate.db.get_place_from_handle(handle)
            self._context.place = place
            if not place:
                return

            place_data = self.get_place_data(place)
            self.populate_links(place_data, {}, SupportedNavTypes.PLACES.value, place)
            self.update()
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)

    def active_source_changed(self, handle):
        """Handles updates when the active source changes in the GUI."""
        source = self.dbstate.db.get_source_from_handle(handle)
        self._context.source = source
        if not source:
            return

        source_data = self.get_source_data(source)
        self.populate_links(source_data, {}, SupportedNavTypes.SOURCES.value, source)
        self.update()

    def active_family_changed(self, handle):
        """Handles updates when the active family changes in the GUI."""
        family = self.dbstate.db.get_family_from_handle(handle)
        self._context.family = family
        if not family:
            return

        family_data = self.get_family_data(family)
        self.populate_links(family_data, {}, SupportedNavTypes.FAMILIES.value, family)
        self.update()

    def get_person_data(self, person):
        """Extracts structured personal and date-related data from a Person object."""
        try:
            name = person.get_primary_name().get_first_name().strip()
            middle_name_handling = self.config_ini_manager.get_enum(
                "websearch.middle_name_handling",
                MiddleNameHandling,
                DEFAULT_MIDDLE_NAME_HANDLING,
            )

            if middle_name_handling == MiddleNameHandling.SEPARATE.value:
                given, middle = (
                    (name.split(" ", 1) + [None])[:2] if name else (None, None)
                )
            elif middle_name_handling == MiddleNameHandling.REMOVE.value:
                given, middle = (
                    (name.split(" ", 1) + [None])[:2] if name else (None, None)
                )
                middle = None
            elif middle_name_handling == MiddleNameHandling.LEAVE_ALONE.value:
                given, middle = name, None
            else:
                given, middle = name, None

            surname = person.get_primary_name().get_primary().strip() or None
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            given, middle, surname = None, None, None

        (
            birth_year,
            birth_year_from,
            birth_year_to,
            birth_year_before,
            birth_year_after,
        ) = self.get_birth_years(person)
        (
            death_year,
            death_year_from,
            death_year_to,
            death_year_before,
            death_year_after,
        ) = self.get_death_years(person)

        person_data = {
            PersonDataKeys.GIVEN.value: given or "",
            PersonDataKeys.MIDDLE.value: middle or "",
            PersonDataKeys.SURNAME.value: surname or "",
            PersonDataKeys.BIRTH_YEAR.value: birth_year or "",
            PersonDataKeys.BIRTH_YEAR_FROM.value: birth_year_from or "",
            PersonDataKeys.BIRTH_YEAR_TO.value: birth_year_to or "",
            PersonDataKeys.BIRTH_YEAR_BEFORE.value: birth_year_before or "",
            PersonDataKeys.BIRTH_YEAR_AFTER.value: birth_year_after or "",
            PersonDataKeys.DEATH_YEAR.value: death_year or "",
            PersonDataKeys.DEATH_YEAR_FROM.value: death_year_from or "",
            PersonDataKeys.DEATH_YEAR_TO.value: death_year_to or "",
            PersonDataKeys.DEATH_YEAR_BEFORE.value: death_year_before or "",
            PersonDataKeys.DEATH_YEAR_AFTER.value: death_year_after or "",
            PersonDataKeys.BIRTH_PLACE.value: self.get_birth_place(person) or "",
            PersonDataKeys.BIRTH_ROOT_PLACE.value: self.get_birth_root_place(person)
            or "",
            PersonDataKeys.DEATH_PLACE.value: self.get_death_place(person) or "",
            PersonDataKeys.DEATH_ROOT_PLACE.value: self.get_death_root_place(person)
            or "",
            PersonDataKeys.SYSTEM_LOCALE.value: self.system_locale or "",
        }

        uids_data = self.attribute_loader.get_attributes_for_nav_type("Person", person)

        return person_data, uids_data

    def get_family_data(self, family):
        """Extracts structured data related to a family, including parents and events."""
        father = (
            self.dbstate.db.get_person_from_handle(family.get_father_handle())
            if family.get_father_handle()
            else None
        )
        mother = (
            self.dbstate.db.get_person_from_handle(family.get_mother_handle())
            if family.get_mother_handle()
            else None
        )

        father_data, father_uids_data = self.get_person_data(father) if father else {}
        mother_data, mother_uids_data = self.get_person_data(mother) if mother else {}

        marriage_year = marriage_year_from = marriage_year_to = marriage_year_before = (
            marriage_year_after
        ) = ""
        marriage_place = marriage_root_place = None

        divorce_year = divorce_year_from = divorce_year_to = divorce_year_before = (
            divorce_year_after
        ) = ""
        divorce_place = divorce_root_place = None

        event_ref_list = family.get_event_ref_list()
        for event_ref in event_ref_list:
            event = self.dbstate.db.get_event_from_handle(
                event_ref.get_reference_handle()
            )
            event_type = event.get_type()
            event_place = self.get_event_place(event)
            event_root_place = self.get_root_place_name(event_place)
            if event_type == EventType.MARRIAGE:
                (
                    marriage_year,
                    marriage_year_from,
                    marriage_year_to,
                    marriage_year_before,
                    marriage_year_after,
                ) = self.get_event_years(event)
                marriage_place = self.get_place_name(event_place)
                marriage_root_place = event_root_place
            if event_type == EventType.DIVORCE:
                (
                    divorce_year,
                    divorce_year_from,
                    divorce_year_to,
                    divorce_year_before,
                    divorce_year_after,
                ) = self.get_event_years(event)
                divorce_place = self.get_place_name(event_place)
                divorce_root_place = event_root_place

        family_data = {
            FamilyDataKeys.FATHER_GIVEN.value: father_data.get(
                PersonDataKeys.GIVEN.value, ""
            ),
            FamilyDataKeys.FATHER_MIDDLE.value: father_data.get(
                PersonDataKeys.MIDDLE.value, ""
            ),
            FamilyDataKeys.FATHER_SURNAME.value: father_data.get(
                PersonDataKeys.SURNAME.value, ""
            ),
            FamilyDataKeys.FATHER_BIRTH_YEAR.value: father_data.get(
                PersonDataKeys.BIRTH_YEAR.value, ""
            ),
            FamilyDataKeys.FATHER_BIRTH_YEAR_FROM.value: father_data.get(
                PersonDataKeys.BIRTH_YEAR_FROM.value, ""
            ),
            FamilyDataKeys.FATHER_BIRTH_YEAR_TO.value: father_data.get(
                PersonDataKeys.BIRTH_YEAR_TO.value, ""
            ),
            FamilyDataKeys.FATHER_BIRTH_YEAR_BEFORE.value: father_data.get(
                PersonDataKeys.BIRTH_YEAR_BEFORE.value, ""
            ),
            FamilyDataKeys.FATHER_BIRTH_YEAR_AFTER.value: father_data.get(
                PersonDataKeys.BIRTH_YEAR_AFTER.value, ""
            ),
            FamilyDataKeys.FATHER_DEATH_YEAR.value: father_data.get(
                PersonDataKeys.DEATH_YEAR.value, ""
            ),
            FamilyDataKeys.FATHER_DEATH_YEAR_FROM.value: father_data.get(
                PersonDataKeys.DEATH_YEAR_FROM.value, ""
            ),
            FamilyDataKeys.FATHER_DEATH_YEAR_TO.value: father_data.get(
                PersonDataKeys.DEATH_YEAR_TO.value, ""
            ),
            FamilyDataKeys.FATHER_DEATH_YEAR_BEFORE.value: father_data.get(
                PersonDataKeys.DEATH_YEAR_BEFORE.value, ""
            ),
            FamilyDataKeys.FATHER_DEATH_YEAR_AFTER.value: father_data.get(
                PersonDataKeys.DEATH_YEAR_AFTER.value, ""
            ),
            FamilyDataKeys.FATHER_BIRTH_PLACE.value: father_data.get(
                PersonDataKeys.BIRTH_PLACE.value, ""
            ),
            FamilyDataKeys.FATHER_BIRTH_ROOT_PLACE.value: father_data.get(
                PersonDataKeys.BIRTH_ROOT_PLACE.value, ""
            ),
            FamilyDataKeys.FATHER_DEATH_PLACE.value: father_data.get(
                PersonDataKeys.DEATH_PLACE.value, ""
            ),
            FamilyDataKeys.FATHER_DEATH_ROOT_PLACE.value: father_data.get(
                PersonDataKeys.DEATH_ROOT_PLACE.value, ""
            ),
            FamilyDataKeys.MOTHER_GIVEN.value: mother_data.get(
                PersonDataKeys.GIVEN.value, ""
            ),
            FamilyDataKeys.MOTHER_MIDDLE.value: mother_data.get(
                PersonDataKeys.MIDDLE.value, ""
            ),
            FamilyDataKeys.MOTHER_SURNAME.value: mother_data.get(
                PersonDataKeys.SURNAME.value, ""
            ),
            FamilyDataKeys.MOTHER_BIRTH_YEAR.value: mother_data.get(
                PersonDataKeys.BIRTH_YEAR.value, ""
            ),
            FamilyDataKeys.MOTHER_BIRTH_YEAR_FROM.value: mother_data.get(
                PersonDataKeys.BIRTH_YEAR_FROM.value, ""
            ),
            FamilyDataKeys.MOTHER_BIRTH_YEAR_TO.value: mother_data.get(
                PersonDataKeys.BIRTH_YEAR_TO.value, ""
            ),
            FamilyDataKeys.MOTHER_BIRTH_YEAR_BEFORE.value: mother_data.get(
                PersonDataKeys.BIRTH_YEAR_BEFORE.value, ""
            ),
            FamilyDataKeys.MOTHER_BIRTH_YEAR_AFTER.value: mother_data.get(
                PersonDataKeys.BIRTH_YEAR_AFTER.value, ""
            ),
            FamilyDataKeys.MOTHER_DEATH_YEAR.value: mother_data.get(
                PersonDataKeys.DEATH_YEAR.value, ""
            ),
            FamilyDataKeys.MOTHER_DEATH_YEAR_FROM.value: mother_data.get(
                PersonDataKeys.DEATH_YEAR_FROM.value, ""
            ),
            FamilyDataKeys.MOTHER_DEATH_YEAR_TO.value: mother_data.get(
                PersonDataKeys.DEATH_YEAR_TO.value, ""
            ),
            FamilyDataKeys.MOTHER_DEATH_YEAR_BEFORE.value: mother_data.get(
                PersonDataKeys.DEATH_YEAR_BEFORE.value, ""
            ),
            FamilyDataKeys.MOTHER_DEATH_YEAR_AFTER.value: mother_data.get(
                PersonDataKeys.DEATH_YEAR_AFTER.value, ""
            ),
            FamilyDataKeys.MOTHER_BIRTH_PLACE.value: mother_data.get(
                PersonDataKeys.BIRTH_PLACE.value, ""
            ),
            FamilyDataKeys.MOTHER_BIRTH_ROOT_PLACE.value: mother_data.get(
                PersonDataKeys.BIRTH_ROOT_PLACE.value, ""
            ),
            FamilyDataKeys.MOTHER_DEATH_PLACE.value: mother_data.get(
                PersonDataKeys.DEATH_PLACE.value, ""
            ),
            FamilyDataKeys.MOTHER_DEATH_ROOT_PLACE.value: mother_data.get(
                PersonDataKeys.DEATH_ROOT_PLACE.value, ""
            ),
            FamilyDataKeys.MARRIAGE_YEAR.value: marriage_year or "",
            FamilyDataKeys.MARRIAGE_YEAR_FROM.value: marriage_year_from or "",
            FamilyDataKeys.MARRIAGE_YEAR_TO.value: marriage_year_to or "",
            FamilyDataKeys.MARRIAGE_YEAR_BEFORE.value: marriage_year_before or "",
            FamilyDataKeys.MARRIAGE_YEAR_AFTER.value: marriage_year_after or "",
            FamilyDataKeys.MARRIAGE_PLACE.value: marriage_place or "",
            FamilyDataKeys.MARRIAGE_ROOT_PLACE.value: marriage_root_place or "",
            FamilyDataKeys.DIVORCE_YEAR.value: divorce_year or "",
            FamilyDataKeys.DIVORCE_YEAR_FROM.value: divorce_year_from or "",
            FamilyDataKeys.DIVORCE_YEAR_TO.value: divorce_year_to or "",
            FamilyDataKeys.DIVORCE_YEAR_BEFORE.value: divorce_year_before or "",
            FamilyDataKeys.DIVORCE_YEAR_AFTER.value: divorce_year_after or "",
            FamilyDataKeys.DIVORCE_PLACE.value: divorce_place or "",
            FamilyDataKeys.DIVORCE_ROOT_PLACE.value: divorce_root_place or "",
            FamilyDataKeys.SYSTEM_LOCALE.value: self.system_locale or "",
        }

        return family_data

    def get_place_data(self, place):
        """Extracts structured place data such as name, coordinates, and type."""
        place_name = root_place_name = latitude = longitude = place_type = None
        try:
            place_name = self.get_place_name(place)
            root_place_name = self.get_root_place_name(place)
            place_title = self.get_place_title(place)
            latitude = self.get_place_latitude(place)
            longitude = self.get_place_longitude(place)
            place_type = self.get_place_type(place)
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)

        place_data = {
            PlaceDataKeys.PLACE.value: place_name or "",
            PlaceDataKeys.ROOT_PLACE.value: root_place_name or "",
            PlaceDataKeys.LATITUDE.value: latitude or "",
            PlaceDataKeys.LONGITUDE.value: longitude or "",
            PlaceDataKeys.TYPE.value: place_type or "",
            PlaceDataKeys.TITLE.value: place_title or "",
            PlaceDataKeys.SYSTEM_LOCALE.value: self.system_locale or "",
        }

        return place_data

    def get_place_latitude(self, place):
        """Returns the latitude of the place if available."""
        try:
            if place is None:
                return None
            latitude = place.get_latitude()
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            return None
        return latitude

    def get_place_longitude(self, place):
        """Returns the longitude of the place if available."""
        try:
            if place is None:
                return None
            longitude = place.get_longitude()
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            return None
        return longitude

    def get_place_type(self, place):
        """Returns the place type as a string or XML identifier."""
        try:
            if place is None:
                return None

            place_type = place.get_type()
            if isinstance(place_type, str):
                place_type_value = place_type
            elif isinstance(place_type, PlaceType):
                place_type_value = place_type.xml_str()
            else:
                place_type_value = None

        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            return None
        return place_type_value

    def get_source_data(self, source):
        """Extracts basic information from a source object, including title and locale."""
        try:
            title = source.get_title() or None
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            title = None

        source_data = {
            SourceDataKeys.TITLE.value: title or "",
            SourceDataKeys.SYSTEM_LOCALE.value: self.system_locale or "",
        }

        return source_data

    def get_root_place_name(self, place):
        """Returns the root place name by traversing place hierarchy upward."""
        try:
            if place is None:
                return None
            name = place.get_name()
            if name is None:
                return None
            root_place_name = name.get_value()
            place_ref = (
                place.get_placeref_list()[0] if place.get_placeref_list() else None
            )
            while place_ref:
                p = self.dbstate.db.get_place_from_handle(
                    place_ref.get_reference_handle()
                )
                if p:
                    root_place_name = p.get_name().get_value()
                    place_ref = (
                        p.get_placeref_list()[0] if p.get_placeref_list() else None
                    )
                else:
                    break
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            return None

        return root_place_name

    def get_place_title(self, place):
        """Returns a full hierarchical title for the place (including parents)."""
        try:
            if not place:
                return ""
            name = place.get_name()
            if not name:
                return ""
            place_names = [name.get_value()]
            place_ref = (
                place.get_placeref_list()[0] if place.get_placeref_list() else None
            )
            while place_ref:
                parent_place = self.dbstate.db.get_place_from_handle(
                    place_ref.get_reference_handle()
                )
                if parent_place:
                    place_names.append(parent_place.get_name().get_value())
                    place_ref = (
                        parent_place.get_placeref_list()[0]
                        if parent_place.get_placeref_list()
                        else None
                    )
                else:
                    break

            return ", ".join(place_names) if place_names else ""
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            return ""

    def get_birth_year(self, person):
        """Returns the exact birth year from a person's birth event."""
        event = self.get_birth_event(person)
        return self.get_event_exact_year(event)

    def get_birth_years(self, person):
        """Returns different birth year formats from the person's birth event."""
        event = self.get_birth_event(person)
        year, year_from, year_to, year_before, year_after = self.get_event_years(event)
        return year, year_from, year_to, year_before, year_after

    def get_death_years(self, person):
        """Returns different death year formats from the person's death event."""
        event = self.get_death_event(person)
        year, year_from, year_to, year_before, year_after = self.get_event_years(event)
        return year, year_from, year_to, year_before, year_after

    def get_event_years(self, event):
        """Returns a tuple of year values extracted from an event's date object."""
        year = None
        year_from = None
        year_to = None
        year_before = None
        year_after = None

        if not event:
            return year, year_from, year_to, year_before, year_after
        date = event.get_date_object()
        if not date or date.is_empty():
            return year, year_from, year_to, year_before, year_after
        try:
            modifier = date.get_modifier()
            if modifier in [Date.MOD_NONE, Date.MOD_ABOUT]:
                year = date.get_year() or None
                year_from = date.get_year() or None
                year_to = date.get_year() or None
            if modifier in [Date.MOD_AFTER]:
                year_after = date.get_year() or None
            if modifier in [Date.MOD_BEFORE]:
                year_before = date.get_year() or None
            if modifier in [Date.MOD_SPAN, Date.MOD_RANGE]:
                start_date = date.get_start_date()
                stop_date = date.get_stop_date()
                year_from = start_date[2] if start_date else None
                year_to = stop_date[2] if stop_date else None
            return year, year_from, year_to, year_before, year_after
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
        return year, year_from, year_to, year_before, year_after

    def get_birth_place(self, person):
        """Returns the place name associated with the person's birth."""
        event = self.get_birth_event(person)
        place = self.get_event_place(event)
        return self.get_place_name(place)

    def get_birth_root_place(self, person):
        """Returns the root place name from the person's birth event."""
        event = self.get_birth_event(person)
        place = self.get_event_place(event)
        return self.get_root_place_name(place)

    def get_death_root_place(self, person):
        """Returns the root place name from the person's death event."""
        event = self.get_death_event(person)
        place = self.get_event_place(event)
        return self.get_root_place_name(place)

    def get_death_place(self, person):
        """Returns the place name associated with the person's death."""
        event = self.get_death_event(person)
        place = self.get_event_place(event)
        return self.get_place_name(place)

    def get_birth_event(self, person):
        """Returns the birth event object for the given person."""
        try:
            if person is None:
                return None
            ref = person.get_birth_ref()
            if ref is None:
                return None
            return (
                self.dbstate.db.get_event_from_handle(ref.get_reference_handle())
                or None
            )
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            return None

    def get_death_event(self, person):
        """Returns the death event object for the given person."""
        try:
            ref = person.get_death_ref()
            if ref is None:
                return None
            return (
                self.dbstate.db.get_event_from_handle(ref.get_reference_handle())
                or None
            )
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            return None

    def get_death_year(self, person):
        """Returns the exact year of the person's death."""
        event = self.get_death_event(person)
        return self.get_event_exact_year(event)

    def get_event_place(self, event):
        """Returns the place object associated with the given event."""
        try:
            if event is None:
                return None
            place_ref = event.get_place_handle()
            if not place_ref:
                return None
            return self.dbstate.db.get_place_from_handle(place_ref) or None
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            return None

    def get_event_exact_year(self, event):
        """Returns the exact year from a non-compound event date."""
        try:
            if event is None:
                return None
            date = event.get_date_object()
            if date and not date.is_compound():
                return date.get_year() or None
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
        return None

    def get_place_name(self, place):
        """Returns the primary name value of the given place."""
        try:
            if place is None:
                return None
            name = place.get_name()
            if name is None:
                return None
            value = name.get_value()
            return value or None
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            return None

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
        self.add_sorting(self.ui.columns.locale, ModelColumns.LOCALE_TEXT.value)
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
        self.ui.columns.vars.add_attribute(
            self.ui.text_renderers.vars_replaced,
            "text",
            ModelColumns.REPLACED_VARS_COUNT.value,
        )
        self.ui.columns.vars.add_attribute(
            self.ui.text_renderers.vars_total,
            "text",
            ModelColumns.TOTAL_VARS_COUNT.value,
        )
        self.ui.columns.vars.add_attribute(
            self.ui.text_renderers.vars_replaced,
            "foreground",
            ModelColumns.VARS_COLOR.value,
        )
        self.ui.text_renderers.vars_total.set_property("foreground", "green")
        self.ui.columns.locale.add_attribute(
            self.ui.text_renderers.locale, "text", ModelColumns.LOCALE_TEXT.value
        )
        self.ui.columns.locale.add_attribute(
            self.ui.text_renderers.locale,
            "visible",
            ModelColumns.LOCALE_TEXT_VISIBLE.value,
        )
        self.ui.columns.locale.add_attribute(
            self.ui.icon_renderers.locale, "pixbuf", ModelColumns.LOCALE_ICON.value
        )
        self.ui.columns.locale.add_attribute(
            self.ui.icon_renderers.locale,
            "visible",
            ModelColumns.LOCALE_ICON_VISIBLE.value,
        )
        self.ui.columns.title.add_attribute(
            self.ui.text_renderers.title, "text", ModelColumns.TITLE.value
        )
        self.ui.columns.url.add_attribute(
            self.ui.icon_renderers.uid, "pixbuf", ModelColumns.UID_ICON.value
        )
        self.ui.columns.url.add_attribute(
            self.ui.icon_renderers.uid, "visible", ModelColumns.UID_VISIBLE.value
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
        self.update_url_column_visibility()
        self.update_vars_column_visibility()

        self.reorder_columns()

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

    def update_url_column_visibility(self):
        """Updates the visibility of the 'Website URL' column."""
        self._show_url_column = self.config_ini_manager.get_boolean_option(
            "websearch.show_url_column", DEFAULT_SHOW_URL_COLUMN
        )
        self.ui.columns.url.set_visible(self._show_url_column)

    def update_vars_column_visibility(self):
        """Updates the visibility of the 'Vars' column."""
        self._show_vars_column = self.config_ini_manager.get_boolean_option(
            "websearch.show_vars_column", DEFAULT_SHOW_VARS_COLUMN
        )
        self.ui.columns.vars.set_visible(self._show_vars_column)

    def translate(self):
        """Sets translated text for UI elements and context menu."""
        self.ui.columns.locale.set_title("")
        self.ui.columns.vars.set_title(_("Vars"))
        self.ui.columns.title.set_title(_("Title"))
        self.ui.columns.url.set_title(_("Website URL"))
        self.ui.columns.comment.set_title(_("Comment"))

        self.ui.context_menu_items.add_note.set_label(_("Add link to note"))
        self.ui.context_menu_items.show_qr.set_label(_("Show QR-code"))
        self.ui.context_menu_items.copy_link.set_label(_("Copy link to clipboard"))
        self.ui.context_menu_items.hide_selected.set_label(
            _("Hide link for selected item")
        )
        self.ui.context_menu_items.hide_all.set_label(_("Hide link for all items"))

        self.ui.ai_recommendations_label.set_text(_("🔍 AI Suggestions"))

    def toggle_badges_visibility(self):
        """Shows or hides the badge container based on OpenAI usage."""
        if self._use_openai:
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

    def populate_badges(self, domain_url_pairs):
        """Displays AI-suggested site badges in the interface."""
        self.ui.boxes.badges.container.foreach(self.remove_widget)
        for domain, url in domain_url_pairs:
            badge = self.create_badge(domain, url)
            self.ui.boxes.badges.container.add(badge)
        self.ui.boxes.badges.container.show_all()

    def remove_widget(self, widget):
        """Removes a widget from the container."""
        self.ui.boxes.badges.container.remove(widget)

    def create_badge(self, domain, url):
        """Creates a clickable badge widget for an AI-suggested domain."""
        badge_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        badge_box.get_style_context().add_class("badge")

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

    def on_button_press_event(self, widget, event, url):
        """Handles button press event to open a URL."""
        self.open_url(url)

    def open_url(self, url):
        """Opens the given URL in the default web browser."""
        webbrowser.open(urllib.parse.quote(url, safe=URL_SAFE_CHARS))

    def on_remove_badge(self, button, badge):
        """Handles removing a badge and saving its domain to skipped list."""
        domain_label = None
        for child in badge.get_children():
            if isinstance(child, Gtk.EventBox):
                for sub_child in child.get_children():
                    if isinstance(sub_child, Gtk.Label):
                        domain_label = sub_child.get_text().strip()
                        break
        if domain_label:
            self.website_loader.save_skipped_domain(domain_label)

        self.ui.boxes.badges.container.remove(badge)

    def on_button_press(self, widget, event):
        """Handles right-click context menu activation in the treeview."""
        if event.button == RIGHT_MOUSE_BUTTON:
            path_info = widget.get_path_at_pos(event.x, event.y)
            if path_info:
                path, column, cell_x, cell_y = path_info
                tree_iter = self.model.get_iter(path)
                if not tree_iter or not self.model.iter_is_valid(tree_iter):
                    return
                url = self.model.get_value(tree_iter, ModelColumns.FINAL_URL.value)
                nav_type = self.model.get_value(tree_iter, ModelColumns.NAV_TYPE.value)

                self._context.active_tree_path = path
                self._context.active_url = url
                self.ui.context_menu.show_all()
                # add_attribute_item = self.builder.get_object("AddAttribute")

                if nav_type == SupportedNavTypes.PEOPLE.value:
                    # add_attribute_item.show()
                    self.ui.context_menu_items.add_note.show()
                else:
                    # add_attribute_item.hide()
                    self.ui.context_menu_items.add_note.hide()

                self.ui.context_menu.popup_at_pointer(event)

    def on_add_note(self, widget):
        """Adds the current selected URL as a note to the person record."""
        if not self._context.active_tree_path:
            print("❌ Error: No saved path to the iterator!", file=sys.stderr)
            return

        note = Note()
        note.set(
            _(
                "📌 This web link was added using the WebSearch gramplet for future reference:\n\n"
                "🔗 {url}\n\nYou can use this link to revisit the source and verify the "
                "information related to this person."
            ).format(url=self._context.active_url)
        )

        note.set_privacy(True)

        tree_iter = self.get_active_tree_iter(self._context.active_tree_path)
        nav_type = self.model.get_value(tree_iter, ModelColumns.NAV_TYPE.value)

        with DbTxn(_("Add Web Link Note"), self.dbstate.db) as trans:
            note_handle = self.dbstate.db.add_note(note, trans)
            if nav_type == SupportedNavTypes.PEOPLE.value:
                self._context.person.add_note(note_handle)
                self.dbstate.db.commit_person(self._context.person, trans)

        tree_iter = self.get_active_tree_iter(self._context.active_tree_path)

        self.add_icon_event(
            SimpleNamespace(
                file_path=SAVED_HASH_FILE_PATH,
                icon_path=ICON_SAVED_PATH,
                tree_iter=tree_iter,
                model_icon_pos=ModelColumns.SAVED_ICON.value,
                model_visibility_pos=ModelColumns.SAVED_ICON_VISIBLE.value,
            )
        )

    def on_show_qr_code(self, widget):
        """Opens a window showing the QR code for the selected URL."""
        selection = self.ui.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            url = model[tree_iter][ModelColumns.FINAL_URL.value]
            qr_window = QRCodeWindow(url)
            qr_window.show_all()

    def on_copy_url_to_clipboard(self, widget):
        """Copies the selected URL to the system clipboard."""
        selection = self.ui.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            url = model[tree_iter][ModelColumns.FINAL_URL.value]
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(url, -1)
            clipboard.store()
            notification = self.show_notification(_("URL is copied to the Clipboard"))
            notification.show_all()

    def on_hide_link_for_selected_item(self, widget):
        """Hides the selected link only for the current Gramps object."""
        selection = self.ui.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            url_pattern = model[tree_iter][ModelColumns.URL_PATTERN.value]
            obj_handle = model[tree_iter][ModelColumns.OBJ_HANDLE.value]
            nav_type = model[tree_iter][ModelColumns.NAV_TYPE.value]
            if not self.website_loader.has_string_in_file(
                f"{url_pattern}|{obj_handle}|{nav_type}", HIDDEN_HASH_FILE_PATH
            ):
                self.website_loader.save_string_to_file(
                    f"{url_pattern}|{obj_handle}|{nav_type}", HIDDEN_HASH_FILE_PATH
                )
            model.remove(tree_iter)

    def on_hide_link_for_all_items(self, widget):
        """Hides the selected link for all Gramps objects."""
        selection = self.ui.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            url_pattern = model[tree_iter][ModelColumns.URL_PATTERN.value]
            nav_type = model[tree_iter][ModelColumns.NAV_TYPE.value]
            if not self.website_loader.has_string_in_file(
                f"{url_pattern}|{nav_type}", HIDDEN_HASH_FILE_PATH
            ):
                self.website_loader.save_string_to_file(
                    f"{url_pattern}|{nav_type}", HIDDEN_HASH_FILE_PATH
                )
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
        except Exception as e:
            print(f"❌ Error in get_active_tree_iter: {e}", file=sys.stderr)
            return None

    def on_add_attribute(self, widget):
        """(Unused) Adds the selected URL as an attribute to the person."""
        if not self._context.active_tree_path:
            print("❌ Error: No saved path to the iterator!", file=sys.stderr)
            return

        attribute = Attribute()
        attribute.set_type(_("WebSearch Link"))
        attribute.set_value(self._context.active_url)
        attribute.set_privacy(True)

        tree_iter = self.get_active_tree_iter(self._context.active_tree_path)
        nav_type = self.model.get_value(tree_iter, ModelColumns.NAV_TYPE.value)

        # with DbTxn(_("Add Web Link Attribute"), self.dbstate.db) as trans:
        #    if nav_type == SupportedNavTypes.PEOPLE.value:
        #        self._context.person.add_attribute(attribute)
        #        self.dbstate.db.commit_person(self._context.person, trans)

        tree_iter = self.get_active_tree_iter(self._context.active_tree_path)
        self.add_icon_event(
            SimpleNamespace(
                file_path=SAVED_HASH_FILE_PATH,
                icon_path=ICON_SAVED_PATH,
                tree_iter=tree_iter,
                model_icon_pos=ModelColumns.SAVED_ICON.value,
                model_visibility_pos=ModelColumns.SAVED_ICON_VISIBLE.value,
            )
        )

    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        """Displays a tooltip with variable and comment information."""
        bin_x, bin_y = widget.convert_widget_to_bin_window_coords(x, y)
        path_info = widget.get_path_at_pos(bin_x, bin_y)

        if path_info:
            path, column, cell_x, cell_y = path_info
            tree_iter = self.model.get_iter(path)
            title = self.model.get_value(tree_iter, ModelColumns.TITLE.value)
            comment = self.model.get_value(tree_iter, ModelColumns.COMMENT.value) or ""

            variables_json = self.model.get_value(
                tree_iter, ModelColumns.VARIABLES_JSON.value
            )
            variables = json.loads(variables_json)
            replaced_variables = [
                f"{key}={value}"
                for var in variables["replaced_variables"]
                for key, value in var.items()
            ]
            empty_variables = list(variables["empty_variables"])

            tooltip_text = _("Title: {title}\n").format(title=title)
            if replaced_variables:
                tooltip_text += _("Replaced: {variables}\n").format(
                    variables=", ".join(replaced_variables)
                )
            if empty_variables:
                tooltip_text += _("Empty: {variables}\n").format(
                    variables=", ".join(empty_variables)
                )
            if comment:
                tooltip_text += _("Comment: {comment}\n").format(comment=comment)
            tooltip_text = tooltip_text.rstrip()
            tooltip.set_text(tooltip_text)
            return True
        return False

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
        self.config_ini_manager.set_boolean_option(
            "websearch.use_openai", self.opts[5].get_value()
        )
        self.config_ini_manager.set_string(
            "websearch.openai_api_key", self.opts[6].get_value()
        )
        self.config_ini_manager.set_boolean_option(
            "websearch.show_url_column", self.opts[7].get_value()
        )
        self.config_ini_manager.set_boolean_option(
            "websearch.show_vars_column", self.opts[8].get_value()
        )
        self.config_ini_manager.set_boolean_option(
            "websearch.show_user_data_icon", self.opts[9].get_value()
        )
        self.config_ini_manager.set_boolean_option(
            "websearch.show_flag_icons", self.opts[10].get_value()
        )
        self.config_ini_manager.set_boolean_option(
            "websearch.show_attribute_links", self.opts[11].get_value()
        )
        self.config_ini_manager.save()

    def save_update_options(self, obj):
        """Saves configuration options and refreshes the Gramplet view."""
        self.save_options()
        self.update()
        self.on_load()
        self.update_url_column_visibility()
        self.update_vars_column_visibility()

    def on_load(self):
        """Loads all persistent WebSearch configuration settings."""
        self._enabled_files = self.config_ini_manager.get_list(
            "websearch.enabled_files", DEFAULT_ENABLED_FILES
        )
        self._use_openai = self.config_ini_manager.get_boolean_option(
            "websearch.use_openai", DEFAULT_USE_OPEN_AI
        )
        self._openai_api_key = self.config_ini_manager.get_string(
            "websearch.openai_api_key"
        )
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
        self._show_url_column = self.config_ini_manager.get_boolean_option(
            "websearch.show_url_column", DEFAULT_SHOW_URL_COLUMN
        )
        self._show_vars_column = self.config_ini_manager.get_boolean_option(
            "websearch.show_vars_column", DEFAULT_SHOW_VARS_COLUMN
        )
        self._show_user_data_icon = self.config_ini_manager.get_boolean_option(
            "websearch.show_user_data_icon", DEFAULT_SHOW_USER_DATA_ICON
        )
        self._show_flag_icons = self.config_ini_manager.get_boolean_option(
            "websearch.show_flag_icons", DEFAULT_SHOW_FLAG_ICONS
        )
        self._show_attribute_links = self.config_ini_manager.get_boolean_option(
            "websearch.show_attribute_links", DEFAULT_SHOW_ATTRIBUTE_LINKS
        )
        self._columns_order = self.config_ini_manager.get_list(
            "websearch.columns_order", DEFAULT_COLUMNS_ORDER
        )
