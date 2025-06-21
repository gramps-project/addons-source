from gramps_gedcom7 import import_gedcom, ImportSettings


def import_data(database, filename, user):
    """Import a GEDCOM file into a Gramps database with user context."""
    settings = ImportSettings()
    import_gedcom(input_file=filename, db=database, settings=settings)
