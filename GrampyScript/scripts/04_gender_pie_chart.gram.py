# Gender Breakdown (Pie Chart)
"""
Count how many people are male, female, or of unknown gender, then draw a pie
chart of the totals. Check the Chart tab after running.
"""

counts = counter()
for person in people():
    counts[person.gender] += 1

chart("pie", counts)
