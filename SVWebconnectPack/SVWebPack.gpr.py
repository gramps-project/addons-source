# ------------------------------------------------------------------------
#
# Register the Addon
#
# ------------------------------------------------------------------------

register(
    GENERAL,
    category="WebConnect",
    id="SV Web Connect Pack",
    name=_("SV Web Connect Pack"),
    description=_("Collection of Web sites for Sweden (requires libwebconnect)"),
    status=STABLE,
    version = '1.0.5',
    gramps_target_version="6.0",
    fname="SVWebPack.py",
    load_on_reg=True,
    depends_on=["libwebconnect"],
    help_url="Addon:Web_Connect_Pack#Available_Web_connect_Packs",
)
