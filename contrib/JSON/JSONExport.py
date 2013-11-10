# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2013       Doug Blank <doug.blank@gmail.com>
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

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
import sys

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gui.plug.export import WriterOptionBox
from gramps.gen.plug.utils import OpenFileOrStdout
from gramps.gen.lib import (Note, Person, Event, Family, 
                            Repository, Place, MediaObject, 
                            Source, Tag)

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
                 len(database.source_map) +
                 len(database.tag_map))
        count = 0.0

        # ---------------------------------
        # Notes
        # ---------------------------------
        for handle in database.note_map.keys():
            serial = database.note_map[handle]
            write_line(fp, Note.create(serial))
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Event
        # ---------------------------------
        for handle in database.event_map.keys():
            serial = database.event_map[handle]
            write_line(fp, Event.create(serial))
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Person
        # ---------------------------------
        for handle in database.person_map.keys():
            serial = database.person_map[handle]
            write_line(fp, Person.create(serial))
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Family
        # ---------------------------------
        for handle in database.family_map.keys():
            serial = database.family_map[handle]
            write_line(fp, Family.create(serial))
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Repository
        # ---------------------------------
        for handle in database.repository_map.keys():
            serial = database.repository_map[handle]
            write_line(fp, Repository.create(serial))
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Place 
        # ---------------------------------
        for handle in database.place_map.keys():
            serial = database.place_map[handle]
            write_line(fp, Place.create(serial))
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Source
        # ---------------------------------
        for handle in database.source_map.keys():
            serial = database.source_map[handle]
            write_line(fp, Source.create(serial))
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Media
        # ---------------------------------
        for handle in database.media_map.keys():
            serial = database.media_map[handle]
            write_line(fp, MediaObject.create(serial))
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Tag
        # ---------------------------------
        for handle in database.tag_map.keys():
            serial = database.tag_map[handle]
            write_line(fp, Tag.create(serial))
            count += 1
            callback(100 * count/total)

    return True

def write_line(fp, obj):
    """
    Write a single object to the file.
    """
    fp.write(str(obj.to_struct()) + "\n")
