addons-source [![Build Status](https://travis-ci.org/gramps-project/addons-source.svg?branch=master)](https://travis-ci.org/gramps-project/addons-source)
=============

Source code of contributed Third-party addons for the Gramps genealogy program.

To develop your own addon:

* https://gramps-project.org/wiki/index.php?title=Addons_development

Usage
=====

Use `make.py` for Gramps addons.

Clone both this repository and the addon repository if you intend to rebuild the addon

https://github.com/gramps-project/addons

Once you use the comands below the version number will be incremented and the resulting
files will be in the second addon repository to be commited.

Examples:
* Creates the initial addon-source directories for the addon.
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

* Create or update the listing entry for your addon
```
python make.py gramps42 listing AddonDirectory
```
