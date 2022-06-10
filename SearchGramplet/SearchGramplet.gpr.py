#------------------------------------------------------------------------
#
# Register the Gramplet
#
#------------------------------------------------------------------------

register(GRAMPLET,
         id="Search Gramplet",
         name=_("Search"),
         description = _("Gramplet for search objects in database."),
         version = '0.0.2',
         gramps_target_version = "6.0",
         status=EXPERIMENTAL,
         audience=EXPERT,
         help_url="https://github.com/gramps-project/addons-source/pull/541",
         height=200,
         gramplet = "SearchGramplet",
         fname="SearchGramplet.py",
         gramplet_title=_("Search"),
         )
