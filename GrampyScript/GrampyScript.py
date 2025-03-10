#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021-2023 Kari Kujansuu
# Copyright (C) 2025      Doug Blank
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

import csv
import ast
import keyword
import datetime
from collections import defaultdict
import math
import time
import traceback
import sys
import re
import io
import os

from gi.repository import Gtk, Gdk, cairo, Pango

from gramps.gen.db import DbTxn
from gramps.gen.plug import Gramplet
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.datehandler import displayer as date_displayer
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.lib import Date
from gramps.gen.simple import SimpleAccess
from gramps.gui.widgets.undoablebuffer import UndoableBuffer
from gramps.gui.utils import match_primary_mask
from gramps.gen.config import config as configman
from gramps.gui.dialog import OkDialog, ErrorDialog
from gramps.gui.editors import (
    EditCitation,
    EditEvent,
    EditFamily,
    EditMedia,
    EditNote,
    EditPerson,
    EditPlace,
    EditRepository,
    EditSource,
)
from datadict2 import DataDict2, NoneData, set_sa

_ = glocale.translation.gettext

config = configman.register_manager("grampy_script")
config.register("defaults.encoding", "utf-8")
config.register("defaults.delimiter", "comma")
config.register("defaults.last_filename", "")

def contains_any_none_data(args):
    if isinstance(args, list):
        return any(contains_any_none_data(arg) for arg in args)
    else:
        return not isinstance(args, NoneData)


def get_columns(source, func_name):
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if hasattr(node.func, "id") and node.func.id == func_name:
                    return [ast.unparse(arg) for arg in node.args]
    except Exception:
        return []


class ScriptOpenFileChooserDialog(Gtk.FileChooserDialog):
    def __init__(self, uistate):
        # type: (DisplayState) -> None
        Gtk.FileChooserDialog.__init__(
            self,
            title=_("Load query from a .script file"),
            transient_for=uistate.window,
            action=Gtk.FileChooserAction.OPEN,
        )

        self.add_buttons(
            _("_Cancel"), Gtk.ResponseType.CANCEL, _("Load"), Gtk.ResponseType.OK
        )

        filter_scriptfile = Gtk.FileFilter()
        filter_scriptfile.set_name("Script files")
        filter_scriptfile.add_pattern("*" + ".gram.py")
        self.add_filter(filter_scriptfile)

        filter_json = Gtk.FileFilter()
        filter_json.set_name("JSON files")
        filter_json.add_pattern("*.json")
        self.add_filter(filter_json)

        filter_all = Gtk.FileFilter()
        filter_all.set_name("All files")
        filter_all.add_pattern("*.*")
        self.add_filter(filter_all)


class ScriptSaveFileChooserDialog(Gtk.FileChooserDialog):
    def __init__(self, uistate):
        # type: (DisplayState) -> None
        Gtk.FileChooserDialog.__init__(
            self,
            title=_("Save query to a .script file"),
            transient_for=uistate.window,
            action=Gtk.FileChooserAction.SAVE,
        )

        self.add_buttons(
            _("_Cancel"), Gtk.ResponseType.CANCEL, _("Save"), Gtk.ResponseType.OK
        )

        filter_scriptfile = Gtk.FileFilter()
        filter_scriptfile.set_name("Script files")
        filter_scriptfile.add_pattern("*" + ".gram.py")
        self.add_filter(filter_scriptfile)


class CsvFileChooserDialog(Gtk.FileChooserDialog):
    def __init__(self, uistate):
        # type: (DisplayState) -> None
        Gtk.FileChooserDialog.__init__(
            self,
            title=_("Download results as a CSV file"),
            transient_for=uistate.window,
            action=Gtk.FileChooserAction.SAVE,
        )

        self.add_buttons(
            _("_Cancel"), Gtk.ResponseType.CANCEL, _("Save"), Gtk.ResponseType.OK
        )

        box = Gtk.VBox()
        box1 = Gtk.HBox()
        box2 = Gtk.HBox()

        encoding = config.get("defaults.encoding")
        delimiter = config.get("defaults.delimiter")

        self.cb_utf8 = Gtk.RadioButton.new_with_label_from_widget(None, "UTF-8")
        self.cb_iso8859_1 = Gtk.RadioButton.new_with_label_from_widget(
            self.cb_utf8, "ISO8859-1"
        )
        if encoding == "iso8859-1":
            self.cb_iso8859_1.set_active(True)

        box1.add(Gtk.Label("Encoding:"))
        box1.add(self.cb_utf8)
        box1.add(self.cb_iso8859_1)
        frame1 = Gtk.Frame()
        frame1.add(box1)

        self.cb_comma = Gtk.RadioButton.new_with_label_from_widget(None, "comma")
        self.cb_semicolon = Gtk.RadioButton.new_with_label_from_widget(
            self.cb_comma, "semicolon"
        )
        if delimiter == ";":
            self.cb_semicolon.set_active(True)

        box2.add(Gtk.Label("Delimiter:"))
        box2.add(self.cb_comma)
        box2.add(self.cb_semicolon)
        frame2 = Gtk.Frame()
        frame2.add(box2)
        box.set_spacing(5)
        box.add(frame1)
        box.add(frame2)
        box.show_all()
        self.set_extra_widget(box)
        self.set_do_overwrite_confirmation(True)

        filter_csv = Gtk.FileFilter()
        filter_csv.set_name("CSV files")
        filter_csv.add_pattern("*.csv")
        self.add_filter(filter_csv)

class GrampyScript(Gramplet):
    def init(self):
        self.keywords = [
            "_",
            "and",
            "as",
            "assert",
            "async",
            "await",
            "break",
            "case",
            "class",
            "continue",
            "def",
            "del",
            "elif",
            "else",
            "except",
            "finally",
            "for",
            "from",
            "global",
            "if",
            "import",
            "in",
            "is",
            "lambda",
            "match",
            "nonlocal",
            "not",
            "or",
            "pass",
            "raise",
            "return",
            "try",
            "type",
            "while",
            "with",
            "yield",
        ]
        self.functions = [
            "print",
            "row",
            "columns",
            "begin_changes",
            "end_changes",
            "counter",
            "people",
            "families",
            "notes",
            "repositories",
            "sources",
            "citations",
            "media",
            "places",
            "events",
            "selected",
            "filtered",
        ]
        self.constants = [
            "True",
            "False",
            "None",
            "today",
            "active_note",
            "active_media",
            "active_person",
            "active_family",
            "active_repository",
            "active_source",
            "active_citation",
            "active_place",
            "active_event",
        ]
        config.load()
        self.csv_filename = ""
        self.last_filename = config.get("defaults.last_filename")
        self.column_names = []
        self.treeview = None
        self.liststore = None
        self.text_length = 0
        self.chart_data = None
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.gui.WIDGET)
        if os.path.exists(self.last_filename):
            self.ebuf.set_text(open(self.last_filename).read())
            self.statusmsg.set_text("Loaded %r" % self.last_filename)
        else:
            self.statusmsg.set_text("Current filename: %r" % self.last_filename)
            self.ebuf.set_text(
                """# This is a sample script

for person in people():
    row(person)
"""
            )

    def build_gui(self):
        """
        Build the GUI interface.
        """
        widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        menubar = Gtk.MenuBar()

        filemenu = Gtk.Menu()
        fileitem = Gtk.MenuItem(label=_("Script"))
        fileitem.set_submenu(filemenu)
        newitem = Gtk.MenuItem(label=_("New"))
        openitem = Gtk.MenuItem(label=_("Open..."))
        save_item = Gtk.MenuItem(label=_("Save"))
        save_as_item = Gtk.MenuItem(label=_("Save as..."))
        filemenu.append(newitem)
        filemenu.append(openitem)
        filemenu.append(save_item)
        filemenu.append(save_as_item)
        menubar.append(fileitem)
        newitem.connect("activate", self.new_script)
        openitem.connect("activate", self.open_script)
        save_as_item.connect("activate", self.save_as_script)
        save_item.connect("activate", self.save_script)

        datamenu = Gtk.Menu()
        dataitem = Gtk.MenuItem(label=_("Data"))
        dataitem.set_submenu(datamenu)
        save_csv = Gtk.MenuItem(label=_("Save as CSV"))
        copy_to_clipboard = Gtk.MenuItem(label=_("Copy to clipboard"))
        datamenu.append(save_csv)
        datamenu.append(copy_to_clipboard)
        menubar.append(dataitem)
        save_csv.connect("activate", self.save_csv)
        copy_to_clipboard.connect("activate", self.copy_to_clipboard)

        widget.pack_start(menubar, False, False, 0)
        widget.set_border_width(6)
        self.accel_group = Gtk.AccelGroup()
        self.uistate.window.add_accel_group(self.accel_group)

        save_item.add_accelerator(
            "activate", self.accel_group, ord('s'),
            Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE
        )

        self.editor = Gtk.ScrolledWindow()
        self.editor.set_shadow_type(Gtk.ShadowType.IN)
        self.editor_textview = Gtk.TextView()
        self.editor.add(self.editor_textview)
        font_desc = self.editor_textview.get_pango_context().get_font_description()
        font_desc.set_family(
            "Monospace"
        )  # You can also use "Courier New", "Consolas", etc.
        self.editor_textview.modify_font(font_desc)

        self.editor_textview.connect("key-press-event", self.on_key_press)
        self.editor_textview.connect("button-press-event", self.on_textview_click)
        key, mods = Gtk.accelerator_parse("<Alt>c")
        self.editor_textview.add_accelerator(
            "copy-clipboard", self.accel_group, key, mods, Gtk.AccelFlags.VISIBLE
        )
        key, mods = Gtk.accelerator_parse("<Control>v")
        self.editor_textview.add_accelerator(
            "paste-clipboard", self.accel_group, key, mods, Gtk.AccelFlags.VISIBLE
        )
        key, mods = Gtk.accelerator_parse("<Control>x")
        self.editor_textview.add_accelerator(
            "cut-clipboard", self.accel_group, key, mods, Gtk.AccelFlags.VISIBLE
        )
        self.ebuf = UndoableBuffer()
        self.editor_textview.set_buffer(self.ebuf)
        self.keyword_tag = self.ebuf.create_tag(
            "keyword", foreground="blue", weight=700
        )
        self.constant_tag = self.ebuf.create_tag(
            "constant", foreground="red", weight=700
        )
        self.function_tag = self.ebuf.create_tag(
            "function", foreground="green", weight=700
        )
        self.comment_tag = self.ebuf.create_tag(
            "comment", foreground="gray", style=Pango.Style.ITALIC
        )
        self.ebuf.connect("changed", self.on_buffer_changed)

        widget.pack_start(self.editor, True, True, 0)

        self.notebook = Gtk.Notebook()

        self.page1 = Gtk.ScrolledWindow()
        self.notebook.append_page(self.page1, Gtk.Label(label=_("Table")))

        page2 = Gtk.ScrolledWindow()
        textview = Gtk.TextView()
        self.notebook.append_page(page2, Gtk.Label(label=_("Output")))
        page2.add(textview)
        textview.modify_font(font_desc)
        self.output_buffer = textview.get_buffer()

        page3 = Gtk.ScrolledWindow()
        self.canvas = Gtk.DrawingArea()
        self.canvas.connect("draw", self.on_draw)
        page3.add(self.canvas)
        self.notebook.append_page(page3, Gtk.Label(label=_("Chart")))

        widget.pack_start(self.notebook, True, True, 0)

        bbox = Gtk.ButtonBox()
        self.apply_button = Gtk.Button(label=_("Execute <Alt+Enter>"))
        self.apply_button.connect("clicked", self.apply_clicked)
        self.apply_button.set_tooltip_text(_("Execute the script"))
        css = b"* {background: #00aa00; color: white}"
        provider = Gtk.CssProvider()
        try:
            provider.load_from_data(css)
            self.apply_button.get_style_context().add_provider(
                provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        except:
            pass

        bbox.pack_start(self.apply_button, False, False, 6)
        widget.pack_start(bbox, False, False, 6)

        self.statusmsg = Gtk.Label(_("Ready..."))
        self.statusmsg.set_xalign(0)  # 0.0 for left, 0.5 for center, 1.0 for right
        self.statusmsg.get_style_context().add_class('bordered-label')  #add a css class
        css = b"""
        .bordered-label {
            border: 1px solid gray;
            padding: 1px; 
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        self.statusmsg.get_style_context().add_provider(
            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        widget.pack_start(self.statusmsg, False, False, 1)

        widget.show_all()
        return widget

    def new_script(self, widget):
        # type: (Any) -> None
        self.ebuf.set_text("")
        self.statusmsg.set_text("Ready...")

    def open_script(self, widget):
        # type: (Gtk.Widget) -> None
        choose_file_dialog = ScriptOpenFileChooserDialog(self.uistate)
        if self.last_filename:
            choose_file_dialog.set_filename(self.last_filename)

        while True:
            response = choose_file_dialog.run()
            if response == Gtk.ResponseType.CANCEL:
                break
            elif response == Gtk.ResponseType.DELETE_EVENT:
                break
            elif response == Gtk.ResponseType.OK:
                filename = choose_file_dialog.get_filename()
                self.ebuf.set_text(open(filename).read())
                self.statusmsg.set_text("Script loaded")
                self.last_filename = filename
                config.set("defaults.last_filename", filename)
                config.save()
                self.statusmsg.set_text("Loaded %r" % self.last_filename)
                break

        choose_file_dialog.destroy()

    def save_script(self, widget):
        with open(self.last_filename, "w") as fp:
            fp.write(self.get_text())
        self.statusmsg.set_text("Saved %r" % self.last_filename)

    def save_as_script(self, widget):
        choose_file_dialog = ScriptSaveFileChooserDialog(self.uistate)
        title = "Script"
        fname = title + ".gram.py"
        choose_file_dialog.set_current_name(fname)
        choose_file_dialog.set_do_overwrite_confirmation(True)
        if self.last_filename:
            choose_file_dialog.set_filename(self.last_filename)

        while True:
            response = choose_file_dialog.run()
            if response == Gtk.ResponseType.CANCEL:
                break
            elif response == Gtk.ResponseType.DELETE_EVENT:
                break
            elif response == Gtk.ResponseType.OK:
                filename = choose_file_dialog.get_filename()
                with open(filename, "w") as fp:
                    fp.write(self.get_text())
                self.last_filename = filename
                config.set("defaults.last_filename", filename)
                config.save()
                self.statusmsg.set_text("Saved as %r (now current)" % self.last_filename)
                break

        choose_file_dialog.destroy()

    def save_csv(self, widget):
        if self.liststore is None:
            self.statusmsg.set_text("No data to save")
            return
        # type: (Gtk.Widget) -> None
        choose_file_dialog = CsvFileChooserDialog(self.uistate)
        title = "Script"
        fname = title + ".gram.csv"

        choose_file_dialog.set_current_name(fname)
        if self.csv_filename:
            if title:
                dirname = os.path.split(self.csv_filename)[0]
                self.csv_filename = os.path.join(dirname, fname)
            choose_file_dialog.set_filename(self.csv_filename)

        while True:
            response = choose_file_dialog.run()
            if response == Gtk.ResponseType.CANCEL:
                break
            elif response == Gtk.ResponseType.DELETE_EVENT:
                break
            elif response == Gtk.ResponseType.OK:
                self.csv_filename = choose_file_dialog.get_filename()
                delimiter = ","
                if choose_file_dialog.cb_comma.get_active():
                    delimiter = ","
                if choose_file_dialog.cb_semicolon.get_active():
                    delimiter = ";"
                encoding = "utf-8"
                if choose_file_dialog.cb_utf8.get_active():
                    encoding = "utf-8"
                if choose_file_dialog.cb_iso8859_1.get_active():
                    encoding = "iso8859-1"

                config.set("defaults.encoding", encoding)
                config.set("defaults.delimiter", delimiter)
                config.save()

                #assert self.csv_filename is not None  # for mypy
                try:
                    writer = csv.writer(
                        open(self.csv_filename, "w", encoding=encoding, newline=""),
                        delimiter=delimiter,
                    )
                    for row in self.liststore:
                        writer.writerow(row)
                except Exception as e:
                    msg = traceback.format_exc()
                    ErrorDialog("Saving the file failed", msg)

                break

        choose_file_dialog.destroy()

    def copy_to_clipboard(self, widget):
        if self.liststore is None:
            self.statusmsg.set_text("No data to copy")
            return
        # type: (Gtk.Widget) -> None
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        stringio = io.StringIO()
        writer = csv.writer(stringio)
        for row in self.liststore:
            writer.writerow(row)
        clipboard.set_text(stringio.getvalue(), -1)
        OkDialog("Info", "Result list copied to clipboard")

    def on_buffer_changed(self, buffer):
        self.highlight_syntax()

    def highlight_syntax(self):
        start_iter = self.ebuf.get_start_iter()
        end_iter = self.ebuf.get_end_iter()
        self.ebuf.remove_all_tags(start_iter, end_iter)  # Clear previous highlighting

        text = self.ebuf.get_text(start_iter, end_iter, True)

        comment_matches = []
        for match in re.finditer(r"#.*", text):
            start = self.ebuf.get_iter_at_offset(match.start())
            end = self.ebuf.get_iter_at_offset(match.end())
            self.ebuf.apply_tag(self.comment_tag, start, end)
            comment_matches.append((match.start(), match.end()))

        def inside_comment(match):
            start_offset = match.start()
            end_offset = match.end()
            # Check if the keyword overlaps with a comment
            for comment_start, comment_end in comment_matches:
                if start_offset >= comment_start and end_offset <= comment_end:
                    return True
            return False

        for keyword in self.keywords:
            for match in re.finditer(r"\b" + keyword + r"\b", text):
                if not inside_comment(match):
                    start = self.ebuf.get_iter_at_offset(match.start())
                    end = self.ebuf.get_iter_at_offset(match.end())
                    self.ebuf.apply_tag(self.keyword_tag, start, end)
        for constant in self.constants:
            for match in re.finditer(r"\b" + constant + r"\b", text):
                if not inside_comment(match):
                    start = self.ebuf.get_iter_at_offset(match.start())
                    end = self.ebuf.get_iter_at_offset(match.end())
                    self.ebuf.apply_tag(self.constant_tag, start, end)
        for function in self.functions:
            for match in re.finditer(r"\b" + function + r"\b", text):
                if not inside_comment(match):
                    start = self.ebuf.get_iter_at_offset(match.start())
                    end = self.ebuf.get_iter_at_offset(match.end())
                    self.ebuf.apply_tag(self.function_tag, start, end)

    def treeview_button_press(self, treeview, event):
        # type: (Gtk.TreeView, Gtk.Event) -> bool
        try:  # may fail if clicked too frequently
            if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS and event.button == 1:
                model, treeiter = self.treeview.get_selection().get_selected() # type: ignore
                row = list(model[treeiter])
                self.edit_object(row[-2], row[-1])
                return True
        except Exception:
            traceback.print_exc()
        return False

    def edit_object(self, table_name, handle):
        map = {
            "Person": EditPerson,
            "Family": EditFamily,
            "Note": EditNote,
            "Event": EditEvent,
            "Place": EditPlace,
            "Repository": EditRepository,
            "Source": EditSource,
            "Citation": EditCitation,
            "Media": EditMedia,
        }
        if table_name in map:
            editfunc = map[table_name]
            obj = self.db._get_table_func(table_name, "handle_func")(handle)
            editfunc(self.dbstate, self.uistate, [], obj)

    def add_table(self, args):
        # We store all data as strings
        types = [str for arg in args] + [str, str] # type, handle
        self.liststore = Gtk.ListStore(*types)
        self.treeview = Gtk.TreeView(model=self.liststore)
        self.treeview.connect("button-press-event", self.treeview_button_press)
        for i, column_name in enumerate(self.column_names):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(
                column_name.replace("_", "__"), renderer, text=i
            )
            column.set_sort_column_id(i)  # Enable sorting for the column
            self.treeview.append_column(column)

            column_type = type(args[i])
            self.liststore.set_sort_func(i, self.get_sort_column(column_type), i)
        
        self.page1.add(self.treeview)
        self.page1.show_all()

    def get_sort_column(self, func):

        if func not in [str, int, float]:
            func = str

        def sort_column(model, row1, row2, data):
            value1 = model.get_value(row1, data)
            value2 = model.get_value(row2, data)

            if value1 is None and value2 is None:
                return 0  # None equals None
            elif value1 is None:
                return -1  # None is smaller
            elif value2 is None:
                return 1  # None is smaller

            value1 = func(value1)
            value2 = func(value2)

            if value1 < value2:
                return -1
            elif value1 > value2:
                return 1
            else:
                return 0

        return sort_column

    def sort_int(self, model, row1, row2, data):
        value1 = int(model.get_value(row1, data))
        value2 = int(model.get_value(row2, data))
        if value1 < value2:
            return -1
        elif value1 > value2:
            return 1
        else:
            return 0

    def sort_float(self, model, row1, row2, data):
        value1 = float(model.get_value(row1, data))
        value2 = float(model.get_value(row2, data))
        if value1 < value2:
            return -1
        elif value1 > value2:
            return 1
        else:
            return 0

    def row(self, *args):
        if self.treeview is None:
            self.add_table(args)

        if contains_any_none_data(args[0]):
            self.count += 1
            table_name = None
            handle = None
            for arg in args:
                if isinstance(arg, dict) and hasattr(arg, "root"):
                    table_name = arg.root["_class"]
                    handle = arg.root["handle"]
                    break
            self.liststore.append([self.pp(arg) for arg in args] + [table_name, handle])

    def pp(self, item):
        if isinstance(item, list):
            return "; ".join([self.pp(i) for i in item])
        if isinstance(item, dict):
            if "_class" in item:
                if item["_class"] == "Person":
                    return "[%s] %s" % (
                        item.gramps_id,
                        self.sa.name(item._object),
                    )
                elif item["_class"] == "Event":
                    return "[%s] %s" % (
                        item.gramps_id,
                        self.sa.event_type(item._object),
                    )
                elif item["_class"] == "Family":
                    return "[%s] %s/%s" % (
                        item.gramps_id,
                        self.pp(item.mother),
                        self.pp(item.father),
                    )
                elif item["_class"] == "Media":
                    return "[%s] %s" % (item.gramps_id, item._object.desc)
                elif item["_class"] == "Source":
                    return "[%s] %s" % (
                        item.gramps_id,
                        self.sa.title(item._object),
                    )
                elif item["_class"] == "Citation":
                    return "[%s] %s" % (item.gramps_id, item.page if item.page else "")
                elif item["_class"] == "Place":
                    place_title = place_displayer.display(self.sa.dbase, item._object)
                    return "[%s] %s" % (item.gramps_id, place_title)
                elif item["_class"] == "Repository":
                    return "[%s] %s" % (item.gramps_id, item._object.type)
                elif item["_class"] == "Note":
                    return "[%s] %s" % (item.gramps_id, item._object.type)
                elif item["_class"] == "Tag":
                    return "%s" % (item.name)
                # Misc:
                elif item["_class"] == "Name":
                    return "%s, %s" % (
                        item.surname_list[0].surname,
                        item.first_name,
                    )
                elif item["_class"] == "Date":
                    return date_displayer.display(item._object) if item else ""
                elif item["_class"] == "PlaceName":
                    return item["value"]
                else:
                    return "<%s>" % item["_class"]
            else:
                # Dictionary
                return str(item)
        else:
            return str(item)

    def on_textview_click(self, widget, event):
        if event.button == 1:  # Left mouse button
            widget.grab_focus()

    def on_key_press(self, textview, event):
        if event.keyval == Gdk.KEY_Tab:
            # buffer = textview.get_buffer()
            iter_ = self.ebuf.get_iter_at_mark(self.ebuf.get_insert())
            self.ebuf.insert(iter_, "    ")  # Insert 4 spaces
            return True

        elif event.keyval == Gdk.KEY_Return and (
            event.state & Gdk.ModifierType.MOD1_MASK
        ):
            self.apply_button.emit("clicked")
            return True

        elif event.keyval == Gdk.KEY_c and (event.state & Gdk.ModifierType.MOD1_MASK):
            self.copy_selected_text()
            return True

        elif (Gdk.keyval_name(event.keyval) == "Z") and match_primary_mask(
            event.get_state(), Gdk.ModifierType.SHIFT_MASK
        ):
            self.redo()
            return True
        elif (Gdk.keyval_name(event.keyval) == "z") and match_primary_mask(
            event.get_state()
        ):
            self.undo()
            return True

        return False

    def undo(self):
        self.ebuf.undo()
        self.text_length = len(self.get_text())

    def redo(self):
        self.ebuf.redo()
        self.text_length = len(self.get_text())

    def get_text(self):
        start = self.ebuf.get_start_iter()
        end = self.ebuf.get_end_iter()
        return self.ebuf.get_text(start, end, True)  # include invisible chars

    def copy_selected_text(self):
        buffer = self.ebuf
        selection_bounds = buffer.get_selection_bounds()

        selection = buffer.get_selection_bounds()
        if selection_bounds:
            start, end = selection_bounds
            selected_text = buffer.get_text(start, end, True)
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(selected_text, -1)
            clipboard.store()

    def apply_clicked(self, obj):
        text = str(
            self.ebuf.get_text(
                self.ebuf.get_start_iter(), self.ebuf.get_end_iter(), False
            )
        )
        self.execute_code(text)

    def get_active_data(self, table_name):
        handle = self.get_active(table_name)
        if handle:
            method = self.db._get_table_func(table_name, "raw_func")
            data = method(handle)
            return DataDict2(dict(data), callback=self.callback)

    def callback(self, action, data):
        if action == "set":
            if "_class" in data:
                if self.db._get_table_func(data["_class"]):
                    method = self.db._table(data["_class"], "commit_func")
                    method(data._object, self.TRANSACTION)
                else:
                    raise Exception("%r class is not a PrimaryObject" % data["_class"])
            else:
                raise Exception("unable to add %r to transaction" % data)

    def chart(self, type, data, count=20, **kwargs):
        self.chart_data = (type, data, count, kwargs)

    def on_draw(self, widget, cr):
        colors = [
            (0.20, 0.45, 0.75),  # Blue
            (0.75, 0.30, 0.25),  # Red
            (0.65, 0.60, 0.20),  # Yellow
            (0.35, 0.65, 0.40),  # Green
            (0.55, 0.40, 0.70),  # Purple
            (0.25, 0.60, 0.65),  # Cyan
            (0.80, 0.55, 0.35),  # Orange
            (0.70, 0.70, 0.70),  # Light Grey
            (0.45, 0.45, 0.45),  # Medium Grey
            (0.15, 0.15, 0.15),  # Dark Grey
        ]
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        if self.chart_data:
            if self.chart_data[0] == "pie":
                # {"male": count, "female": count}
                if isinstance(self.chart_data[1], dict):
                    data = sorted(
                        self.chart_data[1].items(),
                        key=lambda row: row[1],
                        reverse=True,
                    )[: self.chart_data[2]]
                else:
                    # [["male", count], ["female", count]]
                    data = sorted(
                        self.chart_data[1],
                        key=lambda row: row[1],
                        reverse=True,
                    )[: self.chart_data[2]]

                center_x = width / 2
                center_y = height / 2
                radius = min(center_x, center_y) * 0.8  # Adjust radius as needed

                total = sum(count for _, count in data)
                start_angle = 0

                for i, (name, count) in enumerate(data):
                    angle = (count / total) * 2 * math.pi
                    end_angle = start_angle + angle

                    cr.set_source_rgb(*colors[i % len(colors)])  # Cycle through colors
                    cr.move_to(center_x, center_y)
                    cr.arc(center_x, center_y, radius, start_angle, end_angle)
                    cr.fill()

                    # Optional: Draw labels
                    label_angle = start_angle + angle / 2
                    label_x = center_x + (radius * 1.1) * math.cos(label_angle)
                    label_y = center_y + (radius * 1.1) * math.sin(label_angle)
                    cr.set_source_rgb(0, 0, 0)  # Black text
                    cr.move_to(label_x, label_y)
                    cr.show_text(str(name))

                    start_angle = end_angle

            elif self.chart_data[0] == "bar":
                # {"male": count, "female": count}
                if isinstance(self.chart_data[1], dict):
                    data = sorted(
                        self.chart_data[1].items(),
                        key=lambda row: row[1],
                        reverse=True,
                    )[: self.chart_data[2]]
                else:
                    # [["male", count], ["female", count]]
                    data = sorted(
                        self.chart_data[1],
                        key=lambda row: row[1],
                        reverse=True,
                    )[: self.chart_data[2]]

                bar_width = width / (len(data) * 1.5)
                max_value = max(count for _, count in data)
                padding = 20

                for i, (name, count) in enumerate(data):
                    x = i * bar_width * 1.5 + bar_width * 0.25 + padding
                    bar_height = (count / max_value) * (height - 2 * padding)
                    y = height - bar_height - padding

                    cr.set_source_rgb(*colors[i % len(colors)])
                    cr.rectangle(x, y, bar_width, bar_height)
                    cr.fill()

                    # Draw labels below bars
                    cr.set_source_rgb(0, 0, 0)
                    cr.move_to(
                        x + bar_width / 2 - len(str(name)) * 3, height - padding / 2
                    )
                    cr.show_text(str(name))

            elif self.chart_data[0] == "histogram":
                data = self.chart_data[1]
                if not data:
                    return
                max_val = max(data)
                min_val = min(data)
                if max_val == min_val:
                    return
                interval = (max_val - min_val) / self.chart_data[2]
                buckets = [0] * (int(max_val / interval) + 1)
                for value in data:
                    if value > max_val:
                        buckets[int(max_val / interval)] += 1
                    else:
                        buckets[int(value / interval)] += 1

                labels = []
                decimal_places = self.chart_data[3].get("decimal_places", 0)
                format = "%0." + str(decimal_places) + "f"
                for i in range(int(max_val / interval)):
                    begin = format % (i * interval)
                    end = format % ((i + 1) * interval)
                    if begin != end:
                        labels.append(begin + "-" + end)
                    else:
                        labels.append(begin)
                labels.append(format % ((i + 1) * interval,))

                # Draw a bar chart with values
                bar_width = width / (len(buckets) * 1.5)
                padding = 20
                max_value = max(buckets)

                for i, count in enumerate(buckets):
                    x = i * bar_width * 1.5 + bar_width * 0.25 + padding
                    bar_height = (count / max_value) * (height - 2 * padding)
                    y = height - bar_height - padding

                    cr.set_source_rgb(*colors[0])
                    cr.rectangle(x, y, bar_width, bar_height)
                    cr.fill()

                    # Draw labels below bars
                    name = labels[i]
                    cr.set_source_rgb(0, 0, 0)
                    cr.move_to(x + bar_width / 2 - len(name) * 3, height - padding / 2)
                    cr.show_text(name)
        else:
            # Clear canvas:
            cr.set_source_rgb(1, 1, 1)  # White background
            cr.rectangle(0, 0, width, height)
            cr.fill()

    def execute_filename(self, filename):
        if os.path.exists(filename):
            with open(filename) as file:
                code = file.read()
                self.execute_code(code)

    def execute_code(self, code):
        self.db = self.dbstate.db
        self.sa = SimpleAccess(self.db)
        set_sa(self.sa)
        self.CHANGING = False
        self.column_names = get_columns(code, "row")
        self.statusmsg.set_text("")

        def begin_changes(message=_("Gram.py Script Edited Data")):
            if self.CHANGING:
                end_changes()

            self.CHANGING = True
            self.TRANSACTION = DbTxn(message, self.db)
            self.db._txn_begin()

        def end_changes():
            if self.CHANGING:
                self.db._txn_commit()

        def _iter_raw_person_data():
            for handle, data in self.db._iter_raw_person_data():
                yield DataDict2(dict(data), callback=self.callback)

        def _iter_raw_family_data():
            for handle, data in self.db._iter_raw_family_data():
                yield DataDict2(dict(data), callback=self.callback)

        def _iter_raw_note_data():
            for handle, data in self.db._iter_raw_note_data():
                yield DataDict2(dict(data), callback=self.callback)

        def _iter_raw_place_data():
            for handle, data in self.db._iter_raw_place_data():
                yield DataDict2(dict(data), callback=self.callback)

        def _iter_raw_repository_data():
            for handle, data in self.db._iter_raw_repository_data():
                yield DataDict2(dict(data), callback=self.callback)

        def _iter_raw_citation_data():
            for handle, data in self.db._iter_raw_citation_data():
                yield DataDict2(dict(data), callback=self.callback)

        def _iter_raw_source_data():
            for handle, data in self.db._iter_raw_source_data():
                yield DataDict2(dict(data), callback=self.callback)

        def _iter_raw_event_data():
            for handle, data in self.db._iter_raw_event_data():
                yield DataDict2(dict(data), callback=self.callback)

        def _iter_raw_media_data():
            for handle, data in self.db._iter_raw_media_data():
                yield DataDict2(dict(data), callback=self.callback)

        def columns(*column_names):
            self.column_names = [str(column_name) for column_name in column_names]

        row = self.row

        people = _iter_raw_person_data
        families = _iter_raw_family_data
        notes = _iter_raw_note_data
        events = _iter_raw_event_data
        repositories = _iter_raw_repository_data
        citations = _iter_raw_citation_data
        sources = _iter_raw_source_data
        media = _iter_raw_media_data
        places = _iter_raw_place_data

        active_note = self.get_active_data("Note")
        active_media = self.get_active_data("Media")
        active_person = self.get_active_data("Person")
        active_family = self.get_active_data("Family")
        active_repository = self.get_active_data("Repository")
        active_source = self.get_active_data("Source")
        active_citation = self.get_active_data("Citation")
        active_place = self.get_active_data("Place")
        active_event = self.get_active("Event")

        chart = self.chart

        def selected(table_name):
            pages = [
                page
                for page in self.uistate.viewmanager.pages
                if hasattr(page, "FILTER_TYPE") and page.FILTER_TYPE == table_name
            ]
            if len(pages) > 0:
                get_data = self.db._get_table_func(table_name, "raw_func")
                for handle in pages[0].selected_handles():
                    data = get_data(handle)
                    yield DataDict2(dict(data), callback=self.callback)

        def filtered(table_name):
            pages = [
                page
                for page in self.uistate.viewmanager.pages
                if hasattr(page, "FILTER_TYPE") and page.FILTER_TYPE == table_name
            ]
            if len(pages) > 0:
                get_data = self.db._get_table_func(table_name, "raw_func")
                store = pages[0].model
                for row in store:
                    handle = store.get_handle_from_iter(row.iter)
                    data = get_data(handle)
                    yield DataDict2(dict(data), callback=self.callback)

        today = Date(
            datetime.datetime.today().year,
            datetime.datetime.today().month,
            datetime.datetime.today().day,
        )
        counter = lambda: defaultdict(int)

        if self.treeview:
            self.page1.remove(self.treeview)
            self.treeview = None

        self.chart_data = None

        self.TRANSACTION = None
        self.output_buffer.set_text("")
        # -----------------
        # User code
        # FIXME: don't use stdout?
        old_stdout = sys.stdout
        redirected_output = io.StringIO()
        sys.stdout = redirected_output
        start_time = time.time()
        self.count = 0
        try:
            exec(code)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        print("Executed: %r" % self.last_filename)
        if self.treeview:
            print("Selected: %s" % self.count)
        print("Execution time: %0.5f (seconds)" % (time.time() - start_time))
        # Restore stdout
        sys.stdout = old_stdout
        STDOUT = redirected_output.getvalue()

        # Automatically close transaction:
        if self.CHANGING:
            end_changes()

        # Cleanup:
        # people.close()
        # families.close()
        # -----------------

        # Display in UI:
        if STDOUT:
            self.output_buffer.set_text(STDOUT)

        if "Traceback (most recent call last)" in STDOUT:
            self.statusmsg.set_text("Error in script")
            self.notebook.set_current_page(1)
        elif self.chart_data:
            self.notebook.set_current_page(2)
            self.canvas.queue_draw()
            self.statusmsg.set_text("Chart is ready")
        elif self.count > 0:
            self.notebook.set_current_page(0)
            self.statusmsg.set_text("Table is ready")
        else:
            self.notebook.set_current_page(1)
            self.statusmsg.set_text("Completed")
