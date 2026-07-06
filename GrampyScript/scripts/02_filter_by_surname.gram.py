# Filter By Surname

TARGET_SURNAME = "Smith"

for person in people():
    if person.surname.surname == TARGET_SURNAME:
        row(person.gramps_id, person.name.first_name, person.surname.surname)
