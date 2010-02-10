#------------------------------------------------------------------------
#
# Register the Gramplet
#
#------------------------------------------------------------------------

register(GRAMPLET, 
         id="Query Gramplet", 
         name=_("Query Gramplet"), 
         status = STABLE,
         version="1.0.0",
         gramps_target_version = "3.2",
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
         category = CATEGORY_QR_MISC,
         status = STABLE,
         description= _("Display data that matches a query"),
         fname="QueryQuickview.py",
         authors="Douglas Blank",
         authors_email="dblank@cs.brynmawr.edu",
         version="1.0.0",
         gramps_target_version = "3.2",
         )

