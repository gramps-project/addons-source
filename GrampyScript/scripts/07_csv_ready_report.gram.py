# CSV-Ready People Report

columns("ID", "Given Name", "Surname", "Gender", "Birth Year")

for person in people():
    birth = person.birth
    birth_year = birth.get_date_object().get_year() if birth else ""
    row(
        person.gramps_id,
        person.name.first_name,
        person.surname.surname,
        person.gender,
        birth_year,
    )
