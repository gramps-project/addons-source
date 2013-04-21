register(QUICKREPORT,
         id    = 'NumberOfDescendantsQuickview',
         name  = _("Number of descendants"),
         description= _("Shows the number of descendants of the current person"),
         version = '3.4.15',
         gramps_target_version = '4.1',
         status = UNSTABLE, # not yet tested with python 3, error on unicode row
         fname = 'NumberOfDescendantsQuickview.py',
         authors = ["Reinhard Mueller"],
         authors_email = ["reinhard.mueller@igal.at"],
         category = CATEGORY_QR_PERSON,
         runfunc = 'run')
