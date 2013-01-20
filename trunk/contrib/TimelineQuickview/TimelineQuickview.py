#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009       Douglas S. Blank
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
#
# $Id$
#
#
"""
Display references for any object
"""

from gramps.gen.simple import SimpleAccess, SimpleDoc, by_date
from gramps.gui.plug.quick import QuickTable
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.lib.date import Today
from gramps.gen.relationship import get_relationship_calculator
from gramps.gen.utils.db import get_birth_or_fallback, get_death_or_fallback
import gramps.gen.lib

_ = glocale.get_addon_translator(__file__).gettext
rel_calc = get_relationship_calculator()

def levelname(inlaw, level):
    if level == 1:
        if not inlaw:
            return _("Parents")
        else:
            return _("Inlaw Parents")
    elif level == 2:
        if not inlaw:
            return _("Grandparents")
        else:
            return _("Inlaw Grandparents")
    elif level == 3:
        if not inlaw:
            return _("Great grandparents")
        else:
            return _("Inlaw Great grandparents")
    elif level >= 4:
        if not inlaw:
            return (_("Great, ") + (_("great, ") * (level - 4))) + _("great grandparents")
        else:
            return (_("Inlaw Great, ") + (_("great, ") * (level - 4))) + _("great grandparents")

def get_events(person, sa, all=False):
    if all:
        return sa.events(person)
    else:
        return [get_birth_or_fallback(sa.dbase, person), 
                get_death_or_fallback(sa.dbase, person)]

def process(database, sa, event_list, handled, center_person, inlaw, person, level=0, maxlevel=1):
    if person is None: return
    if person.handle not in handled:
        handled[person.handle] = person
        relation = rel_calc.get_one_relationship(database, center_person, person).title()
        for event in get_events(person, sa, person == center_person):
            if event:
                if person.handle == center_person.handle:
                    event_list += [(event, person, event)]
                elif relation == "":
                    return
                else:
                    event_list += [(event, person, "%s, %s" % (relation, sa.event_type(event)))]
    # get all families that the person was a parent in:
    for family in sa.parent_in(person):
        if family.handle in handled:
            continue
        father = sa.father(family)
        mother = sa.mother(family)
        handled[family.handle] = family
        for event in sa.events(family):
            etype = sa.event_type(event)
            if person.handle in [obj.handle for obj in [mother, father] 
                                 if obj is not None]:
                desc = rel_calc.get_one_relationship(database, center_person, person).title()
                if desc == "":
                    desc = etype
                else:
                    desc += ", " + etype
            else:
                desc = "%s, %s" % (_("Partner's spouse"), etype)
            event_list += [(event, family, desc)]
        # get details of spouse
        if father:
            process(database, sa, event_list, handled, center_person, 
                    person.handle != father.handle, father, level=level+1)
        if mother:
            process(database, sa, event_list, handled, center_person, 
                    person.handle != mother.handle, mother, level=level+1)
        # get details of children
        for handle in family.get_child_ref_list():
            child = database.get_person_from_handle(handle.ref) 
            if child is not None and child.handle not in handled:
                handled[child.handle] = child
                relation = rel_calc.get_one_relationship(database, center_person, child).title()
                if relation != "": # otherwise, no official relationship
                    for event in get_events(child, sa):
                        if event:
                            etype = sa.event_type(event)
                            event_list += [(event, child, "%s, %s" % (relation, etype))]

    # if not too far away, get details of families person was child in:
    if level < maxlevel:
        for family in sa.child_in(person):
            if family.handle not in handled:
                handled[family.handle] = family
                relation = levelname(inlaw, level + 1)
                event_list += [(event, family, "%s, %s" % 
                                (relation, sa.event_type(event))) 
                               for event in sa.events(family)]
                if level+1 <= maxlevel:
                    father = sa.father(family)
                    process(database, sa, event_list, handled, center_person, False, father, level=level+1)
                if level+1 <= maxlevel:
                    mother = sa.mother(family)
                    process(database, sa, event_list, handled, center_person, False, mother, level=level+1)
            # get details of siblings
            for handle in family.get_child_ref_list():
                child = database.get_person_from_handle(handle.ref) 
                if child.handle not in handled:
                    handled[child.handle] = child
                    relation = rel_calc.get_one_relationship(database, center_person, child).title()
                    if relation != "": # otherwise, no official relationship
                        for event in get_events(child, sa):
                            if event:
                                etype = sa.event_type(event)
                                event_list += [(event, child, "%s, %s" % (relation, etype))]

def run(database, document, person):
    """
    Display a person's timeline.
    """
    sa = SimpleAccess(database)
    sd = SimpleDoc(document)
    sd.title(_("Timeline for %s") % sa.name(person))
    sd.paragraph("")
    stab = QuickTable(sa)
    stab.columns(_("Date"), 
                 _("Event"), 
                 _("Age"), 
                 _("Place"), 
                 _("People involved"))
    stab.set_link_col(4)

    handled = {}
    birth_ref = gramps.gen.lib.Person.get_birth_ref(person)
    birth_date = get_event_date_from_ref(database, birth_ref)
    event_list = []

    process(database, sa, event_list, handled, person, False, person)
    # DeprecationWarning: the cmp argument is not supported in 3.x
    event_list.sort(lambda a,b: by_date(a[0], b[0]))

    for (event, obj, desc) in event_list:
        edate = sa.event_date_obj(event)
        span_str, span_int = format_date(birth_date, edate, obj == person)
        if desc == None:
            desc = event
        stab.row(edate,
                 desc,
                 span_str,
                 sa.event_place(event),
                 obj)
        stab.row_sort_val(2, span_int)
    today = Today()
    span_str, span_int = format_date(birth_date, today, False)
    stab.row(today, _("Today"), span_str, "", person)
    stab.row_sort_val(2, span_int)
    stab.write(sd)
    sd.paragraph("")

def format_date(date_start, date_end, as_age):
    date_str, date_sort = _("Unknown"), 0
    if date_start != None and date_end != None:
        diff_span = (date_end - date_start)
        date_str = diff_span.get_repr(as_age)
        date_sort = int(diff_span)
    return (date_str, date_sort)

def get_event_date_from_ref(database, ref):
    date = None
    if ref:
        handle = ref.get_reference_handle()
        if handle:
            event = database.get_event_from_handle(handle)
            if event:
                date = event.get_date_object()
    return date


