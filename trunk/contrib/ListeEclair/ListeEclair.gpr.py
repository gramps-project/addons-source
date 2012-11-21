register(REPORT,
id    = 'ListeEclair',
name  = _("Liste Eclair"),
description =  _("Produit une liste eclair"),
version = '1.0.3',
gramps_target_version = '4.0',
include_in_listing = False,
status = STABLE, # not yet tested with python 3
fname = 'ListeEclair.py',
authors = ["Eric Doutreleau"],
authors_email = ["eric@doutreleau.fr"],
category = CATEGORY_TEXT,
require_active = False,
reportclass = 'ListeEclairReport',
optionclass = 'ListeEclairOptions',
report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI]
)
