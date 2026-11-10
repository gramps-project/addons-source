"""Consume an internal resumable operation through its synchronous API."""


def complete(steps):
    while True:
        try:
            next(steps)
        except StopIteration as result:
            return result.value
