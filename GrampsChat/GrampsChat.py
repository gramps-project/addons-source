# Clock Example by Ralph Glass
# http://ralph-glass.homepage.t-online.de/clock/readme.html

from gi.repository import Gtk, GObject, Pango, GLib
import threading
import os

try:
    import litellm
except ImportError:
    raise Exception("GrampsChat requires litellm")
# import markdown

from gramps.gen.plug import Gramplet
from gramps.gen.const import GRAMPS_LOCALE as glocale

_ = glocale.translation.gettext

HELP_TEXT = """
GrampsChat uses the following OS environment variables:

```
export GRAMPS_AI_MODEL_NAME="<ENTER MODEL NAME HERE>"
```

This is always needed. Examples: "ollama/deepseek-r1:1.5b", "openai/gpt-4o-mini"

```
export GRAMPS_AI_MODEL_URL="<ENTER URL HERE>" 
```

This is needed if running your own LLM server. Example: "http://127.0.0.1:8000"

You can find a list of litellm providers here:
https://docs.litellm.ai/docs/providers

You can find a list of ollama models here:
https://ollama.com/library/deepseek-r1:1.5b

### Optional

If you are running a commercial AI model provider, you will need their API key.

#### Example

For OpenAI:

```
export OPENAI_API_KEY="sk-..."
```

To record your conversations in Opik:

```
export OPIK_API_KEY="<ENTER OPIK API KEY HERE>"
```

To get an Opik API Key:
https://www.comet.com/site/
"""

SYSTEM_PROMPT = """
You are a helpful genealogist and an expert in the
Gramps open source genealogy program.
"""

GRAMPS_AI_MODEL_NAME = os.environ.get("GRAMPS_AI_MODEL_NAME")
GRAMPS_AI_MODEL_URL = os.environ.get("GRAMPS_AI_MODEL_URL")
OPIK_API_KEY = os.environ.get("OPIK_API_KEY")
OPIK_PROJECT_NAME = os.environ.get("OPIK_PROJECT_NAME")
if OPIK_PROJECT_NAME is None:
    os.environ["OPIK_PROJECT_NAME"] = "gramps"

if OPIK_API_KEY:
    try:
        from litellm.integrations.opik.opik import OpikLogger
    except Exception:
        raise Exception("GrampsChat with OPIK_API_KEY set requires opik")

    opik_logger = OpikLogger()
    litellm.callbacks = [opik_logger]


class GrampsChat(Gramplet):
    def init(self):
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.gui.WIDGET)

    def build_gui(self):
        """
        Build the GUI interface.
        """
        self.top = Chatbot()
        self.top.show_all()
        return self.top


class Chatbot(Gtk.Box):
    def __init__(self, parent=None):
        super(Chatbot, self).__init__(spacing=10, orientation=Gtk.Orientation.VERTICAL)
        self.thread = None
        self.set_border_width(10)

        self.textview = Gtk.TextView()
        self.textview.set_editable(False)
        self.textview.connect("button-press-event", self.on_button_press)
        self.textview.set_editable(False)
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)

        self.textbuffer = self.textview.get_buffer()
        tag = self.textbuffer.create_tag("user_message")
        tag.set_property("justification", Gtk.Justification.LEFT)
        tag.set_property("weight", Pango.Weight.BOLD)
        # tag.set_property("background", "#E9EEF6")
        tag = self.textbuffer.create_tag("chatbot_message")
        tag.set_property("justification", Gtk.Justification.LEFT)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(self.textview)  # Use add() in Gtk 3
        self.pack_start(scrolled_window, True, True, 0)  # Use pack_start

        hbox = Gtk.Box(spacing=5, orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label(label="Ask Gramps:")
        self.entry = Gtk.Entry()
        self.entry.set_halign(Gtk.Align.FILL)
        self.entry.connect("activate", self.on_send_clicked)
        hbox.pack_start(label, False, False, 0)
        hbox.pack_start(self.entry, True, True, 0)
        self.pack_start(hbox, False, False, 0)

        self.clear_button = Gtk.Button(label="New Conversation")
        self.clear_button.connect("clicked", self.on_clear_clicked)
        self.pack_start(self.clear_button, False, False, 0)
        self.on_clear_clicked()

        if GRAMPS_AI_MODEL_NAME is None:
            self.append_message(HELP_TEXT, is_user=False)
        else:
            self.append_message(
                f"""Enviroment:
    GRAMPS_AI_MODEL_NAME="{GRAMPS_AI_MODEL_NAME}"
    GRAMPS_AI_MODEL_URL="{GRAMPS_AI_MODEL_URL if GRAMPS_AI_MODEL_URL else ''}"

""",
                is_user=False,
            )

        self.show_all()

    def on_button_press(self, widget, event):
        return True

    def append_message(self, message, is_user=False):
        # FIXME: write a dynamic parser
        # text = markdown.markdown(message)
        # replacements = [
        #     ("<p>", ""), ("</p>", " "),
        #     ("<strong>", "<b>"), ("</strong>", "</b>"),
        #     ("<em>", "<i>"), ("</em>", "</i>"),
        #     ("
        #     ("<code>", "<span font_family='monospace'>"), ("</code>", "</span>"),
        #     ("<h1>", "<span size='xx-large' weight='bold'>"), ("</h1>", "</span>"),
        #     ("<h2>", "<span size='x-large' weight='bold'>"), ("</h2>", "</span>"),
        #     ("<h3>", "<span size='large' weight='bold'>"), ("</h3>", "</span>"),
        #     ("<h4>", "<span size='medium' weight='bold'>"), ("</h4>", "</span>"),
        # ]
        # for old, new in replacements:
        #     text = text.replace(old, new)
        # self.textbuffer.insert_markup(self.textbuffer.get_end_iter(), text, -1)

        text = message
        self.textbuffer.insert_at_cursor(text, len(text))

        end_iter = self.textbuffer.get_end_iter()
        start_iter = self.textbuffer.get_iter_at_offset(
            end_iter.get_offset() - len(text)
        )

        if is_user:
            tag_name = "user_message"
        else:
            tag_name = "chatbot_message"
        tag = self.textbuffer.get_tag_table().lookup(tag_name)
        self.textbuffer.apply_tag(tag, start_iter, end_iter)

        iter = self.textbuffer.get_end_iter()
        self.textview.scroll_to_iter(iter, 0.0, False, 0.0, 1.0)
        # self.textview.scroll_to_iter(iter, True, True, 0.0, 1.0)

    def append_message_chunk(self, chunk):
        if chunk:
            chunk = chunk.replace("<think>", "")
            chunk = chunk.replace("</think>", "\nDone with analysis.")
            self.append_message(chunk, is_user=False)
        return False

    def on_send_clicked(self, widget):
        user_input = self.entry.get_text()
        if user_input:
            self.entry.set_text("")
            self.append_message(user_input + "\n\n", is_user=True)
            if user_input.lower().strip() == "help":
                self.append_message(HELP_TEXT, is_user=False)
            else:
                self.append_message("Thinking...\n\n", is_user=False)

                if GRAMPS_AI_MODEL_NAME is not None:
                    self.entry.set_sensitive(False)
                    self.clear_button.set_sensitive(False)
                    if self.thread:
                        self.thread.join()
                    self.thread = threading.Thread(
                        target=self.get_chatbot_response, args=(user_input,)
                    )
                    self.thread.daemon = True
                    self.thread.start()

    def on_clear_clicked(self, widget=None):
        self.messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
        ]
        self.textbuffer.set_text("")

    def get_chatbot_response(self, user_input):
        self.messages.append({"role": "user", "content": user_input})
        response = litellm.completion(
            model=GRAMPS_AI_MODEL_NAME,
            api_base=GRAMPS_AI_MODEL_URL,
            messages=self.messages[:],
            stream=True,
        )
        retval = ""
        for chunk in response:
            text = chunk.choices[0].delta.content
            if text is not None:
                retval += text
                GLib.idle_add(self.append_message_chunk, text)
        GLib.idle_add(self.append_message_chunk, "\n\n\n")
        self.messages.append(
            {
                "role": "assistant",
                "content": retval,
            }
        )
        self.entry.set_sensitive(True)
        self.clear_button.set_sensitive(True)
        self.entry.grab_focus()
