
plg = newplugin()
plg.id = 'database-differences-report'
plg.name = _("Database Differences Report")
plg.description = _("Compares an external database with the current one.")
plg.version = '1.0'
plg.gramps_target_version = '3.5'
plg.status = STABLE
plg.fname = 'differences.py'
plg.ptype = REPORT
plg.authors = ["Doug Blank"]
plg.authors_email = ["doug.blank@gmail.com"]
plg.category = CATEGORY_TEXT
plg.reportclass = 'DifferencesReport'
plg.optionclass = 'DifferencesOptions'
plg.report_modes = [REPORT_MODE_GUI, REPORT_MODE_BKI, REPORT_MODE_CLI]
plg.require_active = False
