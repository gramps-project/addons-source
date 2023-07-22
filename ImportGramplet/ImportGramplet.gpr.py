#------------------------------------------------------------------------
#
# Register the Gramplet
#
#------------------------------------------------------------------------

register(GRAMPLET,
         id="Import Gramplet",
         name=_("Import Text"),
         description = _("Gramplet for importing text"),
         status = STABLE,
         audience = DEVELOPER,
         version = '1.0.39',
         gramps_target_version = "5.2",
         height=200,
         gramplet = "ImportGramplet",
         fname="ImportGramplet.py",
         gramplet_title=_("Import Text"),
         help_url = "ImportGramplet",
         )
