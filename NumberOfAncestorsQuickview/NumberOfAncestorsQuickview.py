#
# Gramps - a GTK+/GNOME based genealogy program - descendant counter plugin
#
# Copyright (C) 2019 Matthias Kemmer
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
"""Quickview report to display the number of ancestors of a person."""

# ------------------------------------------------------------------------
#
# GRAMPS modules
#
# ------------------------------------------------------------------------
import gramps.gen.display.name
from gramps.gen.simple import SimpleDoc
from gramps.gui.plug.quick import QuickTable
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext


# ------------------------------------------------------------------------
#
# Quickview run function
#
# ------------------------------------------------------------------------
def run(database, document, person):
    """Handle quick view report generation."""
    sdoc = SimpleDoc(document)
    name = gramps.gen.display.name.displayer.display(person)

    sdoc.title(_("Number of %s's ancestors") % name)
    sdoc.paragraph("")

    stab = QuickTable(document)
    stab.columns(_("Generation"),
                 _("Found"),
                 _("Theoretical"),
                 _("Percent"))

    num_lst = count_ancestors(database, person)
    for entry in num_lst[1:-1]:
        stab.row(*entry)

    stab.write(sdoc)
    vals = num_lst[-1][1:]
    sdoc.paragraph(_("There were {} of {} ancestors ({}) found.\n"
                     "Only individual ancestors were count. Doubles caused by "
                     "pidigree colapse were ignored."
                     .format(*vals)))


# ------------------------------------------------------------------------
#
# Count ancestors
#
# ------------------------------------------------------------------------
def count_ancestors(database, person):
    """
    Calculate persons's number of ancestors and theoretical number.

    This function uses the text report 'numberofancestorsreport.py' as
    template. It calculates all values needed for the report and returns
    them as a list.

    :returns: a list of values
    :example return_lst: [gen1 (lst), gen2 (lst), ..., total (lst)]
    :example gen1: [generation (int),
                    generation size (int),
                    theoretical generation size (int),
                    percent (str)]
    """
    thisgen = {}
    all_people = {}
    total_theoretical = 0
    thisgen[person.get_handle()] = 1
    return_lst = []

    thisgensize = 1
    gen = 0
    while thisgensize > 0:
        thisgensize = 0
        if thisgen != {}:
            thisgensize = len(thisgen)
            gen += 1
            theoretical = 2**(gen-1)
            total_theoretical += theoretical
            val = (sum(thisgen.values()) / theoretical) * 100
            percent = '%3.2f' % val
            text = [gen-1, thisgensize, int(theoretical), percent]
            return_lst.append(text)

        temp = thisgen
        thisgen = {}
        for person_handle, person_data in temp.items():
            person = database.get_person_from_handle(person_handle)
            family_handle = person.get_main_parents_family_handle()
            if family_handle:
                family = database.get_family_from_handle(family_handle)
                father_handle = family.get_father_handle()
                mother_handle = family.get_mother_handle()
                if father_handle:
                    thisgen[father_handle] = (
                        thisgen.get(father_handle, 0) + person_data
                        )
                    all_people[father_handle] = (
                        all_people.get(father_handle, 0) + person_data
                        )
                if mother_handle:
                    thisgen[mother_handle] = (
                        thisgen.get(mother_handle, 0) + person_data
                        )
                    all_people[mother_handle] = (
                        all_people.get(mother_handle, 0) + person_data
                        )

    if total_theoretical != 1:
        percent = '%3.2f%%' % (
            (sum(all_people.values()) / (total_theoretical-1)) * 100)
    else:
        percent = 0

    return_lst.append([int(gen-1), int(len(all_people)),
                       int(total_theoretical)-1, percent])
    return return_lst
