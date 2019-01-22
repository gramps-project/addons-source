# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2013       Doug Blank <doug.blank@gmail.com>
# Copyright (C) 2016-2017  Nick Hall
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

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------
from gramps.gen.plug.utils import OpenFileOrStdout
from gramps.gen.lib.serialize import to_json

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
        for obj in db.iter_notes():
            write_line(fp, obj)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Event
        # ---------------------------------
        for obj in db.iter_events():
            write_line(fp, obj)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Person
        # ---------------------------------
        for obj in db.iter_people():
            write_line(fp, obj)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Family
        # ---------------------------------
        for obj in db.iter_families():
            write_line(fp, obj)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Repository
        # ---------------------------------
        for obj in db.iter_repositories():
            write_line(fp, obj)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Place
        # ---------------------------------
        for obj in db.iter_places():
            write_line(fp, obj)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Source
        # ---------------------------------
        for obj in db.iter_sources():
            write_line(fp, obj)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Citation
        # ---------------------------------
        for obj in db.iter_citations():
            write_line(fp, obj)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Media
        # ---------------------------------
        for obj in db.iter_media():
            write_line(fp, obj)
            count += 1
            callback(100 * count/total)

        # ---------------------------------
        # Tag
        # ---------------------------------
        for obj in db.iter_tags():
            write_line(fp, obj)
            count += 1
            callback(100 * count/total)

    return True

def write_line(fp, obj):
    """
    Write a single object to the file.
    """
    fp.write(to_json(obj) + "\n")
