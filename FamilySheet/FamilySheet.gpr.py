register(REPORT,
    id   = 'FamilySheet',
    name = _('Family Sheet'),
    description = _("Produces a family sheet showing full information "
                    "about a person and his/her partners and children."),
    version = '3.4.33',
    gramps_target_version = "5.0",
    status = STABLE,
    fname = 'FamilySheet.py',
    authors = ["Reinhard Mueller"],
    authors_email = ["reinhard.mueller@igal.at"],
    category = CATEGORY_TEXT,
    reportclass = 'FamilySheet',
    optionclass = 'FamilySheetOptions',
    report_modes = [REPORT_MODE_CLI, REPORT_MODE_GUI, REPORT_MODE_BKI],
    require_active = True
    )
