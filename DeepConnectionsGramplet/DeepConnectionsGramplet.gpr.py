register(
    GRAMPLET,
    id="Deep Connections Gramplet",
    name=_("Deep Connections Gramplet"),
    description=_(
        "Gramplet showing a deep relationship between active and home people"
    ),
    status=STABLE,  # not yet tested with python 3, g_source_remove: assertion `tag > 0' failed
    fname="DeepConnectionsGramplet.py",
    height=230,
    expand=True,
    gramplet="DeepConnectionsGramplet",
    gramplet_title=_("Deep Connections"),
    detached_width=510,
    detached_height=480,
    version = '1.0.47',
    gramps_target_version="6.0",
    help_url="Deep_Connections_Gramplet",
    navtypes=["Person"],
)
