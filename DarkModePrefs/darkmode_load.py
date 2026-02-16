#
# Gramps - dark mode preferences loader
#

from gi.repository import GLib

from gramps.gui.configure import GrampsPreferences

from darkmode import (
    DarkModePrefs,
    apply_darkmode_settings,
    register_config_defaults,
    setup_system_darkmode_listener,
)


def _apply_patch():
    GrampsPreferences.__init__ = DarkModePrefs.__init__
    apply_darkmode_settings()
    return False


def load_on_reg(dbstate, uistate, plugin):
    """
    Runs when plugin is registered.
    """
    if not uistate:
        # Avoid GUI patches in CLI mode.
        return

    register_config_defaults()
    _apply_patch()
    # Re-apply after startup in case another addon monkey-patches
    # GrampsPreferences later during load_on_reg processing.
    GLib.idle_add(_apply_patch)
    GLib.timeout_add(1000, _apply_patch)
    setup_system_darkmode_listener()
