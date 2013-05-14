register(VIEW, 
         id    = 'graphview',
         name  = _("Graph View"),
         category = ("Ancestry", _("Ancestry")),
         description =  _("Dynamic graph of relations"),
         version = '1.0.37',
         gramps_target_version = '4.1',
         status = UNSTABLE, # ImportError: No module named 'cStringIO'
         fname = 'graphview.py',
         authors = ["Gary Burton"],
         authors_email = ["gary.burton@zen.co.uk"],
         viewclass = 'GraphView',
  )
