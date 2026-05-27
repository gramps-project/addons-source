#------------------------------------------------------------------------
#
# Register the report
#
#------------------------------------------------------------------------

register(QUICKREPORT,
         id    = 'censuscheckquickview',
         name  = _("CensusCheck"),
         description= _("Check whether any Census events are missing for a person and some of their descendents"),
         version = '1.0.4',
         gramps_target_version = '6.0',
         status = STABLE,
         fname = 'CensusCheckQuickview.py',
         authors = ["Tim Lyons"],
         authors_email = ["guy.linton@gmail.com"],
         category = CATEGORY_QR_PERSON,
         runfunc = 'run',
         help_url = "Addon:Census_Check"
  )
register(QUICKREPORT,
         id    = 'censuscheckupquickview',
         name  = _("CensusCheckUp"),
         description= _("Check whether any Census events are missing for a person and some of their ancestors"),
         version = '1.0.4',
         gramps_target_version = '6.0',
         status = STABLE,
         fname = 'CensusCheckUpQuickview.py',
         authors = ["Tim Lyons"],
         authors_email = ["guy.linton@gmail.com"],
         category = CATEGORY_QR_PERSON,
         runfunc = 'run',
         help_url = "Addon:Census_Check"
  )
