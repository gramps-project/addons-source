#------------------------------------------------------------------------
#
# Register the Gramplet
#
#------------------------------------------------------------------------

register(GRAMPLET,
         id="Collections Clipboard Gramplet",
         name=_("Collections Clipboard"),
         description = _("Gramplet for grouping collections of items to aid in data entry."),
         status = STABLE,
         version = '1.0.42',
         gramps_target_version = "5.2",
         height=200,
         gramplet = "ClipboardGramplet",
         fname="ClipboardGramplet.py",
         gramplet_title=_("Collections Clipboard"),
         )

