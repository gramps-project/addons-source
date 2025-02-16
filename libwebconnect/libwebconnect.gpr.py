# ------------------------------------------------------------------------
#
# Register the Addon
#
# ------------------------------------------------------------------------

register(
    GENERAL,
    id="libwebconnect",
    name="libwebconnect",
    description=_("Library for web site collections"),
    status=STABLE,  # not yet tested with python 3
    version = '1.0.37',
    gramps_target_version="6.0",
    fname="libwebconnect.py",
    load_on_reg=True,
    help_url="Addon:Web_Connect_Pack#Prerequisites",
)
