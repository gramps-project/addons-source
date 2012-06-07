#
# Gramps - a GTK+/GNOME based genealogy program - descendant counter plugin
#
# Copyright (C) 2008,2009,2010 Reinhard Mueller, 2009 Doug Blank
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

# $Id$

"""
Display the number of a person's descendants.
"""

#------------------------------------------------------------------------
#
# Standard Python modules
#
#------------------------------------------------------------------------

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
import gen.display.name
from gen.relationship import get_relationship_calculator
from gen.simple import SimpleDoc
from gui.plug.quick import QuickTable
from TransUtils import get_addon_translator
from Utils import probably_alive
_ = get_addon_translator().ugettext

#------------------------------------------------------------------------
#
# Main report function
#
#------------------------------------------------------------------------
def run(database, document, person):

    sdoc = SimpleDoc(document)

    name = gen.display.name.displayer.display(person)
    death_date = _get_date(database, person.get_death_ref())

    sdoc.title(_("Number of %s's descendants") % name)
    sdoc.paragraph("")

    total    = []
    seen     = []
    outlived = []
    alive    = []
    handles  = []

    _count_descendants(database, person, death_date, 0,
            total, seen, outlived, alive, handles)

    # Bring all lists to the same length. No list can be longer than "total".
    while len(seen) < len(total):
        seen.append(0)
    while len(outlived) < len(total):
        outlived.append(0)
    while len(alive) < len(total):
        alive.append(0)

    rel_calc = get_relationship_calculator()

    stab = QuickTable(document)
    if death_date:
        stab.columns(
                _("Generation"),
                _("Total"),
                _("Seen"),
                _("Outlived"),
                _("Now alive"))
    else:
        stab.columns(
                _("Generation"),
                _("Total"),
                _("Now alive"))
    n = 0
    for (a, b, c, d, h) in zip(total, seen, outlived, alive, handles):
        n += 1
        generation = rel_calc.get_plural_relationship_string(0, n)
        if death_date:
            # stab.row([generation, "PersonList"] + h, a, b, c, d) # Needs 3.2
            stab.row(generation, a, b, c, d)
        else:
            # stab.row([generation, "PersonList"] + h, a, d) # Needs 3.2
            stab.row(generation, a, d)
        stab.row_sort_val(0, n)

    if death_date:
        # stab.row([_("Total"), "PersonList"] + sum(handles, []), # Needs 3.2
        stab.row(_("Total"),
                 sum(total), sum(seen), sum(outlived), sum(alive))
    else:
        # stab.row([_("Total"), "PersonList"] + sum(handles, []), # Needs 3.2
        stab.row(_("Total"),
                 sum(total), sum(alive))
    stab.row_sort_val(0, n + 1)

    stab.write(sdoc)

    if death_date:
        sdoc.paragraph(_("Seen = number of descendants whose birth %s has "
            "lived to see") % name)
        sdoc.paragraph(_("Outlived = number of descendants who died while %s "
            "was still alive") % name)


#------------------------------------------------------------------------
#
# Recursively count descendants
#
#------------------------------------------------------------------------
def _count_descendants(database, person, root_death_date, generation,
        total, seen, outlived, alive, handles):

    # "total", "seen", "outlived" and "alive" are lists with the respective
    # descendant count per generation. "handles" is a list of lists of person
    # handles per generation. These parameters are modified by this function!

    for family_handle in person.get_family_handle_list():
        family = database.get_family_from_handle(family_handle)

        for child_ref in family.get_child_ref_list():
            child = database.get_person_from_handle(child_ref.ref)

            birth_date = _get_date(database, child.get_birth_ref())
            death_date = _get_date(database, child.get_death_ref())

            # Total number of descendants.
            _increment(total, 0, 1, generation)

            # Number of descendants born during lifetime of queried person.
            if root_death_date and birth_date and \
                    birth_date.match(root_death_date, "<<"):
                _increment(seen, 0, 1, generation)

            # Number of descendants that queried person outlived.
            if root_death_date and death_date and \
                    death_date.match(root_death_date, "<<"):
                _increment(outlived, 0, 1, generation)

            # Number of descendants now alive.
            if probably_alive(child, database):
                _increment(alive, 0, 1, generation)

            # Handle to this descendant.
            _increment(handles, [], [child.handle], generation)

            _count_descendants(database, child, root_death_date, generation + 1,
                    total, seen, outlived, alive, handles)


# Helper function to increment the nth item of a list, and if necessary expand
# the length of the list to n items beforehand.
# Used for counting (startwith=0, increment=1) and for building lists
# (startwith=[], increment=[item_to_add]).
def _increment(variable, startwith, increment, generation):
    while len(variable) <= generation:
        variable.append(startwith)
    variable[generation] += increment


#------------------------------------------------------------------------
#
# Helper function to get the date of an event
#
#------------------------------------------------------------------------
def _get_date(database, event_ref):

    if not event_ref:
        return None
    event = database.get_event_from_handle(event_ref.ref)
    date = event.get_date_object()
    if not date.is_empty():
        return date
    else:
        return None
