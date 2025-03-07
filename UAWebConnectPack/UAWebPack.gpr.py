# ------------------------------------------------------------------------
#
# Register the Addon
#
# ------------------------------------------------------------------------

register(
    GENERAL,
    category="WebConnect",
    id="UA Web Connect Pack",
    name=_("UA Web Connect Pack"),
    description=_("Collection of Web sites for the UA (requires libwebconnect)"),
    status=STABLE,
    version = '1.0.1',
    gramps_target_version="6.0",
    fname="UAWebPack.py",
    load_on_reg=True,
    depends_on=["libwebconnect"],
    help_url="Addon:Web_Connect_Pack#Available_Web_connect_Packs",
)