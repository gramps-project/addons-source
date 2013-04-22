register(GRAMPLET, 
         id="Headline News Gramplet", 
         name=_("Headline News Gramplet"), 
         description = _("Gramplet for showing latest the Gramps news"),
         status = UNSTABLE, # syntax with python 3; line 136 except Exception, e:
         fname="HeadlineNewsGramplet.py",
         height=300,
         expand=True,
         gramplet = 'HeadlineNewsGramplet',
         gramplet_title=_("Headline News"),
         version = '1.0.18',
         gramps_target_version="4.1",
         )
