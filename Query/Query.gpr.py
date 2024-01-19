#------------------------------------------------------------------------
#
# Register the Gramplet
#
#------------------------------------------------------------------------

register(GRAMPLET,
         id="Query Gramplet",
         name=_("Query Gramplet"),
         description = _("Gramplet for running SQL-like queries"),
         status = UNSTABLE, # not yet tested with python 3
         version = '1.0.36',
         gramps_target_version = "5.1",
         include_in_listing = False,
         height=200,
         gramplet = "QueryGramplet",
         fname="QueryGramplet.py",
         gramplet_title=_("Query"),
         help_url = "QueryGramplet",
         )

#------------------------------------------------------------------------
#
# Register the report
#
#------------------------------------------------------------------------

register(QUICKREPORT,
         id = 'Query Quickview',
         runfunc = "run",
         name = _("Query Quickview"),
         description = _("Quick view for SQL-like running queries"),
         category = CATEGORY_QR_MISC,
         status = STABLE, # not yet tested with python 3
         include_in_listing = False,
         fname="QueryQuickview.py",
         authors="Douglas Blank",
         authors_email="doug.blank@gmail.com",
         version = '1.0.36',
         gramps_target_version = "5.1",
         )

