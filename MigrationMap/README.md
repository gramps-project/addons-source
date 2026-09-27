# Migration Map

A Gramps **Tool** that builds an animated, interactive map of how people and
families moved over time, then opens it in your web browser.

It reads every dated event whose place has coordinates, groups them per person
in time order, and writes a self-contained HTML page (Leaflet) with a timeline
you can play: each person's moves **draw themselves across the years**, dots
**pulse** on the moves happening that year, and a readout shows who is moving
where. Paths are colored by surname.

## Usage

**Tools → Analysis and Exploration → Migration Map**

Options:

| Option | Default | Meaning |
|--------|---------|---------|
| Draw migration paths | on | Connect each person's locations in time order with a line that grows as the animation plays. |
| Output HTML file | (blank) | Where to write the page; blank uses a temp file. |

Press **▶ Play**, drag the gold handle to scrub through time, or **⏮ Restart**.

## Requirements

The map only shows places that have **coordinates**. Genealogy imports usually
have place names but no coordinates, so run a geocoder first — for example the
companion **Geocode Places** tool, or set coordinates with the **Place
Coordinate Gramplet**. Events also need a year.

## Notes

- The page loads Leaflet and OpenStreetMap tiles from the internet (with
  Subresource Integrity pinned), so an internet connection is needed to view it.
- All person, place, and event text is HTML-escaped before being embedded.

## Contact

Brian Caudill — brian.m.caudill@gmail.com
