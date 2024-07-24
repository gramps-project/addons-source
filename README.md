addons-source [![Build Status](https://travis-ci.org/gramps-project/addons-source.svg?branch=master)](https://travis-ci.org/gramps-project/addons-source)
=============

Source code of contributed Third-party addons for the Gramps genealogy program.

To develop your own addon:

* https://gramps-project.org/wiki/index.php?title=Addons_development

Note: The default git branch is `master`.  The master branch should only be used to develop addons that require features or changes found in the Gramps master branch.  Most of the time addons should be developed to work with the current released version of Gramps (`maintenance/gramps51` for the Gramps 5.2.x versions for example).

So use care when creating your addon to base off of the correct branch, and also to select the correct branch when creating a PR on Github.

Usage
=====

Use `make.py` for Gramps addons.

Clone both this repository and the addon repository if you intend to rebuild the addon

https://github.com/gramps-project/addons

Once you use the comands below the version number will be incremented and the resulting
files will be in the second addon repository to be commited.

Examples:
* Creates the initial addon-source directories and .pot file for the addon.
```
python3 make.py gramps52 init AddonDirectory
```

* Creates the initial empty `AddonDirectory/po/fr-local.po` file for the addon.
```
python3 make.py gramps52 init AddonDirectory fr
```

* Updates `AddonDirectory/po/fr-local.po` with the latest translations.
```
python3 make.py gramps52 update AddonDirectory fr
```

* Build `../download/AddonDirectory.addon.tgz`
```
python3 make.py gramps52 build AddonDirectory
```

* Create or update the listing entry for your addon
```
python3 make.py gramps52 listing AddonDirectory
```

* For the developer who is merging PRs or other commits and needs to rebuild
    and list one or more addons
```
python3 make.py gramps52 as-needed
```

Valid command summary
=====================

* **clean** - Removes unnecessary files (locale etc) from the addon

* **init** [subcomand: **all**] - Get all of the strings from the addon and
create necessary subdirectories and the template.pot for the addon or all
addons if **all** is used.

* **update** - Updates the language xx-local.po file from the pot file.

* **compile** [subcomand: **all**] - Compiles the language xx-local.po files
into the locale/xx/LD_MESSAGES/addon.mo files for all languages in addon,
or all addons if **all** is used.

* **build**  [subcomand: **all**] - Builds the addon for release

* **manifest-check** - Checks if all files are correct in addon release file?

* **unlist** - Unlist the addon from the listing

* **fix**  - If the listing shows a repeated addon entry, fix it

* **check** - Checks if the addon listing matches the addon download version
or if missing from the listing

* **listing** [subcomand: **all**] - Builds/Creates a listing for the addon in
each supported language

* **as-needed** [no other parameters] - Builds/Lists/Cleans only out of date
addons in one step.  It also rebuilds the template.pot file so it is also
up to date.


