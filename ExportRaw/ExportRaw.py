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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# $Id$
#

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gui.plug.export import WriterOptionBox
from gramps.gen.plug.utils import OpenFileOrStdout

def exportData(db, filename,
               error_dialog=None, option_box=None, callback=None):
    if not callable(callback):
        callback = lambda percent: None # dummy

    with OpenFileOrStdout(filename, encoding="utf-8") as fp:

        total = (db.get_number_of_notes() +
                 db.get_number_of_people() +
                 db.get_number_of_events() +
                 db.get_number_of_families() +
                 db.get_number_of_repositories() +
                 db.get_number_of_places() +
                 db.get_number_of_media() +
                 db.get_number_of_citations() +
                 db.get_number_of_sources() +
                 db.get_number_of_tags())
        count = 0.0

        # ---------------------------------
        # Notes
        # ---------------------------------
        for note in db.iter_notes():
            write_line(fp, "note:", note.handle, note)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Event
        # ---------------------------------
        for event in db.iter_events():
            write_line(fp, "event:", event.handle, event)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Person
        # ---------------------------------
        for person in db.iter_people():
            write_line(fp, "person:", person.handle, person)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Family
        # ---------------------------------
        for family in db.iter_families():
            write_line(fp, "family:", family.handle, family)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Repository
        # ---------------------------------
        for repository in db.iter_repositories():
            write_line(fp, "repository:", repository.handle, repository)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Place
        # ---------------------------------
        for place in db.iter_places():
            write_line(fp, "place:", place.handle, place)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Source
        # ---------------------------------
        for source in db.iter_sources():
            write_line(fp, "source:", source.handle, source)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Media
        # ---------------------------------
        for media in db.iter_media():
            write_line(fp, "media:", media.handle, media)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Citation
        # ---------------------------------
        for citation in db.iter_citations():
            write_line(fp, "citation:", citation.handle, citation)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Tag
        # ---------------------------------
        for tag in db.iter_tags():
            write_line(fp, "tag:", tag.handle, tag)
            count += 1
            callback(100 * count/total)

    return True

def write_line(fp, heading, handle, obj):
    """
    Write a single object to the file.
    """
    fp.write("%s %s %s\n" % (heading, handle, obj.serialize()))
