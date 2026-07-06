# Gender Breakdown (Pie Chart)

counts = counter()
for person in people():
    counts[person.gender] += 1

chart("pie", counts)
