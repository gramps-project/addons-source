#
# KinshipSort - biological kinship sorting for Gramps
# Copyright (C) 2026 Jacek Kuznia <jacek.kuznia@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <https://www.gnu.org/licenses/>.
#

"""Biological kinship calculation, independent of Gramps and GTK."""

# ------------------------------------------------------------------------
# Standard Python modules
# ------------------------------------------------------------------------
from collections import deque
from heapq import heappop, heappush
from itertools import count


def _ancestor_distances(home_handle, parents):
    """Return minimum upward distance from Home Person to every ancestor.

    The Home Person is included at distance 0.  Distances are counted only
    through biological parent relations.
    """
    distances = {home_handle: 0}
    queue = deque([home_handle])

    while queue:
        handle = queue.popleft()
        next_distance = distances[handle] + 1

        for parent_handle in parents.get(handle, ()):
            old = distances.get(parent_handle)
            if old is None or next_distance < old:
                distances[parent_handle] = next_distance
                queue.append(parent_handle)

    return distances


def calculate_kinship_from_relations(home_handle, parents, children):
    """Return ``(degrees, generations)`` using one multi-source traversal.

    First we calculate every biological ancestor of Home and the minimum
    upward distance to that ancestor.  All of those ancestors then become
    sources of one shared downward search.

    A state contains two values for a person:

    * ``degree``: upward distance from Home to the selected common ancestor
      plus downward distance from that ancestor to the person;
    * ``generation``: upward distance minus downward distance.

    States are ordered first by the smallest degree.  If two equally short
    valid common-ancestor paths reach the same person, the path with the
    highest generation level is retained, matching the previous deterministic
    sorting rule.

    Because traversal after seeding goes only downward through biological
    child links, an invalid path such as ``Home -> child -> other parent`` can
    never occur.

    Unlike the previous implementation, descendants are not re-scanned once
    for every ancestor.  Each useful state is propagated through the graph
    only when it improves the best known result.
    """
    ancestor_distances = _ancestor_distances(home_handle, parents)

    # handle -> (minimum degree, preferred generation for that degree)
    best = {}
    queue = []
    # Equal-cost entries may include opaque markers for unrecorded parents.
    # A sequence number avoids comparing markers with real person handles.
    sequence = count()

    # Variable source costs mean an ordinary FIFO multi-source BFS is not
    # sufficient.  A small Dijkstra-style priority queue gives the same exact
    # result while processing all ancestor sources together.
    for ancestor_handle, up_distance in ancestor_distances.items():
        candidate = (up_distance, up_distance)
        old = best.get(ancestor_handle)
        if (
            old is None
            or candidate[0] < old[0]
            or (candidate[0] == old[0] and candidate[1] > old[1])
        ):
            best[ancestor_handle] = candidate
            heappush(queue, (up_distance, -up_distance,
                            next(sequence), ancestor_handle))

    while queue:
        degree, negative_generation, _, handle = heappop(queue)
        generation = -negative_generation

        # Ignore an entry that became obsolete after a better path was found.
        if best.get(handle) != (degree, generation):
            continue

        child_degree = degree + 1
        child_generation = generation - 1

        for child_handle in children.get(handle, ()):
            old = best.get(child_handle)
            if (
                old is None
                or child_degree < old[0]
                or (child_degree == old[0] and child_generation > old[1])
            ):
                best[child_handle] = (child_degree, child_generation)
                heappush(
                    queue,
                    (child_degree, -child_generation, next(sequence), child_handle),
                )

    degrees = {handle: values[0] for handle, values in best.items()}
    generations = {handle: values[1] for handle, values in best.items()}
    return degrees, generations
