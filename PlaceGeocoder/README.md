# Geocode Places

A Gramps **Tool** that bulk-fills missing place coordinates so the Geography
views can map your tree.

Most Gramps coordinate tools are *interactive* — you set one place at a time
(the Place Coordinate Gramplet, Place Cleanup's GeoNames lookup, or the
Geography view with `geocode-glib`). This tool is the **batch** counterpart: it
walks every place that has no coordinates, looks the place name up with
OpenStreetMap Nominatim, and writes the results in one undoable pass.

## Usage

**Tools → Family Tree Processing → Geocode Places**

Options:

| Option | Default | Meaning |
|--------|---------|---------|
| Keep only town-level or finer | on | Skip matches that resolve only to a state or country centroid (avoids misleading pins). |
| Write coordinates to the tree | on | Turn **off** for a dry run that only reports what would be set. |
| Maximum places (0 = all) | 0 | Process at most this many places. |
| Seconds between lookups | 1 | Nominatim allows at most 1 request/second — do not lower. |
| Contact email | (empty) | Nominatim's usage policy asks bulk users to identify themselves. |

**Recommended first run:** turn *Write coordinates* off and set *Maximum places*
to ~20 for a quick dry run, then run for real once the hit rate looks good.

The whole pass runs in a single transaction, so one **Undo** reverts everything
if you are not happy with the result.

## Notes

- Geocoding accuracy depends on how clean your place names are. Full street
  addresses with apartment numbers and non-places (e.g. census precincts) may
  not resolve; clean "City, County, State, Country" names work best.
- Respect [Nominatim's usage policy](https://operations.osmfoundation.org/policies/nominatim/):
  this tool is rate-limited to one request per second and is intended for
  occasional personal use, not large-scale harvesting.
- Pairs well with **Place Cleanup**, which can merge the duplicate place records
  that genealogy imports often create.

## Contact

Brian Caudill — brian.m.caudill@gmail.com
