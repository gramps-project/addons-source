# Family Overview

for family in families():
    row(family.gramps_id, family.father, family.mother, len(family.children))
