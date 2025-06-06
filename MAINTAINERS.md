# MAINTAINERS
If you are just writing an addon to contribute, this document adds some
context to what comprises an addon _package_.  However, these are **not**
tasks you will need to do.  The tasks described here apply to the
```addons``` repository primarily, and not so much to the ```addons-source```
repository, even though they are tightly connected to one another.

We assume you are familiar with Gramps addons, git, github, and ```gh```,
the [github CLI](https://cli.github.com).

> #### NOTE
> These instructions and the ```make.py``` script have been built to
> operate in a Linux development environment.  They will work on macOS
> with a few adjustments (see examples below).  They have not been tested
> to see if they work on Windows.

## PR Review and Approval
PR (Pull Request) submissions in the ```addons-source``` repository drive
the maintenance tasks in ```addons```.  The only PR submissions to ```addons``` should be the ones you make as the maintainer.

PRs to ```addons-source``` need to be reviewed periodically.  The goal is
to make sure that useful changes don't end up sitting too long before
being merged.  Pay close attention to changes that could impact security
and quality.  Make sure that the PR is only changing what it must, and
has been submitted against the proper branch.  Then, comment on the PR
if necessary, or merge it if ready, having allowed sufficient time for
it to be reviewed.

PRs that continue for a long time as draft or WIP may need to be closed
at some point, or the submitter pinged for progress reports.  When to
do this is a judgement call since not everyone works at the same speed,
but it will also not be done without consulting the author.

All of the above can be done via the github web interface, or via the
command line using the [```gh``` tool](https://cli.github.com).  For
example, to see the current list of open PRs:
```
$ gh pr list

Showing 13 of 13 open pull requests in gramps-project/addons-source

ID    TITLE                          BRANCH                   CREATED AT        
#733  Translations update from H...  weblate:weblate-gram...  about 6 days ago
#668  Gram.py Refinements            dsb/grampy-refinements   about 2 months ago
#614  created GraphView italian ...  SebastianoPistore:gr...  about 7 months ago
#558  small fix to name all data...  loisspitz:translate_...  about 2 years ago
#540  fix: recast list to tuple ...  cdhorn:maintenance/g...  about 2 years ago
#522  [MediaReport] Allow all ou...  Mattkmmr:media-repor...  about 3 years ago
#477  [GraphView] rewrite theme ...  vantu5z:graphview_pe...  about 4 years ago
#473  Introduce the new Geneanet...  bcornec:master           about 4 years ago
#285  [MediaReport]: New image D...  Mattkmmr:update-medi...  about 5 years ago
#267  Form Gramplet: per Form, p...  stevenyoungs:form_ac...  about 5 years ago
#232  [GraphView] Add drag and d...  vantu5z:graphview_dr...  about 5 years ago
#214  GEPS045 update addons for ...  places                   about 5 years ago
#140  [Uncollected Objects]Updat...  leakv2                   about 7 years ago
```
Or, to view the details of a PR:
```
$ gh pr view 668
Gram.py Refinements gramps-project/addons-source#668
Draft • dsblank wants to merge 1 commit into maintenance/gramps60 from dsb/grampy-refinements • about 2 months ago
+27 -1 • No checks
Assignees: dsblank


  WIP:                                                                        
                                                                              
  Updating some items based on feedback from discourse.                       
                                                                              
  1. Be able to iter over NoneData                                            
  2. added references                                                         
  3. added back_references                                                    
  4. added back_references_recursively                                        


View this pull request on GitHub: https://github.com/gramps-project/addons-source/pull/668
```

At some point, there will be sufficient review and testing to merge the
PR -- again, a judgement call will need to be made.  It is this merge
that triggers most tasks in the ```addons``` repository.  For each addon
modified by the merge, the package for it will need to be rebuilt and
submitted as a PR to the ```addons``` repository.

Please go through this brief checklist before merging PRs into the
maintenance branch in ```addons-source```:

* Has the PR been reviewed enough?
* Have the changes in the PR been tested?
* Is the PR targeting the proper maintenance branch?
* Will the merge succeed (github does check this for you)?
* For new addons:
  * Have wiki pages been added describing it?  If they have not, wait to
    do the merge until they have been.
  * Review the ```.gpr.py``` carefully:
    * Is it a good AddOn name and description?
    * Is it in the right tool, report, rule, view or gramplet category?
    * Has the ```help_url``` been changed from the github repository to
      the wiki page?
  * Does it need translatable strings marked?
  * Does it need a different location for config files?
* For changes to existing addons, do they clearly state what they fix or
  add?  Have changes been made to the wiki pages to document that?
* If this is a bug fix, does the PR state which bug?
* Which addons have changed and will need to be repackaged?

<!--
Would it help to have workflows on github to send periodic reminders to
PR submitters that their PR still needs work?  I'm pretty sure this is
possible.  Further, would it be useful to automatically close or delete
PRs that have been around too long?  If so, how long is too long?  PR#140
is seven years old, for example.

One thought would be to send monthly reminder to PR authors; if there has
been NO activity for more than six months, send the PR author a note that
the PR will be closed without merging and can be re-opened if they still
need it.  I'm pretty sure this is possible but I'll have to dig a little
bit to figure out how to automate it.
-->

## Addons Repository Maintenance
The following are steps that only the ```addons``` repository maintainer
needs to complete once an addon has been submitted via PR, **and** the PR
has been approved, **and** the PR has been merged into a maintenance branch.
If you are _not_ managing this repository, you do not need to perform any
of these steps.

### Prerequisites
We recommend you use the ```make.py``` command found in the ```addons-source```
repository to do these tasks.  To do so, the command makes several assumptions:

* You have a work space set up on your system with a directory structure that
  looks like the following, with ```addons-source``` being where the addon
  sources are maintained, and ```make.py``` is kept, and ```addons``` are
  where we will be adding in the packaged form of the addons.
```
    .../my-workspace
           /gramps              => clone of your fork of the current upstream maintenance branch
           /addons              => clone of your fork of the current upstream maintenance branch
           /addons-source       => clone of your fork of the current upstream maintenance branch
```
* Gramps requires Python 3.9 or higher be installed.  If you have installed
  Gramps 6.0 or higher on your system already, then a sufficient version of
  Python should be present.
* The ```make.py``` used in construction of the addons requires that the
  ```LANGUAGE``` environment variable be set to ```en_US.UTF-8```. 
* The ```make.py``` used in construction of the addons requires that the
  ```GRAMPSPATH``` environment variable be set to your path to the Gramps
  source tree.
* ```intltool``` must be installed
  * for Debian-based systems: <code>sudo apt-get install intltool</code>
  * for Fedora-based systems: <code>sudo dnf install intltool</code>

For example, if your home directory is ```/home/user``` and you use the
suggested path names, use:
```
 GRAMPSPATH=/home/user/gramps LANGUAGE='en_US.UTF-8' python3 make.py ...
```
to replace the <code>./make.py</code> in the examples below.

> #### NOTE: Multiple Python Versions Installed
> If you have more than one version of Python installed, you must use the
> correct version for these scripts.  On some systems, both Python 2.x and
> 3.x are installed.  It is possible that the normal invocation of
> <code>python</code> starts up Python 2.x, and that to start up Python 3.x
> requires invoking <code>python3</code> or <code>python3.13</code>, etc.
> You can test the version by <code>python -–version</code> or 
> <code>python3 -–version</code>.  If the command <code>python</code>
> invokes Python 2.x, you will have to replace any usage of 'python' in
> the examples below with the appropriate invocation.

### Basic Steps
In general, for each addon that a PR merge has changed, these are the basic
steps needed:

1. Create (or update) translation information.
1. Verify the addon manifest, if present.
1. Create (or update) a downloadable package for the addon.
1. Create (or update) the listing information needed by the Gramps
   Addon Manager.
1. These steps will have created changes to the local ```addons``` repository.
   Commit them to the repository.
1. Push all the committed changes to your fork of the ```addons``` repository.
1. Create a PR for the commit just pushed to update the upstream tree.
1. Merge the PR to the upstream ```addons``` tree.

### Create/Update Translation Information
You will need the ```gramps.pot``` file that is currently being used for
Weblate translations in your local gramps 6.0 tree. It is used to exclude
strings from the addons translation component that have already been
translated in the core Program component. You can view the file here:
```
   https://github.com/gramps-project/gramps/blob/maintenance/gramps60/po/gramps.pot
```

The translation workflow using ```make.py``` is well automated: use the
''aggregate-pot'' command to collect all of the addon ```template.pot```
files into a single ```po/addons.pot``` file which is then used by Weblate
for translations. The ```GRAMPSPATH``` environment variable must be set to
a current gramps60 repository for this step. If run with no updates in any
```template.pot```, the resulting ```addons.pot``` file will only have a
timestamp update and does not need merged back.

In Linux environments, assuming a workspace created as above, the commands
would look something like this:
```
    $ cd my-workspace
    $ cd addons-source
    $ GRAMPSPATH="../gramps" python3 ./make.py gramps60 aggregate-pot
    $ GRAMPSPATH="../gramps" python3 ./make.py gramps60 extract-po
```
On macOS, the commands look similar:
```
    $ cd my-workspace
    $ cd addons-source
    $ DYLD_LIBRARY_PATH="path_to_local_gramps_installation" GRAMPSPATH="../gramps" \
             python3 ./make.py gramps60 aggregate-pot
    $ DYLD_LIBRARY_PATH="path_to_local_gramps_installation" GRAMPSPATH="../gramps" \
             python3 ./make.py gramps60 extract-po
```

The Weblate translators can now translate the strings. Weblate will in turn
generate a PR. These translation PRs can usually just be merged on a regular
basis. You can do this from the GitHub GUI, or using ```gh``` but **DO NOT
squash the commits**.  For example, suppose PR #1234 is a set of modifications
from Weblate:
```
    $ cd my-workspace
    $ cd addons-source
    $ gh pr merge 1234
```

The ```local.po``` files (which were updated by Weblate) then need to be
updated for publishing using the ```extract-po``` command in ```make.py```.
These updates should be merged back to the ```maintenance/gramps60``` branch
of the ```addons-source``` repository.  The commands would look like this:

In Linux environments:
```
    $ cd my-workspace
    $ cd addons-source
    $ GRAMPSPATH="../gramps" python3 ./make.py gramps60 extract-po
```
On macOS, the commands look similar:
```
    $ cd my-workspace
    $ cd addons-source
    $ DYLD_LIBRARY_PATH="path_to_local_gramps_installation" GRAMPSPATH="../gramps" \
             python3 ./make.py gramps60 extract-po
```

At this point, the translations are committed but not published. Since
publishing updates every addon, the timing for this action is dependent
on how many addons are being updated, and any sort of timing or logistical
concerns from the Gramps maintainers.

### Verify the MANIFEST
The addon developer may or may not have created a ```MANIIFEST``` file as
part of their work.  You shouldn't have to change it or create it if they
did, but you can at least run a simple check on the contents with
```make.py```.  Since this command will examine all ```MANIFEST``` files,
you should only need to do this when publishing an update:
```
    $ cd my-workspace
    $ cd addons-source
    $ GRAMPSPATH="../gramps" python3 ./make.py gramps60 manifest-check
```

Any errors found would then have to be added back into the
```addons-source``` repository as part of the branch being changed.

### Package Each Addon
For each addon that has been created or updated, we now need to create
the downloadable version of the addon.  In this case, it's a tarball
containing a specific set of files, and common enough an operation to
have a ```make.py``` command:
```
    $ cd my-workspace
    $ cd addons-source
    $ ./make.py gramps60 build SomeAddonName
```

If this addon is for a different upstream version of Gramps, use the proper
branch name; for example, for Gramps 5.2:
```
    $ ./make.py gramps52 build SomeAddOnName
```

Before going much further, perform a basic sanity check of the addon. Use
the compressed tarball created by the ```build``` command to manually
install the addon, start gramps from the console, and then test the addon.
If the addon fails to load, it might be the result of an error in the
MANIFEST, or a coding error. If the addon fails to work as described,
then the developer needs to fix the PR.

### List the Addon in the Gramps Plugin Manager

> #### WARNING: Gramps needs to have been built
> Make sure you have already built gramps from the gramps60 or master
> branches.  Change to the appropriate git branch in your gramps directory,
> and run <code>python3 setup.py build</code>  See
> [Linux:Build_from_source](https://gramps-project.org/wiki/index.php/Linux:Build_from_source) for further details.

We now need to provide information that will be needed by the Gramps
Plugin Manager to identify the addon -- the "listing" information
displayed by the Plugin Manager:
```
    $ cd my-workspace
    $ cd addons-source
    $ GRAMPSPATH=../gramps ./make.py gramps60 listing SomeAddOnName>
```

The ```make.py``` command is executed in the ```addons-source``` directory.
The listing files (```*.json```) are created or updated in the
```../addons/gramps60/listings``` directory (for gramps 6.0) -- this is
part of why we recommended the workspace structure that we have.

Always check the diff of one of the JSON files to be sure that the
command worked; only the version number should have changed. However,
there are some open issues with ```make.py``` where the JSON will get
corrupted. If this happens, then run <code>make.py listings all</code>
to regenerate them properly.

There will now be one or more files in the ```../addons/listings/```
directory that will need to be committed:
```
    $ cd ../addons
    $ git add gramps60/listings/*
    $ git commit -m "Added new plugin to listings: SomeAddOnName"
```

#### Example Addon Article 
Whilst you may have checked this before, now would be a good time to
double check that the AddOn Support page on the Gramps wiki has 
information about the addon being added.  Consider including the
following information:

<pre>
<!-- Copy this section to your Addon support page-->
{{Third-party plugin}}<!-- This is a mediawiki template that expands out to display the standard addon message you see at the top of each addon page-->

<!--sections only add if needed-->
== Usage ==

=== Configure Options ===

==Features==

== Prerequisites ==

== Issues ==

<!--default categories-->
[[Category:Addons]]
[[Category:Plugins]]
[[Category:Developers/General]]
</pre>

### Final Push
Having built all of the addons that have changed, and having committed
all of the results to the ```addon``` repository, make sure that they
all get pushed into the upstream repository.  If you have cloned the
```addons``` repository directly (NOT recommended, by the way),
<code>git push</code> is all that's needed.  This can make the git
history a little murky, though.  The preferred method is to push to
your fork of ```addons```, then create a PR to merge the changes.  You
can then do the merge in the upstream ```addons``` repository and 
provide some info in the merge message.  While this creates an additional
step, it provides a bit more history as to what changed.

## Resources
* [Brief_introduction_to_Git](https://gramps-project.org/wiki/index.php/Brief_introduction_to_Git)
* [Getting started with Gramps development](https://gramps-project.org/wiki/index.php/Getting_started_with_Gramps_development)
* [Portal:Developers](https://gramps-project.org/wiki/index.php/Portal:Developers)
* [Registration module (Python source)](https://gramps-project.org/docs/gen/gen_plug.html?highlight=include_in_listing#module-gramps.gen.plug._pluginreg gramps.gen.plug._pluginreg)
* [PluginData in _pluginreg.py](https://github.com/gramps-project/gramps/blob/master/gramps/gen/plug/_pluginreg.py#L55)

**Gramps Addons site for Gramps 4.2 and newer**

* <https://github.com/gramps-project/addons-source>  - Source code (Git)
* <https://github.com/gramps-project/addons>- downloadable .tgz files

**Gramps Addons site for Gramps 4.1 and older**

* For 4.1.x and earlier, see
  [Addons_development_old](https://gramps-project.org/wiki/index.php/Addons_development_old).

## Addons External to Github

To Be Written.

