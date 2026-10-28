#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Brian Caudill
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

# ------------------------------------------------------------------------
#
# Register the Geocode Places tool
#
# ------------------------------------------------------------------------
register(
    TOOL,
    id="PlaceGeocoder",
    name=_("Geocode Places"),
    description=_(
        "Bulk-fill missing place coordinates by looking up each place name "
        "with OpenStreetMap Nominatim. By default keeps only town-level or "
        "finer matches (skipping state/country centroids) and writes the "
        "results in a single undoable transaction."
    ),
    version="0.0.1",
    gramps_target_version="6.0",
    status=STABLE,
    audience=EXPERT,
    fname="PlaceGeocoder.py",
    category=TOOL_DBPROC,
    toolclass="PlaceGeocoderWindow",
    optionclass="PlaceGeocoderOptions",
    tool_modes=[TOOL_MODE_GUI],
    authors=["Brian Caudill"],
    authors_email=["brian.m.caudill@gmail.com"],
    maintainers=["Brian Caudill"],
    maintainers_email=["brian.m.caudill@gmail.com"],
    help_url="Addon:PlaceGeocoder",
)
