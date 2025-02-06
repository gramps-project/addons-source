register(
    TOOL,
    id="Topola",
    name=_("Interactive Family Tree"),
    description=_("Opens an interactive tree in the browser"),
    status=STABLE,
    version="1.1.11",
    fname="topola.py",
    gramps_target_version="6.0",
    authors=["Przemek Więch"],
    authors_email=["pwiech@gmail.com"],
    category=TOOL_ANAL,
    toolclass="Topola",
    optionclass="TopolaOptions",
    tool_modes=[TOOL_MODE_GUI],
    help_url="Addon:Interactive_Family_Tree",
)
