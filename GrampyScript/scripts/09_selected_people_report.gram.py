# Report On Selected People
"""
List just the people currently selected (highlighted) in the People view.
Select some rows in the People view before running this script.
"""

for person in selected("Person"):
    row(person)
