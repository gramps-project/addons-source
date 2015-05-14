DynamicWeb Gramps report addon

For license, see file 'dynamicweb.py'

This add-on for GRAMPS is an alternative to the Narrative Web Report.
It exports the database as web pages.

See http://belissent.github.io/GrampsDynamicWebReport/ for more information and reports examples.


Gramps branches master, 4.0 and 4.1 are supported, previous branches are not supported.



Testing instructions:

- Import example database:
  In the directory DynamicWeb/test
  python dynamicweb_test.py -i

- Run Gramps and set the base directory for media relative paths to %GRAMPS_RESOURCES%/examples/gramps

- Run tests:
  In the directory DynamicWeb/test
  python dynamicweb_test.py

- Results are in the directory DynamicWeb/test_results
