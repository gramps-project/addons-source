#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Douglas S. Blank
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

"""
Generate a blank fillable Ahnentafel pedigree chart PDF.

The chart uses the traditional pedigree tree layout: subject on the left,
ancestors branching to the right in columns, paternal lines at the top and
maternal lines at the bottom.

Field names match what importpdf.py expects:
  Name, Spouse, Birth1, BirthPlace1, Marriage1, MarriagePlace1,
  Death1, DeathPlace1, Father2, Birth2, ..., Mother3, ...

No Gramps installation required.

Usage::

    python3 generate_pedigree_pdf.py                       # interactive
    python3 generate_pedigree_pdf.py --generations 4       # → Pedigree4.pdf
    python3 generate_pedigree_pdf.py --generations 3 --output family.pdf
"""

import argparse
import os
import sys

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
except ImportError:
    print(
        "The reportlab package is required.\n"
        "Install it with:  pip install reportlab",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

MARGIN = 14 * mm     # page margin (all sides)
COL_GAP = 6          # pt — horizontal gap between generation columns
NAME_H = 13          # pt — name field height
FIELD_H = 10         # pt — data field height (birth, death, marriage, place)
SPACE = 4            # pt — uniform vertical gap between every element in a block
DATA_INDENT = 28     # pt — horizontal space reserved for inline field labels

LABEL_FONT = 6       # pt — person-number label above each name field
FIELD_LABEL_FONT = 5  # pt — inline "born / place / ..." labels

# Branding and title block
BRANDING_SIZE = 16   # pt
BRAND_BLOCK_H = 30   # pt
TITLE_SIZE = 11      # pt

COL_LABEL_H = 12     # pt — height reserved for generation column labels
INSTR_H = 9          # pt — height reserved for the one-line instruction

# Total header height consumed above tree_top (must match _draw_header sequence)
HEADER_H = BRAND_BLOCK_H + 4 + TITLE_SIZE + 4 + 6 + INSTR_H + COL_LABEL_H  # = 76 pt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _name_field(n):
    """Return the PDF field name that holds person n's full name."""
    if n == 1:
        return "Name"
    return f"Father{n}" if n % 2 == 0 else f"Mother{n}"


def _person_label(n):
    """Return the short printed label for person n (e.g. '2. Father')."""
    if n == 1:
        return "1. Subject"
    return f"{n}. {'Father' if n % 2 == 0 else 'Mother'}"


def _gen_of(n):
    """Return the generation number for Ahnentafel person n (1-indexed)."""
    g = 1
    while 2 ** g <= n:
        g += 1
    return g


def _gen_persons(gen):
    """Return the list of Ahnentafel numbers in generation gen."""
    start = 2 ** (gen - 1)
    return list(range(start, 2 * start))


def _slot_index(n):
    """Return the 0-based slot index of person n within their generation."""
    return n - 2 ** (_gen_of(n) - 1)


def _fields_for(n):
    """Return (field_name, tooltip) pairs for person n, top-to-bottom."""
    is_father = (n % 2 == 0 and n >= 2)
    is_subject = (n == 1)
    rows = [
        (f"Birth{n}", "Birth date"),
        (f"BirthPlace{n}", "Birth place"),
    ]
    if is_father or is_subject:
        rows += [
            (f"Marriage{n}", "Marriage date"),
            (f"MarriagePlace{n}", "Marriage place"),
        ]
    rows += [
        (f"Death{n}", "Death date"),
        (f"DeathPlace{n}", "Death place"),
    ]
    if is_subject:
        rows.append(("Spouse", "Spouse full name"))
    return rows


def _field_label(fname):
    """Return a short printed label for a data field name like 'Birth3'."""
    for prefix, label in [
        ("BirthPlace", "place"),
        ("Birth", "born"),
        ("MarriagePlace", "m.pl."),
        ("Marriage", "marr."),
        ("DeathPlace", "place"),
        ("Death", "died"),
        ("Spouse", "spouse"),
    ]:
        if fname.startswith(prefix):
            return label
    return ""


def _block_height(n):
    """Return the total rendered height of person n's visual block."""
    n_data = len(_fields_for(n))
    # label + SPACE + name + SPACE + data_fields separated by SPACE
    return LABEL_FONT + SPACE + NAME_H + SPACE + n_data * FIELD_H + max(0, n_data - 1) * SPACE


def _name_field_y_center(n, unit_slot_h, tree_top, generations):
    """Return the y coordinate of the vertical centre of person n's name field."""
    gen = _gen_of(n)
    big_slot = unit_slot_h * 2 ** (generations - gen)
    idx = _slot_index(n)
    slot_y_top = tree_top - idx * big_slot
    bh = _block_height(n)
    padding = max(0.0, (big_slot - bh) / 2)
    name_top = slot_y_top - padding - LABEL_FONT - SPACE
    return name_top - NAME_H / 2


def _find_logo():
    """Return a path to the Gramps logo PNG, or None if not found."""
    candidates = [
        os.path.join(SCRIPT_DIR, "gramps-logo.png"),
        os.path.join(SCRIPT_DIR, "gramps.png"),
    ]
    for prefix in (sys.prefix, sys.exec_prefix):
        candidates.append(os.path.join(prefix, "share", "gramps", "images", "gramps.png"))
    try:
        from gramps.gen.const import IMAGE_DIR
        candidates.append(os.path.join(IMAGE_DIR, "gramps.png"))
    except ImportError:
        pass
    return next((p for p in candidates if os.path.exists(p)), None)


def _draw_branding_header(canv, pw, y):
    """Draw a compact Gramps branding strip. Returns the new y cursor."""
    logo_path = _find_logo()
    brand_top = y - 2

    if logo_path:
        img = ImageReader(logo_path)
        iw, ih = img.getSize()
        img_h = 22
        img_w = iw * img_h / ih
        canv.drawImage(img, MARGIN, brand_top - img_h, width=img_w, height=img_h, mask="auto")
    else:
        canv.setFont("Helvetica-Bold", BRANDING_SIZE)
        canv.setFillColorRGB(0.24, 0.47, 0.24)
        canv.drawString(MARGIN, brand_top - BRANDING_SIZE, "Gramps")
        canv.setFillColorRGB(0, 0, 0)

    canv.setFont("Helvetica", 8)
    canv.drawRightString(pw - MARGIN, brand_top - 9, "Gramps Genealogy Software")
    canv.setFont("Helvetica", 7)
    canv.setFillColorRGB(0.10, 0.32, 0.65)
    canv.drawRightString(pw - MARGIN, brand_top - 18, "https://gramps-project.org")
    canv.setFillColorRGB(0, 0, 0)

    y -= BRAND_BLOCK_H
    canv.setLineWidth(0.5)
    canv.line(MARGIN, y, pw - MARGIN, y)
    y -= 4
    return y


def _draw_person(canv, n, col_x, col_w, slot_y_top, slot_h):
    """
    Draw the name field and data fields for person n, centred within their slot.
    All vertical gaps between elements are equal (SPACE).
    """
    bh = _block_height(n)
    padding = max(0.0, (slot_h - bh) / 2)
    y = slot_y_top - padding  # top of visual block

    # ── Person number label ───────────────────────────────────────────────
    canv.setFont("Helvetica-Bold", LABEL_FONT)
    canv.setFillColorRGB(0.35, 0.35, 0.35)
    canv.drawString(col_x + 1, y - LABEL_FONT, _person_label(n))
    canv.setFillColorRGB(0, 0, 0)
    y -= LABEL_FONT + SPACE

    # ── "name" label + name field ─────────────────────────────────────────
    name_label_y = y - NAME_H + (NAME_H - FIELD_LABEL_FONT) / 2
    canv.setFont("Helvetica", FIELD_LABEL_FONT)
    canv.setFillColorRGB(0.45, 0.45, 0.45)
    canv.drawRightString(col_x + DATA_INDENT - 2, name_label_y, "name")
    canv.setFillColorRGB(0, 0, 0)

    name_fw = max(1.0, col_w - DATA_INDENT - 2)
    canv.acroForm.textfield(
        name=_name_field(n),
        tooltip="Full name",
        x=col_x + DATA_INDENT,
        y=y - NAME_H,
        width=name_fw,
        height=NAME_H,
        fontName="Helvetica",
        fontSize=NAME_H - 2,
        borderWidth=0.5,
    )
    y -= NAME_H + SPACE

    # ── Data fields with inline labels ────────────────────────────────────
    data_x = col_x + DATA_INDENT
    data_fw = max(1.0, col_w - DATA_INDENT - 2)
    fields = _fields_for(n)

    for i, (fname, tip) in enumerate(fields):
        label = _field_label(fname)
        if label:
            canv.setFont("Helvetica", FIELD_LABEL_FONT)
            canv.setFillColorRGB(0.45, 0.45, 0.45)
            canv.drawRightString(
                col_x + DATA_INDENT - 2,
                y - FIELD_H + (FIELD_H - FIELD_LABEL_FONT) / 2,
                label,
            )
            canv.setFillColorRGB(0, 0, 0)

        canv.acroForm.textfield(
            name=fname,
            tooltip=tip,
            x=data_x,
            y=y - FIELD_H,
            width=data_fw,
            height=FIELD_H,
            fontName="Helvetica",
            fontSize=FIELD_H - 2,
            borderWidth=0.4,
        )
        y -= FIELD_H + (SPACE if i < len(fields) - 1 else 0)


def _draw_connector(canv, n, col_w, col_gap, unit_slot_h, tree_top, generations):
    """
    Draw the branching connector from person n to their two parents.
    Connectors attach at the vertical centre of each person's name field.
    """
    g = _gen_of(n)
    if g >= generations:
        return

    child_col_x = MARGIN + (g - 1) * (col_w + col_gap)
    parent_col_x = MARGIN + g * (col_w + col_gap)
    mid_x = child_col_x + col_w + col_gap / 2

    cy = _name_field_y_center(n, unit_slot_h, tree_top, generations)
    fy = _name_field_y_center(2 * n, unit_slot_h, tree_top, generations)
    my = _name_field_y_center(2 * n + 1, unit_slot_h, tree_top, generations)

    canv.setLineWidth(0.35)
    canv.setStrokeColorRGB(0.45, 0.45, 0.45)
    canv.line(child_col_x + col_w, cy, mid_x, cy)
    canv.line(mid_x, fy, mid_x, my)
    canv.line(parent_col_x, fy, mid_x, fy)
    canv.line(parent_col_x, my, mid_x, my)
    canv.setStrokeColorRGB(0, 0, 0)


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_pedigree_pdf(generations, output_path):
    """
    Render a blank fillable Ahnentafel pedigree chart and save to *output_path*.

    The page height is computed from the content so every person block fits
    at full size regardless of the number of generations.

    Args:
        generations: number of ancestor generations to include (1–5)
        output_path: destination file path
    """
    pw = A4[0]

    # unit_slot_h = tallest block in the densest (last) generation
    unit_slot_h = max(_block_height(n) for n in _gen_persons(generations))
    tree_h = unit_slot_h * 2 ** (generations - 1)
    page_h = max(A4[1], 2 * MARGIN + HEADER_H + tree_h)

    avail_w = pw - 2 * MARGIN
    n_cols = generations
    col_gap = COL_GAP
    col_w = (avail_w - (n_cols - 1) * col_gap) / n_cols

    c = canvas.Canvas(output_path, pagesize=(pw, page_h))
    gen_word = f"{generations} Generation{'s' if generations != 1 else ''}"
    c.setTitle(f"Gramps Ahnentafel Pedigree Chart — {gen_word}")
    c.setAuthor("Gramps Genealogy Software")
    c.setSubject("Gramps genealogy form")

    # ── Branding + title header ───────────────────────────────────────────
    y = page_h - MARGIN
    y = _draw_branding_header(c, pw, y)

    c.setFont("Helvetica-Bold", TITLE_SIZE)
    c.drawString(MARGIN, y - TITLE_SIZE, "Gramps Ahnentafel Pedigree Chart")
    c.setFont("Helvetica", 8)
    c.drawRightString(
        pw - MARGIN, y - TITLE_SIZE + 1,
        f"{generations} Generation{'s' if generations != 1 else ''}",
    )
    y -= TITLE_SIZE + 4
    c.setLineWidth(0.4)
    c.line(MARGIN, y, pw - MARGIN, y)
    y -= 6

    # ── Instruction line ──────────────────────────────────────────────────
    c.setFont("Helvetica-Oblique", 6)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawString(
        MARGIN, y - 7,
        "Instructions: Fill in the highlighted fields and save the PDF, "
        "then import into Gramps via File → Import.",
    )
    c.setFillColorRGB(0, 0, 0)
    y -= INSTR_H

    # ── Generation column labels ──────────────────────────────────────────
    gen_labels = {
        1: "Subject", 2: "Parents", 3: "Grandparents",
        4: "Great-Grandparents", 5: "2× Great-Grandparents",
    }
    for gen in range(1, generations + 1):
        col_x = MARGIN + (gen - 1) * (col_w + col_gap)
        label = gen_labels.get(gen, f"Gen {gen}")
        c.setFont("Helvetica-Bold", 5)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawString(col_x, y - 8, label)
        c.setFillColorRGB(0, 0, 0)
    y -= COL_LABEL_H

    # ── Tree ─────────────────────────────────────────────────────────────
    tree_top = y

    # ── Connectors (drawn first, behind person boxes) ─────────────────────
    for gen in range(1, generations):
        for n in _gen_persons(gen):
            _draw_connector(c, n, col_w, col_gap, unit_slot_h, tree_top, generations)

    # ── Person boxes ──────────────────────────────────────────────────────
    for gen in range(1, generations + 1):
        col_x = MARGIN + (gen - 1) * (col_w + col_gap)
        big_slot = unit_slot_h * 2 ** (generations - gen)

        for n in _gen_persons(gen):
            idx = _slot_index(n)
            slot_y_top = tree_top - idx * big_slot
            _draw_person(c, n, col_x, col_w, slot_y_top, big_slot)

    # ── Hidden _form_id so importpdf.py routes to the pedigree importer ──
    c.acroForm.textfield(
        name="_form_id",
        value=f"pedigree{generations}",
        x=0, y=0, width=1, height=1,
        fontName="Helvetica", fontSize=1,
        borderWidth=0,
        fieldFlags="readOnly",
    )

    c.save()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate a blank fillable Gramps Ahnentafel pedigree chart PDF."
    )
    parser.add_argument(
        "--generations", "-g",
        type=int, default=None,
        metavar="N",
        help="Number of generations to include (1–5, default 4)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output PDF path (default: Pedigree{N}.pdf)",
    )
    args = parser.parse_args()

    generations = args.generations
    if generations is None:
        try:
            raw = input("Number of generations [4]: ").strip()
            generations = int(raw) if raw else 4
        except (ValueError, EOFError):
            generations = 4

    if not (1 <= generations <= 5):
        print(f"Generations must be between 1 and 5 (got {generations}).", file=sys.stderr)
        sys.exit(1)

    output = args.output or f"Pedigree{generations}.pdf"
    generate_pedigree_pdf(generations, output)
    print(f"Generated: {output}")


if __name__ == "__main__":
    main()
