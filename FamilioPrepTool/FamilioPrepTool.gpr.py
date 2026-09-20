# -*- coding: utf-8 -*-

# ВАЖНО: если у вас уже были зарегистрированы отдельные плагины
# AddMarriageEvents и SetAttribute (свои .gpr.py файлы) - удалите или
# переименуйте их id/fname, чтобы избежать дублирования в списке инструментов.
#
# Проверьте и при необходимости поправьте gramps_target_version под вашу
# версию Gramps (uistate.get_active/set_active стабильны с давних версий,
# но API MenuToolOptions в редких случаях отличается между релизами).

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
