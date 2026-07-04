# Addon: Check Associations

From the Gramps-project open-source genealogy software project

This is a Third-party Addon. The Addon/Plugin system installs via the Addon Manager and is controlled by the Plugin Manager.

The Check Associations data tool checks the associations of people. It displays the 'Associations' (person_refs) state. The tool provides a quick way to find People who have an Association (from either direction). As there is no method that allows seeking a specific Association type or pattern of types (e.g., in this example: "God*" to seek Godfather, Godmother, Godparent, Godson, Goddaughter, Godchild); this tool comes closest.

## Usage

Select menu **Tools → Utilities → Check Associations data...** to show the results in the Associations state tool window.

### Associations state tool window

The **Associations state tool** window shows a results table with five columns:

| Column | Description |
|---|---|
| **Starting Name** | The person who has the association defined on their record |
| **Calculated** | The relationship calculated between the two people |
| **•** | Direction indicator |
| **Associate** | The associated person |
| **Associate's Link type** | The association type label (e.g. Godfather, Witness) |

#### Sorting

Click any column header (except **•**) to sort by that column. Click again to reverse the sort order.

#### Double-clicking a row

| Column double-clicked | Action |
|---|---|
| **Starting Name** or **Calculated** or **•** | Opens the Person Editor for the Starting Person |
| **Associate** | Opens the Person Editor for the Associate |
| **Associate's Link type** | Opens the Association Editor for that association |

#### Right-click context menu

Right-clicking any row shows a context menu with:

- **Edit Starting Person** — opens the Person Editor for the Starting Person
- **Edit Associate Person** — opens the Person Editor for the Associate
- **Edit Association** — opens the Association Editor
- **Copy row to clipboard** — copies the five visible columns as tab-separated text
- **Create Note from row** — creates a new Note pre-populated with the association data, with the two person names styled as clickable deep-links to their Person records

#### Help button

The **Help** button at the bottom-left of the window opens this wiki page in your default browser.

### Example next steps

The specific workflow AFTER opening the two people could be:

1. Determine which person would be the Godchild; open their Person Editor to look for Baptism/Christening events where they are "Primary".
2. Create an event if missing; open the other Person's Editor.
3. Drag/share the Baptism/Christening event to that person if missing.
4. Set Godparent role on the shared event; open all "God*" Associations.
5. Move any Association Sources/Notes to the appropriate section of the shared Event.
6. Save the Event.
7. Delete the Association.
8. OK to commit the two Edit Persons.

## See also

- Source code on GitHub: <https://github.com/gramps-project/addons-source/blob/maintenance/gramps60/AssociationsTool>
- Wiki page: <https://www.gramps-project.org/wiki/index.php/Addon:Check_Associations>
- [(Gramps-devel) Associations debug tool](https://sourceforge.net/p/gramps/mailman/message/34996074/) — From: jerome — 2016-04-06
- [Check Associations data — published for Gramps 4.2](https://github.com/gramps-project/addons-source/tree/maintenance/gramps42/AssociationsTool) by romjerome on Apr 13, 2016
- [SynchronizeAssociation tool addon](https://www.gramps-project.org/wiki/index.php/Addon:SyncAssociation)
- [Associations on Individuals](https://gramps.discourse.group/t/new-gram-py-script-for-6-0/7192/10) via a gramp.py or SuperTool script
