# Plain Python helper module, importable from any .gram.py script in this
# folder via `from script_helpers import decade` (see 11_import_example.gram.py).
# Unlike .gram.py files this is not a runnable script itself -- it's a
# regular module that GrampyScript's import-path setup makes importable.


def decade(year):
    """Round a year down to the start of its decade, e.g. 1873 -> 1870."""
    return (year // 10) * 10 if year else None
