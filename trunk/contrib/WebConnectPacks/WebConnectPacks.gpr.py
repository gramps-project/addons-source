#------------------------------------------------------------------------
#
# Register the Addon
#
#------------------------------------------------------------------------

register(GENERAL,
         category="WebConnect",
         id="US Web Connect Pack",
         name=_("US Web Connect Pack"),
         description = _("Collection of Web sites for the US"),
         status = STABLE,
         version = '1.0.2',
         gramps_target_version = "3.3",
         fname="USWebPack.py",
         load_on_reg = True,
         )

register(GENERAL,
         category="WebConnect",
         id="UK Web Connect Pack",
         name=_("UK Web Connect Pack"),
         description = _("Collection of Web sites for the UK"),
         status = STABLE,
         version = '1.0.2',
         gramps_target_version = "3.3",
         fname="UKWebPack.py",
         load_on_reg = True,
         )
