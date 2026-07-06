# Delete Unused Repositories (Delete Example)

begin_changes("Delete unused repositories")

count = 0
for repository in repositories():
    if not repository.back_references:
        delete(repository)
        count += 1

end_changes()
print("Deleted %d unused repositories" % count)
