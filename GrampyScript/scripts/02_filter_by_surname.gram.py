# Filter By Surname
"""
List only the people whose surname matches a given value — a starting point for
narrowing any report down by a condition.
"""

TARGET_SURNAME = "Smith"

for person in people():
    if person.surname.surname == TARGET_SURNAME:
        row(person.gramps_id, person.name.first_name, person.surname.surname)
