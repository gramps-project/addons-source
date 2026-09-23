#!/usr/bin/env python3
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026      Douglas S. Blank <doug.blank@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

"""Delete every object on the live demo server tagged live_harness.TEST_TAG
-- run before a live-test session (clean slate) and after (in case a test
crashed before its own cleanup ran). See README.md."""

from live_harness import RestClient, TEST_TAG


def main():
    client = RestClient()
    found = list(client.find_test_objects())
    if not found:
        print(f"No objects tagged {TEST_TAG!r} found.")
        return
    for obj_class, handle in found:
        print(f"Deleting {obj_class} {handle}")
        client.delete_object(obj_class, handle)
    print(f"Swept {len(found)} object(s).")


if __name__ == "__main__":
    main()
