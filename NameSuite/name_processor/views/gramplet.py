# name_processor/ui/gramplet_view.py
# -*- coding: utf-8 -*-
"""
GTK View for the Patronymic Suggestion Gramplet.
Contains all GTK components and i18n message handling.
"""

from gi.repository import Gtk
from typing import TYPE_CHECKING

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gui.dialog import ErrorDialog

from NameSuite.name_processor.models.infer import PatronymicInferenceStatus


if TYPE_CHECKING:
    from NameSuite.name_processor.controllers.gramplet import GrampletController

_ = glocale.translation.gettext


class GrampletView:
    """GTK View for the Patronymic Suggestion Gramplet sidebar."""

    MESSAGES = {
        "SUGGESTION_TEMPLATE": _(
            "Missing Patronymic Detected.\nSuggested: {0}\nBased on father: {1}"
        ),
        "INITIAL": _("Navigate to an individual to check patronymic status."),
        PatronymicInferenceStatus.NO_ACTIVE_PERSON: _("No active person selected."),
        PatronymicInferenceStatus.NON_BINARY: _(
            "Patronymic inference can't be inferred for non-binary or unknown genders."
        ),
        PatronymicInferenceStatus.ALREADY_HAS_PATRONYMIC: _(
            "Individual already has a recorded patronymic."
        ),
        PatronymicInferenceStatus.NO_FATHER: _(
            "No attached father found in database family records."
        ),
        PatronymicInferenceStatus.FATHER_NO_NAME: _(
            "Father lacks a recorded first name."
        ),
        PatronymicInferenceStatus.MORPHOLOGY_FAIL: _(
            "Could not generate valid morphology patterns."
        ),
        PatronymicInferenceStatus.SUCCESS: _("Patronymic applied successfully!"),
    }

    def __init__(self, gramplet) -> None:
        self.gramplet = gramplet
        self._controller: GrampletController | None = None
        self._box: Gtk.Box | None = None
        self._label: Gtk.Label | None = None
        self._apply_btn: Gtk.Button | None = None

    def set_controller(self, controller: GrampletController | None) -> None:
        self._controller = controller

    def init(self) -> None:
        """Sets up the GTK user interface panel."""
        # Build UI Box
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._box.set_border_width(8)

        # Display Message
        self._label = Gtk.Label(label=self.MESSAGES["INITIAL"])
        self._label.set_xalign(0.0)
        self._label.set_line_wrap(True)
        self._box.pack_start(self._label, True, True, 0)

        # Action Trigger
        self._apply_btn = Gtk.Button(label=_("Apply Suggestion"))
        self._apply_btn.set_sensitive(False)
        self._apply_btn.connect("clicked", self._on_apply_clicked)
        self._box.pack_start(self._apply_btn, False, False, 0)
        self._box.show_all()

    def get_root_widget(self) -> Gtk.Box | None:
        """Returns the root GTK widget for Gramps to embed."""
        return self._box

    def _on_apply_clicked(self, widget: Gtk.Button) -> None:
        """Handle apply button click event."""
        if self._controller:
            self._controller.on_apply_clicked()

    def show_status_message(
        self, message_key: PatronymicInferenceStatus, apply_sensitive: bool = False
    ):
        """Display a status message from the MESSAGES dictionary."""
        self._label.set_text(self.MESSAGES.get(message_key, ""))
        self._apply_btn.set_sensitive(apply_sensitive)

    def show_suggestion(self, patronymic: str, father_name: str):
        """Display a patronymic suggestion with the father's name."""
        self._label.set_text(
            self.MESSAGES["SUGGESTION_TEMPLATE"].format(patronymic, father_name)
        )
        self._apply_btn.set_sensitive(True)

    def display_error(self, title_key: str, message: str):
        """Display an error dialog."""
        ErrorDialog(_(title_key), message, self.gramplet.gui.get_window())
