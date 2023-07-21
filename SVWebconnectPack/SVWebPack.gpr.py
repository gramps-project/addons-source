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
         status = STABLE,
         version = '1.0.2',
         gramps_target_version = "5.2",
         fname="SVWebPack.py",
         load_on_reg = True,
         depends_on = ["libwebconnect"]
         )
