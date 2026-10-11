# Filter By Surname
"""
List only the people whose surname matches a given value — a starting point for
narrowing any report down by a condition. The condition is a where= query, so
the database finds the matches instead of the script checking every person.
"""

TARGET_SURNAME = "Smith"

for person in people(where="surname == %r" % TARGET_SURNAME, limit=None):
    row(person.gramps_id, person.name.first_name, person.surname.surname)
