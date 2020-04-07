register(REPORT,
    id   = 'det_descendant_report_i',
    name = _('Detailed Descendant Report With All Images'),
    description = _("Produces a detailed descendant report with all images and optional todo list."),
    version = '1.0.7',
    gramps_target_version = '5.1',
    status = STABLE,
    fname = 'detdescendantreporti.py',
    authors = ["Jon Schewe"],
    authors_email = ["jpschewe@mtu.net"],
    category = CATEGORY_TEXT,
    reportclass = 'DetailedDescendantReportI',
    optionclass = 'DetailedDescendantIOptions',
    report_modes = [REPORT_MODE_GUI, REPORT_MODE_BKI, REPORT_MODE_CLI],
    require_active = True
    )

__author__ = "jpschewe"
