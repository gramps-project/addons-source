# File: Birthdays.gpr.py
register(GRAMPLET,
	id='Birthdays',
	name=_("Birthdays Gramplet"),
	description = _("a gramplet that displays the birthdays of the living people"),
	status = STABLE, # tested with python 2to3
	version = '1.0.16',
	fname="BirthdaysGramplet.py",
	height = 200,
	gramplet = 'BirthdaysGramplet',
	gramps_target_version = "4.0",
	gramplet_title = _("Birthdays Gramplet"),
	help_url = "BirthdaysGramplet",
	)
