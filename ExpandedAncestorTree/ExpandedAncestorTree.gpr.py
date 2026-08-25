#
# Gramps - a GTK+/GNOME based genealogy program
# Plugin registration for Expanded Ancestor Tree
#

register(
    REPORT,
    id="ExpandedAncestorTree",
    name=_("Expanded Ancestor Tree"),
    description=_("Expanded Ancestor Graph showing direct ancestors, siblings, cousins and spouses."),
    version="1.0.0",
    gramps_target_version="6.0",
    status=STABLE,
    fname="ExpandedAncestorTree.py",
    authors=["Bartok Szabolcs"],
    category=CATEGORY_DRAW,
    authors_email=["bartokszabi2005@gmail.com"],
    reportclass="ExpandedAncestorTree",
    optionclass="ExpandedAncestorTreeOptions",
    report_modes=[REPORT_MODE_GUI, REPORT_MODE_CLI, REPORT_MODE_BKI],
)