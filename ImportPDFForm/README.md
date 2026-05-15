# ImportPDF — Gramps Addon

Import genealogy data from a filled-in **Ahnentafel pedigree PDF form**.

The workflow is simple:

1. Print or email the bundled PDF template to a relative.
2. They fill in names, dates, and places using any PDF viewer.
3. They send it back to you.
4. You import it into Gramps with **File → Import**, selecting the `.pdf` file.

---

## The Template

The bundled file `pedigree_AboutGenealogy_FillableForm.pdf` is a standard
4-generation pedigree chart with fillable form fields.  Send it to anyone
whose family line you want to capture.

---

## Pedigree Structure

The chart uses **Ahnentafel numbering**: the subject is person 1, their
father is 2, their mother is 3, and each person's parents are at positions
2n (father) and 2n+1 (mother).

```
                                              ┌──  8  Gr-Gr-Father (pat.)
                              ┌──  4  GrFath ─┤
                              │               └──  9  Gr-Gr-Mother (pat.)
              ┌──  2  Father ─┤
              │               │               ┌── 10  Gr-Gr-Father
              │               └──  5  GrMoth ─┤
              │                               └── 11  Gr-Gr-Mother
1  Self ──────┤
  │           │                               ┌── 12  Gr-Gr-Father
Spouse        │               ┌──  6  GrFath ─┤
              │               │               └── 13  Gr-Gr-Mother
              └──  3  Mother ─┤
                              │               ┌── 14  Gr-Gr-Father
                              └──  7  GrMoth ─┤
                                              └── 15  Gr-Gr-Mother
```

The **Spouse** field (person 1's partner) is outside the Ahnentafel scheme —
they are not an ancestor of person 1.  Only a name is collected for the
spouse; no birth, death, or place fields exist for them in the form.

### PDF Field Names

Each person maps to a set of PDF form fields:

| Person | Name field   | Birth     | Birthplace     | Death     | Deathplace     | Marriage† | Marriage place† |
|--------|-------------|-----------|----------------|-----------|----------------|-----------|-----------------|
| 1 Self | `Name`      | `Birth1`  | `BirthPlace1`  | `Death1`  | `DeathPlace1`  | `Marriage1` | `MarriagePlace1` |
| Spouse | `Spouse`    | —         | —              | —         | —              | —         | —               |
| 2 Father | `Father2` | `Birth2`  | `BirthPlace2`  | `Death2`  | `DeathPlace2`  | `Marriage2` | `MarriagePlace2` |
| 3 Mother | `Mother3` | `Birth3`  | `BirthPlace3`  | `Death3`  | `DeathPlace3`  | —         | —               |
| 4 FF   | `Father4`   | `Birth4`  | `BirthPlace4`  | `Death4`  | `DeathPlace4`  | `Marriage4` | `MarriagePlace4` |
| 5 FM   | `Mother5`   | `Birth5`  | `BirthPlace5`  | `Death5`  | `DeathPlace5`  | —         | —               |
| 6 MF   | `Father6`   | `Birth6`  | `BirthPlace6`  | `Death6`  | `DeathPlace6`  | `Marriage6` | `MarriagePlace6` |
| 7 MM   | `Mother7`   | `Birth7`  | `BirthPlace7`  | `Death7`  | `DeathPlace7`  | —         | —               |
| 8–15   | `Father{n}` / `Mother{n}` | `Birth{n}` | `BirthPlace{n}` | `Death{n}` | `DeathPlace{n}` | `Marriage{n}`‡ | `MarriagePlace{n}`‡ |

† Marriage date and place describe the **couple** formed by this person and
  their partner.  They are stored on the father's (even-numbered) fields only.  
‡ Only for even-numbered persons 8, 10, 12, 14.

---

## Handling Partial Forms

Not every relative will fill in every generation.  The importer handles
missing data gracefully.

### Filled leaf — no gap

If a person is filled in but their ancestors are all blank, they are imported
as an unconnected individual.  No Unknown placeholders are created above them.

```
  Known:  1, 2
  Blank:  4, 5

              ┌── 4 (blank — no ancestor above 2, so nothing added)
  1 ◄── 2 ───┤
              └── 5 (blank)

  Imported: 1 and 2, linked as parent/child.
```

### Gap in the middle — Unknown inserted

If a known grandparent is present but the connecting parent is blank, the
importer detects the gap and inserts an **Unknown** placeholder to preserve
the chain.

```
  Known:  1, 4
  Blank:  2, 3, 5

                              ┌── 4 (known — has a known descendant: 1)
  1 ◄── 2 [Unknown] ◄─────── ┤
                              └── 5 (blank — no ancestors known above 5)

  Imported: 1, 4, and an Unknown male for 2.
  Chain:    4 → 2 [Unknown] → 1
```

Person 5 (the mother at that generation) is **not** added as Unknown because
she has no known ancestors above her — she would be a dangling leaf, not a
bridge between two known people.

### One side of a couple always missing

The form only collects the spouse's name — no birth, death, or place data.
When person 3 (mother) is absent but person 6 (her father) is known, person
3 is added as Unknown (bridging 6 to 1), but person 7 (her mother, with no
ancestors in the chart) is left out:

```
  Known:  1, 3, 6
  Blank:  2, 7

              ┌── 2 (blank — no ancestors on paternal side)
  1 ◄─────── ┤
              └── 3 ◄── 6 (known)
                   └── 7 (blank — no ancestors above, not added)

  Imported: 1, 3, 6.  Family: 6 → 3 → 1 (7 absent, family has one parent).
```

### Multiple gaps

The algorithm works across all four generations.  Each missing step on a
path between two known people gets its own Unknown placeholder.

```
  Known:  1, 8
  Blank:  2, 4

                              ┌── 8 (known)
  1 ◄── 2 [?] ◄── 4 [?] ◄── ┤
                              └── 9 (blank — no ancestors, not added)

  Unknowns inserted: 2 (male), 4 (male)
  Chain: 8 → 4 [Unknown] → 2 [Unknown] → 1
```

---

## Name and Date Formats

Name fields accept two formats (matching the DataEntryGramplet convention):

| Input | Firstname | Surname |
|-------|-----------|---------|
| `John Henry Smith` | `John Henry` | `Smith` |
| `Smith, John Henry` | `John Henry` | `Smith` |
| `Smith` | *(blank)* | `Smith` |

You can also pre-fill a name field with an existing Gramps person ID
(`[I0023]`) to link to that record instead of creating a new person.

Date fields accept the full Gramps date format, the same as the
DataEntryGramplet and the rest of Gramps:

| Input | Meaning |
|-------|---------|
| `15 Mar 1970` | exact date |
| `abt 1970` | about 1970 |
| `bef 1970` | before 1970 |
| `aft 1970` | after 1970 |
| `bet 1965 and 1970` | between 1965 and 1970 |

---

## Requirements

- **Gramps 6.0** or later
- **pypdf** Python package (`pip install pypdf`)

---

## Files

| File | Purpose |
|------|---------|
| `ImportPDF.gpr.py` | Plugin registration |
| `importpdf.py` | Importer logic |
| `pedigree_AboutGenealogy_FillableForm.pdf` | Fillable template to send to relatives |
