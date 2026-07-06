# Mark Unsourced People As Private
"""
Batch-edit example: find every person who has no citations attached and flag
them as private, wrapped in begin_changes()/end_changes() so the edits happen
inside a single, undoable transaction.
"""

begin_changes("Mark unsourced people as private")

count = 0
for person in people():
    if len(person.citations) == 0 and not person.private:
        person.private = True
        count += 1

end_changes()
print("Marked %d people as private" % count)
