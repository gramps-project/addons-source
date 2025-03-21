register(
    GRAMPLET,
    id="HistContext",
    name=_("Historical Context"),
    description=_("Lists relevant historical events during the lifetime of a Person"),
    status=STABLE,
    version = '0.2.29',
    fname="HistContext.py",
    height=20,
    detached_width=510,
    detached_height=480,
    expand=True,
    gramplet="HistContext",
    gramplet_title=_("Historical Context"),
    gramps_target_version="6.0",
    help_url="Addon:Historical_Context",
    navtypes=["Person", "Dashboard"],
    include_in_listing=True,
)
