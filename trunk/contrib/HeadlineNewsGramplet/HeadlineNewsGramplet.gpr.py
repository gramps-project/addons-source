register(GRAMPLET, 
         id="Headline News Gramplet", 
         name=_("Headline News Gramplet"), 
         description = _("Gramplet for showing latest the Gramps news"),
         status = STABLE, # not yet tested with python 3
         fname="HeadlineNewsGramplet.py",
         height=300,
         expand=True,
         gramplet = 'HeadlineNewsGramplet',
         gramplet_title=_("Headline News"),
         version = '1.0.16',
         gramps_target_version="4.1",
         )
