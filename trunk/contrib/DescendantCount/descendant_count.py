#
# Gramps - a GTK+/GNOME based genealogy program - descendant counter plugin
#
# Copyright (C) 2008, 2009 Reinhard Mueller
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
from TransUtils import get_addon_translator
_ = get_addon_translator().ugettext
import operator

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gen.display.name import displayer as name_displayer
from Simple import SimpleDoc, SimpleTable
from gen.plug import CATEGORY_QR_PERSON
from Utils import probably_alive
from gen.plug import PluginManager

#------------------------------------------------------------------------
#
# Main report function
#
#------------------------------------------------------------------------
def run(database, document, person):

    sdoc = SimpleDoc(document)

    name = name_displayer.display(person)
    death_date = _get_date(database, person.get_death_ref())

    sdoc.title(_("Number of %s's descendants") % name)
    sdoc.paragraph("")

    total    = []
    seen     = []
    survived = []
    alive    = []
    handles  = {}

    _count_descendants(database, person, death_date, 0,
            total, seen, survived, alive, handles)

    # Bring all lists to the same length. No list can be longer than "total".
    while len(seen) < len(total):
        seen.append(0)
    while len(survived) < len(total):
        survived.append(0)
    while len(alive) < len(total):
        alive.append(0)

    rel_calc = PluginManager.get_instance().get_relationship_calculator()

    stab = SimpleTable(document)
    if death_date:
        stab.columns(
                _("Generation"),
                _("Total"),
                _("Seen"),
                _("Survived"),
                _("Now alive"))
    else:
        stab.columns(
                _("Generation"),
                _("Total"),
                _("Now alive"))
    n = 0
    for (a, b, c, d) in zip(total, seen, survived, alive):
        n += 1
        if death_date:
            stab.row([rel_calc.get_plural_relationship_string(0, n), 
                      "PersonList"] + handles.get(n-1, []), a, b, c, d)
        else:
            stab.row([rel_calc.get_plural_relationship_string(0, n), 
                      "PersonList"] + handles.get(n-1, []), a, d)
        stab.row_sort_val(0, n)

    if death_date:
        stab.row([_("Total"), "PersonList"] + reduce(operator.add, handles.values(), []),
                 sum(total), sum(seen), sum(survived), sum(alive))
    else:
        stab.row([_("Total"), "PersonList"] + reduce(operator.add, handles.values(), []),
                 sum(total), sum(alive))
    stab.row_sort_val(0, n+1)

    stab.write(sdoc)

    if death_date:
        sdoc.paragraph(_("Seen = number of descendants whose birth %s has "
            "lived to see") % name)
        sdoc.paragraph(_("Survived = number of descendants who died while %s "
            "was still being alive") % name)


#------------------------------------------------------------------------
#
# Recursively count descendants
#
#------------------------------------------------------------------------
def _count_descendants(database, person, root_death_date, generation,
        total, seen, survived, alive, handles):

    # "total", "seen", "survived" and "alive" are lists with the respective
    # descendant count per generation. These parameters are modified by this
    # function!

    for family_handle in person.get_family_handle_list():
        family = database.get_family_from_handle(family_handle)

        for child_ref in family.get_child_ref_list():
            child = database.get_person_from_handle(child_ref.ref)

            birth_date = _get_date(database, child.get_birth_ref())
            death_date = _get_date(database, child.get_death_ref())

            # Total number of descendants.
            _increment(total, generation, handles, child.handle)

            # Number of descendants born during lifetime of queried person.
            if root_death_date and birth_date and \
                    birth_date.match(root_death_date, "<<"):
                _increment(seen, generation)

            # Number of descendants that queried person survived.
            if root_death_date and death_date and \
                    death_date.match(root_death_date, "<<"):
                _increment(survived, generation)

            # Number of descendants now alive.
            if probably_alive(child, database):
                _increment(alive, generation)

            _count_descendants(database, child, root_death_date, generation + 1,
                    total, seen, survived, alive, handles)


# Helper function to increment the nth item of a list, and if necessary expand
# the length of the list to n items beforehand.
def _increment(variable, generation, handles=None, handle=None):
    while len(variable) <= generation:
        variable.append(0)
    variable[generation] += 1
    if handles is not None:
        handles[generation] = handles.get(generation, []) + [handle]


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


#------------------------------------------------------------------------
#
# Register the report
#
#------------------------------------------------------------------------
PluginManager.get_instance().register_quick_report(
    name = 'descendant_count',
    category = CATEGORY_QR_PERSON,
    run_func = run,
    translated_name = _("Descendant count"),
    status = _("Stable"),
    description= _("Displays the number of a person's descendants"),
    author_name = "Reinhard Mueller",
    author_email = "reinhard.mueller@igal.at")
