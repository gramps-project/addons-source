#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Kevin White
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
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""
Generate sample record images for the GWizard source-merge fixtures.

Creates simple placeholder ``.png`` documents (birth/death/marriage/
adoption certificates, a grave marker, newspaper notices and a census
page) under the ``media/`` directory next to this script. They stand in
for real scans so the merge fixtures can exercise Gramps' Media objects
and citation-level OBJE links.
"""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
from __future__ import annotations
import os

# -------------------------------------------------------------------------
#
# Third-party modules
#
# -------------------------------------------------------------------------
from PIL import Image, ImageDraw

MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")

# (filename, title, body lines)
DOCUMENTS: list[tuple[str, str, list[str]]] = [
    (
        "birth_certificate.png",
        "CERTIFICATE OF BIRTH",
        [
            "Name: Anna Lindqvist",
            "Date of Birth: 14 March 1910",
            "Place: Loderup, Malmohus Lan, Sweden",
            "Father: Erik Lindqvist",
            "Mother: Maria Lindqvist",
            "Certificate No. 1910-0042",
        ],
    ),
    (
        "death_certificate.png",
        "CERTIFICATE OF DEATH",
        [
            "Name: Anna Lindqvist",
            "Date of Death: 3 June 1988",
            "Place: Chicago, Cook County, IL",
            "Age: 78 years",
            "Certificate No. 1988-14205",
        ],
    ),
    (
        "grave_marker.png",
        "GRAVE MARKER",
        [
            "ANNA LINDQVIST",
            "1910 - 1988",
            "Beloved Mother & Grandmother",
            "Rosehill Cemetery, Chicago, IL",
        ],
    ),
    (
        "marriage_certificate.png",
        "CERTIFICATE OF MARRIAGE",
        [
            "Groom: Erik Lindqvist",
            "Bride: Anna Svensson",
            "Date: 12 May 1934",
            "Place: Chicago, Cook County, IL",
            "License No. M-1934-8891",
        ],
    ),
    (
        "adoption_certificate.png",
        "CERTIFICATE OF ADOPTION",
        [
            "Child: Nils Lindqvist",
            "Date of Birth: 2 Feb 1938",
            "Adoptive Parents: Erik & Anna Lindqvist",
            "Decree Date: 9 Nov 1940",
            "Cook County Court, Case A-1940-311",
        ],
    ),
    (
        "newspaper_christening.png",
        "CHRISTENING NOTICE",
        [
            "The Daily Chronicle - 24 May 1936",
            "Christened Sunday at Community Church,",
            "infant daughter of Mr. and Mrs. Lindqvist,",
            "named Ingrid Maria. Pastor A. Berg officiating.",
        ],
    ),
    (
        "newspaper_marriage.png",
        "MARRIAGE ANNOUNCEMENT",
        [
            "The Daily Chronicle - 20 May 1934",
            "LINDQVIST - SVENSSON. Erik Lindqvist",
            "and Anna Svensson were united in marriage",
            "May 12 at First Lutheran Church, Chicago.",
        ],
    ),
    (
        "newspaper_obituary.png",
        "OBITUARY",
        [
            "The Daily Chronicle - 6 June 1988",
            "Anna Lindqvist, 78, lifelong Chicago resident,",
            "passed away June 3. Survived by son Nils.",
            "Services June 8, Rosehill Chapel.",
        ],
    ),
    (
        "census_record.png",
        "1930 U.S. CENSUS",
        [
            "Illinois, Cook County, Chicago, Ward 12",
            "Enumeration District 16-432, Sheet 4B",
            "Household 92: Erik Lindqvist 28, Anna 20,",
            "son Nils 2. All born Sweden / Illinois.",
        ],
    ),
]


def make_document(title: str, lines: list[str], path: str) -> None:
    """Render a simple placeholder document image."""
    width, height = 800, 600
    image = Image.new("RGB", (width, height), "ivory")
    draw = ImageDraw.Draw(image)
    draw.rectangle([10, 10, width - 10, height - 10], outline="dimgray", width=4)
    draw.rectangle([24, 24, width - 24, height - 24], outline="gray", width=1)
    y = 60
    draw.text((width // 2 - 10 * len(title) // 2, y), title, fill="black")
    y += 60
    draw.line([80, y, width - 80, y], fill="black", width=2)
    y += 40
    for line in lines:
        draw.text((90, y), line, fill="black")
        y += 45
    image.save(path, "PNG")


def main() -> None:
    """Generate every sample image into the media directory."""
    os.makedirs(MEDIA_DIR, exist_ok=True)
    for filename, title, lines in DOCUMENTS:
        make_document(title, lines, os.path.join(MEDIA_DIR, filename))
    print(f"Wrote {len(DOCUMENTS)} images to {MEDIA_DIR}")


if __name__ == "__main__":
    main()
