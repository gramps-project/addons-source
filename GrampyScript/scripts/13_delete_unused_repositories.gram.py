# Delete Unused Repositories (Delete Example)
"""
Demonstrates delete(): removes any Repository record that nothing else in the
tree refers to. Most trees have no unused repositories, so this is unlikely to
actually delete anything — it's meant to show the pattern, wrapped in
begin_changes()/end_changes() as a single undoable transaction.
"""

begin_changes("Delete unused repositories")

count = 0
for repository in repositories():
    if not repository.back_references:
        delete(repository)
        count += 1

end_changes()
print("Deleted %d unused repositories" % count)
