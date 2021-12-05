# Custom files around Gramps XML and data handling

- 'etreeGramplet' as set of built-in python module.
Very basic (quick and dirty), but should run whatever plateform and any pure 
python standard ecosystem (built-in modules). Designed as a gramps addon.

- 'lxmlGramplet' needs 'lxml' module.
More powerful and more complex. Designed as a gramps addon.
Many experimentations. Will generate some files from a Gramps XML.
```Gramps XML -to-> data```
Some samples of validations and transformations.
Methods and code might be old dated, but it is still fast and does the job.
See also https://gramps-project.org/wiki/index.php/Lxml_Gramplet

- 'grampsxml.dtd', 'grampsxml.rng', 'grampsxml.xsd'
related to validations via 'lxmlGramplet'.

- 'lxml.css', 'query_html.xsl'
basic templates for displaying transformed data via 'lxmlGramplet'.
 ```data -to-> Gramps XML```

- 'superclasses.py', 'subclasses.py'
modules generated with generateDS (Dave Kuhlman).
Did not use as production, rather an advanced documentation

- 'xpaths_x_x_x.txt'
For XPath addict.
Can be used for parsing, handling tags and namespaces for most Gramps XML
file versions. An alternate documentation.
