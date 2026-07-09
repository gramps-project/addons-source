# Family Overview
"""
List every family together with the father, the mother, and how many children
they have — a quick way to spot families that look incomplete.
"""

for family in families():
    row(family.gramps_id, family.father, family.mother, len(family.children))
