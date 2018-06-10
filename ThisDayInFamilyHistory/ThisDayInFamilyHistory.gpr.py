# File: ThisDayInFamilyHistory.gpr.py
register(GRAMPLET,
         id="This Day in Family History",
         name=_("This Day in Family History"),
         description = _("A configurable program that shows you the events from your family tree on this date."),
         version="0.0.1",
         gramps_target_version="5.0",
         status = STABLE,
         fname="ThisDayInFamilyHistory.py",
         height = 200, 
         gramplet = 'ThisDayInFamilyHistory',
         gramplet_title=_("This Day in Family History"),
         help_url="This Day In Family History"
         )
