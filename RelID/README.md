Relationships ID
===================

* Genesis and history

[#4169: To generate numbering class]( https://gramps-project.org/bugs/view.php?id=4169 )

[#7955: Show Kekule numbering in different views]( https://gramps-project.org/bugs/view.php?id=7955 )

Design
------

* *relationships_identifiers* are set on __number.py__ module
* ancestors numbering is based on **sosa/kekule** model
* descendants numbering is based on **matrilineality** kinship
* 'most recent ancestors' are 'most recent mothers'

Performances
------------

On this addon, iteration with sqlite 3.8.2 database backend seems at least
30 % slower than iteration wih bsddb 6.0.1.

Try to limit deep search (generations set on Preferences)
for large table of people. Average of maximum O.O1 second per person
for 5 levels (generations) on modern CPUs.

Documentation
-------------

**TOCHECK**

Tool: **step descendants** may have a mistake on '*most recent mother*'
number if they are direct descendants of the '*father*'.

**TODO**

Tool: to fix modal window

Use *gramps.plugins.lib.librecurse* module
or advanced lib like [pypedal]( https://github.com/wintermind/pypedal ).

**Run via CLI and debug statements**

    $ python3 Gramps.py -O 'example' -a tool -p name=relationtab -d "relation_tab"

**Save and export**

The tool can export the content after calculations
via file generation to OpenDocument Spreadsheet (.ods) format.