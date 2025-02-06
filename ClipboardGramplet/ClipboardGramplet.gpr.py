# ------------------------------------------------------------------------
#
# Register the Gramplet
#
# ------------------------------------------------------------------------

register(
    GRAMPLET,
    id="Collections Clipboard Gramplet",
    name=_("Collections Clipboard"),
    description=_("Gramplet for grouping collections of items to aid in data entry."),
    status=STABLE,
    version = '1.0.45',
    gramps_target_version="6.0",
    height=200,
    gramplet="ClipboardGramplet",
    fname="ClipboardGramplet.py",
    gramplet_title=_("Collections Clipboard"),
    help_url="Addon:Collections_Clipboard_Gramplet",
)
