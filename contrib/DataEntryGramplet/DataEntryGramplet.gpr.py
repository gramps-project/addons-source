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
         version = '1.0.21',
         gramps_target_version = '4.0',
         status=UNSTABLE, # tested with python 2to3, gen.lib issues since 3.4.x, 'Gtk' object has no attribute 'combo_box_new_text'
         fname="DataEntryGramplet.py",
         help_url="Data Entry Gramplet",
         )


