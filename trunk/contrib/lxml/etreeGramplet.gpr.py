#------------------------------------------------------------------------
#
# Register the Gramplet
#
#------------------------------------------------------------------------

register(GRAMPLET, 
         id="etree Gramplet", 
         name=_("etree Gramplet"), 
         description = _("Gramplet for testing etree with Gramps XML"),
         status = STABLE, # not yet tested with python 3
         version = '0.0.14',
         gramps_target_version = "4.1",
         include_in_listing = False,
         height = 400,
         gramplet = "etreeGramplet",
         fname ="etreeGramplet.py",
         gramplet_title =_("etree"),
         )
