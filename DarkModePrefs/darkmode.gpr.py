#
# Gramps - a GTK+/GNOME based genealogy program
#
# Dark mode preference addon
#

register(
    GENERAL,
    id="DarkModePrefs",
    name=_("Dark mode preferences"),
    description=_(
        "Adds robust dark mode controls with Linux-friendly defaults "
        "(Auto/Dark/Light) for Gramps desktop."
    ),
    version="0.1.1",
    gramps_target_version="6.0",
    fname="darkmode_load.py",
    authors=["Codex + stolpee"],
    category=TOOL_UTILS,
    load_on_reg=True,
    status=STABLE,
)
