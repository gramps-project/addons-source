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
    authors_email=[],
    order=END,
)

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
    authors_email=[],
    load_on_reg=True,
)
