register(GRAMPLET, 
         id= "Clock Gramplet", 
         name=_("Clock Gramplet"), 
         description = _("Gramplet for demonstrating Cairo graphics"),
         height=100,
         expand=False,
         gramplet = 'ClockGramplet',
         gramplet_title=_("Clock"),
         status = UNSTABLE, # not yet tested with python 3, TypeError: Error when calling the metaclass bases
         version = '0.0.12',
         gramps_target_version = "4.0",
         fname="ClockGramplet.py",
         help_url="Gramplets#GUI_Interface",
         )
