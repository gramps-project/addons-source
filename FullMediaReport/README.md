# Full Media Report

A Gramps 6.0 report addon based on the original **Media Report** by Matthias Kemmer.

## Purpose

Creates a single PDF catalogue containing every media object in the active family tree. Each media object starts on a new page.

## Options

- **Heading** — optional prefix for each media entry title.
- **Custom note / Include custom note** — optionally adds the selected note to every entry.
- **Include referenced people** — includes person references and face-crop thumbnails for image media.
- **Include media data** — includes description, MIME type, attributes, tags, linked notes, and citations.
- **Media width / Media height** — controls the maximum displayed image dimensions.

Image files are embedded in the PDF. Non-image media (for example audio, video, and document files) are represented by their recorded file path and MIME type; they are not embedded or converted to previews.

## Compatibility

Target: Gramps 6.0.x.

## Credits and license

The report structure and person-thumbnail implementation are derived from the Gramps Media Report addon by Matthias Kemmer. This addon remains distributed under the GNU General Public License, version 2 or later, in accordance with the original addon license.
