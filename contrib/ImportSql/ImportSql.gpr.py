register(IMPORT,
         id    = 'im_sqlite',
         name  = _('SQLite Import'),
         description =  _('SQLite is a common local database format'),
         version = '1.0',
         gramps_target_version = "3.3",
         status = STABLE,
         fname = 'ImportSql.py',
         import_function = 'importData',
         extension = "sql"
)
