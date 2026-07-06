# Active Person Summary

person = active_person
if person:
    row(person)
    for parent in person.parents:
        row(parent)
    if person.spouse:
        row(person.spouse)
    for child in person.children:
        row(child)
else:
    print("No active person is set.")
