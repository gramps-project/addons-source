# -------------------------------------------------------------------------
#
#
#
# -------------------------------------------------------------------------
register(
    REPORT,
    id="denominoviso",
    name=_("DenominoViso"),
    category=CATEGORY_WEB,
    status=STABLE,
    fname="DenominoViso.py",
    reportclass="DenominoVisoReport",
    optionclass="DenominoVisoOptions",
    report_modes=[REPORT_MODE_GUI, REPORT_MODE_CLI],
    authors=["M.D. Nauta"],
    authors_email=["m.d.nauta@hetnet.nl"],
    description=_(
        "Generates a web (HTML) page with a graphical "
        "representation of ancestors/descendants (SVG) "
        "where details about individuals become visible "
        "upon mouse-events."
    ),
    version = '2.3.50',
    gramps_target_version="6.0",
    help_url="Addon:DenominoViso",
)
