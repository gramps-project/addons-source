#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020  Paul Culley
# Copyright (C) 2020  Matthias Kemmer
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

"""Filter rule to match persons in a matching family."""

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gui.editors.filtereditor import MyBoolean, MyFilters
from gramps.gen.filters.rules._matchesfilterbase import MatchesFilterBase
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

# These globals are the only easy way I could think of to communicate between
# checkboxes to make sure at least one was selected.
child_state = True  # used to indicate state of checkbox
parent_state = True


class IncChildren(MyBoolean):
    """Include children."""

    def __init__(self, db):
        MyBoolean.__init__(self, _("Include Children"))
        self.set_tooltip_text(_("Include the children in the matching"
                                " families."))
        self.connect("toggled", self.toggled)
        self.set_active(True)

    def toggled(self, widget):
        """Make sure user doesn't get to turn off both children and parents."""
        if not parent_state:
            if not widget.get_active():
                widget.set_active(True)
        global child_state
        child_state = widget.get_active()
        # print("child:", child_state)

    def set_text(self, val):
        """Set the selector state to display the passed value."""
        is_active = bool(int(val))
        self.set_active(is_active)
        global child_state
        child_state = is_active


class IncParents(MyBoolean):
    """Provide a negation switch."""

    def __init__(self, db):
        MyBoolean.__init__(self, _("Include Parents"))
        self.set_tooltip_text(_("Include the parents in the matching"
                                " families."))
        self.connect("toggled", self.toggled)
        self.set_active(True)

    def toggled(self, widget):
        """Make sure user doesn't get to turn off both children and parents."""
        if not child_state:
            if not widget.get_active():
                widget.set_active(True)
        global parent_state
        parent_state = widget.get_active()
        # print("parent:", parent_state)

    def set_text(self, val):
        """Set the selector state to display the passed value."""
        is_active = bool(int(val))
        self.set_active(is_active)
        global parent_state
        parent_state = is_active


class FamFilt(MyFilters):
    """Add custom family filter selector."""

    # This is a horrible hack that is needed because the filtereditor doesn't
    # have support for a 'Family Filter name' selector. So we have to make our
    # own. Furthermore, we don't have the needed reference to the 'filterdb',
    # the list of custom filters.
    def __init__(self, db):
        import inspect
        stack = inspect.stack()  # our stack frame
        caller_locals = stack[1][0].f_locals  # locals from caller
        # the caller has an attribute 'filterdb' which has what we need
        MyFilters.__init__(self,
                           caller_locals["filterdb"].get_filters('Family'))


# -------------------------------------------------------------------------
#
# Person part of matching family
#
# -------------------------------------------------------------------------
class PersonsInFamilyFilterMatch(MatchesFilterBase):
    """Rule that checks for a person with a selected event role."""

    labels = [(_('Family Filter name:'), FamFilt),
              (_('Include Children'), IncChildren),
              (_('Include Parents'), IncParents)]
    name = _('People who are part of families matching <filter>')
    description = _("People who are part of families matching <filter>")
    category = _('General filters')
    # we want to have this filter show family filters
    namespace = 'Family'

    def prepare(self, db, user):
        """Prepare a reference list for the filter."""
        self.persons = set()
        MatchesFilterBase.prepare(self, db, user)
        self.MFF_filt = self.find_filter()
        if self.MFF_filt:
            for family_handle in db.iter_family_handles():
                if self.MFF_filt.check(db, family_handle):
                    family = db.get_family_from_handle(family_handle)
                    if bool(int(self.list[2])):
                        father = family.get_father_handle()
                        mother = family.get_mother_handle()
                        self.persons.add(father)
                        self.persons.add(mother)
                    if bool(int(self.list[1])):
                        for child_ref in family.get_child_ref_list():
                            self.persons.add(child_ref.ref)

    def apply(self, _db, obj):
        """
        Return True if a person appies to the filter rule.

        :returns: True or False
        """
        if obj.get_handle() in self.persons:
            return True
        return False
