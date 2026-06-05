# patronymic_inference.gpr.py
# ruff: noqa

register(
    TOOL,
    id="name_standardization_tool",
    name=_("Audit Given and Patronymic Names"),
    category=TOOL_DBPROC,  # Standard database processing category
    description=_(
        "Tools to rename given name, audit and infer patronymic (East Slavic) names."
    ),
    version="1.0",
    gramps_target_version="6.0",
    status=STABLE,
    fname="names_tool.py",
    authors=["Dmitry Bryndin"],
    authors_email=["1129396+bryndin@users.noreply.github.com"],
    toolclass="NamesTool",
    optionclass="NamesToolOptions",
)

register(
    GRAMPLET,
    id="patronymic_suggestion_gramplet",
    name=_("Patronymic Suggestion"),
    description=_(
        "Suggests (East Slavic) patronymic names in real-time as you navigate."
    ),
    version="1.0",
    gramps_target_version="6.0",
    status=STABLE,
    fname="patronymics_gramplet.py",
    authors=["Dmitry Bryndin"],
    authors_email=["1129396+bryndin@users.noreply.github.com"],
    gramplet="PatronymicSuggestionGramplet",
    navtypes=["Person", "Relationship"],
    gramplet_title=_("Patronymic Suggestion"),
)
