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
version = '1.0.23',
gramps_target_version="6.0",
include_in_listing=False,
height=300,
gramplet="lxmlGramplet",
fname="lxmlGramplet.py",
gramplet_title=_("lxml"),
)
