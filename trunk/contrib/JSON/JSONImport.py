#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2013       Douglas S. Blank
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

from __future__ import unicode_literals
#-------------------------------------------------------------------------
#
# Standard Python Modules
#
#-------------------------------------------------------------------------

#------------------------------------------------------------------------
#
# Set up logging
#
#------------------------------------------------------------------------
import logging
LOG = logging.getLogger(".ImportJSON")

#-------------------------------------------------------------------------
#
# GRAMPS modules
#
#-------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.sgettext
from gramps.gen.db import DbTxn
from gramps.gen.plug.utils import OpenFileOrStdin
from gramps.gen.constfunc import cuni, conv_to_unicode, STRTYPE
from gramps.gen.config import config
from gramps.gen.merge.diff import from_struct

def importData(dbase, filename, user):
    """Function called by Gramps to import data on persons in CSV format."""
    dbase.disable_signals()
    try:
        with DbTxn(_("JSON import"), dbase, batch=True) as trans:
            with OpenFileOrStdin(filename, 'b') as fp:
                line = fp.readline()
                while line:
                    json = eval(line)
                    obj = from_struct(json)
                    if json["_class"] == "Person":
                        dbase.add_person(obj, trans)
                    elif json["_class"] == "Family":
                        dbase.add_family(obj, trans)
                    elif json["_class"] == "Event":
                        dbase.add_event(obj, trans)
                    elif json["_class"] == "MediaObject":
                        dbase.add_object(obj, trans)
                    elif json["_class"] == "Repository":
                        dbase.add_repository(obj, trans)
                    elif json["_class"] == "Tag":
                        dbase.add_tag(obj, trans)
                    elif json["_class"] == "Source":
                        dbase.add_source(obj, trans)
                    elif json["_class"] == "Citation":
                        dbase.add_citation(obj, trans)
                    elif json["_class"] == "Note":
                        dbase.add_note(obj, trans)
                    elif json["_class"] == "Place":
                        dbase.add_place(obj, trans)
                    else:
                        LOG.warn("ignored: " + json)
                    line = fp.readline()
    except EnvironmentError as err:
        user.notify_error(_("%s could not be opened\n") % filename, str(err))

    dbase.enable_signals()
    dbase.request_rebuild()
