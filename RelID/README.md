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

Documentation
-------------

**TOCHECK**

Tool: **step descendants** may have a mistake on '*most recent mother*'
number if they are direct descendants of the '*father*'.

**TODO**

Use *gramps.plugins.lib.librecurse* module
or advanced lib like [pypedal]( https://github.com/wintermind/pypedal ).

**Run via CLI and debug statements**

    $ python3 Gramps.py -O 'example' -a tool -p name=relationtab -d "relation_tab"

**Save and export**

The tool can export the content after calculations
via file generation to OpenDocument Spreadsheet (.ods) format.