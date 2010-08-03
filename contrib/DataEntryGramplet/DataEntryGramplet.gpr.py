#------------------------------------------------------------------------
#
# Register Gramplet
#
#------------------------------------------------------------------------
register(GRAMPLET, 
         id="Data Entry Gramplet", 
         name=_("Data Entry Gramplet"), 
         description = _("Gramplet for quick data entry"),
         height=375,
         expand=False,
         gramplet = 'DataEntryGramplet',
         gramplet_title=_("Data Entry"),
         detached_width = 510,
         detached_height = 480,
         version = '1.0.1',
         gramps_target_version = '3.3.0',
         status=STABLE,
         fname="DataEntryGramplet.py",
         help_url="Data Entry Gramplet",
         )


