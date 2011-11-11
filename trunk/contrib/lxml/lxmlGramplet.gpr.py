#------------------------------------------------------------------------
#
# Register the Gramplet
#
#------------------------------------------------------------------------

register(GRAMPLET, 
         id="lxml Gramplet", 
         name=_("lxml Gramplet"), 
         description = _("Gramplet for testing lxml and XSLT"),
         status = STABLE,
         version = '0.1.20',
         gramps_target_version = "3.4",
         include_in_listing = False,
         height = 65,
         gramplet = "lxmlGramplet",
         fname ="lxmlGramplet.py",
         gramplet_title =_("lxml"),
         )
