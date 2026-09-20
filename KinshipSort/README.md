# KinshipSort

KinshipSort adds two People views to **Gramps 6.0.x** with a sortable,
calculated **Kinship degree** column relative to the tree's **Home Person**:

- **People by kinship degree**: a flat list.
- **People by kinship, grouped**: people grouped by surname.

Version **0.2.8**, experimental. Author: **Jacek Kuznia**.
Contact: <jacek.kuznia@gmail.com>. GitHub: [jacek-kuznia](https://github.com/jacek-kuznia).
English and Polish interface text is provided. Other languages fall back to
English for the new messages. [Polska instrukcja](README_PL.txt).

## What the degree means

The degree is the shortest biological parent/child path through a common
ancestor. The path goes up from the Home Person to that ancestor, then down
to the relative. Either part may be empty.

| Relationship to Home Person | Degree |
| --- | ---: |
| Home Person | 0 |
| Biological parent or child | 1 |
| Sibling, half-sibling, grandparent or grandchild | 2 |
| Aunt, uncle, niece or nephew | 3 |
| First cousin | 4 |
| No established biological path | blank |

Only relationships recorded as **Birth** are counted. Marriage, partnership,
adoption, foster relationships and associations do not create biological
kinship. A spouse who is also a biological relative is counted through the
common ancestor. The invalid path `Home -> shared child -> spouse` is never
used. Multiple valid paths use the smallest degree.

A blank means no biological relationship can be established from the recorded
data; it is not proof that two people have no biological relationship.
This is a count of genealogical steps, not a genetic kinship coefficient.
Selecting another active person does not change the reference; change the
**Home Person** to calculate relative to somebody else.

## Sorting and columns

Click a column heading to sort; click again to reverse the order. Other
columns retain their usual Gramps sorting behavior.

In the flat view, ascending kinship order uses degree, generation level,
then the normal Gramps alphabetical name key. For equal degrees, higher
generation levels come first: parents before children, and grandparents
before siblings before grandchildren. For equally short paths to one person,
the highest generation level is used.

In the grouped view, ascending kinship order places surname groups by the
smallest degree of any person in the group, then by surname. People within a
group are ordered by degree and name, without the flat view's generation
tie-breaker. A group's degree is calculated from all people assigned to that
surname group, even if a filter hides some of them. When sorting another
column, surname groups are alphabetical and that column orders people inside
each group.

Blank degrees follow related people in ascending order. **Descending order
reverses the entire order**, including blank degrees, generation tie-breakers
and surname groups. With no Home Person, all degrees are blank.

The kinship column is initially second, after Name. The normal column editor
can move or hide it. On opening the view, initial sorting uses kinship when
that column is visible, or the first visible column otherwise.

## Data and performance

Calculated degrees and generation levels are held in memory and are never
written to genealogical records. The standard Gramps add/edit actions remain
available and save records normally. View configuration is saved normally.

The calculation first finds the Home Person's ancestors and then performs one
shared downward search. Relevant person/family changes rebuild the view and
recalculate degrees. Large trees and repeated edits still need interactive
performance testing; graph-only benchmarks do not measure view redraw time.

## Manual installation

1. Close Gramps.
2. Extract the **installation** archive into the user plugin directory so the
   files are under `plugins/KinshipSort/`. Keep only one copy of the addon in
   the plugin search path.
3. Start Gramps, open a tree, set its Home Person and select one of the two new
   views in the People category.

On Windows, Gramps 6.0.8 normally uses
`%APPDATA%\gramps\gramps60\plugins\`. Older installations may use
`%LOCALAPPDATA%\gramps\gramps60\plugins\`. A custom `GRAMPSHOME` changes the
location. Use the directory actually used by your installation. On Linux the
default data directory is normally `~/.local/share/gramps/gramps60/plugins/`
(subject to XDG settings). Check Gramps' user plugin path on other systems.

Source archives contain `po/pl-local.po`; installation archives also contain
`locale/pl/LC_MESSAGES/addon.mo`. Compile the translation when installing from
source if you want Polish text. There are no additional runtime dependencies
beyond Gramps and its GTK dependencies.

## Development and tests

The tests below are included in the source archive, not the installation package.

From the `addons-source` root in a POSIX shell (MSYS2 on Windows), run the
calculation tests without Gramps or GTK:

```console
python3 -m unittest KinshipSort.tests.test_kinship_calculation -v
```

The optional `tests/test_gramps_integration.py` suite requires the Gramps 6.0
Python environment, GTK 3 and a temporary test profile. It uses a temporary
database and does not use a personal family tree. See `tests/README.md` for
the remaining interactive checks.

For upstream publication, use a fork of `gramps-project/addons-source` based
on `maintenance/gramps60`. The normal Gramps `make.py` workflow builds addon
translations, the package and listings. Generated `.mo`, `.pyc`, archive and
`po/template.pot` files should not be committed to the source repository.
The `MANIFEST` adds Markdown documentation and the license to the normal
Python/text/translation package contents.

## License and credits

GNU General Public License, version 2 or later (`GPL-2.0-or-later`). See
[COPYING](COPYING) and [ATTRIBUTION.md](ATTRIBUTION.md). The addon has not yet
been accepted into the Gramps addon repository or the main application.
