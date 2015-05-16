# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2015       Douglas S. Blank
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

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.plug.utils import OpenFileOrStdout
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.utils.alive import probably_alive
from gramps.gen.lib import Person, Family

def escape(text):
    return text.replace("'", "\\'")

def exportData(database, filename, 
               error_dialog=None, option_box=None, callback=None):
    if not callable(callback): 
        callback = lambda percent: None # dummy

    with OpenFileOrStdout(filename) as fp:

        total = (len(database.note_map) + 
                 len(database.person_map) +
                 len(database.event_map) + 
                 len(database.family_map) +
                 len(database.repository_map) +
                 len(database.place_map) +
                 len(database.media_map) +
                 len(database.source_map))
        count = 0.0

        # GProlog ISO directives:
        # /number must match the number of arguments to functions:
        fp.write(":- discontiguous(data/2).\n")
        fp.write(":- discontiguous(is_alive/2).\n")
        fp.write(":- discontiguous(parent/2).\n")

        # Rules:
        fp.write("grandparent(X, Y) :- parent(X, Z), parent(Z, Y).\n")
        fp.write("ancestor(X, Y) :- parent(X, Y).\n")
        fp.write("ancestor(X, Y) :- parent(X, Z), ancestor(Z, Y).\n")
        fp.write("sibling(X, Y) :- parent(Z, X), parent(Z, Y), X \= Y.\n")

        # ---------------------------------
        # Notes
        # ---------------------------------
        for note_handle in database.note_map.keys():
            note = database.note_map[note_handle]
            #write_line(fp, "note_details(%s, %s)" % (note_handle, note))
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Event
        # ---------------------------------
        for event_handle in database.event_map.keys():
            event = database.event_map[event_handle]
            #write_line(fp, "event:", event_handle, event)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Person
        # ---------------------------------
        for person_handle in database.person_map.keys():
            data = database.person_map[person_handle]
            person = Person.create(data)
            gid = person.gramps_id.lower()
            fp.write("data(%s, '%s').\n" % (gid, escape(name_displayer.display(person))))
            fp.write("is_alive(%s, '%s').\n" % (gid, probably_alive(person, database)))
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Family
        # ---------------------------------
        for family_handle in database.family_map.keys():
            data = database.family_map[family_handle]
            family = Family.create(data)
            father_handle = family.get_father_handle()
            mother_handle = family.get_mother_handle()
            parents = []
            if mother_handle:
                mother = database.get_person_from_handle(mother_handle)
                if mother:
                    parents.append(mother.gramps_id.lower())
            if father_handle:
                father = database.get_person_from_handle(father_handle)
                if father:
                    parents.append(father.gramps_id.lower())
            children = []
            for child_ref in family.get_child_ref_list():
                child_handle = child_ref.ref
                child = database.get_person_from_handle(child_handle)
                if child:
                    children.append(child.gramps_id.lower())
            for pid in parents:
                for cid in children:
                    fp.write("parent(%s, %s).\n" % (pid, cid))
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Repository
        # ---------------------------------
        for repository_handle in database.repository_map.keys():
            repository = database.repository_map[repository_handle]
            #write_line(fp, "repository:", repository_handle, repository)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Place 
        # ---------------------------------
        for place_handle in database.place_map.keys():
            place = database.place_map[place_handle]
            #write_line(fp, "place:", place_handle, place)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Source
        # ---------------------------------
        for source_handle in database.source_map.keys():
            source = database.source_map[source_handle]
            #write_line(fp, "source:", source_handle, source)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Media
        # ---------------------------------
        for media_handle in database.media_map.keys():
            media = database.media_map[media_handle]
            #write_line(fp, "media:", media_handle, media)
            count += 1
            callback(100 * count/total)

    return True

def write_line(fp, heading, handle, obj):
    """
    Write a single object to the file.
    """
    fp.write("%s %s %s\n" % (heading, handle.decode(), obj))
