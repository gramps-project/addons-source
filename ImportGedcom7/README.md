# GEDCOM 7 Import

Imports [GEDCOM 7](https://gedcom.io/) files into Gramps.

GEDCOM 7 is a substantial revision of the GEDCOM standard and is not backwards
compatible with GEDCOM 5.5.1, so it needs an importer of its own. Gramps' built-in
GEDCOM importer continues to handle 5.5.1 and earlier files.

## Requirements

This addon requires the [gramps-gedcom7](https://github.com/DavidMStraub/gramps-gedcom7)
Python library, which does the actual parsing and conversion:

```bash
pip install gramps-gedcom7
```

The Plugin Manager can also install it for you when you install this addon.

## File extension

The addon registers the `.ged7` extension. GEDCOM 7 files produced by other
applications usually carry the same `.ged` extension as GEDCOM 5.5.1 files,
which Gramps routes to its built-in GEDCOM 5.5.1 importer — so **rename a
GEDCOM 7 file to `.ged7` before importing it**.

GEDCOM ZIP packages (`.gdz`) are not supported yet; unpack them and import the
GEDCOM file they contain.

## Status

The underlying conversion covers the vast majority of GEDCOM 7 and has been
tested against real-world files. The addon itself is registered as beta because
it is new; as with any conversion tool, check the results after importing.

Please report problems, ideally with a sample file, at the
[gramps-gedcom7 issue tracker](https://github.com/DavidMStraub/gramps-gedcom7/issues).
