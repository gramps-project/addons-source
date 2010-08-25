#------------------------------------------------------------------------
#
# Register the Addon
#
#------------------------------------------------------------------------

register(GENERAL,
         category="WebConnect",
         id="US Web Connect Pack",
         name=_("US Web Connect Pack"),
         description = _("Collection of Web sites for the US (requires libwebconnect)"),
         status = STABLE,
         version = '1.0.3',
         gramps_target_version = "3.3",
         fname="USWebPack.py",
         load_on_reg = True,
         depends_on = ["libwebconnect"]
         )

