#------------------------------------------------------------------------
#
# Register the Addon
#
#------------------------------------------------------------------------

register(GENERAL,
         id="libwebconnect",
         name="libwebconnect",
         description = _("Library for web site collections"),
         status = STABLE,
         version = '1.0.7',
         gramps_target_version = "3.5",
         fname="libwebconnect.py",
         load_on_reg = True,
         )

