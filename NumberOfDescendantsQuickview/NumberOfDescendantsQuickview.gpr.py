register(
    QUICKREPORT,
    id="NumberOfDescendantsQuickview",
    name=_("Number of descendants"),
    description=_("Shows the number of descendants of the current person"),
    version="3.4.32",
    gramps_target_version="6.0",
    status=STABLE,
    fname="NumberOfDescendantsQuickview.py",
    authors=["Reinhard Mueller"],
    authors_email=["reinhard.mueller@igal.at"],
    category=CATEGORY_QR_PERSON,
    runfunc="run",
    help_url="Addon:Number_of_Descendants_Quickview",
)
