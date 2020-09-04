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

import os
import sys
import importlib
import traceback

from gi import Repository
from gramps.gen.const import USER_PLUGINS
from gramps.gen.config import logging
from gramps.gen.config import config
from gramps.gen.plug.utils import Zipfile
inifile = config.register_manager("placecoordinategramplet_warn")
inifile.load()
sects = inifile.get_sections()

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(os.path.join(USER_PLUGINS, 'PlaceCoordinateGramplet', 'PlaceCoordinateGramplet.gpr.py'))
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

#-------------------------------------------------------------------------
#
# set up logging
#
#-------------------------------------------------------------------------
_LOG = logging.getLogger("PlaceCoordinateGramplet")


# we should always try to see if prerequisites are there, in case they
# appear at a later time than first run.  But we still don't need to do
# this if there is no GUI, as Gramplet and view are not necessary.
_uistate = locals().get('uistate')
some_import_error = False
while _uistate:
    plugin_name = _("Place Coordinate Gramplet")
    try:
        import gi
        gi.require_version('GeocodeGlib', '1.0')
        from gi.repository import GeocodeGlib
    except:
        if('placecoordinategramplet_warn' not in sects or not
           inifile.is_set('placecoordinategramplet_warn.missingmodules') or
           inifile.get('placecoordinategramplet_warn.missingmodules') !=
           'False'):
            message = _(
                "Failed to load the required module {module_name}.").format(
                    module_name="gi.repository.GeocodeGlib")
            logging.warning(plugin_name + ': ' + message)

            from gramps.gui.dialog import QuestionDialog2
            warn_dialog = QuestionDialog2(
                plugin_name + ' Plugin',
                message,
                _("Don't show again"), _("OK"),
                parent=_uistate.window)
            if warn_dialog.run():
                inifile.register(
                    'placecoordinategramplet_warn.missingmodules', "")
                inifile.set(
                    'placecoordinategramplet_warn.missingmodules', "False")
                inifile.save()
        some_import_error = True
        break

    # now test to make sure that we can actually perform a search.  If there
    # is a problem with connectivity this will fail
    try:
        location_ = GeocodeGlib.Forward.new_for_string("Berlin")
        result = location_.search()
        inifile.register('placecoordinategramplet_warn.connectivity', "")
        inifile.set('placecoordinategramplet_warn.connectivity', "True")
        break
    except Exception as e:
        result = None

        if('placecoordinategramplet_warn' not in sects or not
           inifile.is_set('placecoordinategramplet_warn.connectivity') or
           inifile.get('placecoordinategramplet_warn.connectivity') !=
           'False'):
            message = _(
                "Internet connectivity test failed for {module_name}.").format(
                    module_name="gi.repository.GeocodeGlib") + "\n\n" + str(e)
            logging.warning(plugin_name + ': ' + message)

            from gramps.gui.dialog import QuestionDialog2
            warn_dialog = QuestionDialog2(
                plugin_name + ' Plugin',
                message,
                "Don't show again", "OK",
                parent=_uistate.window)
            if warn_dialog.run():
                logging.warning(plugin_name + ': ' + _('Warning disabled.'))
                inifile.register(
                    'placecoordinategramplet_warn.connectivity', "")
                inifile.set(
                    'placecoordinategramplet_warn.connectivity', "False")
                inifile.save()
        some_import_error = True
        break

if locals().get('uistate') is None or not some_import_error:
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
            version = '1.1.11',
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
            version = '1.1.11',
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
    inifile.save()
