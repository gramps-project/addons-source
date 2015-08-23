addons-source [![Build Status](https://travis-ci.org/gramps-project/addons-source.svg?branch=master)](https://travis-ci.org/gramps-project/addons-source)
=============

Source code of contributed Third-party addons for the Gramps genealogy program.

To develop your own addon:

* https://gramps-project.org/wiki/index.php?title=Addons_development

Usage
=====

Use `make.py` for Gramps addons.

Examples:
* Creates the initial directories for the addon.
```
python make.py gramps42 init AddonDirectory
```

* Creates the initial empty `AddonDirectory/po/fr-local.po` file for the addon.
```
python make.py gramps42 init AddonDirectory fr
```

* Updates `AddonDirectory/po/fr-local.po` with the latest translations.
```
python make.py gramps42 update AddonDirectory fr
```

* Build `../download/AddonDirectory.addon.tgz`
```
python make.py gramps42 build AddonDirectory
```

* Create or update the lising entry for your addon
```
python make.py gramps42 listing AddonDirectory
```
