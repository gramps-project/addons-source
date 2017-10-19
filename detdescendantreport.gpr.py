register(REPORT,
    id   = 'det_descendant_report_i',
    name = _('Detailed Descendant Report With All Images'),
    description = _("Produces a detailed descendant report with all images."),
    version = '1.0',
    gramps_target_version = '4.2',
    status = STABLE,
    fname = 'detdescendantreporti.py',
    authors = ["Jon Schewe", "Bruce DeGrasse"],
    authors_email = ["jpschewe@mtu.net", "bdegrasse1@attbi.com"],
    category = CATEGORY_TEXT,
    reportclass = 'DetailedDescendantReportI',
    optionclass = 'DetailedDescendantIOptions',
    report_modes = [REPORT_MODE_GUI, REPORT_MODE_BKI, REPORT_MODE_CLI],
    require_active = True
    )

__author__ = "jpschewe"
