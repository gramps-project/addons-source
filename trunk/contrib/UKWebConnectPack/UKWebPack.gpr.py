#------------------------------------------------------------------------
#
# Register the Addon
#
#------------------------------------------------------------------------

register(GENERAL,
         category="WebConnect",
         id="UK Web Connect Pack",
         name=_("UK Web Connect Pack"),
         description = _("Collection of Web sites for the UK (requires libwebconnect)"),
         status = STABLE, # not yet tested with python 3
         version = '1.0.24',
         gramps_target_version = "4.1",
         fname="UKWebPack.py",
         load_on_reg = True,
         depends_on = ["libwebconnect"]
         )
