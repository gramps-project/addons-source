register(
    VIEW,
    id="descendants_timeline",
    name=_("Descendants Timeline"),
    description=_("Timeline of descendants and their lifespans."),
    version="1.0.0",
    gramps_target_version="6.0",
    status=STABLE,
    fname="descendants_timeline_plugin.py",
    viewclass="create_descendants_timeline_view",
    category=("Ancestry", _("Charts")),
    authors=["Philippe"],
    authors_email=["ph-plqn@users.noreply.github.com"],
    order=END,
    icons=[
        ("gramps-descendants-timeline-view", _("Descendants Timeline")),
        ("gramps-descendants-timeline-view-dark", _("Descendants Timeline")),
    ],
    requires_mod=["cairo"],
    requires_gi=[("Gtk", "3.0"), ("Gdk", "3.0"), ("Atk", "1.0"), ("GLib", "2.0")],
    help_url="https://github.com/ph-plqn/DescendantsTimeline#descendantstimeline-100",
)

# The selector initializer is only needed by Gramps at runtime.
if not locals().get("build_script", False):
    register(
        GENERAL,
        id="descendants_timeline_selector_init",
        name=_("Descendants Timeline selector icon"),
        description=_("Prepare the Descendants Timeline icon for the view selector."),
        version="1.0.0",
        gramps_target_version="6.0",
        status=STABLE,
        fname="descendants_timeline_selector_init.py",
        authors=["Philippe"],
        authors_email=["ph-plqn@users.noreply.github.com"],
        load_on_reg=True,
        include_in_listing=False,
        requires_gi=[("Gtk", "3.0"), ("GdkPixbuf", "2.0"), ("GLib", "2.0")],
    )
