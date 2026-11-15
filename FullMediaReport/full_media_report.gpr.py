#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

register(
    REPORT,
    id="FullMediaReport",
    name=_("Full Media Report"),
    description=_("Generates one PDF catalogue containing all media objects."),
    version="0.1.0",
    gramps_target_version="6.0",
    status=STABLE,
    fname="full_media_report.py",
    authors=["Anton Kurashev", "Based on Media Report by Matthias Kemmer"],
    category=CATEGORY_TEXT,
    reportclass="FullMediaReport",
    optionclass="ReportOptions",
    report_modes=[REPORT_MODE_CLI, REPORT_MODE_GUI],
    help_url="Addon:FullMediaReport",
)
