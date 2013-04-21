register(QUICKREPORT,
         id = 'Descendant Count Quickview',
         name = _("Descendant Count"),
         category = CATEGORY_QR_MISC,
         runfunc = "run",
         status = UNSTABLE, # not yet tested with python 3, error on unicode row
         description= _("Display descendant counts for each person."),
         fname="DescendantCount.py",
         authors=["Douglas S. Blank"],
         authors_email=["doug.blank@gmail.com"],
         version = '1.0.15',
         gramps_target_version = "4.1",
         )

register(GRAMPLET, 
         id="Descendant Count Gramplet", 
         name=_("Descendant Count Gramplet"), 
         description = _("Gramplet for showing people and descendant counts"),
         status= UNSTABLE, # not yet tested with python 3, error on unicode row
         fname="DescendantCount.py",
         height=300,
         expand=True,
         gramplet = "DescendantCountGramplet",
         gramplet_title=_("Descendant Count"),
         detached_width = 600,
         detached_height = 400,
         version = '1.0.16',
         gramps_target_version = "4.1",
         )

