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
         status = STABLE, # not yet tested with python 3
         version = '1.0.22',
         gramps_target_version = "4.0",
         fname="USWebPack.py",
         load_on_reg = True,
         depends_on = ["libwebconnect"]
         )

