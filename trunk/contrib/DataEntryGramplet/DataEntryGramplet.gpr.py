#------------------------------------------------------------------------
#
# Register Gramplet
#
#------------------------------------------------------------------------
register(GRAMPLET, 
         id="Data Entry Gramplet", 
         name=_("Data Entry Gramplet"), 
         height=375,
         expand=False,
         gramplet = 'DataEntryGramplet',
         gramplet_title=_("Data Entry"),
         detached_width = 510,
         detached_height = 480,
         version="1.0.0",
         gramps_target_version = "3.3",
         status=STABLE,
         fname="DataEntryGramplet.py",
         help_url="Data Entry Gramplet",
         )


