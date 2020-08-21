#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020 Christian Schulze
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
# Geography view
#
#------------------------------------------------------------------------

from gi import Repository
from gramps.gen.const import USER_PLUGINS
from gramps.gen.config import logging
from gramps.gen.config import config
from gramps.gen.plug.utils import Zipfile
inifile = config.register_manager("placecoordinategramplet_warn")
inifile.load()
sects = inifile.get_sections()

#-------------------------------------------------------------------------
#
# set up logging
#
#-------------------------------------------------------------------------
import logging
_LOG = logging.getLogger("PlaceCoordinateGramplet")


import os
import sys
import importlib
import traceback

try:
    if 'placecoordinategramplet_warn' not in sects \
        or not inifile.is_set('placecoordinategramplet_warn.missingmodules') \
        or inifile.get('placecoordinategramplet_warn.missingmodules') != 'False' \
            :
        _uistate = locals().get('uistate')
    else:
        _uistate = None

    plugin_name = "Place Coordinate Gramplet"

    try:
        import gi
        gi.require_version('GeocodeGlib', '1.0')
        from gi.repository import GeocodeGlib
        some_import_error = False
    except:
        message = _("Failed to load the required module {module_name}.").format(
                module_name="gi.repository.GeocodeGlib")
        logging.warning(plugin_name + ': ' + message)

        if uistate:
            from gramps.gui.dialog import QuestionDialog2
            warn_dialog = QuestionDialog2(
                plugin_name + ' Plugin',
                message,
                "Don't show again", "OK",
                parent=uistate.window)
            if not warn_dialog.run():
                inifile.register('placecoordinategramplet_warn.missingmodules', "")
                inifile.set('placecoordinategramplet_warn.missingmodules', "False")

        some_import_error = True

    if not some_import_error and ('placecoordinategramplet_warn' not in sects
        or not inifile.is_set('placecoordinategramplet_warn.connectivity')
        or inifile.get('placecoordinategramplet_warn.connectivity') != 'False'
            ):

        location_ = GeocodeGlib.Forward.new_for_string("Berlin")
        try:
            result = location_.search()
        except Exception as e:
            result = None

            message = _("Internet connectivity test failed for {module_name}.").format(
                    module_name="gi.repository.GeocodeGlib") \
                    + "\n\n" + str(e)
            logging.warning(plugin_name + ': ' + message)

            if uistate:
                from gramps.gui.dialog import QuestionDialog2
                warn_dialog = QuestionDialog2(
                    plugin_name + ' Plugin',
                    message,
                    "Don't show again", "OK",
                    parent=uistate.window)
                if warn_dialog.run():
                    logging.warning(plugin_name + ': ' + _('Warning disabled.'))
                    inifile.register('placecoordinategramplet_warn.connectivity', "")
                    inifile.set('placecoordinategramplet_warn.connectivity', "False")
                    inifile.save()
            some_import_error = True

except Exception as e:
    some_import_error = True
    import_error_message = traceback.format_exc()
    logging.log(logging.ERROR, 'Failed to load PlaceCoordinateGramplet plugin.\n' + import_error_message)

if locals().get('uistate') is None or not some_import_error or True:
    # Right after the download the plugin is loaded without uistate
    # If the gui is available, then the error message is shown anyway
    # so here we can import to avoid additional messages.

    # Attempting to import OsmGpsMap gives an error dialog if OsmGpsMap is not
    # available so test first and log just a warning to the console instead.
    # Load the view only if osmgpsmap library is present.
    register(VIEW,
            id='geoIDplaceCoordinateGramplet',
            name=_("Place Coordinate Gramplet view"),
            description=_("View for the place coordinate gramplet."),
            version = '1.1.7',
            gramps_target_version="5.1",
            status=STABLE,
            fname='PlaceCoordinateGeoView.py',
            authors=["Christian Schulze"],
            authors_email=["c.w.schulze@gmail.com"],
            category=("Geography", _("Geography")),
            viewclass='PlaceCoordinateGeoView',
            #order = START,
            stock_icon='geo-place-add',
            )

    register(GRAMPLET,
            id="Place Coordinates",
            name=_("Place and Coordinates"),
            description=_(
                "Gramplet that simplifies setting the coordinates of a place"),
            version = '1.1.7',
            gramps_target_version="5.1",
            status=STABLE,
            fname="PlaceCoordinateGramplet.py",
            height=280,
            gramplet='PlaceCoordinateGramplet',
            authors=["Christian Schulze"],
            authors_email=["c.w.schulze@gmail.com"],
            gramplet_title=_("Place Coordinates"),
            navtypes=["Place"],
            )


if not some_import_error:
    inifile.register('placecoordinategramplet_warn.missingmodules', "")
    inifile.set('placecoordinategramplet_warn.missingmodules', "True")
    inifile.register('placecoordinategramplet_warn.connectivity', "")
    inifile.set('placecoordinategramplet_warn.connectivity', "True")
    inifile.save()
