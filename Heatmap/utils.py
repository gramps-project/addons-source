#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021    Matthias Kemmer
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
"""Collection utility classes and functions for heatmap report."""


# ------------------------------------------------------------------------
#
# GRAMPS modules
#
# ------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale  # type: ignore
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# ------------------------------------------------------------------------
#
# MapTiles Class
#
# ------------------------------------------------------------------------
class MapTiles:
    """Class storing map tiles data."""
    OPENSTREETMAP = 0
    STEAMEN_TERRAIN = 1
    STEAMEN_TERRAIN_BACKGROUND = 2
    STEAMEN_TONER = 3
    STEAMEN_WATERCOLOR = 4
    CARTODB_POSITRON = 5
    CARTODB_DARKMATTER = 6

    _DATAMAP = [
        (OPENSTREETMAP, _("OpenStreetMap"),
         "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
         "\u0026copy <a href=www.openstreetmap.org/copyright>OpenStreetMap</a> contributors"),
        (STEAMEN_TERRAIN, _("Stamen Terrain"),
         "https://stamen-tiles-{s}.a.ssl.fastly.net/terrain/{z}/{x}/{y}.jpg",
         "Map tiles by \u003ca href=\"http://stamen.com\"\u003eStamen Design\u003c/a\u003e, under \u003ca href=\"http://creativecommons.org/licenses/by/3.0\"\u003eCC BY 3.0\u003c/a\u003e. Data by \u0026copy; \u003ca href=\"http://openstreetmap.org\"\u003eOpenStreetMap\u003c/a\u003e, under \u003ca href=\"http://www.openstreetmap.org/copyright\"\u003eODbL\u003c/a\u003e."),
        (STEAMEN_TERRAIN_BACKGROUND, _("Stamen Terrain (Background only)"),
         "https://stamen-tiles-{s}.a.ssl.fastly.net/terrain-background/{z}/{x}/{y}.jpg",
         "Map tiles by \u003ca href=\"http://stamen.com\"\u003eStamen Design\u003c/a\u003e, under \u003ca href=\"http://creativecommons.org/licenses/by/3.0\"\u003eCC BY 3.0\u003c/a\u003e. Data by \u0026copy; \u003ca href=\"http://openstreetmap.org\"\u003eOpenStreetMap\u003c/a\u003e, under \u003ca href=\"http://www.openstreetmap.org/copyright\"\u003eODbL\u003c/a\u003e."),
        (STEAMEN_TONER, _("Stamen Toner"),
         "https://stamen-tiles-{s}.a.ssl.fastly.net/toner/{z}/{x}/{y}.png",
         "Map tiles by \u003ca href=\"http://stamen.com\"\u003eStamen Design\u003c/a\u003e, under \u003ca href=\"http://creativecommons.org/licenses/by/3.0\"\u003eCC BY 3.0\u003c/a\u003e. Data by \u0026copy; \u003ca href=\"http://openstreetmap.org\"\u003eOpenStreetMap\u003c/a\u003e, under \u003ca href=\"http://www.openstreetmap.org/copyright\"\u003eODbL\u003c/a\u003e."),
        (STEAMEN_WATERCOLOR, _("Stamen Watercolor"),
         "https://stamen-tiles-{s}.a.ssl.fastly.net/watercolor/{z}/{x}/{y}.jpg",
         "Map tiles by \u003ca href=\"http://stamen.com\"\u003eStamen Design\u003c/a\u003e, under \u003ca href=\"http://creativecommons.org/licenses/by/3.0\"\u003eCC BY 3.0\u003c/a\u003e. Data by \u0026copy; \u003ca href=\"http://openstreetmap.org\"\u003eOpenStreetMap\u003c/a\u003e, under \u003ca href=\"http://creativecommons.org/licenses/by-sa/3.0\"\u003eCC BY SA\u003c/a\u003e."),
        (CARTODB_POSITRON, _("CartoDB Positron"),
         "https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png",
         "\u0026copy; \u003ca href=\"http://www.openstreetmap.org/copyright\"\u003eOpenStreetMap\u003c/a\u003e contributors \u0026copy; \u003ca href=\"http://cartodb.com/attributions\"\u003eCartoDB\u003c/a\u003e, CartoDB \u003ca href =\"http://cartodb.com/attributions\"\u003eattributions\u003c/a\u003e"),
        (CARTODB_DARKMATTER, _("CartoDB DarkMatter"),
         "https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png",
         "\u0026copy; \u003ca href=\"http://www.openstreetmap.org/copyright\"\u003eOpenStreetMap\u003c/a\u003e contributors \u0026copy; \u003ca href=\"http://cartodb.com/attributions\"\u003eCartoDB\u003c/a\u003e, CartoDB \u003ca href =\"http://cartodb.com/attributions\"\u003eattributions\u003c/a\u003e")
    ]

# ------------------------------------------------------------------------
#
# PersonFilterEnum Class
#
# ------------------------------------------------------------------------


class PersonFilterEnum:
    """Class for enum like constants."""
    ALL = 0
    ANCESTORS = 1
    DESCENDANTS = 2
    SINGLE = 3


# ------------------------------------------------------------------------
#
# HeatmapPlaces Class
#
# ------------------------------------------------------------------------
class HeatmapPlace:
    """Class storing heatmap place data."""

    def __init__(self, name, latitude, longitude, count):
        self.name = name  # gramps_id
        self.lat = latitude
        self.lon = longitude
        self.count = count

    def to_list(self):
        return [self.lat, self.lon, self.count]
