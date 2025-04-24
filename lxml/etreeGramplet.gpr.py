# ------------------------------------------------------------------------
#
# Register the Gramplet
#
# ------------------------------------------------------------------------

register(
    GRAMPLET,
    id="etree Gramplet",
    name=_("etree"),
    description=_("Gramplet for testing etree with Gramps XML"),
    status=EXPERIMENTAL,
    audience = DEVELOPER,
    version = '1.2.1',
    gramps_target_version="6.0",
    include_in_listing=True,
    height=400,
    gramplet="etreeGramplet",
    fname="etreeGramplet.py",
    gramplet_title=_("etree"),
    help_url="https://gramps-project.org/wiki/index.php/Addon:Lxml_Gramplet",
)
