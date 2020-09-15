register(EXPORT,
         id    = 'Prolog Export',
         name  = _('Prolog Export'),
         description =  _('Exports data into a Prolog fact format.  '
                          'Data is in Unicode (utf-8)'),
         version = '1.0.15',
         gramps_target_version = "5.2",
         status = STABLE,
         fname = 'ExportProlog.py',
         export_function = 'exportData',
         extension = "pl"
         )
