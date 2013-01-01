register(VIEW, 
         id    = 'graphview',
         name  = _("Graph View"),
         category = ("Ancestry", _("Ancestry")),
         description =  _("Dynamic graph of relations"),
         version = '1.0.34',
         gramps_target_version = '4.1',
         status = UNSTABLE, # not yet tested with python 3
         fname = 'graphview.py',
         authors = [u"Gary Burton"],
         authors_email = ["gary.burton@zen.co.uk"],
         viewclass = 'GraphView',
  )
