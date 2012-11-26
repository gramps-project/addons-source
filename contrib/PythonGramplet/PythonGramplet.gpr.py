register(GRAMPLET, 
         id="Python Gramplet", 
         name=_("Python Gramplet"), 
         description = _("Interactive Python interpreter"),
         status = UNSTABLE, # not yet tested with python 3, 'Gtk' object has no attribute 'keysyms'
         fname="PythonGramplet.py",
         height=250,
         gramplet = 'PythonGramplet',
         gramplet_title=_("Python Shell"),
         version = '1.0.12',
         gramps_target_version = "4.0",
         help_url="PythonGramplet",
         )
