#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2017       A. Guinane
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
#
"""
Display text summary of person events with sources
"""

from gramps.gen.simple import SimpleAccess, SimpleDoc
from gramps.plugins.lib.libnarrate import Narrator


def run(database, document, person):
    """
    Output a text biography of active person
    """
    sa = SimpleAccess(database)
    sd = SimpleDoc(document)
    sd.title("Biography for %s" % sa.name(person))
    sd.paragraph('')

    narrator = Narrator(database, verbose=True,
                        use_call_name=True, use_fulldate=True)
    narrator.set_subject(person)


    # Birth Details
    text = narrator.get_born_string()
    if text:
        sd.paragraph(text)

    text = narrator.get_baptised_string()
    if text:
        sd.paragraph(text)

    text = narrator.get_christened_string()
    if text:
        sd.paragraph(text)

    text = get_parents_desc(database, person)
    if text:
        sd.paragraph(text)
    sd.paragraph('')

    # Family Details
    for family in sa.parent_in(person):
        text = narrator.get_married_string(family)
        if text:
            sd.paragraph(text)
    sd.paragraph('')

    # Death Details
    text = narrator.get_died_string(True)
    if text:
        sd.paragraph(text)

    text = narrator.get_buried_string()
    if text:
        sd.paragraph(text)
    sd.paragraph('')

    # Sources
    sd.header1('Sources')
    for source in get_sources(database, person):
        sd.paragraph(source)


def get_sources(database, person):
    """
    Create list of sources for person's events
    """
    sources = list()
    sa = SimpleAccess(database)
    events = sa.events(person)
    # Get family events also
    for family in sa.parent_in(person):
        for event in sa.events(family):
            events.append(event)

    for event in events:
        for handle in event.citation_list:
            citation = database.get_citation_from_handle(handle)
            page = citation.page
            source = database.get_source_from_handle(citation.source_handle)
            title = source.title
            author = source.author
            if author:
                source_desc = '* {}, {} - {}'.format(author, title, page)
            else:
                source_desc = '* {} - {}'.format(title, page)

            if source_desc not in sources:
                sources.append(source_desc)
    return sources


def get_parents_desc(database, person):
    """
    Return text describing person's parents
    """
    sa = SimpleAccess(database)
    narrator = Narrator(database, verbose=True,
                        use_call_name=True, use_fulldate=True)
    narrator.set_subject(person)
    family_handle = person.get_main_parents_family_handle()
    if family_handle:
        family = database.get_family_from_handle(family_handle)
        mother_handle = family.get_mother_handle()
        father_handle = family.get_father_handle()
        if mother_handle:
            mother = database.get_person_from_handle(mother_handle)
            mother_name = sa.name(mother)
        else:
            mother_name = ""
        if father_handle:
            father = database.get_person_from_handle(father_handle)
            father_name = sa.name(father)
        else:
            father_name = ""
        return narrator.get_child_string(father_name, mother_name)
