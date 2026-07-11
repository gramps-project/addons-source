# List All People
"""
Iterate over every person in the database and show their Gramps ID, given name,
surname, and gender in the results table.
"""

for person in people():
    row(
        person,
        person.gender,
        person.age,
    )
