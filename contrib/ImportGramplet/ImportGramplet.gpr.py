#------------------------------------------------------------------------
#
# Register the Gramplet
#
#------------------------------------------------------------------------

register(GRAMPLET, 
         id="Import Gramplet", 
         name=_("Import Gramplet"), 
         description = _("Gramplet for importing text"),
         status = UNSTABLE, # not yet tested with python 3
         version = '1.0.13',
         gramps_target_version = "4.0",
         height=200,
         gramplet = "ImportGramplet",
         fname="ImportGramplet.py",
         gramplet_title=_("Import"),
         )
