# Births Per Decade (Import Example)

from script_helpers import decade

columns("Decade", "Births")

counts = counter()
for person in people():
    birth = person.birth
    if birth:
        year = birth.get_date_object().get_year()
        if year:
            counts[decade(year)] += 1

for decade_start, count in sorted(counts.items()):
    row("%ds" % decade_start, count)
