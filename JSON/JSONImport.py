#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2013       Douglas S. Blank
# Copyright (C) 2016       Nick Hall
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

"Import from JSON data"

#-------------------------------------------------------------------------
#
# Standard Python Modules
#
#-------------------------------------------------------------------------
import json
import logging

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from gramps.gen.db import DbTxn
from gramps.gen.plug.utils import OpenFileOrStdin
from gramps.gen.lib import (Note, Person, Event, Family, Repository, Place,
                            Media, Source, Tag, Citation)
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.sgettext

#------------------------------------------------------------------------
#
# Set up logging
#
#------------------------------------------------------------------------
LOG = logging.getLogger(".ImportJSON")

def importData(db, filename, user):
    """Function called by Gramps to import data on persons in CSV format."""
    db.disable_signals()
    try:
        with DbTxn(_("JSON import"), db, batch=True) as trans:
            with OpenFileOrStdin(filename, encoding="utf-8") as fp:
                line = fp.readline()
                while line:
                    data = json.loads(line)
                    if data["_class"] == "Person":
                        obj = Person.create(Person.from_struct(data))
                        db.add_person(obj, trans)
                    elif data["_class"] == "Family":
                        obj = Family.create(Family.from_struct(data))
                        db.add_family(obj, trans)
                    elif data["_class"] == "Event":
                        obj = Event.create(Event.from_struct(data))
                        db.add_event(obj, trans)
                    elif data["_class"] == "Media":
                        obj = Media.create(Media.from_struct(data))
                        db.add_media(obj, trans)
                    elif data["_class"] == "Repository":
                        obj = Repository.create(Repository.from_struct(data))
                        db.add_repository(obj, trans)
                    elif data["_class"] == "Tag":
                        obj = Tag.create(Tag.from_struct(data))
                        db.add_tag(obj, trans)
                    elif data["_class"] == "Source":
                        obj = Source.create(Source.from_struct(data))
                        db.add_source(obj, trans)
                    elif data["_class"] == "Citation":
                        obj = Citation.create(Citation.from_struct(data))
                        db.add_citation(obj, trans)
                    elif data["_class"] == "Note":
                        obj = Note.create(Note.from_struct(data))
                        db.add_note(obj, trans)
                    elif data["_class"] == "Place":
                        obj = Place.create(Place.from_struct(data))
                        db.add_place(obj, trans)
                    else:
                        LOG.warn("ignored: " + data)
                    line = fp.readline()
    except EnvironmentError as err:
        user.notify_error(_("%s could not be opened\n") % filename, str(err))

    db.enable_signals()
    db.request_rebuild()
