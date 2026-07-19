#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Jonathan Biegert
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

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
from __future__ import annotations
import itertools
import logging

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.filters.rules.person import MatchesFilter
from gramps.gen.filters.rules import Rule

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

# -------------------------------------------------------------------------
#
# Typing modules
#
# -------------------------------------------------------------------------
from typing import List, Set
from gramps.gen.lib import Person
from gramps.gen.db import Database
from gramps.gen.types import PersonHandle

LOG = logging.getLogger(__name__)


def get_relatives(db, person):
    """
    Given a person handle, iterate all existing person handles of its
    relatives.

    adapted from IsRelatedWith.add_relative()
    """
    if person:
        for h in itertools.chain(
            # person as child
            person.get_parent_family_handle_list(),
            # person as parent
            person.get_family_handle_list(),
        ):
            family = db.get_family_from_handle(h)
            if family:
                # parents / spouse
                for parent in (family.get_father_handle(), family.get_mother_handle()):
                    if parent:
                        yield parent
                # siblings / children
                for child_ref in family.get_child_ref_list():
                    yield child_ref.ref


# -------------------------------------------------------------------------
#
# ExcludeSubtree
#
# -------------------------------------------------------------------------
class ExcludeSubtree(Rule):
    """
    Person filter rule including all persons reachable (parents/children in the same families) from the active/selected person, except those in the given filter.

    This allows to cut partial trees, e.g. exclude everything learned about my spouse but have all non-relatives in my half of the tree.
    """

    # filter rule operation
    selected_handles: Set[PersonHandle]
    filt = None  # "stop" person filter

    # external interface
    labels = [
        # rule parameters, see
        # gramps.gui.editors.filtereditor.EditRule.__init__
        # must be (label, widget class) or special string as label
        _("ID:"),  # starting person
        _("Person filter name:"),  # TODO: also allow family filter
    ]
    name = _("People reachable from <Person>, stopping at <Filter> matches")
    category = _("Relationship filters")
    description = _(
        "Matches people who are reachable starting from <Person> "
        "(walking all parents and children of attached families, "
        "recursively) stopping at persons in <Filter>."
    )

    def prepare(self, db: Database, user):
        self.reset()
        self.db = db

        if user:
            user.begin_progress(
                self.category,
                _("Retrieving all sub-filter matches"),
                db.get_number_of_people(),
            )
        try:
            # initialize search from filter parameters (passed as self.list)
            start_person = db.get_person_from_gramps_id(self.list[0])
            if start_person is None:
                return
            self.filt = MatchesFilter(self.list[1:])
            self.filt.requestprepare(db, user)

            # walk the db using a queue
            search_list: List[PersonHandle] = [start_person.handle]
            while search_list:
                current_h = search_list.pop()
                if current_h in self.selected_handles:
                    continue  # already got them
                if user:
                    user.step_progress()
                current = db.get_person_from_handle(current_h)
                if LOG.isEnabledFor(logging.DEBUG):
                    LOG.debug("tree walk arrived at id %s", current.gramps_id)
                # check stop filter
                if self.filt.apply_to_one(db, current):
                    if LOG.isEnabledFor(logging.DEBUG):
                        LOG.debug("Stopping at filter match %s", current.gramps_id)
                    continue  # stop at filter matches
                # whitelist person and add their relatives to the queue
                self.selected_handles.add(current_h)
                search_list.extend((h for h in get_relatives(db, current) if h))
            LOG.debug("Found %d filter matches", len(self.selected_handles))

        finally:
            if user:
                user.end_progress()

    def reset(self):
        self.selected_handles = set()
        if self.filt:
            self.filt.requestreset()

    def apply_to_one(self, db: Database, person: Person) -> bool:
        return person.handle in self.selected_handles
