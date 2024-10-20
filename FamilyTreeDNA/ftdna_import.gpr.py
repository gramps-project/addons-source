register(TOOL,
         id = "FamilyTree DNA Import Gramplet",
         name = _("FamilyTree DNA"),
         description = _("Tool to import FamilyFinder DNA data from Family Tree"),
         status = STABLE,
         audience = EXPERT,
         version = '1.0.31',
         gramps_target_version = '5.2',
         fname = "ftdna_import.py",
         category = TOOL_UTILS,
         toolclass = 'FamilyFinder',
         optionclass = 'FamilyFinderOptions',
         tool_modes = [TOOL_MODE_GUI, TOOL_MODE_CLI],
         help_url="Addon:FamilyTree_DNA",
        )
