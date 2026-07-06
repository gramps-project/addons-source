# List All People

for person in people():
    row(
        person.gramps_id,
        person.name.first_name,
        person.surname.surname,
        person.gender,
    )
