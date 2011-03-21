register(REPORT,
        id = 'LinesOfDescendency',
        name = _('Lines of Descendency'),
        description = _('Prints out all descendency lines '
            'from a given ancestor to a given descendent in text.'),
        version = '1.1.5',
        gramps_target_version = '3.4',
        status = STABLE,
        fname = 'lines-of-descendency.py',
        authors = ['lcc'],
        authors_email = ['lcc.mailaddress@gmail.com'],
        category = CATEGORY_TEXT,
        reportclass = 'LinesOfDescendency',
        optionclass = 'LODOptions',
        report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI]
        )
