# Custom Filter Example
"""
Runs one of your own custom filters (from the Filters gramplet/editor) by name
using custom_filter(). Change 'example filter' to the name of a filter you've
already created; if the name doesn't match one, a warning shows up in the
Output tab instead.
"""

for person in custom_filter("example filter"):
    row(person)
