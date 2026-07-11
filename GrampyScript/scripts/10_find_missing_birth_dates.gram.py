# Find People Missing A Birth Date
"""
Data-quality check: list every person who has no recorded birth event, so you
can prioritize research on those records.
"""

for person in people():
    if not person.birth:
        row(person)
