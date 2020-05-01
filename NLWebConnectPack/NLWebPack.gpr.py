#------------------------------------------------------------------------
#
# Register the Addon
#
#------------------------------------------------------------------------

register(GENERAL,
         category="WebConnect",
         id="NL Web Connect Pack",
         name="NL Web Connect Pack",
         description = _("Collection of Web sites for the Netherlands (requires libwebconnect)"),
         status = STABLE,
         version = '1.0.3',
         gramps_target_version = "5.1",
         fname="NLWebPack.py",
         load_on_reg = True,
         depends_on = ["libwebconnect"]
)