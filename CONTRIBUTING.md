# CONTRIBUTING Addons
This document describes the API, methods, and best practices for
developing third-party addons for Gramps 6.0 and later. 

We assume that most addons will be developed using a Linux development
environment.  While it is possible to do so under Windows or MacOS,
many of the steps will differ and the documented processes have not
been as thoroughly reviewed. Developer beware.  Beyond here there be
dragons.

Working knowledge of Python and git is required.  Ideally, all addons
will be contributed and maintained using github, but having a github
account is not required.

The addons source tree in github is licensed under the 
[GNU Public License v2 (GPL-2.0)](https://opensource.org/license/gpl-2-0).
We assume you agree with redsitribution under that license when contributing
addon source.

If you're looking for *existing* addons to install, see
[Third-Party Addons](https://gramps-project.org/wiki/index.php/Third-party_Addons).

If you're looking to contribute to Gramps directly, see
[Portal:Developers](https://gramps-project.org/wiki/index.php/Getting_started_with_Gramps_development).

## Table of Contents
* [What Can Addons Extend?](#what-can-addons-extend)
* [Overview of Writing an Addon](#overview-of-writing-an-addon)
* [Develop Your Addon](#develop-your-addon)
    * [Addons Source Code Repository](#addon-source-code-repository)
    * [Addons Download Repository](#addons-download-repository)
    * [Set Up a Github Account](#setup-a-github-account)
    * [Create Project Forks in Github](#create-project-forks-in-github)
    * [Set Up Addon Development Environment](#set-up-addon-development-environment)
        * [Gramps Repository](#gramps-repository)
        * [Addons Repository](#addons-repository)
        * [Addons Source Repository](#addons-source-repository)
    * [Create Your Development Branch](#create-your-development-branch)
    * [Create Your Addon Subdirectory](#create-your-addon-subdirectory)
    * [Follow the Development API](#follow-the-development-api)
    * [Test Your Addon As You Develop](#test-your-addon-as-you-develop)
    * [Addon Configuration](#addon-configuration)
    * [Localization](#localization)
    * [Files Included in Addon Distribution](#files-included-in-addon-distribution)
* [Create a Gramps Plugin Registration file](#create-a-gramps-plugin-registration-file)
    * [Report Plugins](#report-plugins)
    * [General Plugins](#general-plugins)
    * [Registered GENERAL Categories](#registered-general-categories)
    * [List Your Addon Prerequistes](#list-your-addon-prerequistes)
* [Review the Addon Checklist](#review-the-addon-checklist)
* [Create a Pull Request](#create-a-pull-request)
    * [Commit Your Changes](#commit-your-changes)
    * [Verify Your Addon Is Current](#verify your addon is current)
    * [Push To Your Fork](#push-to-your-fork)
    * [Create the PR](#create-the-pr)
    * [Work Towards a Merge](#work-towards-a-merge)
* [Announce Your Addon](#announce-your-addon)
    * [Gramps Forum](#gramps-forum)
    * [Gramps Wiki](#gramps-wiki)
        * [List Your Addon](#list-your-addon)
        * [Document Your Addon](#document-your-addon)
* [Support Your Addon Through Bug Tracker](#support-your-addon-through-bug-tracker)
* [Maintain Your Addon Code as Gramps Evolves](#maintain-your-addon-code-as-gramps-evolves)
* [Resources](#resources)
* [Addon Development Tutorials and Samples](#addon-development-tutorials-and-samples)
* [Addons External to Github](#addons-external-to-github)

## What Can Addons Extend?
<!-- sync with https://gramps-project.org/wiki/index.php?title=Addon_list_legend&action=edit&section=2 --> 
Addons for Gramps can extend the program in many different ways. You can
add any of the following [types](https://github.com/gramps-project/gramps/blob/master/gramps/gen/plug/_pluginreg.py) of addons:

* **Importer** (IMPORT) - adds additional file format import options to Gramps
* **Exporter** (EXPORT) - adds additional file format export options to Gramps
* **[Gramplet](https://gramps-project.org/wiki/index.php/Gramps_Glossary#gramplet)** (GRAMPLET) - adds a new
interactive interface section to a Gramps view mode, which can be
activated by right-clicking on the dashboard View or from the menu
of the Sidebar/Bottombar in other view categories. 
* **Gramps** [**View mode**](https://gramps-project.org/wiki/index.php/Gramps_Glossary#viewmode) (VIEW) - adds a
new view mode to the list of views available within a
[View Category](https://gramps-project.org/wiki/index.php/Gramps_Glossary#view)
* **[Map Service](https://gramps-project.org/wiki/index.php/[Map_Services)**
(MAPSERVICE) - adds new mapping options to Gramps
* **Plugin lib** (GENERAL) - libraries that provide extra functionality when
present; can add, replace and/or modify builtin Gramps options.
* **[Quickreport/Quickview](https://gramps-project.org/wiki/indew/Gramps_6.0_Wiki_Manual_-_Reports_-_part_8#Quick_Views)** (QUICKREPORT) - a view
that you can run by right-clicking on an object, or if a person quickview,
then via the Quick View Gramplet
* **[Report](https://gramps-project.org/wiki/index.php/Gramps_6.0_Wiki_Manual_-_Reports_-_part_1)** (REPORT) - adds a new output report; this includes
**Website** that outputs a static genealogy website based on your Gramps
Family Tree data.
* **[Rule](https://gramps-project.org/wiki/index.php/Gramps_6.0_Wiki_Manual_-_Filters#Add_Rule_dialog)** (RULE) - adds new
[filter](https://gramps-project.org/wiki/index.php/Gramps_Glossary#filter)
rules. New starting with Gramps 5.1.
* **[Tool](https://gramps-project.org/wiki/index.php/Gramps_6.0_Wiki_Manual_-_Tools)** (TOOL) - adds a utility that helps process data from your family tree.
* **Doc creator** (DOCGEN)
* **Relationships** (RECALC)
* **Sidebar** (SIDEBAR)
* **[Database](https://gramps-project.org/wiki/index.php/Database_Backends)**
(DATABASE) - add support for another database backend. New starting with
Gramps 5.0.
* **Thumbnailer** (THUMBNAILER) New starting with Gramps 5.2
* **Citation formatter** (CITE) New starting with Gramps 5.2

## Overview of Writing an Addon
Writing an addon is fairly straightforward if you have a bit of Python
experience.  And, sharing your addon is the right thing to do.  The
general steps to writing and sharing your own addons are:

* [Develop your addon](#develop-your-addon)
* [Create a Gramps plugin registration file](#create-a-gramps-plugin-registration-file) - e.g., a file named ```my-addon.gpr.py```
* [Review the Addon Checklist](#review-the-addon-checklist)
* [Create a Pull Request for your addon](#create-pr)
* [Announce it on the Gramps forum](#announce-the-addon) - Let users
know it exists and how to use it.
* [Support it through the issue tracker](#support-it-through-issue-tracker)
* [Maintain the code](#maintain-the-code-as-gramps-continues-to-evolve) as
the Gramps code continues to evolve

We'll now expand on each of these steps.

## Develop Your Addon
Addons are found in two locations:

1.  The source code repository, where the addons are developed and
maintained: [addons-source](http://github.com/gramps-project/addons-source)
2.  The download repository, which stores the packages that
Gramps Addons Manager users download and update for addons they want:
[addons](http://github.com/gramps-project/addons)

### Addons Source Code Repository
The [addons-source](http://github.com/gramps-project/addons-source)
github repository holds the source code for addons, with branches
for each version of the different Gramps releases.

Example commands refer to the current public release and maintenance
branch rather than the master branch.  Only addons maintainers will
merge changes into the current release branch(es); the master branch
is only used by the repository maintainers, and only as needed.

Hence, the branches in 
[addons-source](http://github.com/gramps-project/addons-source)
to be concerned with are:

* ```master``` - managed only by addon maintainers, and not necessarily
current
* ```maintenance/gramps52``` - the Gramps 5.2 current release branch, for the
previous version of Gramps
* ```maintenance/gramps60``` - the Gramps 6.0 current release branch, for the
_current_ version of Gramps

If you are working on an addon for gramps for the current
Gramps 6.0 public release, be sure to use the
```maintenance/gramps60``` git branch.  NB: there are branches for
older releases should they be needed.

The source code in
[addons-source](http://github.com/gramps-project/addons-source)
has the following structure, with the code for each addon in its
own subdirectory:
```
    /addons-source
        /IndividualNameOfAddon1
        /IndividualNameOfAddon2
        /...
```
There are some command line tools and documentation in the root directory
as well.

### Addons Download Repository
The [addons](http://github.com/gramps-project/addons) git repository holds
packaged versions of the addons for each release of Gramps. As an addon
developer, you shouldn't _have_ to do anything with this repository.  You
should only need to use this repository if you want to have a model of
an addon repository in order to make and manage your own, or to test the
packaging of your addon.  The repository has the following structure:
```
    /addons
        /gramps52
            /download
            /listings
        /gramps60
            /download
            /listings
```

### Set Up a Github Account
In order to use all of the tools github repositories can offer, it is
necessary to have a github account.  While this is not absolutely required
to develop and addon (see
[Addons External to Github](#addons-external-to-github)),
it can make things easier.  For those new to github and
```git```:

* Create a [Github account](https://github.com/join) if you don't already
have one.
* Create and upload an SSH key for your github account (see
[Connecting to GitHub with SSH](https://help.github.com/articles/generating-an-ssh-key/)).
* There is a [short git introduction](https://gramps-project.org/wiki/index.php/Brief_introduction_to_git)
with instructions for installing ```git``` and getting basic settings configured
in a way familiar to Gramps and addons developers.

Even if you are not using github, you will need some familiarity with ```git```.

### Create Project Forks in Github
Github assumes a similar development process for all projects:

1. Find the project you wish to contribute to -- your **_upstream_** project.
2. Create a github fork of that upstream project in your user account.
3. Make modifications in **_your fork_** of the upstream project.
4. Once your modifications are ready, create a PR (Pull Request)
in the **_upstream_** project pointing to the work in **_your fork_**.
5. The upstream maintainers will then work with you, through the PR,
to make sure your modification fits into their project.

This may require several iterations of the addon code for the PR.

Gramps addon development will only require one fork of a github upstream
project: ```addons-source```.  For testing of the addon packaging, a fork of
```addons``` will be needed:

* The ```addons-source``` project at
[https://github.com/gramps-project/addons-source](https://github.com/gramps-project/addons-source).
* The ```addons``` project (the packaged form) at
[https://github.com/gramps-project/addons](https://github.com/gramps-project/addons).

In the github web interface, login and go to each of the links above.
There is a "Fork" pull-down menu in the upper right hand side of the page.
Just click and follow the directions.  In this document, we will assume
that your github user name is ```user``` and that your forks just re-use
the names ```addons-source``` and ```addons``` (these names are not required,
but are simpler).

This can also be done from the command line with the
[```gh``` command](https://cli.github.com/).  First, authenticate with
github, then do the forks:
```
    $ gh auth login         # just follow instructions ....
    $ mkdir myaddon
    $ cd myaddon
    $ gh repo fork https://github.com/gramps-project/addons-source
    $ gh repo fork https://github.com/gramps-project/addons
```
You'll be asked if you wish to clone the fork.  It's not required
but if you respond ```yes``` it will save you a step later.  When
the forks are ready, you should be able to see them:
```
    $ gh repo list

    Showing 2 of 2 repositories in @user

    NAME                      DESCRIPTION           INFO          UPDATED
    user/addons               Contributed 3rd p...  public, fork  about 1 day ago
    user/addons-source        Contributed 3rd p...  public, fork  about 1 day ago
```

> #### NOTE: Git URIs
> Whilst we use the URI https://github.com/gramps-project/addons-source above,
> the URI git@github.com:gramps-project/addons-source.git points to exactly
> the same place, and accomplishes the same thing.  The former relies on HTTPS
> for security, and the latter relies on SSH.  In general, HTTPS is often used
> for read-only copies of repositories, or when networking precludes SSH usage;
> SSH however is usually more secure and less subject to man-in-the-middle
> attacks and thus often used when write access to repositories is needed.

### Set Up Addon Development Environment
Next, we need to download the addon source and its dependencies to build
up a development environment.  We will need copies of three repositories:
```addons-source```, ```addons``` and the main Gramps source ```gramps```.
All three of these local copies need to have the same root directory so
that the ```make.py``` script to be used later works properly.

To continue the examples above, assume our github user name is ```user```
and the root directory for development is called ```myaddon```.

#### Gramps Repository
In developing an addon, we will not need to change the upstream Gramps
source, but we will need access to it for the ```make.py``` packaging
script (described later) to work properly.  So, just clone a copy of
the current release branch.  With SSH:
```
    $ cd myaddon
    $ git clone -b maintenance/gramps60 git@github.com:gramps-project/gramps
```
Or with HTTPS:
```
    $ cd myaddon
    $ git clone -b maintenance/gramps60 https://github.com/gramps-project/gramps.git
```
The ```-b``` parameter tells ```git``` to checkout and clone from the named
branch.

#### Addons Repository
The addons repository will hold the package and packaging metadata
for the addon being written -- the ```myaddon.gpr.py``` registration file,
for example, and a compressed tarball of the addon itself.  Changes to
the upstream addons repository only happens via PRs and using the
```make.py``` script.

A recommended structure for your local repository is to have two
git remotes, one for upstream, and one for your addon work.  If the
```gh repo fork``` command was used and it cloned for you, this has
already been done.  You can see this with:
```
    $ cd myaddon
    $ cd addons
    $ git remote -v
    origin	git@github.com:user/addons.git (fetch)
    origin	git@github.com:user/addons.git (push)
    upstream	git@github.com:gramps-project/addons.git (fetch)
    upstream	git@github.com:gramps-project/addons.git (push)
```
where ```origin``` is your fork of the upstream repository, and
```upstream``` is the original source.

If just a fork was made, either on github or some other location,
an upstream remote should be added:
```
    $ cd myaddon
    $ cd addons
    $ git remote -v
    origin	git@github.com:user/addons.git (fetch)
    origin	git@github.com:user/addons.git (push)
    $ git remote add upstream git@github.com:gramps-project/addons.git
    $ git pull -a
    $ git remote -v
    origin	git@github.com:user/addons.git (fetch)
    origin	git@github.com:user/addons.git (push)
    upstream	git@github.com:gramps-project/addons.git (fetch)
    upstream	git@github.com:gramps-project/addons.git (push)
```

If not using github, setup is a little different:
```
    $ cd myaddon
    $ mkdir addons
    $ cd addons
    # git init
    $ git remote add upstream git@github.com:gramps-project/addons.git
    $ git pull -a
    $ git remote -v
    origin	<your-git-repository> (fetch)
    origin	<your-git-repository> (push)
    upstream	git@github.com:gramps-project/addons.git (fetch)
    upstream	git@github.com:gramps-project/addons.git (push)
    $ git push origin --all
```

In all cases, cloning will check out the default branch to start.  However,
we will not change these branches so we can always refer back to the
original upstream source.

#### Addons Source Repository
The addons-source repository will hold your addon source code.
Changes to the upstream addons-source repository will only happen
via PRs, and only in the current maintenance branch (e.g.,
```maintenance/gramps60```).  All of your work will be in your
github fork of the addons source repository.

We recommend the same structure for your local repository as above
for the addons tree:  two git remotes, one for upstream, and one for
your addon source.  If the ```gh repo fork``` command was used and it cloned
for you, this has already been done.  You can see this with:
```
    $ cd myaddon
    $ cd addons-source
    $ git remote -v
    origin	git@github.com:user/addons-source.git (fetch)
    origin	git@github.com:user/addons-source.git (push)
    upstream	git@github.com:gramps-project/addons-source.git (fetch)
    upstream	git@github.com:gramps-project/addons-source.git (push)
```
where ```origin``` is your fork of the upstream repository, and
```upstream``` is the original source.

If just a fork was made, either on github or some other location,
the upstream remote will have to be added:
```
    $ cd myaddon
    $ cd addons-source
    $ git remote -v
    origin	git@github.com:user/addons-source.git (fetch)
    origin	git@github.com:user/addons-source.git (push)
    $ git remote add upstream git@github.com:gramps-project/addons-source.git
    $ git pull -a
    $ git remote -v
    origin	git@github.com:user/addons-source.git (fetch)
    origin	git@github.com:user/addons-source.git (push)
    upstream	git@github.com:gramps-project/addons-source.git (fetch)
    upstream	git@github.com:gramps-project/addons-source.git (push)
```

If not using github, setup is a little different:
```
    $ cd myaddon
    $ git clone <your-git-repository> addons-source
    $ cd addons-source
    $ git remote add upstream git@github.com:gramps-project/addons-source.git
    $ git pull -a
    $ git remote -v
    origin	<your-git-repository> (fetch)
    origin	<your-git-repository> (push)
    upstream	git@github.com:gramps-project/addons-source.git (fetch)
    upstream	git@github.com:gramps-project/addons-source.git (push)
```

In all cases, cloning will check out the default branch to start.  However,
we will not change these branches so we can always refer back to the
original upstream source.

### Create Your Development Branch
Now that copies of all the necessary upstream code have been set up,
create the branches that will be used to save your addon and where all
of your work will occur:
```
    $ cd myaddon
    $ cd addons-source
    $ git checkout -b myaddon60 origin/maintenance/gramps60
    $ git push --set-upstream origin myaddon60
    $ cd ../addons
    $ git checkout -b myaddon60 origin/master
    $ git push --set-upstream origin myaddon60
```   
The checkout will create the branch and then set the current
branch to the one just checked out.  The push should be done
in order to define the repository for the branch, and to make
sure you have a good starting point.

> ### TIP
> You can create as many branches as you wish; they have minimal
> overhead.  Using them for experimentation is highly encouraged.
> If you end up with multiple addons, put each in a separate
> branch.  When doing maintenance on your addon, it can be useful
> to create a branch for each bug fix -- all of these simplify
> the PR process for everyone.

### Create Your Addon Subdirectory
Make a new directory in addons-source for your addon:
```
    $ cd myaddon
    $ cd addons-source
    $ git checkout myaddon60
    $ mkdir NewProjectName                     # camel case, please
```
This makes sure we're on the right branch (```myaddon60``` created
in the previous step), and then creates the new directory where your
addon development will occur, ```NewProjectName```.

### Follow the Development API
Create the two required files: ```NewProjectName.py``` that provides
the addon implementation, and ```NewProjectName.gpr.py``` that provides
the information to package the addon so that Gramps can load it and run it.

From this point on, just follow the development API for your specific class
of tool:
[report](https://gramps-project.org/wiki/index.php/Report-writing_tutorial),
view, or
[Gramplet](https://gramps-project.org/wiki/index.php/Gramplets_development).
Place all of your associated ```.py```, ```.glade```, and any other files
in your addon-source directory. For general information on Gramps development,
see
[Portal:Development](https://gramps-project.org/wiki/index.php/Portal:Developers) and
[Writing a Plugin](https://gramps-project.org/wiki/index.php/Writing_a_Plugin)
specifically.


### Test Your Addon As You Develop
To test your addon as you develop, we recommend you copy your
```NewProjectName``` plugin into your Gramps user plugin directory
from your addon development directory, prior to testing.  Or, just
edit in the Gramps user plugin directory until it is ready to publish,
then copy back to your addon development directory.  Your installed Gramps
desktop application will search this folder (and subdirectories) for
any ```.gpr.py``` files, and add them to the plugin list.

You can of course still use the ```git``` branch for your addon to store
intermediate steps and other work in progress.

> #### Warning
> [Bug #10436](https://gramps-project.org/bugs/view.php?id=10436)
> Symbolic links to folders in the gramps plugin directory are not scanned, so
> you cannot just create a symbolic link pointing to your addon source tree;
> you will have to copy it.

If you have code that you want to share between addons, you don't need
to do anything special. Gramps adds each directory in which a ```.gpr.py```
is found onto the ```PYTHONPATH``` which is searched when you perform an
import. Thus ```import NewProjectName``` will work from other addons. You
should always make sure you name your addons with a name appropriate for
Python imports.

### Addon Configuration
Some addons may want to have persistent data (data settings that remain
between sessions). You can handle this yourself, or you can use Gramps'
builtin configure system. 

At the top of the source file for your addon, you would do this:
```
    from config import config as configman
    config = configman.register_manager("grampletname")
    # register the values to save:
    config.register("section.option-name1", value1)
    config.register("section.option-name2", value2)
    ...
    # load an existing file, if one:
    config.load()
    # save it, it case it didn't exist:
    config.save()
```

This will create the file ```grampletname.ini``` and put it in the same
directory as the addon. If the config file already exists, it remains intact.
The natural location for ```.ini``` files is in the directory in which
the addon is installed; using the main ```gramps.ini``` file for addon
preferences could potentially lead to a conflict between addons. Other
locations and file formats are possible.  See
[The Gramps architect recommends leaving this decision to the addon developer](https://gramps.discourse.group/t/add-option-for-boolean-options-in-gramplet/6371/19).

In the addon, you can then:
```
    x = config.get("section.option-name1")
    config.set("section.option-name1", 3)
```

and when this code is exiting, you might want to save the config. In a
Gramplet that would be:
```
     def on_save(self):
         config.save()
```

If your code is a system-level file, then you might want to save the
config in the Gramps system folder:
```
    config = configman.register_manager("system", use_config_path=True)
```

This is rare; most ```.ini``` files go into the plugins directory.

In other code that might use this config file, you would do this:
```
    from config import config as configman
    config = configman.get_manager("grampletname")
    x = config.get("section.option-name1")
```

### Localization

> #### Note
> These instructions will only work for Python strings. If you have a
> glade file, it will not get translated.

For general help with translations for Gramps, see
[Coding for translation](https://gramps-project.org/wiki/index.php/Coding_for_translation). However, that will only use translations that come with Gramps,
or allow you to contribute translations to the Gramps core. To have your own
managed translations that will be packaged with your addon, you will need to
add a way to retrieve the translation. Add the following to the top of your
```NewProjectName.py``` file:
```
    from gramps.gen.const import GRAMPS_LOCALE as glocale
        = glocale.get_addon_translator(__file__).gettext
```
Then you can use the standard "```_()```" function to translate phrases in
your addon. 

You can use one of a few different types of translation functions:
```
    gettext
    lgettext
    ngettext
    lngettext
    sgettext
```

These are obsolete starting in Gramps 4.x; ```gettext```, ```ngettext```, and
```sgettext``` always return translated strings in Unicode for consistent
portability between Python2 and Python3.

See the [Python documentation](http://docs.python.org/3/library/gettext.html#the-gnutranslations-class) for using ```gettext``` and ```ngettext```. The
"l" versions return the string encoded according to the
[currently set locale](http://docs.python.org/3/library/locale.html#locale.setlocale);
the "u" versions return Unicode strings in Python2 and are no longer available
in Python3.

The method ```sgettext``` should always be used; it is a Gramps extension
that filters out clarifying comments for translators, such as in
```_("Remaining names | rest")``` where "rest" is the English string that
we want to present and "Remaining names" is a hint for translators.

### Files Included in Addon Distribution
The process that creates the compressed tar file that the Gramps Download
Manager installs in Gramps to use your addon automatically includes the
following files:
```
    *.py
    *.glade
    *.xml
    *.txt
    locale/*/LC_MESSAGES/*.mo
```
Starting with Gramp 5.0, if you have files other than those listed above,
you should create a ```MANIFEST``` file in the root of your addon folder
that lists the files (or pattern) to be added, one per line, like this
sample ```MANIFEST``` file: 
```
    README.md
    extra_dir/*
    help_files/docs/help.html
```

> #### TIP
> Starting with Gramps 6.0 (and _only_ 6.0) translations can be done on
> [Weblate](https://weblate.org). Initial testing has appeared successful,
> but please let us know if you notice any problems. The Weblate Addons
> component contains aggregated translations for every addon.
>
> See <https://hosted.weblate.org/projects/gramps-project/addons/>

## Create a Gramps Plugin Registration file
First, create the ```NewProjectName.gpr.py``` file. The registration file
takes this general form:
```
    register(PTYPE,
         gramps_target_version = "6.0",
         version = "1.0.0",
         ATTR = value,
    )
```
[PTYPE](https://github.com/gramps-project/gramps/blob/master/gramps/gen/plug/_pluginreg.py#L76) values include:
TOOL, GRAMPLET, REPORT, QUICKVIEW (formerly QUICKREPORT), IMPORT, EXPORT,
DOCGEN, GENERAL, MAPSERVICE, VIEW, RELCALC, SIDEBAR, DATABASE, RULE,
THUMBNAILER, and CITE.

ATTR depends on the PTYPE.

You must include a ```gramps_target_version``` and addon ```version``` values.
```gramps_target_version``` should be a string of the form "X.Y" matching
a Gramps X (major) and Y (minor) version.  ```version``` is a string of
the form "X.Y.Z" representing the version of your addon; X, Y, and Z should
all be integers.

Be sure to include attributes for author name(s) and email(s) in the form
of an array of comma-separated strings. 

There is an additional set of attributes, ```maintainers``` and
```maintainers_email``` (new in Gramps 5.2). If you, the author, are also
the maintainer it will be identical to the author attributes, but you may
also designate a maintainer, in which case the maintainer will become the
primary point of contact.

Here is a sample Tool GPR file:
```
    register(TOOL, 
             id    = 'AttachSource',
             name  = _("Attach Source"),
             description =  _("Attaches a shared source to multiple objects."),
             version = '1.0.0',
             gramps_target_version = '6.0',
             status = STABLE,
             fname = 'AttachSourceTool.py',
             authors = ["Douglas S. Blank"],
             authors_email = ["doug.blank@gmail.com"],
             maintainers = ["Douglas S. Blank"],
             maintainers_email = ["doug.blank@gmail.com"],
             category = TOOL_DBPROC,
             toolclass = 'AttachSourceWindow',
             optionclass = 'AttachSourceOptions',
             tool_modes = [TOOL_MODE_GUI],
             help_url = "Addon:AttachSourceTool"
    )
```

You can see examples of the kinds of addons
[here](https://github.com/gramps-project/gramps/plugins) (such as
[gramps-project/gramps/plugins/drawreport/drawplugins.gpr.py](https://github.com/gramps-project/gramps/plugins/drawreport/drawplugins.gpr.py))
and see the full documentation in the
[master/gramps/gen/plug/_pluginreg.py][https://github.com/gramps-project/gramps/blob/3f0db9303f29811b43325c30149c8844c7ce24b6/gramps/gen/plug/_pluginreg.py#L23)
comments and docstrings.

Note that this example ```.gpr.py``` will automatically use translations
if you have them (see [Localization](#localization)). That is, the
function "_" is predefined to use your
locale translations; you only need to mark the text with ```_("TEXT")```
and include a translation of "TEXT" in your translation file. For example,
in the above example, ```_("Attach Source")``` is marked for translation.
If you have developed and packaged your addon with translation support,
then that phrase will be converted into the user's language.

### Report Plugins
The possible report categories are
[gramps/gen/plug/_pluginreg.py](https://github.com/gramps-project/gramps/blob/892fc270592095192947097d22a72834d5c70447/gramps/gen/plug/_pluginreg.py#L141-L149):
```
    #possible report categories
    CATEGORY_TEXT       = 0
    CATEGORY_DRAW       = 1
    CATEGORY_CODE       = 2
    CATEGORY_WEB        = 3
    CATEGORY_BOOK       = 4
    CATEGORY_GRAPHVIZ   = 5
    CATEGORY_TREE       = 6
    REPORT_CAT          = [ CATEGORY_TEXT, CATEGORY_DRAW, CATEGORY_CODE,
                            CATEGORY_WEB, CATEGORY_BOOK, CATEGORY_GRAPHVIZ, CATEGORY_TREE]
```

Each report category has a set of standards and an interface. The categories
```CATEGORY_TEXT``` and ```CATEGORY_DRAW``` use the Document interface of
Gramps. See also
[Report API](https://gramps-project.org/wiki/index.php/Report_API)
for a draft view on this.

The application programming interface or API for reports is treated in the
[report writing tutorial](https://gramps-project.org/wiki/index.php/Report-writing_tutorial).  For general information on Gramps development, see
[Portal:Developers](https://gramps-project.org/wiki/index.php/Portal:Developers)
and [Writing a Plugin](https://gramps-project.org/wiki/index.php/Writing_a_plugin).

### General Plugins
The plugin framework also allows you to create generic plugins for use.
This includes the ability to create libraries of functions, and plugins
of your own design.

#### Example: A library of functions
In this example, a file named ```library.py``` will be imported at the
time of registration (i.e., any time Gramps starts):
```
    # file: library.gpr.py

    register(GENERAL, 
       id    = 'My Library',
       name  = _("My Library"),
       description =  _("Provides a library for doing something."),
       version = '1.0',
       gramps_target_version = '6.0',
       status = STABLE,
       fname = 'library.py',
       load_on_reg = True,
    )
```

You can access the loaded module in other code by issuing an
```import library``` as Python keeps track of files already
imported. However, the amount of useful code that you can run
when the program is imported is limited. You might like to have
the code do something that requires a ```dbstate``` or ```uistate object```,
but neither of these is available when just importing a file.

If ```load_on_reg``` was not ```True```, this code would be unavailable
until manually loaded. There is no mechanism in Gramps to load ```GENERAL```
plugins automatically.

In addition to importing a file at startup, you can also run a single
function inside a ```GENERAL``` plugin, and it will be passed the
```dbstate```, the ```uistate```, and the plugin data. The function
must be called ```load_on_reg```, and take those three parameters:
```
    # file: library.py

    def load_on_reg(dbstate, uistate, plugin):
        """
        Runs when plugin is registered.
        """
        print("Hello World!")
```

Here, you could connect signals to the ```dbstate```, open windows, etc.

Another example of what you can do with the plugin interface is to create
a general purpose plugin framework for use by other plugins. Here is the
basis for a plugin system that:

* allows plugins to list data files
* allows the plugin to process all of the data files

First, the ```gpr.py``` file:
```
    register(GENERAL, 
      id    = "ID",
      category = "CATEGORY",
      load_on_reg = True,
      process = "FUNCTION_NAME",
    )
```

This example uses three new features:

* ```GENERAL``` plugins can have a category
* ```GENERAL``` plugins can have a load_on_reg function that returns data
* ```GENERAL``` plugins can have a function (called ```process```) which
will process the data

If you (or someone else) create additional general plugins of this category,
and they follow your ```load_on_reg``` data format API, then they could be
used just like your original data. For example, here is an additional
general plugin in the ```WEBSTUFF``` category:
```
    # anew.gpr.py

    register(GENERAL, 
      id    = 'a new plugin',
      category = "WEBSTUFF",
      version = '1.0',
      gramps_target_version = '6.0',
      data = ["a", "b", "c"],
    )
```

This doesn't have ```load_on_reg = True```, nor does it have an ```fname``` or
```process```, but it does set the data directly in the ```.gpr.py``` file.
Then, we have the following results:
```
     >>> from gui.pluginmanager import GuiPluginManager
     >>> PLUGMAN = GuiPluginManager.get_instance()
     >>> PLUGMAN.get_plugin_data('WEBSTUFF')
     ["a", "b", "c", "Stylesheet.css", "Another.css"]
     >>> PLUGMAN.process_plugin_data('WEBSTUFF')
     ["A", "B", "C", "STYLESHEET.CSS", "ANOTHER.CSS"]
```

### Registered GENERAL Categories
The following are examples of the published secondary plugin categories of
APIs of type ```GENERAL```.

#### WEBSTUFF
A sample ```gpr.py``` file:
```
    # stylesheet.gpr.py

    register(GENERAL, 
      id    = 'system stylesheets',
      category = "WEBSTUFF",
      name  = _("CSS Stylesheets"),
      description =  _("Provides a collection of stylesheets for the web"),
      version = '1.0',
      gramps_target_version = '6.0',
      fname = "stylesheet.py",
      load_on_reg = True,
      process = "process_list",
    )
```

Here is the associated program:
```
    # file: stylesheet.py

    def load_on_reg(dbstate, uistate, plugin):
        """
        Runs when plugin is registered.
        """
        return ["Stylesheet.css", "Another.css"]

    def process_list(files):
        return [file.upper() for file in files]
```

#### Filters
For example, ```gpr.py```:
```
    register(GENERAL,
       category="Filters",
       ...
       load_on_reg = True
    )
```
And the actual plugin:
```
    def load_on_reg(dbstate, uistate, plugin):
        # returns a function that takes a namespace, 'Person', 'Family', etc.

        def filters(namespace):
            print("Ok...", plugin.category, namespace, uistate)
            # return a Filter object here

        return filters
```

### List Your Addon Prerequistes
In your ```.gpr.py``` file, you can have a line like:
```
    ...
    depends_on = ["libwebconnect"],
    ...
```

which is a list of plug-in identifiers from other ```.gpr.py``` files.
This example will ensure that
[libwebconnect](https://gramps-project.org/wiki/index.php/Addon:Web_Connect_Pack#Prerequisites)
is loaded before your addon. If that ID can't be found, or you have a cycle
(a circular import), then your addons won't be loaded. The Gramps architect
summarizes this as: "The ```depends_on``` list is used to specify other plugins
which the plugin depends on. These will be installed automatically."

Example code in the Addon:Web_Connect_Pack that references ```libwebconnect```
prerequistes can be seen in
[addons-source/RUWebPack.gpr.py#L17](https://github.com/gramps-project/addons-source/blob/1304b65a7d758bfe17339c26260473ac3e9c4061/RUWebConnectPack/RUWebPack.gpr.py#L17).

This allows common prerequisites to be shared between addons. Code can be
maintained in its own ```.gpr.py```/addon file instead of trying to
synchronize the maintenance of multiple copies across various silos.

Additional requirements properties were implemented starting with the 
Gramps 5.2 
[Registration Options](https://gramps-project.org/wiki/index.php/Gramplets_development#Register_Options) that provide for specifying plug-in preqrequisites:

* For modules: [```requires_mod```](https://github.com/gramps-project/gramps/blob/0f8d4ecd429431b4df64910962f8764af9ff1766/gramps/gen/plug/_pluginreg.py#L689-L719)
* For GObject introspection: [```requires_gi```](https://github.com/gramps-project/gramps/blob/0f8d4ecd429431b4df64910962f8764af9ff1766/gramps/gen/plug/_pluginreg.py#L689-L719)
* For executables: [```requires_exe```](https://github.com/gramps-project/gramps/blob/0f8d4ecd429431b4df64910962f8764af9ff1766/gramps/gen/plug/_pluginreg.py#L689-L719)

## Review the Addon Checklist
Before you publish your new addon, review this checklist for completeness:

* Is it a good addon name and description?
* Is it in the right tool, report, rule, view, gramplet category?
* Does it need translatable strings marked?
* Does it need a different location for config files?
* Has a wiki page been generated?
* Has the <tt>help_url</tt> been changed from the GitHub repository to the
wiki page?

## Create a Pull Request
Once you have created your addon, built the ```.gpr.py``` registration
file, and have tested it (you *did* test it, right?) so that you're sure
it works well, you next need to submit a Github Pull Request (PR).

If you are already familiar with github and PRs, you can probably
skip this section.

There is a script called ```make.py``` that can help with some of
these tasks; examples of usage will be given below, along with examples
for the command line utility ```gh```, and the github web interface,
where appropriate.

### Commit Your Changes
To begin with, make sure you're in the right local git repository, and
on the right branch (all created earlier); you should be able to see
something like this:
```
    $ cd myaddon
    $ cd addons-source
    $ git ls-remote --get-url
    git@github.com:user/addons-source.git
    $ git status
    On branch workflow60
    Your branch is up to date with 'origin/workflow60'.

    nothing to commit, working tree clean
```
where ```user``` is your github user name, your fork was also
called ```addons-source```, and ```workflow60``` is the branch we created
earlier to store the new addon.  The key point is you want to put your changes
into _your_ fork, _not_ the upstream ```gramps-project/addons-source```
repository.

Next, commit your changes to your local repository; the ```git status```
command will show you what changes it has and has not been told about.

If using the ```make.py``` command, remove the files that should not be
added to github using the ```clean``` command (e.g., ```template.pot/```,
```locale```, etc.):
```
    $ cd myaddon
    $ cd addons-source
    $ ./make.py gramps60 clean NewProjectName
```

If you choose to do the same thing manually:
```
    $ cd myaddon
    $ cd addons-source
    $ git checkout myaddon60
    $ cd NewProjectName
    $ rm -i *~ po/*~ po/*-global.po po/*-temp.po po/??.po po/????.po
    $ rm -i *.pyc *.pyo
    $ rm -ir locale
```

Now add the project code to your local repository (this adds _all_ files
in that directory):
```
    $ git add NewProjectName
```

Commit it with an appropriate message
```
    $ git commit -m "A message describing what this addon does"
```

You should now be able to see your commit in the local log:
```
    $ git log
```

> #### TIP
> A ```.gitignore``` file in the ```NewProjectName``` addon directory
> (or any directory) can be created, added and commited to your repository.
> The regular expression patterns in this file tell ```git``` that files
> matching the patterns are not important and can be ignored.  For example,
> the pattern ```locale/*``` would mean never having to worry about accidentally
> adding or committing any of those files.

All of these commands operate on your local repository only; there is
no need to use ```gh``` or the github web interface.  

### Verify Your Addon Is Current
Before you push your changes into your github fork (the ```origin``` remote
repository), make sure the changes can actually be merged into the
upstream ```addons-source``` project.

* Sync your fork to the upstream source to incorporate all the latest
upstream changes into your remote repository on github; with the github
web interface, this means pushing a button at the top of the "Code" page
labeled "Sync fork".  Or, via command line:
```
    $ gh repo set-default user/addons-source
    $ gh repo sync
```
* Rebase the changes for your addon, just in case something
happened upstream that affects your code; assuming the same example
we've been using:
```
    $ git checkout myaddon60
    $ git pull --rebase
```
* Use ```git status``` to make sure you haven't missed any files.

Correcting problems when rebasing or merging is a complicated topic.
If there are problems, you'll have to fix those before going any further (the
```git pull --rebase``` will complain). Typically this
a problem when maintaining an addon with multiple contributors
working on the same branch at the same time; ```git mergetool```
and ```git revert``` or ```git rebase --abort``` will be your friends
here, along with learning more about ```git``` than we can cover.  And of
course, make sure to add and commit and rebase again, if you do make changes.

### Push To Your Fork
To now make your new addon visible to the world, push it to your
fork in github:
```
    $ cd myaddon
    $ cd addons-source
    $ git checkout myaddon60
    $ git push
```
If for some reason you get a message like this:
```
    fatal: The current branch myaddon60 has no upstream branch.
    To push the current branch and set the remote as upstream, use

        git push --set-upstream origin myaddon60

    To have this happen automatically for branches without a tracking
    upstream, see 'push.autoSetupRemote' in 'git help config'.
```
It means that the branch was not pushed as recommended in
[Create Your Development Branch](#create-your-development-branch).
Simply enough, just use the push command shown in the message.

Your addon is now visible in your fork of the ```addons-source```
repository on github.

### Create the PR
Github will usually give you a hint on how to create the PR when you
do the push:
```
    $ git push
    Total 0 (delta 0), reused 0 (delta 0), pack-reused 0 (from 0)
    remote: 
    remote: Create a pull request for 'myaddon60' on GitHub by visiting:
    remote:      https://github.com/user/addons-source/pull/new/myaddon60
    remote: 
```
If you know where the "Code" page is on your repository fork, go
to the "Pull requests" tab, then click on "New pull request" -- which
takes you to the URL shown above.  Fill in a good description of what
the addon does and how it helps and then submit the PR.

> ### NOTE
> Draft PRs can be very handy for changes like RFCs (Request For Comments)
> where you've got questions about your addon's utility, future directions
> for the project, or if you need advice on structuring your addon properly.
> Marking a PR as a draft tells the maintainer that this is a test of your
> idea and may not be it's final form.

When using the command line, submit the PR this way:
```
    $ cd myaddon
    $ cd addons-source
    $ git checkout myaddon60
    $ gh repo set-default user/addons-source
    $ gh pr create --title "One line title for your addon" \ 
          --body "description of what the addon does"
```

### Work Towards a Merge
With the PR created, it's now a matter of working with the ```addons-source```
maintainers.  Suggestions and corrections will be made and it may be mecessary
to modify the original submission to get the addon accepted.

The key thing is to monitor progress and comments.  Your PR will have an
ID number -- 1234, for example -- so you can always go to the github web
page for it:
```
    https://github.com/gramps-project/addons-source/pull/1234
```
and follow the comments and discussion.  This can also be done via
the command line:
```
    $ cd myaddon
    $ cd addons-source
    $ git checkout myaddon60
    $ gh repo set-default user/addons-source
    $ gh pr view 1234
```
Respond to comments as soon as you can and as clearly as you can.  With
any luck, there will be a little clean up here and there, and then your
PR will get merged.  Once it has, it's time to let others know it exists,
if they don't already.

## Announce Your Addon
At some point after the PR gets merged, you should be able to do
a ```git pull``` of the ```maintenance/gramps60``` branch in
your ```addons-source``` repository and see your addon in the tree.

At the same time, the ```addons-source``` maintainer will have also
packaged up the addon and inserted the package into the ```addons```
repository (see the <tt>MAINTAINERS.md</tt> file in <tt>addons-source</tt> or
[Addons MAINTAINERS](https://gramps-project.org/wiki/index.php/Addons_MAINTAINERS)).  And again, a ```git pull``` from ```addons``` should
show your addon as a package.

Now it is time to announce your addon to those who may not have heard
about it yet.

### Gramps Forum
Join the [Gramps Forum](#https://gramps-project.org/wiki/index.php/Contact#Forum) if you have not already.  Announce your addon to forum users with general
information on why you created it, what it does for the user, and how to use
it.

### Gramps Wiki
Create an account on the
[Gramps Wiki](#https://gramps-project.org/wiki/index.php/Main_page)
if you don't already have one.

#### List Your Addon
Add a short description of your addon to the Addons list in the wiki by
editing the current release listing: i.e., 
[6.0_Addons](https://gramps-project.org/wiki/index.php/6.0_Addons),
or if the addon is meant for a future release,
[6.1_Addons](https://gramps-project.org/wiki/index.php/6.1_Addons)
when available.  Examine other addon entries when editing the wiki page,
and refer to the
[Addon list legend]]](https://gramps-project.org/wiki/index.php/Addon_list_legend)
list legend]] to understand the meaning of each column.  When ready, use the
following template to include your addon in the list:
```
|- <!-- Copy this section and list your Addon -->
|<!-- Plugin / Documentation -->
|<!-- Type -->
|<!-- Image -->
|<!-- Description -->
|<!-- Use -->
|<!-- Rating (out of 4) -->
|<!-- Contact -->
|<!-- Download -->
|-
```

#### Document Your Addon
Document your addon in the wiki using the page name format 
**Addon:NewProjectName**.  Examine some of the other addon documentaion
pages for suggestions, and for the general format to use.

> ##### TIP
> To create a new wiki page, use the search box to search for the name
> you would like to use. If that page doesn't exist, then on the search
> results page you will be provided with a link to create the new page.
> Select that link to add your content.

Consider including the following information in your wiki page:

```
<!-- Copy this section to your Addon support page-->
{{Third-party plugin}}  <!-- This is a mediawiki template that expands out
                         to display the standard addon message you see at
                         the top of each addon page-->

<!--add these sections if needed-->
== Usage ==

=== Configure Options ===

==Features==

== Prerequisites ==

== Issues ==

<!--default categories-->
[[Category:Addons]]
[[Category:Plugins]]
[[Category:Developers/General]]
```

## Support Your Addon Through Bug Tracker
Create a user account on the
[Gramps Mantis Bug Tracker (BT)](https://gramps-project.org/bugs/view_all_bug_page.php),
and please check it regularly.  There is no automated notification of issues
(or possible feature requests) related to your addon when reported by users. 

Users tend to not understand coding and they make assumptions. So be kind
and guiding if a report is ambiguous or inaccurate. A negative remark from
an addon developer or anyone can be very discouraging.

## Maintain Your Addon as Gramps Evolves

> #### TIP
> When submitting an update to the ```addons``` packaging repository,
> the patch part of the version number MAJOR.MINOR.PATCH in your ```.gpr.py```
> registration file is incremented during the addon build process
> (e.g., 1.1.3 to 1.1.4).  You can see this step in
> [addons-source/make.py](https://github.com/gramps-project/addons-source/blob/master/make.py#L125).
> Discussion of this feature can be found at
> [Should addons PR include version numbers](https://gramps.discourse.group/t/should-addons-pr-include-version-number-update/2591).

Remember that Gramps addons exist for many reasons and there are many
Gramps developers that support their addons in various ways -- translations,
triage, keeping in sync with master, download infrastructure, and so on.

Here are just some of the reasons addons exist; they provide:

* A quick way for anyone to share their work; the Gramps project has
never denied adding a addon.
* A method to continuously update and develop a stand-alone component,
often before being officially accepted.
* A place for controversial plugins that will never be accepted into
core, but are loved by many users (e.g., the Data Entry Gramplet).
* A place for experimental components to live.

### Examples of Common Enhancements
And here are just some of the kinds of enhancements that might make sense:

* Copy all the Gramplet's output to a system clipboard via context
pop-up menu:
    * Enhancement Request [bug #11573](https://gramps-project.org/bugs/view.php?id=11573)
    * Resulting [Pull Request](https://github.com/gramps-project/gramps/pull/1014/commits/72012e13b4ca15caca4b7f36fdb9702c1fd470fd)
* Add a custom
[View Mode](https://gramps-project.org/wiki/index.php/Gramps_Glossary#viewmode)
toolbar icon via the <tt>.gpr.py</tt>:
    * Discussion for [Pull Request 1017](https://github.com/gramps-project/gramps/pull/1017)
    * Resulting [Pull Request](https://github.com/gramps-project/gramps/pull/1017/commits/76e41d546d6ec519dd78fbe07f663135b5c79351)

### Change Code, Submit PR
Enhancements are added to ```addons-source``` the same way as the original
addon: create a Pull Request with the changes.  We recommend putting each
enhancement (or bug fix) on a different branch of your local repository.
This isolates the changes to be reviewed to only what has actually changed,
making them easier to review.

Before committing additional changes to your addon, you should run through
a simple checklist again:

* Make sure that outside changes do not affect your commit:
<tt>git pull --rebase</tt>
* Verify only the files you changed are in this list: <tt>git status</tt>
* Commit the changes with an appropriate message describing _why_ the
change was made: <tt>git commit -m "A message describing the changes"</tt>

Then, submit another PR just like before.

<!-- I recommend removing this part completely; it is far too easy to have far
     too many maintainers, and ending up in some sort of mess.

If you have been given 'push' rights to GitHub 'gramps-project/addons-source', and when you are sure you are done and want to publish to the repository:

* to make sure that outside changes do not affect your commit
: <code>git pull --rebase</code>
: <code>git push origin gramps60</code>

Also you may want to [[Addons_development#Package_your_addon |Package your addon]] so it can be downloaded via the plugin manager.
-->

## Resources
* [Brief introduction to Git](https://gramps-project.org/wiki/index.php/Brief_introduction_to_git)
* [Getting started with Gramps development](https://gramps-project.org/wiki/index.php/Getting_started_with_Gramps_development)
* [Portal:Developers](https://gramps-project.org/wiki/index.php/Portal:Developers)
* [Registration module (Python source)](https://gramps-project.org/docs/gen/gen_plug.html?highlight=include_in_listing#module-gramps.gen.plug._pluginreg gramps.gen.plug._pluginreg)
* [PluginData in _pluginreg.py](https://github.com/gramps-project/gramps/blob/master/gramps/gen/plug/_pluginreg.py#L55)
* Gramps Addons site for Gramps 4.2 and newer
    * <https://github.com/gramps-project/addons-source>  - Source code (Git)
    * <https://github.com/gramps-project/addons> - downloadable .tgz files
* Gramps Addons site for Gramps 4.1 and older
    * For 4.1.x and earlier, see [Addons development old](https://gramps-project.org/wiki/index.php/Addons_development_old).

## Addon Development Tutorials and Samples
* [Develop an Addon Gramplet](https://gramps-project.org/wiki/index.php/Gramplets_development) (or add a [custom filtering option](https://gramps.discourse.group/t/looking-for-an-example-of-a-gramplet-with-a-custom-filter-configuration-option/5967))
* [Develop_an_Addon_Rule](https://gramps-project.org/wiki/index.php/Develop_an_Addon_Rule) for custom filters
* [Develop_an_Addon_Tool](https://gramps-project.org/wiki/index.php/Develop_an_Addon_Tool)
* [Develop an Addon Quick_View](https://gramps-project.org/wiki/index.php/Quick_Views)
* Develop an Addon Report ([tutorial](https://gramps-project.org/wiki/index.php/Report-writing_tutorial),
[samples](https://gramps.discourse.group/t/sample-report-for-new-developers/3046))
* [Adapt_a_builtin_Report](https://gramps-project.org/wiki/index.php/Adapt_a_builtin_Report)

## Addons External to Github

To Be Written.

