#------------------------------------------------------------------------
#
# Register the Gramplet
#
#------------------------------------------------------------------------

register(GRAMPLET, 
         id="Clipboard Gramplet", 
         name=_("Clipboard Gramplet"), 
         description = _("Gramplet for grouping items"),
         status = STABLE, # not yet tested with python 3
         version = '1.0.20',
         gramps_target_version = "4.1",
         height=200,
         gramplet = "ClipboardGramplet",
         fname="ClipboardGramplet.py",
         gramplet_title=_("Clipboard"),
         )

