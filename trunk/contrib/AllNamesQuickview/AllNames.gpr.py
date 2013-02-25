register(QUICKREPORT, 
         id    = 'allnames',
         name  = _("All Names of All People"),
         description= _("Display all names of all people"),
         version = '1.0.13',
         gramps_target_version = '4.1',
         status = UNSTABLE, # TypeError: unorderable types: Person() < Person()
         fname = 'AllNames.py',
         authors = ["Douglas Blank"],
         authors_email = ["dblank@cs.brynmawr.edu"],
         category = CATEGORY_QR_PERSON,
         runfunc = 'run'
  )
