#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 David Straub
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

"""Import a GEDCOM 7 file into Gramps."""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
import logging

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.errors import DbError
from gramps.gen.utils.libformatting import ImportInfo

# -------------------------------------------------------------------------
#
# GEDCOM 7 library
#
# -------------------------------------------------------------------------
from gramps_gedcom7 import ImportSettings, import_gedcom

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

LOG = logging.getLogger(".ImportGedcom7")


def _object_counts(database):
    """Return the number of objects of each type, keyed by display label."""
    return {
        label: getattr(database, method)()
        for label, method in (
            (_("People"), "get_number_of_people"),
            (_("Families"), "get_number_of_families"),
            (_("Events"), "get_number_of_events"),
            (_("Places"), "get_number_of_places"),
            (_("Sources"), "get_number_of_sources"),
            (_("Citations"), "get_number_of_citations"),
            (_("Repositories"), "get_number_of_repositories"),
            (_("Media"), "get_number_of_media"),
            (_("Notes"), "get_number_of_notes"),
            (_("Tags"), "get_number_of_tags"),
        )
    }


def _import_statistics(before, after):
    """Return the number of objects added, omitting types with no additions."""
    added = {
        label: after[label] - before[label]
        for label in after
        if after[label] > before[label]
    }
    return added or {_("Results"): _("No objects were imported")}


def import_data(database, filename, user):
    """Import a GEDCOM 7 file into a Gramps database.

    :returns: an :class:`ImportInfo` with the object counts, or None if the
              file could not be imported. Gramps treats None as a failure.
    """
    # A fresh ImportSettings per import: the library records HEAD.PLAC.FORM on
    # it, so a shared instance would leak that default into the next import.
    settings = ImportSettings()
    before = _object_counts(database)
    try:
        import_gedcom(input_file=filename, db=database, settings=settings)
    except OSError as err:
        user.notify_error(_("%s could not be opened") % filename, str(err))
        return None
    except ValueError as err:
        # raised for invalid UTF-8 and for GEDCOM 7 parse errors
        user.notify_error(
            _("Invalid GEDCOM 7 file"),
            _("%s could not be imported") % filename + "\n" + str(err),
        )
        return None
    except DbError as err:
        user.notify_db_error(str(err.value))
        return None
    except Exception as err:
        LOG.error("Failed to import GEDCOM 7 file.", exc_info=True)
        user.notify_error(
            _("Error reading GEDCOM 7 file"),
            _("%s could not be imported") % filename + "\n" + str(err),
        )
        return None
    return ImportInfo(_import_statistics(before, _object_counts(database)))
