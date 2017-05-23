register(EXPORT,
         id    = 'Prolog Export',
         name  = _('Prolog Export'),
         description =  _('Exports data into a Prolog fact format'),
         version = '1.0.4',
         gramps_target_version = "5.1",
         status = STABLE,
         fname = 'ExportProlog.py',
         export_function = 'exportData',
         extension = "pl"
         )
