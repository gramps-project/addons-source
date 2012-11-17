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
         status = UNSTABLE,
         version = '1.0.20',
         gramps_target_version = "3.5",
         fname="USWebPack.py",
         load_on_reg = True,
         depends_on = ["libwebconnect"]
         )

