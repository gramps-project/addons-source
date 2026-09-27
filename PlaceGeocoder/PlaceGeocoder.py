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

"""
Geocode Places tool.

Walks every place that has no coordinates, looks the place name up with
OpenStreetMap Nominatim, and writes back latitude/longitude. By default only
town-level or finer matches are kept, so vague names that resolve to a state or
country centroid are skipped rather than dropping a misleading pin.
"""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
import json
import time
import urllib.request
import urllib.parse

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.db import DbTxn
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.plug.menu import NumberOption, BooleanOption, StringOption
from gramps.gui.plug import MenuToolOptions, PluginWindows
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Result granularities coarser than a town -- skipped when "town or better" is
# requested, so a vague name never drops a state/country centroid pin.
COARSE_TYPES = {
    "country",
    "state",
    "county",
    "region",
    "province",
    "state_district",
    "continent",
}
# Nominatim place_rank: lower == larger area. county is ~12, city ~16, town ~18.
MIN_RANK_TOWN = 13


# -------------------------------------------------------------------------
#
# Helper functions
#
# -------------------------------------------------------------------------
def geocode(name, user_agent, timeout=20):
    """
    Look one place name up with Nominatim.

    :returns: a dict with lat, lon, rank, atype and match on success, or None
        when there is no result. Network/parse errors propagate to the caller.
    """
    query = urllib.parse.urlencode({"q": name, "format": "json", "limit": 1})
    request = urllib.request.Request(
        NOMINATIM_URL + "?" + query, headers={"User-Agent": user_agent}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    if not data:
        return None
    hit = data[0]
    return {
        "lat": hit["lat"],
        "lon": hit["lon"],
        "rank": int(hit.get("place_rank", 0)),
        "atype": hit.get("addresstype", ""),
        "match": hit.get("display_name", ""),
    }


def is_town_or_better(hit):
    """
    Return True if a Nominatim hit is town-level or finer.
    """
    if hit["atype"] in COARSE_TYPES:
        return False
    return hit["rank"] >= MIN_RANK_TOWN


# -------------------------------------------------------------------------
#
# PlaceGeocoderOptions
#
# -------------------------------------------------------------------------
class PlaceGeocoderOptions(MenuToolOptions):
    """
    Options for the Geocode Places tool.
    """

    def add_menu_options(self, menu):
        """
        Add the tool options.
        """
        category = _("Options")

        town_or_better = BooleanOption(_("Keep only town-level or finer"), True)
        town_or_better.set_help(
            _("Skip matches that only resolve to a state or country centroid.")
        )
        menu.add_option(category, "town_or_better", town_or_better)

        write_changes = BooleanOption(_("Write coordinates to the tree"), True)
        write_changes.set_help(
            _("Turn off for a dry run that only reports what would be set.")
        )
        menu.add_option(category, "write_changes", write_changes)

        limit = NumberOption(_("Maximum places (0 = all)"), 0, 0, 100000)
        limit.set_help(_("Process at most this many places; 0 means no limit."))
        menu.add_option(category, "limit", limit)

        delay = NumberOption(_("Seconds between lookups"), 1, 1, 10)
        delay.set_help(
            _("Nominatim asks for at most one request per second; do not lower.")
        )
        menu.add_option(category, "delay", delay)

        email = StringOption(_("Contact email (for the request header)"), "")
        email.set_help(
            _("Nominatim's usage policy asks bulk users to identify themselves.")
        )
        menu.add_option(category, "email", email)


# -------------------------------------------------------------------------
#
# PlaceGeocoderWindow
#
# -------------------------------------------------------------------------
class PlaceGeocoderWindow(PluginWindows.ToolManagedWindowBatch):
    """
    Tool window that performs the geocoding pass.
    """

    def get_title(self):
        """
        Return the tool window title.
        """
        return _("Geocode Places")

    def initial_frame(self):
        """
        Return the name of the options frame.
        """
        return _("Options")

    def run(self):
        """
        Geocode every place that is missing coordinates.
        """
        opts = self.options.handler.options_dict
        town_or_better = opts["town_or_better"]
        write_changes = opts["write_changes"]
        limit = opts["limit"]
        delay = max(1, opts["delay"])
        email = (opts["email"] or "").strip()
        user_agent = "Gramps-PlaceGeocoder/0.0.1"
        if email:
            user_agent += " (%s)" % email

        todo = []
        for place in self.db.iter_places():
            lat = (place.get_latitude() or "").strip()
            lon = (place.get_longitude() or "").strip()
            if not lat and not lon:
                todo.append(place.get_handle())
            if limit and len(todo) >= limit:
                break

        self.add_results_frame(_("Results"))
        if not todo:
            self.results_write(_("Every place already has coordinates.\n"))
            return

        mode = _("dry run") if not write_changes else _("writing changes")
        self.results_write(
            _("Geocoding %(count)d place(s) [%(mode)s]...\n")
            % {"count": len(todo), "mode": mode}
        )
        self.progress.set_pass(_("Geocoding places..."), len(todo))

        set_count = skip_count = miss_count = error_count = 0
        trans = None
        if write_changes:
            trans = DbTxn(_("Geocode Places"), self.db, batch=True)
            trans.__enter__()
            self.db.disable_signals()
        try:
            for handle in todo:
                place = self.db.get_place_from_handle(handle)
                name = place_displayer.display(self.db, place)
                try:
                    hit = geocode(name, user_agent)
                except Exception as err:  # network / parse problem
                    error_count += 1
                    self.results_write(_("  error: %s (%s)\n") % (name, err))
                    self.progress.step()
                    time.sleep(delay)
                    continue

                if hit is None:
                    miss_count += 1
                elif town_or_better and not is_town_or_better(hit):
                    skip_count += 1
                else:
                    set_count += 1
                    if write_changes:
                        place.set_latitude(str(hit["lat"]))
                        place.set_longitude(str(hit["lon"]))
                        self.db.commit_place(place, trans)
                self.progress.step()
                time.sleep(delay)
        finally:
            if write_changes:
                self.db.enable_signals()
                trans.__exit__(None, None, None)
                self.db.request_rebuild()

        self.results_write("\n")
        self.results_write(
            _("Set coordinates: %d\n") % set_count
        )
        self.results_write(
            _("Skipped (too coarse): %d\n") % skip_count
        )
        self.results_write(_("No match: %d\n") % miss_count)
        if error_count:
            self.results_write(_("Errors: %d\n") % error_count)
        if not write_changes:
            self.results_write(
                _("\nDry run only -- no coordinates were written.\n")
            )
