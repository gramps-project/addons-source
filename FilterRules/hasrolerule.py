#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2018  Paul Culley
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
Filter rule to match persons with a particular event.
"""
#-------------------------------------------------------------------------
#
# Standard Python modules
#
#-------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from gramps.gen.lib.eventroletype import EventRoleType
from gramps.gui.editors.filtereditor import MySelect, MyBoolean
from gramps.gen.filters.rules import Rule


class Roletype(MySelect):
    """ Provide a Role type selector """
    def __init__(self, db):
        MySelect.__init__(self, EventRoleType, db.get_event_roles())


class NoMatch(MyBoolean):
    """ Provide a negation switch """
    def __init__(self, db):
        MyBoolean.__init__(self, _("Does NOT match with selected Role"))
        self.set_tooltip_text(_("Finds the items that don't have event Roles "
                                "of the selected type."))
#-------------------------------------------------------------------------
#
# HasEvent
#
#-------------------------------------------------------------------------
class HasPersonEventRole(Rule):
    """Rule that checks for a person with a selected event role"""

    labels = [(_('Role'), Roletype),
              (_('Inverse'), NoMatch)]
    name = _('People with events with a selected role')
    description = _("Matches people with an event with a selected role")
    category = _('Event filters')

    def apply(self, dbase, person):
        if not self.list[0]:
            return False
        for event_ref in person.get_event_ref_list():
            if not event_ref:
                continue
            if self.list[1] == '1':
                if event_ref.role.xml_str() != self.list[0]:
                    return True
            else:
                if event_ref.role.xml_str() == self.list[0]:
                    return True
        return False


class HasFamilyEventRole(Rule):
    """Rule that checks for a family with a selected event role"""

    labels = [(_('Role'), Roletype),
              (_('Inverse'), NoMatch)]
    name = _('Families with events with a selected role')
    description = _("Matches families with an event with a selected role")
    category = _('Event filters')

    def apply(self, dbase, family):
        if not self.list[0]:
            return False
        for event_ref in family.get_event_ref_list():
            if not event_ref:
                continue
            if self.list[1] == '1':
                if event_ref.role.xml_str() != self.list[0]:
                    return True
            else:
                if event_ref.role.xml_str() == self.list[0]:
                    return True
        return False
