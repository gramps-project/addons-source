#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2016, 2026       Tim G L Lyons
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
"""
Display whether census records have been found for a person, their spouse(s) and
children
"""

from gramps.gen.simple import SimpleAccess, SimpleDoc
from gramps.gui.plug.quick import QuickTable
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.utils.alive import probably_alive
from gramps.gen.lib.date import Today
import form

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


def process_person(database, sdb, stab, person, census_list):
    """
    Analyze a person's census participation and append the results to a
    summary table.

    This function examines the events associated with a person to identify
    existing census citations. It then evaluates which censuses the person
    may have appeared in based on their estimated birth and death range, and
    outputs a row summarizing this information.

    :param database: GRAMPS database object
    :type database: DbBase
    :param sdb: Simple database access.
    :type sdb: SimpleAccess
    :param stab: The summary table where the results will be recorded.
    :type stab: SimpleTable
    :param person: The individual whose census data is being processed.
    :type person: L{gen.lib.Person}
    :param census_list: Dictionary of census form IDs, keyed by census year
    :type census_list: dict
    :return: None
    :rtype: None
    """
    if not person:
        return

    # Check for any existing census events for the person
    found_census = []
    for event_ref in person.get_event_ref_list():
        event = database.get_event_from_handle(event_ref.ref)
        if event:
            citation = form.get_form_citation(database, event)
            if citation:
                source_handle = citation.get_reference_handle()
                source = database.get_source_from_handle(source_handle)
                if source:
                    form_id = form.get_form_id(source)
                    found_census.append(form_id)

    # Process all the possible censuses
    census_result = ()
    for key in sorted(census_list):
        if key in found_census:
            census_result += ("OK",)
        else:
            # Check whether the person is probably alive on the census date
            if probably_alive(person, database, census_list[key]):
                # If the person would be less than 100 today,
                # the record may be closed
                if probably_alive(person, database, Today(), max_age_prob_alive=100):
                    census_result += ("closed",)
                else:
                    census_result += ("miss",)
            else:
                census_result += ("-",)

    # Construct the results line
    columns = (
        person,
        sdb.birth_date_obj(person),
        sdb.death_date_obj(person),
    ) + census_result
    stab.row(*columns)


def run(database, document, person):
    """
    Display whether census records have been found for a person, their spouse(s)
    and children
    """

    # Construct a dictionary of census IDs and date
    census_list = {}
    for handle in database.get_source_handles():
        source = database.get_source_from_handle(handle)
        form_id = form.get_form_id(source)
        if form_id in form.get_form_ids():
            form_type = form.get_form_type(form_id)
            if form_type == "Census":
                census_list[form_id] = form.get_form_date(form_id)

    sdb = SimpleAccess(database)
    sdoc = SimpleDoc(document)
    sdoc.title(_("Census Check for %s") % sdb.name(person))
    sdoc.paragraph("")
    stab = QuickTable(sdb)

    columns = (_("Name"), _("Birth date"), _("Death date")) + tuple(
        key for key in sorted(census_list)
    )
    stab.columns(*columns)
    process_person(database, sdb, stab, person, census_list)

    child_list = []
    for child in sdb.children(person):
        if child not in child_list:
            child_list.append(child)
    for person_family in sdb.parent_in(person):
        father = sdb.father(person_family)
        mother = sdb.mother(person_family)
        if father and father.handle and father.handle != person.handle:
            spouse = father
        elif mother and mother.handle and mother.handle != person.handle:
            spouse = mother
        else:
            spouse = None
        if spouse:
            process_person(database, sdb, stab, spouse, census_list)
            for spouse_family in sdb.parent_in(spouse):
                for child in sdb.children(spouse_family):
                    if child not in child_list:
                        child_list.append(child)
    for child in child_list:
        process_person(database, sdb, stab, child, census_list)

    stab.write(sdoc)
    sdoc.paragraph("")
