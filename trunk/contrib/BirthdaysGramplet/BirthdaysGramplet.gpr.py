# File: Birthdays.gpr.py
register(GRAMPLET,
	id='Birthdays',
	name=_("Birthdays Gramplet"),
	description = _("a gramplet that displays the birthdays of the living people"),
	status = STABLE,
	version = '1.0.4',
	fname="BirthdaysGramplet.py",
	height = 200,
	gramplet = 'BirthdaysGramplet',
	gramps_target_version="3.2",
	gramplet_title=_("Birthdays Gramplet")
	)
