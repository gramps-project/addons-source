register(
    GRAMPLET,
    id="Note Gramplet",
    name=_("Note Gramplet"),
    description=_("Gramplet for editing active person's notes"),
    status=STABLE,  # not yet tested with python 3
    fname="NoteGramplet.py",
    height=100,
    expand=True,
    gramplet="NoteGramplet",
    gramplet_title=_("Note"),
    detached_width=500,
    detached_height=400,
    version = '1.0.41',
    gramps_target_version="6.0",
    help_url="NoteGramplet",
    navtypes=["Person"],
)
