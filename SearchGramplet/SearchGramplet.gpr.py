#------------------------------------------------------------------------
#
# Register the Gramplet
#
#------------------------------------------------------------------------

register(GRAMPLET,
         id="Search Gramplet",
         name=_("Search"),
         description = _("Gramplet for search objects in database."),
         status = STABLE,
         version = '0.0.1',
         gramps_target_version = "5.1",
         height=200,
         gramplet = "SearchGramplet",
         fname="SearchGramplet.py",
         gramplet_title=_("Search"),
         )
