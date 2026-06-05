# Name Standardization Suite for Gramps

Welcome to the Name Standardization Suite! This is an addon for Gramps that helps you clean up, fix, and fill in missing names across your entire family tree. It is especially helpful for East Slavic names: fixing typos, updating historical name spellings to modern ones, and figuring out missing patronymics (names based on a father's given name).

## How It Helps You (Real-World Use Cases)

Genealogical databases often grow messy over time due to evolving spelling rules, transcription errors, or merging trees from different sources. Here is how this suite handles common research hurdles:

* **Standardizing Church vs. Civil Names:** If you are working with older parish registers, you might have canonical church names like *Иоанн* or *Иаков* (or *Johannes* in Western records). The suite allows you to safely bulk-update these to modern, searchable civil forms like *Иван*, *Яков*, or *Johann* while automatically saving the original historical spelling as an "Alternative Name."
* **Fixing Widespread Typos and Orthography:** Rapid digitization often introduces typos like *Иоаннн*, or leaves you with mixed pre-reform spellings (*Федор* vs. *Фёдор*). You can use exact or substring matches to correct these across thousands of records instantly. For example, fixing a substring from *Иоан* to *Иван* inside a hyphenated name like *Анна-Иоанновна*.
* **Reconstructing Missing Patronymics:** If you have census data or Revision Lists that list a father but omit the children's patronymic middle names, the Auditor can scan those family links and automatically infer the historically accurate patronymic suffix (e.g., generating Slavic patronymics or traditional Nordic (future work) *Sven* $\rightarrow$ *Svensson*/*Svensdotter* suffixes).
* **Tracking Immigrant Anglicization:** Standardize given names for immigrants who assimilated across borders (e.g., bulk updating *Giuseppe* to *Joseph* or *Heinrich* to *Henry* for census consistency).

## What's Included

The suite is located in your Gramps menu under `Tools -> Family Tree Processing -> Standardize Names...`. It includes three main tools to help you manage your database:

### 1. Bulk Given Name Renamer

![Autocompletion Screenshot](docs/renamer_autocomplete.png)
![Renamer Tab Screenshot](docs/renamer_screenshot.png)

This tool lets you easily fix typos or update historical given names across your entire database all at once. You can search using **exact matches**, **substrings** (parts of names), or **regular expressions** (advanced text patterns) to find exactly what you want to change. To speed up your data entry, the tool features built-in autocompletion based on the people already existing in your database.

When updating primary names, you have the option to turn on a setting that preserves the original spelling as an "Alternative Name" (Also Known As). As mentioned above, this allows you to safely standardize records without losing any attached notes or citations from the original document.

### 2. Patronymic Auditor

![Audit Tab Screenshot](docs/audit_screenshot.png)

This tab acts as a proofreader for your existing family tree. It checks for mistakes in patronymics (like wrong gender endings or timeline issues) and can even suggest missing patronymics based on who a person's father is.

### 3. Contextual Patronymic Assistant (Gramplet)

![Gramplet Screenshot](docs/gramplet_screenshot.png)

For when you aren't doing bulk updates, we've included a handy side panel (Gramplet) available in both the People and Relationships views. As you browse your tree, it will automatically suggest missing patronymic names and let you apply them with a single click.

## Keeping Your Data Safe

Genealogists spend countless hours entering data, so this tool is built from the ground up to protect your hard work.

* **Review Before Saving:** The tool will *never* change your database behind your back. You will always get a clear list of proposed changes to review and approve before anything is actually saved.
* **Preserving Historical Records:** Updating a primary given name does not mean destroying data. The optional setting to save the original spelling as an "Alternative Name" ensures you never lose the exact way a name was written in the original historical record.
* **Easy Undo:** All bulk updates are processed using Gramps' built-in transaction system. If you realize you made a mistake after clicking apply, you can simply use the standard Gramps `Edit -> Undo` button to revert the entire batch.

## Technical Information

Under the hood, this addon is built to be reliable and easy to maintain, adhering to the MVCS (Model-View-Controller-Service) pattern combined with elements of Clean Architecture.

**System Requirements:**

* Gramps 6.0+
* Python 3.10+

**Dependencies:**
You do not need to install any additional software or libraries to use this addon. It works right out of the box! *(Note for developers: The `requirements.txt` file found in the repository code is only needed if you are running automated tests).*
