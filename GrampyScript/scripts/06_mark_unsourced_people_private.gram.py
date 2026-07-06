# Mark Unsourced People As Private

begin_changes("Mark unsourced people as private")

count = 0
for person in people():
    if len(person.citations) == 0 and not person.private:
        person.private = True
        count += 1

end_changes()
print("Marked %d people as private" % count)
