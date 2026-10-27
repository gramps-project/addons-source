#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009 Doug Blank <doug.blank@gmail.com>
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
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""
Deep Connections search, independent of any user interface.

Finds chains of family links (spouse, parent, child, sibling and, optionally,
associations and person links in notes) between two people.  This module has
no GTK or Gramps GUI dependencies: it only calls the read methods of a Gramps
database (``get_person_from_handle``, ``get_family_from_handle`` and
``get_note_from_handle``), so it can run headless, for example in a web
server.  Anything a database returns as ``None`` (missing or hidden by a
privacy proxy) is never passed through.

A path is a linked list of nodes ``(previous_node, step)``.  The step of a
node says how that node's person relates to the person of ``previous_node``,
so a path read from the found person back to the root reads like
"A is the sibling of B, who is a parent of C, ...".  The root node is
``(None, Step(SELF, start_handle))``.
"""

from collections import deque
from typing import NamedTuple, Optional, Tuple

# Relation keys.  They are not translated; a user interface maps them to
# display text.  They are gender-neutral: a family's father and mother
# slots say nothing reliable about gender, so the wording ("father",
# "wife", ...) is chosen from the person's own recorded gender.
SELF = "self"
CHILD = "child"
SPOUSE = "spouse"
SIBLING = "sibling"
PARENT = "parent"
ASSOCIATION = "association"
NOTE = "note"


class Step(NamedTuple):
    """One step of a path: ``handle``'s person is ``relation`` of the next."""

    # One of the relation keys above.
    relation: str
    # The person this step is anchored to (the person the relation is to).
    handle: str
    # The parents of the family the step went through, if any.
    parents: Tuple[Optional[str], ...] = ()
    # Extra text, e.g. the description of an association.
    detail: str = ""


def get_links_from_notes(db, obj, path, person_handle):
    """
    Get anyone mentioned in any note attached to this object.
    """
    retval = []
    for note_handle in obj.get_note_list():
        note = db.get_note_from_handle(note_handle)
        if note:
            for link in note.get_links():
                if link[0] == "gramps" and link[1] == "Person":
                    if link[2] == "handle":
                        retval += [(link[3], (path, Step(NOTE, person_handle)))]
    return retval


def get_relatives(
    db,
    person_handle,
    path,
    start_handle=None,
    follow_associations=True,
    follow_notes=True,
):
    """
    Gets all of the relations of person_handle, as ``(handle, path)`` pairs.

    When ``start_handle`` (the start person) is given, the start person is
    kept out of the body of every produced path (issue 8653) -- see the
    post-processing at the end of this function.
    """
    retval = []
    person = db.get_person_from_handle(person_handle)
    if person is None:
        return []
    for family_handle in person.get_family_handle_list():
        family = db.get_family_from_handle(family_handle)
        if family:
            husband = family.get_father_handle()
            wife = family.get_mother_handle()
            retval.extend(
                (child_ref.ref, (path, Step(CHILD, person_handle, (husband, wife))))
                for child_ref in family.get_child_ref_list()
            )
            if husband and husband != person_handle:
                retval += [(husband, (path, Step(SPOUSE, person_handle)))]
            if wife and wife != person_handle:
                retval += [(wife, (path, Step(SPOUSE, person_handle)))]
            if follow_notes:
                retval += get_links_from_notes(db, family, path, person_handle)

    for family_handle in person.get_parent_family_handle_list():
        family = db.get_family_from_handle(family_handle)
        if family:
            husband = family.get_father_handle()
            wife = family.get_mother_handle()
            retval.extend(
                (
                    child_ref.ref,
                    (path, Step(SIBLING, person_handle, (husband, wife))),
                )
                for child_ref in family.get_child_ref_list()
                if child_ref.ref != person_handle
            )
            if husband and husband != person_handle:
                retval += [(husband, (path, Step(PARENT, person_handle, (wife,))))]
            if wife and wife != person_handle:
                retval += [(wife, (path, Step(PARENT, person_handle, (husband,))))]
            if follow_notes:
                retval += get_links_from_notes(db, family, path, person_handle)

    if follow_associations:
        for assoc in person.get_person_ref_list():
            retval += [
                (
                    assoc.get_reference_handle(),
                    (
                        path,
                        Step(ASSOCIATION, person_handle, detail=assoc.get_relation()),
                    ),
                )
            ]

    if follow_notes:
        retval += get_links_from_notes(db, person, path, person_handle)

    # Issue 8653: the start person is the search origin, so it may appear in a
    # produced path only as its terminal "self" root -- never as, nor as the
    # anchor of, an intermediate relationship step.  Two cases, applied only
    # once the caller has supplied the start handle:
    #   * drop a relative that *is* the start person, so the origin is never
    #     re-entered as an interior node of a path; and
    #   * when the start person itself is being expanded, attach its
    #     relatives straight to the root node (``path`` is that root here)
    #     instead of through a redundant "(relation, start)" step that would
    #     render the start person mid-path (the reporter's
    #     "... / sibling of <Home>" chain).
    if start_handle is not None:
        retval = [item for item in retval if item[0] != start_handle]
        if person_handle == start_handle:
            retval = [(item[0], path) for item in retval]
    return retval


def path_depth(path):
    """Calculate the depth of a relationship path."""
    depth = 0
    while path[0] is not None:
        depth += 1
        path = path[0]
    return depth


def path_steps(path):
    """
    Return the steps of a path as a list, from the found person's step back
    to the root ``SELF`` step.
    """
    steps = []
    while path is not None:
        steps.append(path[1])
        path = path[0]
    return steps


class ConnectionSearch:
    """
    Breadth-first search for paths from a start person to a target person.

    Iterate over :meth:`steps` to run the search one person at a time; a user
    interface can update its display between steps.  Use
    :func:`find_connections` to get only the paths.
    """

    def __init__(
        self,
        db,
        start_handle,
        target_handle,
        follow_associations=True,
        follow_notes=True,
    ):
        self.db = db
        self.start_handle = start_handle
        self.target_handle = target_handle
        self.follow_associations = follow_associations
        self.follow_notes = follow_notes
        self.people_processed = 0
        self.depth = 0
        self.queue = deque([(start_handle, (None, Step(SELF, start_handle)))])
        self.visited = set()
        # Everyone ever queued.  A person already queued would only be
        # skipped when popped again, so queuing them twice is wasted work.
        self.queued = {start_handle}

    @property
    def queue_size(self):
        """Number of people waiting to be processed."""
        return len(self.queue)

    def steps(self):
        """
        Run the search, yielding after each person is processed.

        Yields the path to the target each time one is found, and ``None``
        after each other person is expanded.  Paths are yielded in
        breadth-first order, so shorter paths come first.
        """
        while self.queue:
            current_handle, current_path = self.queue.popleft()
            self.people_processed += 1

            if current_handle == self.target_handle:
                yield current_path
                # The target is the search *target*, not a waypoint:
                # expanding it would feed its own relatives back into the
                # queue, which then re-reach the target and re-emit the
                # connection just reported -- the "same path returned every
                # time you press Continue" of issue 10628.  Skip straight to
                # the next queued candidate so each path is a genuinely
                # different connection; the distinct paths other relatives
                # already queued before the target was found are still
                # reported.
                continue
            if current_handle in self.visited:
                continue

            self.visited.add(current_handle)
            relatives = get_relatives(
                self.db,
                current_handle,
                current_path,
                self.start_handle,
                self.follow_associations,
                self.follow_notes,
            )

            if current_path[0] is not None:
                self.depth = max(self.depth, path_depth(current_path))

            for person_handle, path in relatives:
                if person_handle is None:
                    continue
                # The target is queued once per path to it, so each
                # different connection is still reported.
                if person_handle != self.target_handle:
                    if person_handle in self.queued:
                        continue
                    self.queued.add(person_handle)
                self.queue.append((person_handle, path))

            yield None


def find_connections(
    db,
    start_handle,
    target_handle,
    max_paths=None,
    max_people=None,
    follow_associations=True,
    follow_notes=True,
):
    """
    Yield paths from the start person to the target person.

    Stops after ``max_paths`` paths or after ``max_people`` people have been
    processed, whichever comes first (``None`` means no limit).
    """
    search = ConnectionSearch(
        db, start_handle, target_handle, follow_associations, follow_notes
    )
    found = 0
    for path in search.steps():
        if path is not None:
            yield path
            found += 1
            if max_paths is not None and found >= max_paths:
                return
        if max_people is not None and search.people_processed >= max_people:
            return
