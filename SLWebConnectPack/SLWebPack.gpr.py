#------------------------------------------------------------------------
#
# Register the Addon
#
#------------------------------------------------------------------------

register(GENERAL,
         category="WebConnect",
         id="SL Web Connect Pack",
         name=_("SL Web Connect Pack"),
         description = _("Collection of Web sites for SL (requires libwebconnect)"),
         status = STABLE,
         version = '0.0.1',
         gramps_target_version = "5.1",
         fname="SLWebPack.py",
         load_on_reg = True,
         depends_on = ["libwebconnect"]
         )

