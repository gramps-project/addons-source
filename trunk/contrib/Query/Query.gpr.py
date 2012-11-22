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
         version = '1.0.9',
         gramps_target_version = "4.0",
         height=200,
         gramplet = "QueryGramplet",
         fname="QueryGramplet.py",
         gramplet_title=_("Query"),
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
         fname="QueryQuickview.py",
         authors="Douglas Blank",
         authors_email="dblank@cs.brynmawr.edu",
         version = '1.0.9',
         gramps_target_version = "4.0",
         )

