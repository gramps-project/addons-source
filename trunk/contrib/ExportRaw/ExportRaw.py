# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2008       Douglas S. Blank
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

        # ---------------------------------
        # Notes
        # ---------------------------------
        for note_handle in database.note_map.keys():
            note = database.note_map[note_handle]
            write_line(fp, "note:", note_handle, note)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Event
        # ---------------------------------
        for event_handle in database.event_map.keys():
            event = database.event_map[event_handle]
            write_line(fp, "event:", event_handle, event)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Person
        # ---------------------------------
        for person_handle in database.person_map.keys():
            person = database.person_map[person_handle]
            write_line(fp, "person:", person_handle, person)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Family
        # ---------------------------------
        for family_handle in database.family_map.keys():
            family = database.family_map[family_handle]
            write_line(fp, "family:", family_handle, family)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Repository
        # ---------------------------------
        for repository_handle in database.repository_map.keys():
            repository = database.repository_map[repository_handle]
            write_line(fp, "repository:", repository_handle, repository)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Place 
        # ---------------------------------
        for place_handle in database.place_map.keys():
            place = database.place_map[place_handle]
            write_line(fp, "place:", place_handle, place)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Source
        # ---------------------------------
        for source_handle in database.source_map.keys():
            source = database.source_map[source_handle]
            write_line(fp, "source:", source_handle, source)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Media
        # ---------------------------------
        for media_handle in database.media_map.keys():
            media = database.media_map[media_handle]
            write_line(fp, "media:", media_handle, media)
            count += 1
            callback(100 * count/total)

    return True

def write_line(fp, heading, handle, obj):
    """
    Write a single object to the file.
    """
    if sys.version_info[0] >= 3:
        handle = handle.decode()
    fp.write("%s %s %s\n" % (heading, handle, obj))
