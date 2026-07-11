# CSV-Ready People Report
"""
Build a simple tabular report — ID, name, gender, birth year — for every
person. Once it runs, use Data > Save as CSV or Copy to clipboard to export the
Table tab's contents.
"""

columns("Person", "Gender", "Birth Year")

for person in people():
    birth = person.birth
    birth_year = birth.get_date_object().get_year() if birth else ""
    row(
        person,
        person.gender,
        birth_year,
    )
