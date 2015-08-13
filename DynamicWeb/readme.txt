DynamicWeb Gramps report addon

For license, see file 'dynamicweb.py'

This add-on for GRAMPS is an alternative to the Narrative Web Report.
It exports the database as web pages.

See http://belissent.github.io/GrampsDynamicWebReport/ for more information and reports examples.


GRAMPS branches 4.0, 4.1, 4.2, 5.0 (master) are supported, previous branches are not supported.



Instructions for generating report examples (GRAMPS version 5.0 only):

- See .travis.yml in the addons-source repository, which lists the installations to be performed first.
- Run nosetests -vv -a 'slow'
- Results are in the directory DynamicWeb/reports



Instructions for generating report examples (GRAMPS versions 4.0, 4.1, 4.2):

- Import example database:
  In the directory DynamicWeb
  python run_dynamicweb.py -i

- Run Gramps and set the base directory for media relative paths to %GRAMPS_RESOURCES%/examples/gramps

- Generate the example reports:
  In the directory DynamicWeb
  python run_dynamicweb.py

- Results are in the directory DynamicWeb/reports

