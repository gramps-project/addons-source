#------------------------------------------------------------------------
#
# Register the Addon
#
#------------------------------------------------------------------------

register(GENERAL,
         category="WebConnect",
         id="SV Web Connect Pack",
         name=_("SV Web Connect Pack"),
         description = _("Collection of Web sites for Sweden (requires libwebconnect)"),
         status = STABLE, # not yet tested with python 3
         version = '1.0',
         gramps_target_version = "5.1",
         fname="SVWebPack.py",
         load_on_reg = True,
         depends_on = ["libwebconnect"]
         )
