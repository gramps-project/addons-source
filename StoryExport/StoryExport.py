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
Generate Story: saves the story of a person or a family as a .story.zip,
a slideshow of their events with dates, places and photos that opens in
the Gramps Connect Story Viewer
(https://dsblank.github.io/gramps-connect-stories/) or any other program
that reads the format.
"""

import html
import logging
import os
import re
import tempfile

from gi.repository import Gtk

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.const import USER_HOME
from gramps.gen.proxy import LivingProxyDb, PrivateProxyDb
from gramps.gui.dialog import ErrorDialog, QuestionDialog2
from gramps.gui.display import display_url
from gramps.gui.plug import tool

from storyexport_builder import (
    StoryExportError,
    build_family_story,
    build_person_story,
    family_label,
    left_out_reason,
    no_living_in_photo,
    person_name,
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
    """Asks whose story and what to include, then where to save, then
    writes the story."""

    def __init__(self, dbstate, user, options_class, name, callback=None):
        tool.Tool.__init__(self, dbstate, options_class, name)
        self.uistate = user.uistate
        parent = self.uistate.window

        subjects = self.subjects()
        if not subjects:
            ErrorDialog(
                _("No active person"),
                _("Select the person whose story to generate, then try again."),
                parent=parent,
            )
            return

        choice = self.ask_options(parent, subjects)
        if choice is None:
            return
        reason = left_out_reason(
            self.db,
            choice["kind"],
            choice["handle"],
            choice["private"],
            choice["living"],
        )
        if reason:
            ErrorDialog(_("Couldn't generate the story"), reason, parent=parent)
            return
        path = self.ask_file(parent, choice["label"])
        if not path:
            return
        if not path.endswith(SUFFIX):
            path = (
                os.path.splitext(path)[0] + SUFFIX
                if path.endswith(".zip")
                else path + SUFFIX
            )

        try:
            count = self.generate(choice, path)
        except (StoryExportError, OSError, ValueError) as err:
            LOG.debug("story generation failed", exc_info=True)
            ErrorDialog(_("Couldn't generate the story"), str(err), parent=parent)
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

    def subjects(self):
        """Whose story can be told: the active person, then each family
        they're a parent in, then the active family if it isn't one of
        those. (kind, handle, label) each."""
        db = self.db
        found = []
        person_handle = self.uistate.get_active("Person")
        person = db.get_person_from_handle(person_handle) if person_handle else None
        family_handles = []
        if person is not None:
            found.append(("person", person_handle, person_name(person)))
            family_handles = list(person.get_family_handle_list())
        active_family = self.uistate.get_active("Family")
        if active_family and active_family not in family_handles:
            family_handles.append(active_family)
        for handle in family_handles:
            family = db.get_family_from_handle(handle)
            if family is not None:
                found.append(("family", handle, family_label(db, family)))
        return found

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

    def ask_options(self, parent, subjects):
        """Whose story, and what to include, from the options dialog: a
        dict (kind, handle, label, include_families, excluded, private,
        living), or None if cancelled."""
        dialog = Gtk.Dialog(title=_("Generate Story"), transient_for=parent, modal=True)
        dialog.add_buttons(
            _("_Cancel"), Gtk.ResponseType.CANCEL, _("_Next"), Gtk.ResponseType.OK
        )
        dialog.set_default_response(Gtk.ResponseType.OK)
        box = dialog.get_content_area()
        box.set_spacing(8)
        box.set_border_width(12)

        heading = Gtk.Label(xalign=0)
        heading.set_markup("<b>%s</b>" % html.escape(_("Generate the story of:")))
        box.pack_start(heading, False, False, 0)
        radios = []
        group = None
        for kind, handle, label in subjects:
            text = label if kind == "person" else _("Family: %s") % label
            radio = Gtk.RadioButton.new_with_label_from_widget(group, text)
            group = group or radio
            radios.append(radio)
            box.pack_start(radio, False, False, 0)

        # The chosen subject's own options, as in Gramps Connect.
        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        details.set_margin_top(8)
        box.pack_start(details, False, False, 0)
        include_families = Gtk.CheckButton(label=_("Include families"))
        include_families_help = Gtk.Label(
            label=_(
                "Also draw on this person's own families: a spouse's and "
                "children's births and deaths, and their parents' and siblings'."
            ),
            xalign=0,
            wrap=True,
            max_width_chars=50,
        )
        include_families_help.get_style_context().add_class("dim-label")
        include_families_help.set_margin_start(24)
        member_checks = {}

        def show_details(_radio=None):
            for child in details.get_children():
                details.remove(child)
            member_checks.clear()
            kind, handle, _label = subjects[
                next(i for i, r in enumerate(radios) if r.get_active())
            ]
            if kind == "person":
                details.pack_start(include_families, False, False, 0)
                details.pack_start(include_families_help, False, False, 0)
            else:
                details.pack_start(
                    Gtk.Label(
                        label=_(
                            "Include each person's own birth and death in this "
                            "family's story:"
                        ),
                        xalign=0,
                        wrap=True,
                        max_width_chars=50,
                    ),
                    False,
                    False,
                    0,
                )
                for member in self.family_members(handle):
                    check = Gtk.CheckButton(label=person_name(member))
                    check.set_active(True)
                    member_checks[member.get_handle()] = check
                    details.pack_start(check, False, False, 0)
            details.show_all()

        for radio in radios:
            radio.connect("toggled", show_details)
        show_details()

        box.pack_start(Gtk.Separator(), False, False, 4)
        include_private = Gtk.CheckButton(label=_("Include data marked private"))
        include_living = Gtk.CheckButton(
            label=_("Include living people (and photos they appear in)")
        )
        box.pack_start(include_private, False, False, 0)
        box.pack_start(include_living, False, False, 0)

        dialog.show_all()
        response = dialog.run()
        kind, handle, label = subjects[
            next(i for i, r in enumerate(radios) if r.get_active())
        ]
        choice = {
            "kind": kind,
            "handle": handle,
            "label": label,
            "include_families": include_families.get_active(),
            "excluded": {h for h, c in member_checks.items() if not c.get_active()},
            "private": include_private.get_active(),
            "living": include_living.get_active(),
        }
        dialog.destroy()
        return choice if response == Gtk.ResponseType.OK else None

    def family_members(self, family_handle):
        """Father, mother, then children, as recorded."""
        family = self.db.get_family_from_handle(family_handle)
        handles = [family.get_father_handle(), family.get_mother_handle()]
        handles += [ref.ref for ref in family.get_child_ref_list()]
        people = (self.db.get_person_from_handle(h) for h in handles if h)
        return [person for person in people if person is not None]

    def ask_file(self, parent, name):
        """Where to save the story, or None if cancelled."""
        dialog = Gtk.FileChooserDialog(
            title=_("Generate Story"),
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

    def generate(self, choice, path):
        """Write the story chosen in the options dialog; return its number
        of slides."""
        db = self.db
        if not choice["private"]:
            db = PrivateProxyDb(db)
        photo_allowed = None
        if not choice["living"]:
            db = LivingProxyDb(db, LivingProxyDb.MODE_EXCLUDE_ALL)
            photo_allowed = no_living_in_photo(self.db)
        if choice["kind"] == "family":
            story = build_family_story(
                db, choice["handle"], choice["excluded"], photo_allowed
            )
        else:
            story = build_person_story(
                db, choice["handle"], choice["include_families"], photo_allowed
            )
        story.write(path)
        return len(story.slides)


class StoryExportOptions(tool.ToolOptions):
    """No saved options: the dialog asks each time."""

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
