# -*- coding: utf-8 -*-

register(TOOL,
    id='familiopreptool',
    name=_("Prepare for Familio export"),
    description=_(
        "Adds a missing _UID attribute to persons (without overwriting "
        "existing ones) and adds missing 'Marriage' events to families, "
        "so that GEDCOM export produces the tags Familio expects."
    ),
    version = '1.0.0',
    gramps_target_version="6.0",
    status=STABLE,
    fname='FamilioPrepTool.py',
    authors=["Alexander Aganichev", "Claude", "Gemini"],
    authors_email=["aaganichev@gmail.com"],
    category=TOOL_DBPROC,
    toolclass='FamilioPrepTool',
    optionclass='FamilioPrepOptions',
    tool_modes=[TOOL_MODE_GUI],
    )
