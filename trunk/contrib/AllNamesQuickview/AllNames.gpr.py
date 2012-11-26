register(QUICKREPORT, 
         id    = 'allnames',
         name  = _("All Names of All People"),
         description= _("Display all names of all people"),
         version = '1.0.11',
         gramps_target_version = '4.0',
         status = STABLE, # not yet tested with python 3
         fname = 'AllNames.py',
         authors = ["Douglas Blank"],
         authors_email = ["dblank@cs.brynmawr.edu"],
         category = CATEGORY_QR_PERSON,
         runfunc = 'run'
  )
