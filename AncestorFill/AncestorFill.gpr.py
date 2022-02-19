#-------------------------------------------------------------------------
#
# register_report
#
#-------------------------------------------------------------------------
register(REPORT,
  id    = 'AncestorFill',
  name  = _("AncestorFill"),
  description =  _("Report on the filling of the tree"),
  version = '1.0.17',
  gramps_target_version = "5.1",
  include_in_listing = True,
  status = STABLE,
  fname = 'AncestorFill.py',
  authors = ["Eric Doutreleau"],
  authors_email = ["eric@doutreleau.fr"],
  category = CATEGORY_TEXT,
  require_active = False,
  reportclass = 'AncestorFillReport',
  optionclass = 'AncestorFillOptions',
  report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI, REPORT_MODE_BKI],
)
