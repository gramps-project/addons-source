#------------------------------------------------------------------------
#
# Register the Addon
#
#------------------------------------------------------------------------

register(GENERAL,
         category="WebConnect",
         id="RU Web Connect Pack",
         name=_("RU Web Connect Pack"),
         description = _("Collection of Web sites for the RU (requires libwebconnect)"),
         status = STABLE,
         version = '1.0.0',
         gramps_target_version = "5.1",
         fname="RUWebPack.py",
         load_on_reg = True,
         depends_on = ["libwebconnect"]
         )

