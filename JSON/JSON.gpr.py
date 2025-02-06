register(
    EXPORT,
    id="JSON Export",
    name=_("JSON Export"),
    description=_("This is a JSON export"),
    version="1.0.22",
    gramps_target_version="6.0",
    status=STABLE,
    fname="JSONExport.py",
    export_function="exportData",
    export_options="WriterOptionBox",
    export_options_title=_("JSON options"),
    extension="json",
    help_url="Addon:JSON_Export_Import#Export_JSON",
)

register(
    IMPORT,
    id="JSON Import",
    name=_("JSON Import"),
    description=_("This is a JSON import"),
    version="1.0.22",
    gramps_target_version="6.0",
    status=STABLE,
    fname="JSONImport.py",
    import_function="importData",
    extension="json",
    help_url="Addon:JSON_Export_Import#Import_JSON",
)
