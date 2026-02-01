addons-source [![Build Status](https://travis-ci.org/gramps-project/addons-source.svg?branch=master)](https://travis-ci.org/gramps-project/addons-source) <a href="https://hosted.weblate.org/engage/gramps-project/">
<img src="https://hosted.weblate.org/widget/gramps-project/addons/svg-badge.svg" alt="Translation status" />
</a>
=============

Source code of contributed third-party addons for the [Gramps genealogy program](https://github.com/gramps-project/gramps).

You can develop your own addon following the [Addons Development](https://gramps-project.org/wiki/index.php?title=Addons_development) wiki.

Note: The default git branch is `master`.  The master branch should only be used to develop addons that require features or changes found in the Gramps master branch.  Most of the time addons should be developed to work with the current released version of Gramps (`maintenance/gramps60` for the Gramps 6.0.x versions for example).

So use care when creating your addon to base off of the correct branch, and also to select the correct branch when creating a PR on Github.

Usage
=====

Use `make.py` for Gramps addons.

Clone both this repository and the packaged [addons](https://github.com/gramps-project/addons) repository if you intend to rebuild and publish the addon.

Once you use the commands below the version number will be incremented and the resulting
files will be in the addons repository, ready to be committed.

Examples:
* Creates the initial addon-source directories and .pot file for the addon.
```
python3 make.py gramps60 init AddonDirectory
```

* Creates the initial empty `AddonDirectory/po/fr-local.po` file for the addon.
```
python3 make.py gramps60 init AddonDirectory fr
```

* Updates `AddonDirectory/po/fr-local.po` with the latest translations.
```
python3 make.py gramps60 update AddonDirectory fr
```

* Build `../download/AddonDirectory.addon.tgz`
```
python3 make.py gramps60 build AddonDirectory
```

* Create or update the listing entry for your addon.
```
python3 make.py gramps60 listing AddonDirectory
```

* For the developer who is merging PRs or other commits and needs to rebuild.
    and list one or more addons
```
python3 make.py gramps60 as-needed
```

Valid command summary
=====================

* **clean** - Removes unnecessary files (locale etc.) from the addon.

* **init** [subcommand: **all**] - Get all of the strings from the addon and
create necessary subdirectories and the template.pot for the addon or all
addons if **all** is used.

* **update** - Updates the language xx-local.po file from the pot file.

* **compile** [subcommand: **all**] - Compiles the language xx-local.po files
into the locale/xx/LD_MESSAGES/addon.mo files for all languages in addon,
or all addons if **all** is used.

* **build**  [subcommand: **all**] - Builds the addon for release.

* **manifest-check** - Checks if all files are correct in addon release file?

* **unlist** - Unlist the addon from the listing.

* **fix**  - If the listing shows a repeated addon entry, fix it.

* **check** - Checks if the addon listing matches the addon download version
or if missing from the listing.

* **listing** [subcommand: **all**] - Builds/creates a listing for the addon in
each supported language.

* **as-needed** [no other parameters] - Builds/lists/cleans only out of date
addons in one step.  It also rebuilds the template.pot file so it is also
up to date.


