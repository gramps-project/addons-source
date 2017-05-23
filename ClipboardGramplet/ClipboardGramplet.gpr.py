#------------------------------------------------------------------------
#
# Register the Gramplet
#
#------------------------------------------------------------------------

register(GRAMPLET,
         id="Clipboard Gramplet",
         name=_("Clipboard Gramplet"),
         description = _("Gramplet for grouping items"),
         status = STABLE,
         version = '1.0.31',
         gramps_target_version = "5.1",
         height=200,
         gramplet = "ClipboardGramplet",
         fname="ClipboardGramplet.py",
         gramplet_title=_("Clipboard"),
         )

