register(
    REPORT,
    id="database-differences-report",
    name=_("Database Differences Report"),
    description=_("Compares an external database with the current one."),
    version = '1.0.27',
    gramps_target_version="6.0",
    status=STABLE,  # not yet tested with python 3, comparing unequal types not supported in 3.x
    fname="differences.py",
    authors=["Doug Blank"],
    authors_email=["doug.blank@gmail.com"],
    category=CATEGORY_TEXT,
    reportclass="DifferencesReport",
    optionclass="DifferencesOptions",
    report_modes=[REPORT_MODE_GUI, REPORT_MODE_BKI, REPORT_MODE_CLI],
    require_active=False,
    help_url="Addon:Database_Differences_Report",
)
