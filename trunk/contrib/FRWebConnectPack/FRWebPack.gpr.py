#------------------------------------------------------------------------
#
# Register the Addon
#
#------------------------------------------------------------------------

register(GENERAL,
         category="WebConnect",
         id="FR Web Connect Pack",
         name=_("FR Web Connect Pack"),
         description = _("Collection of Web sites for the FR (requires libwebconnect)"),
         status = STABLE,
         version = '1.0.21',
         gramps_target_version = "4.2",
         fname="FRWebPack.py",
         load_on_reg = True,
         depends_on = ["libwebconnect"]
         )

