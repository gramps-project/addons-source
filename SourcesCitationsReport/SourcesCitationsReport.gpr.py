#------------------------------------------------------------------------
#
# SourcesCitations Report
#
#------------------------------------------------------------------------

register(REPORT,
    id    = 'SourcesCitationsReport',
    name  = _("Sources and Citations Report"),
    description =  _("Provides a source and Citations with notes"),
    version = '1.0.3',
    gramps_target_version = "5.1",
    status = STABLE,
    fname = 'SourcesCitationsReport.py',
    authors = ["Uli22"],
    authors_email = ["hansulrich.frink@gmail.com"],
    category = CATEGORY_TEXT,
    reportclass = 'SourcesCitationsReport',
    optionclass = 'SourcesCitationsOptions',
    report_modes = [REPORT_MODE_GUI, REPORT_MODE_BKI, REPORT_MODE_CLI],
    require_active = False
    )
