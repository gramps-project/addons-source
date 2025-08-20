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
LOG = logging.getLogger(".")
LOG.debug("loading chatwithtree")
# ==============================================================================
# Standard Python libraries
# ==============================================================================
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk
from gi.repository import GLib

# ==============================================================================
# GRAMPS API
# ==============================================================================
from gramps.gen.plug import Gramplet
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.get_addon_translator(__file__).gettext

from chatwithllm import IChatLogic, ChatWithLLM, YieldType

try:
    from ChatWithTreeBot import ChatBot
except ImportError as e:
    LOG.warning(e)
    raise ImportError("Failed to import ChatBot from chatbot module: " + str(e))

LOG.debug("ChatWithTree file header loaded successfully.")

ONE_SECOND = 1000 # milliseconds

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
        
        # Instantiate the chat logic class. This decouples the logic from the UI.
        # Choose ChatWIthLLM for simple reverse chat
        # self.chat_logic = ChatWithLLM()
        # Choose Chatbot for chat with Tree
        self.chat_logic = None
        #self.chat_logic = ChatBot(self)
    
    def change_db(self, db):
        """
        This method is called when the database is opened or closed.
        The 'dbstate' parameter is the current database state object.
        """
        # Add the initial message to the list box.
        self._add_message_row(_("Database change detected"), YieldType.PARTIAL)
        
        if self.dbstate.db:
            LOG.debug("Database handle is now available. Initializing chatbot.")
            # The database is open, so it is now safe to instantiate the chatbot
            # and pass the Gramplet instance with a valid db handle.
            self.chat_logic = ChatBot(self)
        else:
            LOG.debug("Database is closed. Chatbot logic is reset.")
            self.chat_logic = None

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
        self._add_message_row(_("Chat with Tree initialized. Type /help for help."), YieldType.PARTIAL)
        
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
        context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        
        # We need to set up a style context on the chat listbox
        style_context = self.chat_listbox.get_style_context()
        style_context.add_class("message-box") # This won't work on the listbox itself, but it's good practice.

    def _add_message_row(self, text:str, reply_type: YieldType):
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
        message_label.set_max_width_chars(80) # Limit width to prevent it from spanning the entire window.
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

        # The goal is to scroll down after adding a row to the box
        # after one full second
        # so that Gtk has time to redraw the listbox in that time
        GLib.timeout_add(ONE_SECOND, self.scroll_to_bottom)
            
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

    def _get_reply_on_idle(self):
        """
        This is a separate method and to be called via GLib.idle_add
        Goal: gets the reply from chatbot and updates the UI.
        It runs when the main loop is idle, therefore we return
        either GLib.SOURCE_CONTINUE in case there are more replies,
        or GLib.SOURCE_REMOVE when the iteration is done
        """
        try:
            
            # Using a sentinel object to check for exhaustion
            SENTINEL = object()
            # use the assigned self.reply_iterator iterator to get the next reply
            result = next(self.reply_iterator, SENTINEL)
            if result is SENTINEL:
                # end of iteration, no replies from iterator
                return GLib.SOURCE_REMOVE
            # unpack the result tuple
            reply_type, content = result 
            if reply_type == YieldType.PARTIAL:
                # sometimes there is no content in the partial yield
                # if there is, it is usually an explained strategy what the
                # model will do to achieve the final result
                self._add_message_row(content, reply_type)
            if reply_type == YieldType.TOOL_CALL:
                if self.current_tool_call_label is None:
                    self.current_tool_call_label = self._add_message_row(content, reply_type)
                else:
                # This is a subsequent tool call. Update the existing label.
                # We append the new content to the old content for a streaming effect.
                    existing_text = self.current_tool_call_label.get_text()
                    self.current_tool_call_label.set_text(existing_text + " " + content)
            elif reply_type == YieldType.FINAL:
                # Final reply from the chatbot
                # We let the iterator SENTINEL take care of returning Glib.SOURCE_REMOVE
                self._add_message_row(content, reply_type)
    
            return GLib.SOURCE_CONTINUE
            
        except Exception as e:
            # Handle potential errors from the get_reply function
            error_message = f"Error: {type(e).__name__} - {e}"
            self._add_message_row(f"Type 'help' for help. \n{error_message}", YieldType.PARTIAL)
                
            return GLib.SOURCE_REMOVE # Stop the process on error
            
        # This function must return False to be removed from the idle handler list.
        # If it returns True, it will be called again on the next idle loop.
        return False
     
    def on_process_button_clicked(self, widget):
        """
        Callback function when the 'Send' button is clicked or 'Enter' is pressed.
        """
        # Check if the chat_logic instance has been set.
        # This handles the case where the addon is loaded for the first time
        # on an already running Gramps session.
        if self.chat_logic is None:
            self._add_message_row(
                _("The ChatWithTree addon is not yet initialized. Please reload Gramps or select a database."),
                YieldType.FINAL
            )
            return
        # Normal handling of user input
        user_input = self.input_entry.get_text()
        self.input_entry.set_text("")
        if user_input.strip():
            # Add the user's message to the chat.
            self._add_message_row(f"{user_input}", YieldType.USER)
                        
            # Now, schedule the reply-getting logic to run when the main loop is idle.
            self.reply_iterator = self.chat_logic.get_reply(user_input)
            self.current_tool_call_label = None
            
            GLib.idle_add(self._get_reply_on_idle)
            
        
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
