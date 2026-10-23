#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Doug Blank <doug.blank@gmail.com>
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

"""
Export Story: saves the active person's life as a .story.zip, a slideshow
of their events with dates, places and photos that opens in the Gramps
Connect Story Viewer (https://dsblank.github.io/gramps-connect-stories/)
or any other program that reads the format.
"""

import html
import logging
import os
import re
import tempfile

from gi.repository import GLib, Gtk

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.const import USER_HOME
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.proxy import LivingProxyDb, PrivateProxyDb
from gramps.gui.dialog import ErrorDialog, QuestionDialog2
from gramps.gui.display import display_url
from gramps.gui.plug import tool

from storyexport_builder import (
    StoryExportError,
    build_story,
    left_out_reason,
    no_living_in_photo,
    viewer_page,
)

_ = glocale.get_addon_translator(__file__).gettext
LOG = logging.getLogger(__name__)

SUFFIX = ".story.zip"


def default_file_name(name):
    """ "Josef Meyer" -> "Josef Meyer.story.zip", minus characters some
    file systems refuse."""
    safe = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", name)
    safe = re.sub(r"\s+", " ", safe).strip()[:120]
    return (safe or "story") + SUFFIX


class StoryExport(tool.Tool):
    """Asks what to include, then where to save, then writes the story."""

    def __init__(self, dbstate, user, options_class, name, callback=None):
        tool.Tool.__init__(self, dbstate, options_class, name)
        self.uistate = user.uistate
        parent = self.uistate.window

        person_handle = self.uistate.get_active("Person")
        person = (
            self.db.get_person_from_handle(person_handle) if person_handle else None
        )
        if person is None:
            ErrorDialog(
                _("No active person"),
                _("Select the person whose story to export, then try again."),
                parent=parent,
            )
            return

        name = name_displayer.display(person)
        choice = self.ask_options(parent, name)
        if choice is None:
            return
        private, living = choice
        reason = left_out_reason(self.db, person_handle, private, living)
        if reason:
            ErrorDialog(_("Couldn't export the story"), reason, parent=parent)
            return
        path = self.ask_file(parent, name)
        if not path:
            return
        if not path.endswith(SUFFIX):
            path = (
                os.path.splitext(path)[0] + SUFFIX
                if path.endswith(".zip")
                else path + SUFFIX
            )

        try:
            count = self.export(person_handle, path, private, living)
        except (StoryExportError, OSError, ValueError) as err:
            LOG.debug("story export failed", exc_info=True)
            ErrorDialog(_("Couldn't export the story"), str(err), parent=parent)
            return
        open_it = QuestionDialog2(
            _("Story saved"),
            html.escape(
                _(
                    "%(count)d slides saved to %(path)s.\n\nOpen it in the "
                    "Gramps Connect Story Viewer: "
                    "https://dsblank.github.io/gramps-connect-stories/"
                )
                % {"count": count, "path": path}
            ),
            _("_Open in Browser"),
            _("_Close"),
            parent=parent,
        ).run()
        if open_it:
            self.open_in_browser(path)

    def open_in_browser(self, path):
        """Show the saved story in the web browser, from a temporary page
        holding it (see viewer_page)."""
        with open(path, "rb") as handle:
            story_zip = handle.read()
        title = os.path.basename(path)[: -len(SUFFIX)] or _("Story")
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", prefix="story-", suffix=".html", delete=False
        ) as page:
            page.write(viewer_page(story_zip, title, glocale.lang[:2]))
        display_url("file://" + page.name, self.uistate)

    def ask_options(self, parent, name):
        """(include private, include living) from the options dialog, or
        None if cancelled."""
        dialog = Gtk.Dialog(title=_("Export Story"), transient_for=parent, modal=True)
        dialog.add_buttons(
            _("_Cancel"), Gtk.ResponseType.CANCEL, _("_Next"), Gtk.ResponseType.OK
        )
        dialog.set_default_response(Gtk.ResponseType.OK)
        box = dialog.get_content_area()
        box.set_spacing(8)
        box.set_border_width(12)
        heading = Gtk.Label(xalign=0)
        heading.set_markup(
            "<b>%s</b>" % GLib.markup_escape_text(_("The Story of %s") % name)
        )
        include_private = Gtk.CheckButton(label=_("Include data marked private"))
        include_living = Gtk.CheckButton(
            label=_("Include living people (and photos they appear in)")
        )
        for widget in (heading, include_private, include_living):
            box.pack_start(widget, False, False, 0)
        dialog.show_all()
        response = dialog.run()
        choice = (include_private.get_active(), include_living.get_active())
        dialog.destroy()
        return choice if response == Gtk.ResponseType.OK else None

    def ask_file(self, parent, name):
        """Where to save the story, or None if cancelled."""
        dialog = Gtk.FileChooserDialog(
            title=_("Export Story"),
            transient_for=parent,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons(
            _("_Cancel"), Gtk.ResponseType.CANCEL, _("_Save"), Gtk.ResponseType.OK
        )
        dialog.set_do_overwrite_confirmation(True)
        dialog.set_current_folder(USER_HOME)
        dialog.set_current_name(default_file_name(name))
        stories = Gtk.FileFilter()
        stories.set_name(_("Stories (*.story.zip)"))
        stories.add_pattern("*" + SUFFIX)
        dialog.add_filter(stories)
        response = dialog.run()
        path = dialog.get_filename()
        dialog.destroy()
        return path if response == Gtk.ResponseType.OK else None

    def export(self, person_handle, path, include_private, include_living):
        """Write the story; return its number of slides."""
        reason = left_out_reason(
            self.db, person_handle, include_private, include_living
        )
        if reason:
            raise StoryExportError(reason)
        db = self.db
        if not include_private:
            db = PrivateProxyDb(db)
        photo_allowed = None
        if not include_living:
            db = LivingProxyDb(db, LivingProxyDb.MODE_EXCLUDE_ALL)
            photo_allowed = no_living_in_photo(self.db)
        story = build_story(db, person_handle, photo_allowed)
        story.write(path)
        return len(story.slides)


class StoryExportOptions(tool.ToolOptions):
    """No saved options: the dialog asks each time."""

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
