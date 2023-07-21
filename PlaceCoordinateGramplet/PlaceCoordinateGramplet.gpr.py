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

register(VIEW,
        id='geoIDplaceCoordinateGramplet',
        name=_("Place Coordinate Gramplet view"),
        description=_("View for the place coordinate gramplet."),
        version = '1.1.18',
        gramps_target_version="5.2",
        status=STABLE,
        fname='PlaceCoordinateGeoView.py',
        authors=["Christian Schulze"],
        authors_email=["c.w.schulze@gmail.com"],
        category=("Geography", _("Geography")),
        viewclass='PlaceCoordinateGeoView',
        #order = START,
        stock_icon='geo-place-add',
        requires_gi=[('GeocodeGlib', '1.0')],
        )

register(GRAMPLET,
        id="Place Coordinates",
        name=_("Place and Coordinates"),
        description=_(
            "Gramplet that simplifies setting the coordinates of a place"),
        version = '1.1.18',
        gramps_target_version="5.2",
        status=STABLE,
        fname="PlaceCoordinateGramplet.py",
        height=280,
        gramplet='PlaceCoordinateGramplet',
        authors=["Christian Schulze"],
        authors_email=["c.w.schulze@gmail.com"],
        gramplet_title=_("Place Coordinates"),
        navtypes=["Place"],
        requires_gi=[('GeocodeGlib', '1.0')],
        )
