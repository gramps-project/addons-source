# Data access

[← Previous](04-fundamentals.md) · [Index](01-overview.md) · [Next →](06-api-reference.md)

<!--
  Data access is the first non-trivial thing every addon does: read the
  family tree the user has open. This chapter covers the shape of the
  database API, not the full API reference (that's
  [06-api-reference](06-api-reference.md)). Aim: enough to write a working
  addon without first having to read gramps/gen/db source.

  Authoritative cross-reference: the standalone wiki page
  [Using database API](wiki:Using_database_API) covers internals and
  performance in more depth; this chapter sticks to what addon authors
  actually need.
-->

## Summary

Every addon that does anything useful with a family tree reads or writes through the **database API** — the `DbReadBase` / `DbWriteBase` interface implemented by Gramps' database backends (BSDDB historically, SQLite from 6.0 onward).

You don't instantiate a database yourself. The plugin loader hands you a `DbState` object; the live database is `dbstate.db`. Everything below is methods on that handle.

```python
db = dbstate.db   # this is your entry point
```

The same `db` works for read-only addons (reports, gramplets, quick views) and for tools that mutate data. Mutation goes through transactions; see [Mutating data](#mutating-data) below.

The page follows the order in which questions actually come up. It starts with the distinction that trips up nearly everyone — **handles versus Gramps IDs**: the handle is the immutable internal key you traverse the data with, the `gramps_id` (`I0042`, `P0001`) is the user-facing label that users can and do change, and mixing them up produces code that works on your tree and fails on someone else's. Then **reading one object at a time** by handle or ID, and **iterating whole object types** with the cursor and iterator methods that keep memory flat on large trees.

From there it gets into structure: **following references** from one object to another (a Person to their Families, a Family to its Events, an Event to its Place), and **backlinks** — the reverse question, "what refers to this object?", which is how you find every citation of a source or every event at a place. **Filters** covers reusing Gramps' own filter machinery instead of hand-rolling selection logic. **Mutating data** covers the write path: every change goes inside a `DbTxn` transaction, which is what makes it undoable in the UI and atomic on failure.

Two shorter sections close it out: **testing data access** — how to exercise this code without a GUI, cross-referenced to [Testing](07-testing.md) — and **performance notes** on the access patterns that stay fast as trees grow into the tens of thousands of objects.

## Identifying objects: handles vs Gramps IDs

Every primary object (Person, Family, Event, Place, Source, Citation, Repository, Media, Note, Tag) has **two identifiers**:

| Identifier | Stable | Format | Used for |
|------------|--------|--------|----------|
| **Handle** | Yes (internal, never reused) | 32-char hex string | Cross-references in the database |
| **Gramps ID** | User-renameable | `I0001`, `F0001`, `E0001`, ... | User-visible labels and external interop |

**Rule of thumb:** use handles inside your code; show Gramps IDs to the user. Handles never change; Gramps IDs do (the user can edit them, the "Reorder Gramps IDs" tool can rewrite them in bulk).

```python
# Right: traverse by handle
person = db.get_person_from_handle(handle)

# Right: show the user a Gramps ID
print(f"Working on {person.gramps_id}")

# Wrong: traverse by Gramps ID (works, but slower and breaks under reorder)
person = db.get_person_from_gramps_id("I0001")
```

Each object class has both lookup methods (`get_<type>_from_handle` and `get_<type>_from_gramps_id`); see [06-api-reference](06-api-reference.md) for the full list.

## Reading: one object at a time

The fastest pattern, when you have a handle in hand:

```python
person = db.get_person_from_handle(person_handle)
family = db.get_family_from_handle(family_handle)
event  = db.get_event_from_handle(event_handle)
```

Each returns `None` if the handle isn't in the database (deleted, broken reference). Always guard:

```python
person = db.get_person_from_handle(handle)
if person is None:
    return  # silently skip, or raise a HandleError if the caller expects one
```

For `HandleError` and friends, import from `gramps.gen.errors`.

## Reading: iterating all objects

For reports and surveys you'll want every object of a given type. The database exposes one generator per object class:

```python
for person in db.iter_people():
    ...

for family in db.iter_families():
    ...
```

These are **generators**, not lists — they stream through the database without loading everything into memory. Don't call `list(db.iter_people())` on a 50,000-person tree unless you have a reason.

To iterate just the handles (cheaper when you only need to count or filter):

```python
for handle in db.iter_person_handles():
    ...
```

Counts come without iteration:

```python
db.get_number_of_people()
db.get_number_of_families()
db.get_number_of_events()
```

## Following references

![Fig. 1 — Gramps primary objects and the most-traversed relationships. Edges labelled `<Type>Ref` (e.g. `EventRef`, `CitationRef`, `MediaRef`) go through a ref object that carries metadata such as the role or relationship; bare-labelled edges are direct handle references. Notes and Tags can be attached to any primary object and are omitted to keep arrows readable. Reverse traversals — "who refers to this object?" — go through `db.find_backlink_handles()` instead of these forward links; see Backlinks below.](_media/data-model.svg)

Most addons don't visit objects in isolation — they follow the relationships between them. Gramps' object model exposes references as **handle lists** on the parent object.

Person → families they're a parent in:

```python
for family_handle in person.get_family_handle_list():
    family = db.get_family_from_handle(family_handle)
    ...
```

Person → events:

```python
for ref in person.get_event_ref_list():
    event = db.get_event_from_handle(ref.ref)
    role  = ref.get_role()
    ...
```

`event_ref` carries more than the handle — also the role (Primary, Witness, etc.) and any private flag. Read the ref, then dereference if you need the event itself.

Family → children:

```python
for child_ref in family.get_child_ref_list():
    child = db.get_person_from_handle(child_ref.ref)
    ...
```

The full handle-list / ref-list inventory per object class lives in the [Gramps API docs](https://gramps-project.org/wiki/index.php/Gramps_6.0_Developer_Reference); see also [06-api-reference](06-api-reference.md) for the addon-facing subset.

## Backlinks: who refers to this object?

The forward direction (person → events they participated in) lives on the object. The reverse direction (event → people who participated in it) lives on the database:

```python
for (obj_type, obj_handle) in db.find_backlink_handles(event.handle):
    if obj_type == "Person":
        person = db.get_person_from_handle(obj_handle)
        ...
```

`find_backlink_handles` returns `(class_name, handle)` tuples for every primary object that references the given handle. Use it for:

- Finding all sources that cite a given place
- Finding all people present at a given event
- Detecting orphaned objects (no backlinks → unreferenced)

Note that `obj_type` is the **class name as a string** (`"Person"`, `"Family"`, ...), not the Python class itself.

## Filters

For non-trivial selection (e.g. "all people born in Hamburg between 1850 and 1900"), use Gramps' filter framework rather than hand-rolling predicates:

```python
from gramps.gen.filters import GenericFilterFactory

GenericFilter = GenericFilterFactory("Person")
filt = GenericFilter()
filt.add_rule(SomeRule([arg1, arg2]))
handles = filt.apply(db, db.iter_person_handles())
```

Filters compose, cache, and integrate with the GUI's filter sidebar — a report that defines its own filter gets it as a sidebar option for free. The rule catalogue lives under `gramps.gen.filters.rules`; the user-facing counterpart is documented in [Filters](https://gramps-project.org/wiki/index.php/Gramps_6.0_Wiki_Manual_-_Filters).

## Mutating data

Write addons (mainly tools) modify data through **transactions**. The pattern is always the same:

```python
with DbTxn(_("Tool name: what it did"), db) as trans:
    person = db.get_person_from_handle(handle)
    person.set_privacy(True)
    db.commit_person(person, trans)
```

Three things matter:

1. **The transaction message is user-visible** in the Undo History. Make it descriptive and translated.
2. **Always `db.commit_<type>(obj, trans)`** after mutating — the object is a copy; commit writes it back.
3. **Group related changes** in one transaction so the user can undo as a single step.

Creating a new object follows the same shape:

```python
from gramps.gen.lib import Person, Name

with DbTxn(_("Add unknown spouse"), db) as trans:
    person = Person()
    name = Name()
    name.set_surname(surname)
    person.set_primary_name(name)
    person.gramps_id = db.find_next_person_gramps_id()
    db.add_person(person, trans)
```

`find_next_<type>_gramps_id()` allocates an unused ID; `add_<type>()` inserts and assigns the handle.

## Testing data access

Two complementary approaches:

- **Real-data tests** — load `example.gramps` (shipped with Gramps, canonical test fixture) and exercise your code against it. Best for catching real-world data quirks (cross-typed backlinks, ID normalisation, unusual character sets). See [07-testing](07-testing.md).
- **Mocked tests** — substitute the database with a stub that returns fixed objects. Best for tight unit-test loops that don't need a database on disk.

The lesson, learned the hard way: mocked DB tests can pass while the real-DB code is broken, because the mock doesn't reproduce the cross-typed backlinks and ID quirks of a populated tree. Prefer example.gramps for anything that traverses the DB; reserve mocks for pure helpers.

## Performance notes

The database API is fast enough that most addons don't need to think about performance. When you do:

- Iterating **handles** is cheaper than iterating **objects** — only dereference when you need the object's contents.
- `get_number_of_<type>()` is O(1); `len(list(db.iter_<type>()))` is O(n).
- Backlinks aren't free — they read an index but still scan it. Don't call `find_backlink_handles` in a tight inner loop.
- The 5.x → 6.0 SQLite backend is roughly comparable to BSDDB for reads, faster for writes. Avoid backend-specific assumptions; addons should work on either.

## See also

- [04-fundamentals](04-fundamentals.md) — the plugin lifecycle that wraps this DB access in
- [06-api-reference](06-api-reference.md) — the addon-facing API surface
- [07-testing](07-testing.md) — testing strategies, real-data vs mocks
- [Using database API](https://gramps-project.org/wiki/index.php/Using_database_API) — the standalone wiki reference, covers backends and internals in more depth
- [Gramps Developer Reference](https://gramps-project.org/wiki/index.php/Gramps_6.0_Developer_Reference) — the full API docs
