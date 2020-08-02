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
inifile = config.register_manager("placecoordinategramplet_warn")
inifile.load()
sects = inifile.get_sections()

#-------------------------------------------------------------------------
#
# set up logging
#
#-------------------------------------------------------------------------
import logging
_LOG = logging.getLogger("PlaceCoordinateGeography View")


import os
import sys
import importlib


spec = importlib.util.spec_from_file_location(
    'ModuleProvider',
    os.path.join(
        USER_PLUGINS,
        'PlaceCoordinateGramplet',
        'ModuleProvider.py')
    )
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
ModuleProvider = module.ModuleProvider


try:
    if 'placecoordinategramplet_warn' not in sects or not inifile.get('placecoordinategramplet_warn.missingmodules') != 'False':
        _uistate = locals().get('uistate')
    else:
        _uistate = None
    mp=ModuleProvider('PlaceCoordinateGramplet', _uistate)
    geopy = mp.request(
        'geopy',
        '2.0.0',
        'https://pypi.python.org/packages/source/g/geopy/geopy-2.0.0.tar.gz'
    )

    # use additional icons:
    # fname = os.path.join(USER_PLUGINS, 'PlaceCoordinateGramplet')
    # icons = Gtk.IconTheme().get_default()
    # icons.append_search_path(fname)
    some_import_error = geopy is None

except Exception as e:
    some_import_error = True
    import_error_message = traceback.format_exc()
    logging.log(logging.ERROR, 'Failed to load PlaceCoordinateGramplet plugin.\n' + import_error_message)

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
            version = '1.1.4',
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
            name=_("Place Coordinates"),
            description=_(
                "Gramplet that simplifies setting the coordinates of a place"),
            version = '1.1.4',
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
    inifile.register('placecoordinate_warn.missingmodules', "")
    inifile.set('placecoordinate_warn.missingmodules', "True")
    inifile.save()
