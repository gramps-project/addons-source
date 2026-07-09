# Births Per Decade (Import Example)
"""
Counts births by decade, using a decade() function imported from
script_helpers.py in this same folder — a template for sharing helper code
between your own scripts with a plain 'import' statement.
"""

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
