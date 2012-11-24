#------------------------------------------------------------------------
#
# Register the Gramplet
#
#------------------------------------------------------------------------

register(GRAMPLET, 
         id="Clipboard Gramplet", 
         name=_("Clipboard Gramplet"), 
         description = _("Gramplet for grouping items"),
         status = STABLE, # tested with python 2to3
         version = '1.0.16',
         gramps_target_version = "4.0",
         height=200,
         gramplet = "ClipboardGramplet",
         fname="ClipboardGramplet.py",
         gramplet_title=_("Clipboard"),
         )

