Building instructions
Under Windows
Using Master branch
(for branches 4.0 and 4.1 see below, previous branches not supported)
Using python 3


- Install GrampsAIO4D

- Install git client
- Get gramps source tree from
    git://git.code.sf.net/p/gramps/source
    Branch "master"

- Install tortoiseSVN client
Option 1
- Create gramps-addons directory in the gramps source tree
- Checkout HEAD revision of gramps-addons
  svn://svn.code.sf.net/p/gramps-addons/code
  in the directory gramps-addons created above
Option 2:
- make a hard link to an existing gramps-addons directory
  cd %GRAMPS_RESOURCES% (gramps source tree)
  mklink /D gramps-addons "path to the existing gramps-addons directory"
  (command to be run as admin)

- Set the following environment variables:
  set PATH=Path to GrampsAIO4\bin;%PATH%
  set GRAMPSHOME=Path to testing environment (! DO NOT use the GRAMPSHOME that contains your data !)
  set GRAMPS_RESOURCES=Path to the GRAMPS source directory
  set GRAMPSPATH=..\..\..
  set LANG=fr_FR.UTF-8
  set LANGUAGE=fr_FR.UTF-8
  (or other language)

- Make sure that GRAMPS runs from source:
  cd %GRAMPS_RESOURCES%
  python setup.py build
  cd %GRAMPS_RESOURCES%
  python Gramps.py

- Build addon
  set LANG=en_US.UTF-8
  set LANGUAGE=en_US.UTF-8
  cd %GRAMPS_RESOURCES%\gramps-addons\trunk\contrib
  python make.py init DynamicWeb
  python make.py update DynamicWeb fr

- Update translation "DynamicWeb\po\fr-local.po" (with poedit for example)

- Compile translation files:
  python make.py compile DynamicWeb

- Testing: see below

- Build archive
  cd %GRAMPS_RESOURCES%\gramps-addons\trunk\contrib
  python make.py build DynamicWeb DynamicWeb/templates DynamicWeb/test


-------------------------------------------------------------------------
For testing:

- Create a symbolic link to the plugin in the user GRAMPSHOME directory
    Run cmd.exe as administrator
    Go to directory $GRAMPSHOME/gramps/trunk/plugins/
    mklink /D DynamicWeb %GRAMPS_RESOURCES%\gramps-addons\trunk\contrib\DynamicWeb

- Import example database:
  cd %GRAMPS_RESOURCES%\gramps-addons\trunk\contrib\DynamicWeb\test
  python dynamicweb_test.py -i

- Run gramps and set the base directory for media relative paths to %GRAMPS_RESOURCES%\examples\gramps

- Run tests:
  cd %GRAMPS_RESOURCES%\gramps-addons\trunk\contrib\DynamicWeb\test
  python dynamicweb_test.py



-------------------------------------------------------------------------
Using Maintenance branch 4.1
-------------------------------------------------------------------------
- Use branch "maintenace/gramps41" instead of "master"
- set GRAMPSPATH=..\..\..\..
- Use %GRAMPS_RESOURCES%\gramps-addons\branches\gramps41\contrib
  instead of %GRAMPS_RESOURCES%\gramps-addons\trunk\contrib


-------------------------------------------------------------------------
Using Maintenance branch 4.0
-------------------------------------------------------------------------
- Use branch "maintenace/gramps40" instead of "master"
- set GRAMPSPATH=..\..\..\..
- For building addon:
	Use python2 instead of python3
    Use %GRAMPS_RESOURCES%\gramps-addons\branches\gramps40\contrib
    instead of %GRAMPS_RESOURCES%\gramps-addons\trunk\contrib
