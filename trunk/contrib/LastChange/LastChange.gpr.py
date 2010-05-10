# File: HelloWorld.gpr.py
register(GRAMPLET,
         id="LastChangeGramplet",
         name=_("Last Change Gramplet"),
         description=_("List the last ten person records that have been changed"),
         status=STABLE,
         version="0.0.2",
         fname="LastChangeGramplet.py",
         authors=['Jakim Friant'],
         authors_email=["jmodule@friant.org"],
         height=170,
         gramplet='LastChangeGramplet',
         gramps_target_version="3.3",
         gramplet_title=_("Latest Changes")
         )

register(REPORT,
         id="LastChangeReport",
         name=_("Last Change Report"),
         description=_("Report of the last records that have been changed"),
         status=STABLE,
         version="0.0.1",
         fname="LastChangeReport.py",
         gramps_target_version="3.3",
         authors=['Jakim Friant'],
         authors_email=["jmodule@friant.org"],
         category=CATEGORY_TEXT,
         reportclass='LastChangeReport',
         optionclass='LastChangeOptions',
         report_modes=[REPORT_MODE_GUI, REPORT_MODE_BKI, REPORT_MODE_CLI],
         require_active=False
         )