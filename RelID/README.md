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

* Gramplet

* Tool

**TOCHECK**

Tool: **step descendants** may have a mistake on '*most recent mother*'
number if they are direct descendants of the '*father*'.

**TODO**

Tool: Fix FileChosser for properly selecting a folder

Use __gramps.plugins.lib.librecurse__ module

**Save and export**

Both gramplet and tool can export the content after calculations.
Either via the context menu (*right_clic*) on gramplet or via file
generation to OpenDocument Spreadsheet (.ods) format on tool.