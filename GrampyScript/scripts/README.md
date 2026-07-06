# Gram.py Script examples

This folder ships with the GrampyScript addon and doubles as the default
folder for Script > Open... and Script > Save as... in the gramplet. The
numbered files below are examples; anything else you save here is yours.

| File | Description |
| --- | --- |
| `01_list_people.gram.py` | List every person with ID, given name, surname, and gender. |
| `02_filter_by_surname.gram.py` | List only people whose surname matches a given value. |
| `03_family_overview.gram.py` | List every family with father, mother, and child count. |
| `04_gender_pie_chart.gram.py` | Pie chart of the gender breakdown of everyone in the tree. |
| `05_age_histogram.gram.py` | Histogram of age at death, for people with both birth and death recorded. |
| `06_mark_unsourced_people_private.gram.py` | Batch-edit example: mark people with no citations as private. |
| `07_csv_ready_report.gram.py` | Tabular report meant to be exported via Data > Save as CSV. |
| `08_active_person_summary.gram.py` | Summary of the active person plus their parents, spouse, and children. |
| `09_selected_people_report.gram.py` | Report on just the rows currently selected in the People view. |
| `10_find_missing_birth_dates.gram.py` | Data-quality check: people with no recorded birth event. |

Each script's title and description are also shown as a preview when you
highlight it in the Open dialog.

**Note:** addon updates only overwrite files that share a name with
something in the released package. It's safe to save your own scripts in
this folder under any other name — just avoid editing the numbered
examples above in place, since a future addon update could overwrite those
edits.
