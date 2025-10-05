#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Melle Koning
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# ChatWithTree.py
import logging

import gi
from AsyncChatService import AsyncChatService
from chatwithllm import YieldType
from gi.repository import Gdk, GLib, Gtk
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.plug import Gramplet

LOG = logging.getLogger(".")
LOG.debug("loading chatwithtree")
# ==============================================================================
# Standard Python libraries
# ==============================================================================

gi.require_version("Gtk", "3.0")
# ==============================================================================
# GRAMPS API
# ==============================================================================

_ = glocale.get_addon_translator(__file__).gettext

LOG.debug("ChatWithTree file header loaded successfully.")

ONE_SECOND = 1000  # milliseconds


# ==============================================================================
# Gramplet Class Definition
# ==============================================================================
class ChatWithTreeClass(Gramplet):
    """
    A simple interactive Gramplet that takes user input and provides a reply.

    This version uses a Gtk.ListBox to create a dynamic, chat-like interface
    with styled message "balloons" for user input and system replies.
    """

    def __init__(self, parent=None, **kwargs):
        """
        The constructor for the Gramplet.
        We call the base class constructor here. The GUI is built in the
        init() method.
        """
        # Call the base class constructor. This is a mandatory step.
        Gramplet.__init__(self, parent, **kwargs)

    def init(self):
        """
        This method is called by the Gramps framework after the Gramplet
        has been fully initialized. We build our GUI here.
        """
        # Build our custom GUI widgets.
        self.vbox = self._build_gui()
        # The Gramplet's container widget is found via `self.gui`.
        # We first remove the default textview...
        self.gui.get_container_widget().remove(self.gui.textview)
        # ... and then we add our new vertical box.
        self.gui.get_container_widget().add(self.vbox)
        # Show all widgets.
        self.vbox.show()
        # db change signal
        self.dbstate.connect('database-changed', self.change_db)
        self.chat_service = None

    def change_db(self, db):
        """
        This method is called when the database is opened or closed.
        The 'dbstate' parameter is the current database state object.
        """
        # Add the initial message to the list box.

        if self.dbstate.db:
            try:
                active_db_name = self.dbstate.db.get_dbname()
                if active_db_name:
                    self._add_message_row(_(f"Database change detected\
                                            Database {active_db_name}."
                                            ""), YieldType.PARTIAL)
                    self.chat_service = AsyncChatService(active_db_name)
            except Exception as e:
                # Catch the likely TypeError or any other startup error
                LOG.error(f"Failed to initialize AsyncChatService: {e}")
                self.chat_service = None   # Ensure it's None on failure
                return
        else:
            LOG.error("Database is closed. Chatbot logic is reset.")
            self.chat_service = None

    def _build_gui(self):
        """
        Creates all the GTK widgets for the Gramplet's user interface.
        Returns the top-level container widget.
        """
        # Create the main vertical box to hold all our widgets.
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # -------------------
        # 1. Chat History Section
        # -------------------
        # We use a Gtk.ListBox to hold our chat "balloons".
        self.chat_listbox = Gtk.ListBox()
        # Set a name for CSS styling.
        self.chat_listbox.set_name("chat-listbox")
        # Ensure the listbox is a single-column list.
        self.chat_listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        # We need a reference to the scrolled window to control its scrolling.
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_hexpand(True)
        self.scrolled_window.set_vexpand(True)
        self.scrolled_window.add(self.chat_listbox)
        vbox.pack_start(self.scrolled_window, True, True, 0)

        # Apply CSS styling for the chat balloons.
        self._apply_css_styles()

        # -------------------
        # 2. Input Section
        # -------------------
        input_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.input_entry = Gtk.Entry()
        self.input_entry.set_placeholder_text(_("Type a message..."))
        self.input_entry.connect("activate", self.on_process_button_clicked)
        input_hbox.pack_start(self.input_entry, True, True, 0)

        self.process_button = Gtk.Button(label=_("Send"))
        self.process_button.connect("clicked", self.on_process_button_clicked)
        input_hbox.pack_start(self.process_button, False, False, 0)

        vbox.pack_start(input_hbox, False, False, 0)

        # Add the initial message to the list box.
        self._add_message_row(_(
            "Chat with Tree initialized. \
                Type /help for help."),
            YieldType.PARTIAL
            )

        return vbox

    def _apply_css_styles(self):
        """
        Defines and applies CSS styles to the Gramplet's widgets.
        """
        css_provider = Gtk.CssProvider()
        css = """
        #chat-listbox {
            background-color: white;
        }
        .message-box {
            background-color: #f0f0f0; /* Default background */
            padding: 10px;
            margin: 5px;
            border-radius: 15px;
        }
        .user-message-box {
            background-color: #dcf8c6; /* Light green for user messages */
        }
        .tree-reply-box {
            background-color: #d1e2f4; /* Light blue for replies */
        }
        .tree-toolcall-box {
            background-color: #fce8b2; /* Light yellow for tool calls */
        }
        """
        css_provider.load_from_data(css.encode('utf-8'))
        screen = Gdk.Screen.get_default()
        context = Gtk.StyleContext()
        context.add_provider_for_screen(screen, css_provider,
                                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # We need to set up a style context on the chat listbox
        style_context = self.chat_listbox.get_style_context()
        style_context.add_class("message-box")

    def _add_message_row(self, text: str, reply_type: YieldType):
        """
        Creates a new message "balloon" widget and adds it to the listbox.
        """
        # Create a horizontal box to act as the message container.
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        hbox.set_spacing(6)

        # Create the message "balloon" box.
        message_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        message_box.get_style_context().add_class("message-box")

        # Create the label for the text.
        message_label = Gtk.Label(label=text)
        message_label.set_halign(Gtk.Align.START)
        message_label.set_line_wrap(True)
        message_label.set_max_width_chars(80)
        message_box.pack_start(message_label, True, True, 0)

        if reply_type == YieldType.USER:
            message_box.get_style_context().add_class("user-message-box")
            # Align the message balloon to the right.
            hbox.set_halign(Gtk.Align.END)
        elif reply_type in (YieldType.PARTIAL, YieldType.TOOL_CALL):
            message_box.get_style_context().add_class("tree-toolcall-box")
            # Align the message balloon to the left.
            hbox.set_halign(Gtk.Align.CENTER)

        elif reply_type == YieldType.FINAL:
            message_box.get_style_context().add_class("tree-reply-box")
            # Align the message balloon to the left.
            hbox.set_halign(Gtk.Align.START)

        # Add the message balloon to the main horizontal container.
        hbox.add(message_box)

        # Add the whole row to the listbox.
        self.chat_listbox.add(hbox)
        self.chat_listbox.show_all()

        return message_label

    def scroll_to_bottom(self):
        """
        Helper function to scroll the listbox to the end.
        This runs on the main GTK thread after a redraw.
        """
        adj = self.scrolled_window.get_vadjustment()
        adj.set_value(adj.get_upper())

        # Return False to run the callback only once
        return GLib.SOURCE_REMOVE

    def _check_queue_for_reply(self):
        """
        Pulls the next available result from the AsyncChatService's internal
        result queue on the main GTK thread to update the UI.

        This method runs repeatedly via GLib.idle_add until the job is done.
        """
        # 1. Safety check
        if self.chat_service is None:
            LOG.error("Chat service is unexpectedly None in _check_queue_for_reply.")
            return GLib.SOURCE_REMOVE

        try:
            # Non-blocking attempt to get the next result from the worker thread's queue.
            # This result will be ReplyItem or None (the sentinel).
            reply = self.chat_service.get_next_result_from_queue()

            if reply is None:
                # Queue is empty. Check the status of the background job.
                if self.chat_service.is_processing():
                    # Job is still running, check the queue again later.
                    return GLib.SOURCE_CONTINUE
                else:
                    # Job is finished (sentinel already processed or queue is empty
                    # after job completion). Stop the idle handler.
                    return GLib.SOURCE_REMOVE

            # --- 2. Process and Update UI ---
            # If we reached here, 'reply' is a valid (type, content) tuple
            reply_type, content = reply

            if reply_type == YieldType.PARTIAL:
                self._add_message_row(content, reply_type)

            elif reply_type == YieldType.TOOL_CALL:
                # Append to an existing label for streaming effect, or create a new one
                if self.current_tool_call_label is None:
                    self.current_tool_call_label = self._add_message_row(
                        content,
                        reply_type
                    )
                else:
                    existing_text = self.current_tool_call_label.get_text()
                    # Append new content
                    self.current_tool_call_label.set_text(existing_text + " " + content)

            elif reply_type == YieldType.FINAL:
                # Final reply from the chatbot.
                self._add_message_row(content, reply_type)

            # Since we successfully retrieved and processed an item,
            # we immediately check the queue again for the next item.
            return GLib.SOURCE_CONTINUE

        except Exception as e:
            # Handle unexpected errors on the main GTK thread
            error_message = f"Critical UI Error: {type(e).__name__} - {e}"
            LOG.error(error_message, exc_info=True)
            self._add_message_row(f"Application Error. {error_message}", YieldType.FINAL)

            return GLib.SOURCE_REMOVE    # Stop the process on error

    def on_process_button_clicked(self, widget):
        """
        Callback function when the 'Send' button is clicked or 'Enter' is pressed.
        """
        # Check if the chat_logic instance has been set.
        # This handles the case where the addon is loaded for the first time
        # on an already running Gramps session.
        if self.chat_service is None:
            self._add_message_row(
                _("The ChatWithTree addon is not yet initialized. \
                  Please reload Gramps or select a database."),
                YieldType.FINAL
            )
            return

        if self.chat_service.is_processing():
            self._add_message_row(
                _("The chatbot is currently processing a query. Please wait."),
                YieldType.PARTIAL
            )
            return
        # Normal handling of user input
        user_input = self.input_entry.get_text()
        self.input_entry.set_text("")
        if user_input.strip():
            # Add the user's message to the chat.
            self._add_message_row(f"{user_input}", YieldType.USER)

            # Now, schedule the reply-getting logic to run when the main loop is idle.
            # Run the asynchronous processing for this single query
            try:
                self.current_tool_call_label = None
                # 1. Start the job in the background (non-blocking call)
                self.chat_service.start_query(user_input)

                # queue-checking logic to run repeatedly on the main thread
                # consumes the yielded results from the worker thread
                GLib.idle_add(self._check_queue_for_reply)

            except Exception as e:
                LOG.error(f"Error running async query: {e}")
                self._add_message_row(
                     _("An error occurred while processing your query."),
                     YieldType.FINAL
                )
                return

    async def process_query_async(self, query):
        """
        Asynchronously processes a single query and prints the replies as they come in.
        """
        # The ChatThreading service handles all the threading and queues.
        # We just iterate over the async generator it returns.
        async for reply in self.chat_service.get_reply_stream(query):
            reply_type, content = reply
            if reply_type == YieldType.PARTIAL:
                # sometimes there is no content in the partial yield
                # if there is, it is usually an explained strategy what the
                # model will do to achieve the final result
                self._add_message_row(content, reply_type)
            if reply_type == YieldType.TOOL_CALL:
                if self.current_tool_call_label is None:
                    self.current_tool_call_label = self._add_message_row(
                        content,
                        reply_type
                        )
                else:
                    # This is a subsequent tool call. Update the existing label.
                    # We append the new content to the existing label.
                    existing_text = self.current_tool_call_label.get_text()
                    self.current_tool_call_label.set_text(existing_text + " " + content)
            elif reply_type == YieldType.FINAL:
                # Final reply from the chatbot
                # We let the iterator SENTINEL take care of returning Glib.SOURCE_REMOVE
                self._add_message_row(content, reply_type)

    def main(self):
        """
        This method is called when the Gramplet needs to update its content.
        """
        pass

    def destroy(self):
        """
        Clean up resources when the Gramplet is closed.
        """
        Gramplet.destroy(self)
