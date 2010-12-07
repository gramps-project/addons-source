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
         status = UNSTABLE,
         version = '0.9.11',
         gramps_target_version = "3.3",
         fname="FRWebPack.py",
         load_on_reg = True,
         depends_on = ["libwebconnect"]
         )

