# ------------------------------------------------------------------------
#
# Register the Addon
#
# ------------------------------------------------------------------------

register(
    GENERAL,
    category="WebConnect",
    id="NL Web Connect Pack",
    name="NL Web Connect Pack",
    description=_(
        "Collection of Web sites for the Netherlands (requires libwebconnect)"
    ),
    status=STABLE,
    version = '1.0.9',
    gramps_target_version="6.0",
    fname="NLWebPack.py",
    load_on_reg=True,
    depends_on=["libwebconnect"],
    help_url="Addon:Web_Connect_Pack#Available_Web_connect_Packs",
)
