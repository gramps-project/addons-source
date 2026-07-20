# Tutorials

[← Previous](01-overview.md) · [Index](01-overview.md) · [Next →](03-addon-kinds.md)

<!--
  Walkthroughs, one per addon kind, in order of increasing surface area.
  Each tutorial:
    - states the goal in one sentence
    - shows the .gpr.py and the implementation module in full
    - walks the new concepts (not every line — the explanatory lines)
    - ends with "reload, restart, run" and what to expect

  Cross-link out to 03-addon-kinds for kind-level details, 04-fundamentals
  for cross-cutting concepts, 05-data-access for DB API details, and the
  standalone wiki pages for deeper coverage.

  Each tutorial assumes the reader has already followed the getting-started
  walkthrough on 01-overview — so the development loop (where addons live,
  restart cycle) is not re-explained.
-->

## Overview

End-to-end walkthroughs that take an author from empty folder to working addon. Each tutorial picks one kind, covers registration, implementation, and the reload cycle, and points at the conventions used to test it.

Read these in order or skip to the one that matches what you're building — they're independent. They assume you've already followed [the getting-started walkthrough in 01-overview](01-overview.md#your-first-addon-a-minimal-gramplet), so we don't re-explain the user plugin directory or the restart cycle.

| Tutorial                  | Kind          | What it shows                                                       |
|---------------------------|---------------|---------------------------------------------------------------------|
| [A live Gramplet](#a-live-gramplet) | `GRAMPLET`   | Reading the DB, refreshing on selection change, signal subscriptions |
| [A simple Tool](#a-simple-tool)     | `TOOL`       | The Tool / ToolOptions pair, opening a dialog, writing in a `DbTxn` |
| [A text Report](#a-text-report)     | `REPORT`     | The Report / ReportOptions pair, the docgen abstraction, paragraph styles |
| [A Quick View](#a-quick-view)       | `QUICKVIEW`  | The `run()` entry point, the Simple Access API, context-menu integration |
| [A custom filter Rule](#a-custom-filter-rule) | `RULE` | Subclassing the namespace Rule base, declaring `labels`, `apply_to_one` |

For the conceptual map, see [01-overview](01-overview.md). For the full inventory of addon kinds and their registration constants, see [03-addon-kinds](03-addon-kinds.md).

### A note on tutorial-style code

The implementation modules below show the smallest code that demonstrates each kind. Two things are deliberately omitted to keep the lesson in focus, and both are **required** for shipped addons:

- A **GPL-2.0-or-later license header** at the top of every `.py` file. Copy the header from any existing addon, or see [16-guidelines → Coding style](16-guidelines.md#coding-style).
- **Type hints** on public functions and methods (Python 3.10+ syntax — `X | None`, `list[X]`). The tutorials skip them for readability; production addons should include them per [16-guidelines → Coding style](16-guidelines.md#coding-style).

Both are CI-checked on gramps core PRs (Black formats around the license header; `mypy` verifies the type hints); addons-source doesn't gate on them today but the rules apply to addon code regardless.

## A live Gramplet

**Goal.** Build a sidebar Gramplet that reads the active person from the database and shows their direct events, refreshing whenever the active person changes or the database is updated.

The Hello Gramplet from [the overview's walkthrough](01-overview.md#your-first-addon-a-minimal-gramplet) was static text. This one is dynamic — it subscribes to signals and re-reads the DB on each update.

### Layout

Two files in a new folder `PersonEvents/`:

```
PersonEvents/
├── PersonEvents.gpr.py
└── personevents.py
```

### `PersonEvents/PersonEvents.gpr.py`

```python
register(
    GRAMPLET,
    id="PersonEvents",
    name=_("Person Events"),
    description=_("Lists the active person's direct events."),
    version="1.0.0",
    gramps_target_version="6.0",
    status=STABLE,
    fname="personevents.py",
    gramplet="PersonEventsGramplet",
    gramplet_title=_("Events"),
    height=200,
    expand=True,
)
```

`height` and `expand` are Gramplet-specific layout fields; the rest are the same registration shape introduced in [04-fundamentals → The `.gpr.py` registration file](04-fundamentals.md#the-gprpy-registration-file).

### `PersonEvents/personevents.py`

```python
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.plug import Gramplet

_ = glocale.get_addon_translator(__file__).gettext


class PersonEventsGramplet(Gramplet):
    """List the active person's direct events; refresh on changes."""

    def init(self):
        """Build the static parts of the UI once."""
        self.set_use_markup(True)
        self.set_text(_("No active person."))

    def db_changed(self):
        """Subscribe to DB signals each time the active DB changes."""
        self.connect(self.dbstate.db, "person-update", self.update)
        self.connect(self.dbstate.db, "person-delete", self.update)
        self.connect(self.dbstate.db, "event-update", self.update)

    def active_changed(self, handle):
        """Active person changed — re-render."""
        self.update()

    def main(self):
        """Pull events for the active person and render them."""
        person_handle = self.get_active("Person")
        if not person_handle:
            self.set_text(_("No active person."))
            return

        person = self.dbstate.db.get_person_from_handle(person_handle)
        if person is None:
            self.set_text(_("Active person not found."))
            return

        lines = [f"<b>{person.gramps_id}</b>\n"]
        for event_ref in person.get_event_ref_list():
            event = self.dbstate.db.get_event_from_handle(event_ref.ref)
            if event is None:
                continue
            date = event.get_date_object()
            lines.append(f"{event.get_type()}  {date}")

        self.set_text("\n".join(lines))
```

### What's new vs. Hello Gramplet

- **`db_changed()`** subscribes to DB signals. Using `self.connect(...)` (defined on `Gramplet`) instead of `self.dbstate.db.connect(...)` means Gramps tracks the subscription keys for you and disconnects them automatically when the gramplet closes or the DB swaps out. The forgotten-disconnect bug class is gone.
- **`active_changed(handle)`** is called by Gramps when the user selects a different person in the active view. The default does nothing; calling `self.update()` triggers a redraw.
- **`get_active("Person")`** returns the handle of the active person for the current view, or `None`. It honours navigation context — in a Place view it returns the active place, etc.
- **`set_use_markup(True)`** lets `set_text()` interpret Pango markup (`<b>`, `<i>`, …); see [Gramplet textual methods](https://gramps-project.org/wiki/index.php/Gramplets_development#Textual_Output_Methods).

### Try it

Drop the folder into your user plugin directory (or symlink it if you're on Gramps 6.1+), restart Gramps, open a tree, and add the Gramplet from the sidebar menu. Click around different people — the displayed events should change with the selection.

For the API surface this tutorial used (handles, refs, `iter_*`, `commit_*`), see [05-data-access](05-data-access.md). For the signal inventory, see [04-fundamentals → Signals](04-fundamentals.md#signals-addons-reacting-to-changes).

## A simple Tool

**Goal.** A menu-launched Tool that scans the database for people with no recorded birth date and shows the list in a dialog.

Tools differ from gramplets in two ways: they're invoked from the Tools menu (not always visible), and they always carry an Options class — even a tool with no options must register an empty `ToolOptions` subclass.

### Layout

```
MissingBirthDates/
├── MissingBirthDates.gpr.py
└── missingbirthdates.py
```

### `MissingBirthDates/MissingBirthDates.gpr.py`

```python
register(
    TOOL,
    id="MissingBirthDates",
    name=_("Missing Birth Dates"),
    description=_("Lists people with no recorded birth date."),
    version="1.0.0",
    gramps_target_version="6.0",
    status=STABLE,
    fname="missingbirthdates.py",
    category=TOOL_ANAL,
    toolclass="MissingBirthDates",
    optionclass="MissingBirthDatesOptions",
    tool_modes=[TOOL_MODE_GUI],
)
```

`category=TOOL_ANAL` puts the tool under *Tools → Analysis and Exploration*. Other categories (`TOOL_DBPROC`, `TOOL_DBFIX`, …) are listed in [03-addon-kinds → `TOOL`](03-addon-kinds.md#tool).

### `MissingBirthDates/missingbirthdates.py`

```python
from gi.repository import Gtk

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gui.dialog import OkDialog
from gramps.gui.plug import tool

_ = glocale.get_addon_translator(__file__).gettext


class MissingBirthDates(tool.Tool):
    """Scan the DB and report people with no recorded birth date."""

    def __init__(self, dbstate, user, options_class, name, callback=None):
        tool.Tool.__init__(self, dbstate, options_class, name)

        db = dbstate.db
        missing = []
        for person in db.iter_people():
            birth_ref = person.get_birth_ref()
            if birth_ref is None:
                missing.append(person)
                continue
            event = db.get_event_from_handle(birth_ref.ref)
            if event is None or event.get_date_object().is_empty():
                missing.append(person)

        if not missing:
            OkDialog(
                _("Missing Birth Dates"),
                _("Every person has a recorded birth date."),
                parent=user.uistate.window,
            )
            return

        lines = [f"{p.gramps_id}: {p.get_primary_name().get_name()}"
                 for p in missing]
        OkDialog(
            _("Missing Birth Dates"),
            _("{n} people with no recorded birth date:\n\n{listing}").format(
                n=len(missing),
                listing="\n".join(lines),
            ),
            parent=user.uistate.window,
        )


class MissingBirthDatesOptions(tool.ToolOptions):
    """No options — placeholder required by the tool framework."""
```

### What's new

- **`tool.Tool.__init__(self, dbstate, options_class, name)`** — the base-class constructor. The body of `__init__` is *where the tool runs*; there's no separate `run()` method for GUI tools.
- **`MissingBirthDatesOptions`** is required even though we have no options. The `register(...)` call names it via `optionclass`, and Gramps would refuse to load the tool without it.
- **`OkDialog`** is the simplest modal report-back surface; for richer output, build a `Gtk.Dialog` directly (see `gramps/plugins/tool/dumpgenderstats.py` for the standard recipe).

### Writing data

If your tool *modifies* the database, all writes go inside a `DbTxn`:

```python
from gramps.gen.db import DbTxn

with DbTxn(_("Mark unreferenced media private"), db) as trans:
    for media in db.iter_media():
        if not db.find_backlink_handles(media.handle):
            media.set_privacy(True)
            db.commit_media(media, trans)
```

The transaction message is user-visible in the Undo history; translate it. See [05-data-access → Mutating data](05-data-access.md#mutating-data) for the full pattern.

### Try it

After restart, the tool appears in *Tools → Analysis and Exploration → Missing Birth Dates*. Run it on `example.gramps` to see the dialog.

## A text Report

**Goal.** A simple text report that summarises the database — number of people, number of families, count by gender. Produces the same content through PDF, HTML, ODF, or any other docgen-supported format.

Reports are the heaviest of the everyday addon kinds. Three pieces work together:

- A **Report** class that knows how to walk the data and emit it as paragraphs and tables, leaving format details to the docgen.
- An **Options** class that defines user-adjustable options and the paragraph / font styles.
- A **registration** call wiring both into the menu.

### Layout

```
DbSummary/
├── DbSummary.gpr.py
└── dbsummary.py
```

### `DbSummary/DbSummary.gpr.py`

```python
register(
    REPORT,
    id="DbSummary",
    name=_("Database Summary"),
    description=_("Produces a short summary of the family tree."),
    version="1.0.0",
    gramps_target_version="6.0",
    status=STABLE,
    fname="dbsummary.py",
    category=CATEGORY_TEXT,
    require_active=False,
    reportclass="DbSummaryReport",
    optionclass="DbSummaryOptions",
    report_modes=[REPORT_MODE_GUI, REPORT_MODE_CLI],
)
```

`category=CATEGORY_TEXT` makes this a text report — Gramps will offer the user the text-output document backends (PDF, ODF, plain text, …). `require_active=False` because a database summary doesn't need a specific active person.

### `DbSummary/dbsummary.py`

```python
from collections import Counter

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.lib import Person
from gramps.gen.plug import docgen
from gramps.gen.plug.report import MenuReportOptions, Report
from gramps.gen.plug.report import stdoptions

_ = glocale.get_addon_translator(__file__).gettext


class DbSummaryReport(Report):
    """A text report summarising the database."""

    def __init__(self, database, options_class, user):
        Report.__init__(self, database, options_class, user)
        self.set_locale(
            options_class.menu.get_option_by_name("trans").get_value()
        )
        self._count()

    def _count(self):
        """Walk every Person and tally."""
        self.total = 0
        gender_counts = Counter()
        surnames = Counter()
        for person in self.database.iter_people():
            self.total += 1
            gender_counts[person.get_gender()] += 1
            primary = person.get_primary_name()
            surnames[primary.get_primary_surname().get_surname()] += 1
        self.gender_counts = gender_counts
        self.unique_surnames = len(surnames)
        self.top_surname = (
            surnames.most_common(1)[0] if surnames else (_("(none)"), 0)
        )

    def write_report(self):
        """Emit paragraphs into self.doc."""
        self.doc.start_paragraph("DBS-Title")
        self.doc.write_text(self._("Database Summary"))
        self.doc.end_paragraph()

        self.doc.start_paragraph("DBS-Normal")
        self.doc.write_text(
            self._("Total persons: {n}").format(n=self.total))
        self.doc.end_paragraph()

        for gender_code, label in [
            (Person.MALE, _("Males")),
            (Person.FEMALE, _("Females")),
            (Person.UNKNOWN, _("Unknown gender")),
        ]:
            self.doc.start_paragraph("DBS-Normal")
            self.doc.write_text(
                self._("{label}: {n}").format(
                    label=label,
                    n=self.gender_counts.get(gender_code, 0),
                )
            )
            self.doc.end_paragraph()

        self.doc.start_paragraph("DBS-Normal")
        self.doc.write_text(
            self._("Unique surnames: {n}").format(n=self.unique_surnames)
        )
        self.doc.end_paragraph()

        self.doc.start_paragraph("DBS-Normal")
        self.doc.write_text(
            self._("Most common surname: {name} ({n})").format(
                name=self.top_surname[0], n=self.top_surname[1])
        )
        self.doc.end_paragraph()


class DbSummaryOptions(MenuReportOptions):
    """Options form and default styles for DbSummaryReport."""

    def add_menu_options(self, menu):
        category = _("Report Options")
        stdoptions.add_localization_option(menu, category)

    def make_default_style(self, default_style):
        # Title style: 18 pt bold sans-serif, centred, header level 1.
        font = docgen.FontStyle()
        font.set_size(18)
        font.set_type_face(docgen.FONT_SANS_SERIF)
        font.set_bold(True)
        para = docgen.ParagraphStyle()
        para.set_header_level(1)
        para.set_alignment(docgen.PARA_ALIGN_CENTER)
        para.set_font(font)
        para.set_description(_("Style used for the title of the report."))
        default_style.add_paragraph_style("DBS-Title", para)

        # Body style: 12 pt serif.
        font = docgen.FontStyle()
        font.set_size(12)
        font.set_type_face(docgen.FONT_SERIF)
        para = docgen.ParagraphStyle()
        para.set_font(font)
        para.set_description(_("Style used for normal report text."))
        default_style.add_paragraph_style("DBS-Normal", para)
```

### What's new

- **Two classes, one file.** The `register()` call points `reportclass` at the Report and `optionclass` at the Options.
- **`self.doc` is not a file.** It's the live document — a docgen backend instance. The report writes paragraphs and text into it regardless of output format.
- **Paragraph style names are prefixed.** Use `DBS-` (or any short prefix unique to your report) on every style name. Reports get composed into Book reports, where every style name has to be unique across all contributing reports.
- **Localisation is explicit.** `stdoptions.add_localization_option` adds the standard "report locale" option to the form; the report reads it with `self.set_locale(...)` and uses `self._()` for strings that should follow the *report's* chosen locale rather than the UI locale. The leading underscore in `self._` is intentional.
- **`MenuReportOptions`** is the convenient base; for a no-options report, override only `add_menu_options` (to add the locale option) and `make_default_style` (to define paragraph styles).

### Try it

After restart, the report appears in *Reports → Text Reports → Database Summary*. Run it through any text document backend (PDF, ODF, plain text) to see the same content reformatted by each.

For more on the docgen abstraction, see [Report Generation](https://gramps-project.org/wiki/index.php/Report_Generation). For richer reports (tables, multiple paragraph levels, graphical reports using `CATEGORY_DRAW`), see [Report API](https://gramps-project.org/wiki/index.php/Report_API).

## A Quick View

**Goal.** A right-click action on a person that lists their siblings — brothers and sisters from every family they're a child in.

Quick Views are the shortest path to a usable report. There's no class to subclass and no options form to maintain — just a `run()` function and the registration. They're written against the **Simple Access API** (`SimpleAccess`, `SimpleDoc`), which trades some power for very little code.

### Layout

```
Siblings/
├── Siblings.gpr.py
└── siblings.py
```

### `Siblings/Siblings.gpr.py`

```python
register(
    QUICKVIEW,
    id="Siblings",
    name=_("Siblings"),
    description=_("Lists the active person's siblings."),
    version="1.0.0",
    gramps_target_version="6.0",
    status=STABLE,
    fname="siblings.py",
    category=CATEGORY_QR_PERSON,
    runfunc="run",
)
```

`category=CATEGORY_QR_PERSON` puts the entry on the person context menu. `runfunc="run"` names the function Gramps calls. The full set of categories is listed in [03-addon-kinds → `QUICKVIEW`](03-addon-kinds.md#quickview).

### `Siblings/siblings.py`

```python
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.simple import SimpleAccess, SimpleDoc
from gramps.gui.plug.quick import QuickTable

_ = glocale.get_addon_translator(__file__).gettext


def run(database, document, person):
    """Display all siblings of the given person."""
    sdb = SimpleAccess(database)
    sdoc = SimpleDoc(document)

    sdoc.title(_("Siblings of {name}").format(name=sdb.name(person)))
    sdoc.paragraph("")

    table = QuickTable(sdb)
    table.columns(_("Person"), _("Gender"), _("Birth date"))

    own_gid = sdb.gid(person)
    for family in sdb.child_in(person):
        for child in sdb.children(family):
            if sdb.gid(child) == own_gid:
                continue
            table.row(child, sdb.gender(child), sdb.birth_date(child))
            document.has_data = True

    table.write(sdoc)
```

### What's new

- **`run(database, document, person)`** — the function signature is fixed by the QuickView kind. The third argument is the *selected object* of the category (`CATEGORY_QR_PERSON` → person, `CATEGORY_QR_FAMILY` → family, …).
- **`SimpleAccess`** is the high-level read interface — `sdb.children(family)`, `sdb.birth_date(person)`, `sdb.name(person)`. It hides handle dereferencing, refs, and date formatting. For the full surface, see [Simple Access API](https://gramps-project.org/wiki/index.php/Simple_Access_API).
- **`SimpleDoc`** is the matching write interface — `sdoc.title(...)`, `sdoc.paragraph(...)`, `sdoc.header1(...)`.
- **`QuickTable`** builds an interactive table where each row links back to a real Gramps object — clicking a person opens that person.
- **`document.has_data = True`** tells Gramps the report produced output. When all rows are filtered out, the empty-state path triggers instead.

### Try it

After restart, right-click any person in the People view or the person editor. *Quick View → Siblings* appears in the menu. The result opens in a Quick View window; clicking a row in the table opens that person.

For Quick Views that don't fit the Simple Access surface, you can reach for the full DB API — see [05-data-access](05-data-access.md). The two are complementary; a complex Quick View can use both.

## A custom filter Rule

**Goal.** A filter rule "Has at least N children" that the user can add to a custom person filter from the Filter Editor.

Filter rules are the smallest addon kind by line count and the one with the most reuse: a single rule, written once, drops into every filter the user composes — search, narrative website, reports, gramplets that accept a filter.

### Layout

```
HasNChildren/
├── HasNChildren.gpr.py
└── hasnchildren.py
```

### `HasNChildren/HasNChildren.gpr.py`

```python
register(
    RULE,
    id="HasNChildren",
    name=_("People with at least N children"),
    description=_("Matches people who have at least N children."),
    version="1.0.0",
    gramps_target_version="6.0",
    status=STABLE,
    fname="hasnchildren.py",
    ruleclass="HasNChildren",
    namespace="Person",
)
```

`namespace="Person"` says this rule applies to people. The other namespaces (`Family`, `Event`, `Place`, `Source`, `Citation`, `Repository`, `Media`, `Note`) get their own rules — Gramps' filter editor groups rules by namespace.

### `HasNChildren/hasnchildren.py`

```python
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.filters.rules import Rule

_ = glocale.get_addon_translator(__file__).gettext


class HasNChildren(Rule):
    """Matches people with at least N children."""

    labels = [_("Minimum count:")]
    name = _("People with at least N children")
    category = _("Family filters")
    description = _("Matches people with at least N children")

    def apply_to_one(self, db, person):
        try:
            minimum = int(self.list[0])
        except (TypeError, ValueError):
            return False
        total = 0
        for family_handle in person.get_family_handle_list():
            family = db.get_family_from_handle(family_handle)
            if family is None:
                continue
            total += len(family.get_child_ref_list())
            if total >= minimum:
                return True
        return False
```

### What's new

- **`labels`** declares the user-prompted arguments — one entry per text box in the filter-editor dialog. The user's typed values arrive on `self.list` in the same order. Always parse defensively; `self.list[0]` is a string straight from the GUI.
- **`name`, `category`, `description`** are class attributes — Gramps reads them off the class (no instance needed) when building the Add Rule dialog. `category` is the section the rule appears under in that dialog.
- **`apply_to_one(self, db, person)`** is the per-object hook. It returns `True` for a match, `False` for a non-match. Gramps calls it for every person in the namespace when applying the filter. On Gramps 6.0 the API is `apply_to_one`; older releases used `apply` (see [gramps/gen/filters/rules/_rule.py:162](https://github.com/gramps-project/gramps/blob/maintenance/gramps60/gramps/gen/filters/rules/_rule.py#L162)).

### Optional hooks

- **`prepare(self, db, user)`** — called once before the rule is applied to many objects, on demand. Use it to precompute lookup tables when `apply_to_one` would otherwise repeat expensive work. Pair with `reset()` to release memory afterwards.
- **`allow_regex = True`** — opt the first label into regex input.

### Try it

After restart, *Edit → Person Filter Editor → Add → Add Rule* shows "People with at least N children" under *Family filters*. The user types a number in the "Minimum count" field; the rule does the rest.

The rule is also visible from gramplets like *Filter Gramplet* and as an input to any tool or report that accepts a person filter — no extra work needed; rules are uniform across the framework.

## See also

- [01-overview → Your first addon](01-overview.md#your-first-addon-a-minimal-gramplet) — the prerequisites and the development loop these tutorials build on.
- [03-addon-kinds](03-addon-kinds.md) — registration details per kind.
- [04-fundamentals](04-fundamentals.md) — `.gpr.py` fields, signals, `requires_mod`, lifecycle hooks.
- [05-data-access](05-data-access.md) — the DB API patterns used by these tutorials.
- [07-testing](07-testing.md) — how to test what you just wrote without launching Gramps.
- [Report API](https://gramps-project.org/wiki/index.php/Report_API), [Report Generation](https://gramps-project.org/wiki/index.php/Report_Generation) — depth on the docgen abstraction.
- [Simple Access API](https://gramps-project.org/wiki/index.php/Simple_Access_API) — the Quick View read surface.
