#------------------------------------------------------------------------
#
# Register the Gramplet
#
#------------------------------------------------------------------------

register(GRAMPLET, 
         id="etree Gramplet", 
         name=_("etree Gramplet"), 
         description = _("Gramplet for testing etree with Gramps XML"),
         status = STABLE,
         version = '0.0.10',
         gramps_target_version = "3.5",
         include_in_listing = False,
         height = 400,
         gramplet = "etreeGramplet",
         fname ="etreeGramplet.py",
         gramplet_title =_("etree"),
         )
