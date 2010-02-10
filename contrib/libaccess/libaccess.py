#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010  Douglas Blank <doug.blank@gmail.com>
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
An experiment in delayed field lookup. This defines an interface that
allows:

>>> from libaccess import *
>>> init(db)
>>> p = Person.get(handle="3897894893247842")
>>> p.birth.date.year
1963

The idea would be to write an interface for each DB type.

This interface brings together the database methods and the gen.lib
objects, so that developers need not know about either.

The goals of this interface are:

1. To abstract all functionality of gen.lib and the db layer
2. To hide all uses of handles from the developer 
3. To put all of the "business logic" in one place
4. To make multi-field logic easy (if person.name.surname == "Blank")
5. To make edits easy.

Additionals goals:

* the code should never crash due to the database being in an
  inconsistent state.

"""

import itertools

database = None

def init(db):
    """
    Set the global database.
    """
    global database
    database = db

def nth(g, n):
    """
    Get the nth item from a generator. Starting with 1.
    """
    return list(itertools.islice(g, n - 1, n))[0]

class Null(object):
    """
    A None object that allows Null chaining (ie, Null().x.y.z[0].a == None)
    """
    def __eq__(self, other):
        return hash(other) == hash(None)

    def __call__(self, *args, **kwargs):
        return NONE

    def __cmp__(self, other):
        return cmp(None, other)

    def __hash__(self):
        return hash(None)

    def __getattr__(self, attr):
        return NONE

    def __getitem__(self, item):
        return NONE

    def __str__(self):
        return "None"

    def __repr__(self):
        return "None"

    def __len__(self):
        return 0

    def __nonzero__(self):
        return False

NONE = Null()

class Object(object):
    """
    Base delayed object that defines methods for looking objects up,
    and methods for retrieving a field's value.
    """
    query = {}
    fields = {}

    def __init__(self, instance=None, **kwargs):
        self.instance = instance
        for keyword in kwargs:
            self.fields[keyword] = kwargs[keyword]

    def __getattr__(self, attr):
        if attr in self.fields:
            if callable(self.fields[attr]):
                # cache it if it is not an object
                #self.fields[attr] = self.fields[attr](self)
                pass
            return self.fields[attr](self)
        return NONE

    @classmethod
    def get(self, **kwargs):
        for attr in kwargs:
            if attr in self.query:
                return self(self.query[attr](kwargs[attr]))
        return NONE

    @classmethod
    def all(self):
        if "id" in self.query:
            count = 1
            while True:
                yield self(self.query["id"](count))
                count += 1

class ListOf(object):
    def __init__(self, obj, ltype, list):
        self.obj = obj
        self.ltype = ltype
        self.list = list

    def __iter__(self):
        for i in range(len(self)):
            yield self.list[i]

    def __getitem__(self, item):
        if item < len(self.list):
            return self.list[item]
        else:
            return NONE

    def __len__(self):
        return len(self.list)

    def __repr__(self):
        return repr(self.list)

    def __str__(self):
        return str(self.list)

    def append(self, item):
        self.append_item(item)

    def delete(self, item):
        self.delete_item(item)

###################################################################
#
# The objects that define the relationships between gen.lib and
# the database.
#
###################################################################
class Name(Object):
    """
    fields is a dictionary of names to functions, where the function
    is always given one argument, the self. The low-level, internal
    representation is stored in instance.
    """
    fields = {
        "surname": lambda self: self.instance.get_surname(),
        "given": lambda self: self.instance.get_first_name(),
        }

    def __repr__(self):
        return "%s, %s" % (self.surname, self.given)

class Person(Object):
    """
    query is a dictionary that maps field names to functions to query
    the database.

    query will be give to self(result) to create a return object.
    """
    query = {
        "id": lambda id: database.get_person_from_handle(
            nth(database.iter_person_handles(), id)),
        "handle": lambda handle: database.get_person_from_handle(handle),
        "gramps_id": lambda gramps_id: database.get_person_from_gramps_id(gramps_id),
        }
    fields = {
        "handle": lambda self: self.instance.handle,
        "gender": lambda self: ["female", "male", "unknown"][self.instance.get_gender()],
        "birth": lambda self: self.__get_birth_date(),
        "death": lambda self: self.__get_death_date(),
        "name": lambda self: self.__get_primary_name(),
        "names": lambda self: self.__get_names(),
        "events": lambda self: self.__get_primary_events(),
        "families": lambda self: ListOf(self, Family, [Family(database.get_family_from_handle(h)) for h in 
                                                       self.instance.get_family_handle_list()])
        }

    def __get_primary_events(self):
        ref_list = self.instance.get_primary_event_ref_list()
        return ListOf(self, Event, [Event(database.get_event_from_handle(ref.ref)) for ref in ref_list])

    def __repr__(self):
        if self.name == None:
            return "[%s]" % self.gramps_id
        else:
            return "%s, %s" % (self.name.surname, self.name.given)

    @classmethod
    def all(self):
        return itertools.imap(Person, database.iter_people())

    def __get_names(self):
        if self.instance:
            name = self.__get_primary_name()
            if name:
                return ListOf(self, Name,
                              [name] + [Name(n, primary=False, 
                                             person=self.instance) for n in 
                                        self.instance.get_alternate_names()],)
            else:
                return ListOf(self, Name,
                              [Name(n, primary=False, 
                                    person=self.instance) for n in 
                               self.instance.get_alternate_names()],)
        return ListOf(self, Name, [])

    def __add_name(self, name):
        pass

    def __del_name(self, name):
        pass

    def __get_birth_date(self):
        if self.instance:
            ref = self.instance.get_birth_ref()
            if ref:
                return Event.get(handle=ref.ref)
        return NONE

    def __get_death_date(self):
        if self.instance:
            ref = self.instance.get_death_ref()
            if ref:
                return Event.get(handle=ref.ref)
        return NONE

    def __get_primary_name(self):
        if self.instance:
            return Name(self.instance.get_primary_name(), primary=True, 
                        person=self.instance)
        return NONE

class Event(Object):
    """
    query will be give to self(result) to create a return object.
    """
    query = {
        "id": lambda id: nth(database.iter_event_handles(), id),
        "handle": lambda handle: database.get_event_from_handle(handle),
        "gramps_id": lambda gramps_id: database.get_event_from_gramps_id(gramps_id),
        }
    fields = {
        "handle": lambda self: self.instance.handle,
        "date": lambda self: Date(self.instance.get_date_object()),
        "type": lambda self: str(self.instance.get_type()),
        }

    @classmethod
    def all(self):
        return itertools.imap(Event, database.iter_events())

#class Type(Object):
#    fields = {
#        "value": lambda self: self.instance.value,
#        "name": lambda self: self.instance.string,
#        }

class Date(Object):
    fields = {
        "year": lambda self: self.instance.get_year(),
        "month": lambda self: self.instance.get_month(),
        "day": lambda self: self.instance.get_month(),
        }

    def __repr__(self):
        return "%s/%s/%s" % (self.year, self.month, self.day)

class Family(Object):
    query = {
        "id": lambda id: nth(database.iter_family_handles(), id),
        "handle": lambda handle: database.get_family_from_handle(handle),
        "gramps_id": lambda gramps_id: database.get_family_from_gramps_id(gramps_id),
        }
    fields = {
        "father": lambda self: Person(database.get_person_from_handle(self.instance.get_father_handle())),
        "mother": lambda self: Person(database.get_person_from_handle(self.instance.get_mother_handle())),
        "events": lambda self: ListOf(self, Event, [Event(database.get_event_from_handle(h)) 
                                                    for h in self.instance.get_event_ref_list()]),
        }
