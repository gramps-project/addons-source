register(IMPORT,
         id    = 'im_sqlite',
         name  = _('SQLite Import'),
         description =  _('SQLite is a common local database format'),
         version = '1.0.32',
         gramps_target_version = "5.1",
         status = STABLE, # tested with python 3, need to review unicode usage
         fname = 'ImportSql.py',
         import_function = 'importData',
         extension = "sql"
)

register(EXPORT,
         id    = 'ex_sqlite',
         name  = _('SQLite Export'),
         description =  _('SQLite is a common local database format'),
         version = '1.0.31',
         gramps_target_version = "5.1",
         status = STABLE, # tested with python 3 but still gives errors
         fname = 'ExportSql.py',
         export_function = 'exportData',
         extension = "sql",
         export_options = 'WriterOptionBox'
)
