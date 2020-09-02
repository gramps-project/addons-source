
# File: ThisDayInFamilyHistory.gpr.py

register(GRAMPLET,
         status = STABLE,
         id="This Day in Family History",
         name=_("This Day in Family History"),
         description = _("A configurable program that shows you the connected events from your family tree that match today's day and month."),
         version = '1.0.8',
         fname="ThisDayInFamilyHistory.py",
         authors="Stephen Adams",
         gramplet = 'ThisDayInFamilyHistory',
         expand=True,
         gramplet_title=_("This Day in Family History"),
         help_url="This Day In Family History",
         gramps_target_version="5.1"
        )
