# Age At Death Histogram

ages = []
for person in people():
    age = person.age
    if age:
        ages.append(age.tuple()[0])

chart("histogram", ages, count=15)
