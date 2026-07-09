# Age At Death Histogram
"""
For everyone with both a birth and a death event recorded, compute their age in
whole years and draw a histogram of the distribution. Check the Chart tab after
running.
"""

ages = []
for person in people():
    age = person.age
    if age:
        ages.append(age.tuple()[0])

chart("histogram", ages, count=15)
