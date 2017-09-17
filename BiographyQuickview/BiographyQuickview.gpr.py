#------------------------------------------------------------------------
#
# Register the report
#
#------------------------------------------------------------------------

register(QUICKREPORT,
         id    = 'biographyquickview',
         name  = _("Biography"),
         description= _("Display a text biography"),
         version = '1.0.0',
         gramps_target_version = '4.2',
         status = STABLE,
         fname = 'BiographyQuickview.py',
         authors = ["A Guinane"],
         category = CATEGORY_QR_PERSON,
         runfunc = 'run',
  )
