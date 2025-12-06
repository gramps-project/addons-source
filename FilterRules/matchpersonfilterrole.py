#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2002-2006  Donald N. Allingham
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
from gramps.gen.const import GRAMPS_LOCALE as glocale

_ = glocale.translation.gettext

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules import MatchesFilterBase


# -------------------------------------------------------------------------
#
# Typing modules
#
# -------------------------------------------------------------------------
from gramps.gen.lib import Event
from gramps.gen.db import Database
from gramps.gen.lib.eventroletype import EventRoleType
from gramps.gui.editors.filtereditor import MySelect


class Roletype(MySelect):
    """Provide a Role type selector"""

    def __init__(self, db):
        MySelect.__init__(self, EventRoleType, db.get_event_roles())


# -------------------------------------------------------------------------
#
# MatchesFilter
#
# -------------------------------------------------------------------------
class MatchesPersonFilterRole(MatchesFilterBase):
    """
    Rule that checks against another filter.
g
    This is a base rule for subclassing by specific objects.
    Subclasses need to define the namespace class attribute.

    """

    labels = [_("Person filter name:"), _("Include Family events:"), (_('Role:'), Roletype)]
    name = _("Events of persons matching the <person filter>")
    description = _(
        "Matches events of persons matched by the specified " "person filter name"
    )
    category = _("General filters")

    # we want to have this filter show person filters
    namespace = "Person"

    def prepare(self, db: Database, user):
        MatchesFilterBase.prepare(self, db, user)

        try:
            if int(self.list[1]):
                self.MPF_famevents = True
            else:
                self.MPF_famevents = False
        except IndexError:
            self.MPF_famevents = False

    def apply_to_one(self, db: Database, event: Event) -> bool:
        filt = self.find_filter()
        if filt:
            for classname, handle in db.find_backlink_handles(event.handle, ["Person"]):
                person = db.method("get_%s_from_handle", classname)(handle)
                if filt.apply_to_one(db, person):
                    if self.list[2]:
                        for event_ref in person.get_event_ref_list():
                            if not event_ref:
                                continue
                            if event.handle in event_ref.get_reference_handle():
                                return event_ref.role.xml_str() == self.list[2]
                        return False
                    return True
            if self.MPF_famevents:
                # also include if family event of the person
                for classname, handle in db.find_backlink_handles(
                    event.handle, ["Family"]
                ):
                    family = db.get_family_from_handle(handle)
                    if family:
                        if family.father_handle:
                            father = db.get_person_from_handle(family.father_handle)
                            if father and filt.apply_to_one(db, father):
                                return True

                        if family.mother_handle:
                            mother = db.get_person_from_handle(family.mother_handle)
                            if mother and filt.apply_to_one(db, mother):
                                return True

        return False

