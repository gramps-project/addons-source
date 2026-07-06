# Find People Missing A Birth Date

for person in people():
    if not person.birth:
        row(person.gramps_id, person.name.first_name, person.surname.surname)
