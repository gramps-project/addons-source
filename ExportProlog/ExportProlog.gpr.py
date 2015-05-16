register(EXPORT,
         id    = 'Prolog Export',
         name  = _('Prolog Export'),
         description =  _('Exports data into a Prolog fact format'),
         version = '1.0.1',
         gramps_target_version = '4.2',
         status = STABLE, 
         fname = 'ExportProlog.py',
         export_function = 'exportData',
         extension = "pl"
         )
