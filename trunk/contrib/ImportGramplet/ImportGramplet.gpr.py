#------------------------------------------------------------------------
#
# Register the Gramplet
#
#------------------------------------------------------------------------

register(GRAMPLET, 
         id="Import Gramplet", 
         name=_("Import Gramplet"), 
         description = _("Gramplet for importing text"),
         status = STABLE,
         version = '1.0.21',
         gramps_target_version = "4.2",
         height=200,
         gramplet = "ImportGramplet",
         fname="ImportGramplet.py",
         gramplet_title=_("Import"),
         )
