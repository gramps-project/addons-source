Circle Tree View
================
A third-party addon for Gramps (target: 6.1.x)

Descendant tree with circular nodes, multi-spouse/marriage support,
spouse infinity mark (∞), automatic generation depth (max 6),
and SVG/PNG export.

Version 1.4.0
-------------
Full support for multiple spouses/marriages per person.
Children are properly grouped under their respective marriage midpoints.

Installation (manual)
---------------------
1. Close Gramps if it is running.
2. Extract this archive so that the folder "CircleTreeView" appears inside
   your Gramps user plugins directory:

   Linux / macOS:
     ~/.gramps/gramps61/plugins/CircleTreeView/

   Windows:
     %AppData%\gramps\gramps60\plugins\CircleTreeView\

3. Restart Gramps.
4. Open the Charts category (or Ancestry views) and select "Circle Tree".

Configuration
-------------
View → Configure… (or the view settings) allows you to toggle:
  - Show dates in labels
  - Strip patronymics in labels
  - Show spouses

Export
------
Use the toolbar buttons "Export SVG" or "Export PNG".

License
-------
GNU GPL v2 or later (same as Gramps).
