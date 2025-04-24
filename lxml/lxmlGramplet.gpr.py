# ------------------------------------------------------------------------
#
# Register the Gramplet
#
# ------------------------------------------------------------------------

register(
GRAMPLET,
id="lxml Gramplet",
name=_("lxml"),
description=_("Gramplet for testing lxml and XSLT"),
status=EXPERIMENTAL,
audience = DEVELOPER,
version = '1.2.1',
gramps_target_version="6.0",
include_in_listing=True,
height=400,
gramplet="lxmlGramplet",
fname="lxmlGramplet.py",
gramplet_title=_("lxml"),
help_url="https://gramps-project.org/wiki/index.php/Addon:Lxml_Gramplet",
)
