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
Generate a blank fillable PDF form from a Gramps Form addon XML definition.

No Gramps installation required — reads the form_*.xml files directly.

Usage::

    python3 Form/generate_pdf.py                    # interactive
    python3 Form/generate_pdf.py US1790             # → US1790.pdf
    python3 Form/generate_pdf.py US1790 out.pdf     # explicit output path
    python3 Form/generate_pdf.py --list             # list all form IDs
    python3 Form/generate_pdf.py US1790 --rows 25  # custom row count
"""

import argparse
import os
import re
import sys
import xml.dom.minidom

try:
    from reportlab.lib.pagesizes import A4, landscape as rl_landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
except ImportError:
    print(
        "The reportlab package is required.\n"
        "Install it with:  pip install reportlab",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Look for Form XML files in the sibling Form/ directory first
_sibling_form = os.path.join(os.path.dirname(SCRIPT_DIR), "Form")
FORM_XML_DIR = _sibling_form if os.path.isdir(_sibling_form) else SCRIPT_DIR

DEFINITION_FILES = [
    "form_be.xml",
    "form_ca.xml",
    "form_dk.xml",
    "form_fr.xml",
    "form_gb.xml",
    "form_pl.xml",
    "form_us.xml",
    "custom.xml",
]

MARGIN = 14 * mm        # page margin (all sides)
TITLE_SIZE = 13         # pt — form title
LABEL_SIZE = 8          # pt — heading labels and section titles
HEADER_SIZE = 7         # pt — column header text
FIELD_SIZE = 8          # pt — font inside editable fields
ROW_HEIGHT = 13         # pt — height of one data row (field + padding)
FIELD_HEIGHT = 11       # pt — AcroForm field height
HEADER_LINES = 2        # max lines reserved for wrapped column headers
SECTION_GAP = 8         # pt — vertical gap between sections
HEADING_PER_ROW = 3     # heading label+field pairs per line
BRANDING_HEIGHT = 35    # pt — Gramps branding block (text + divider gap)
INSTR_SIZE = 7          # pt — instructions line font size


# ---------------------------------------------------------------------------
# XML parsing helpers (no Gramps imports)
# ---------------------------------------------------------------------------

def _text(element, tag):
    """Return the text content of the first matching child element, or ''."""
    nodes = element.getElementsByTagName(tag)
    if nodes and nodes[0].childNodes:
        return nodes[0].childNodes[0].data.strip()
    return ""


def list_forms(xml_dir=None):
    """Return [(form_id, title), ...] for every form in every definition file."""
    xml_dir = xml_dir or FORM_XML_DIR
    forms = []
    for fname in DEFINITION_FILES:
        path = os.path.join(xml_dir, fname)
        if not os.path.exists(path):
            continue
        try:
            dom = xml.dom.minidom.parse(path)
        except Exception:
            continue
        for el in dom.getElementsByTagName("form"):
            fid = el.getAttribute("id")
            title = el.getAttribute("title")
            if fid and title:
                forms.append((fid, title))
        dom.unlink()
    return forms


def load_form(form_id, xml_dir=None):
    """
    Parse one form definition and return a dict, or None if not found.

    Returned dict structure::

        {
            "id":       "US1790",
            "title":    "1790 US Census",
            "date":     "1790-08-02",
            "headings": ["NARA publication", "Roll No.", ...],
            "sections": [
                {
                    "role":    "Primary",
                    "type":    "multi",       # "multi" | "person" | "family"
                    "title":   "",
                    "columns": [
                        {"attribute": "Name", "size": 25, "longname": "Full name..."},
                        ...
                    ],
                },
                ...
            ],
        }
    """
    xml_dir = xml_dir or FORM_XML_DIR
    for fname in DEFINITION_FILES:
        path = os.path.join(xml_dir, fname)
        if not os.path.exists(path):
            continue
        try:
            dom = xml.dom.minidom.parse(path)
        except Exception:
            continue
        for el in dom.getElementsByTagName("form"):
            if el.getAttribute("id") != form_id:
                continue
            form = {
                "id": form_id,
                "title": el.getAttribute("title"),
                "date": el.getAttribute("date"),
                "headings": [],
                "sections": [],
            }
            for h in el.getElementsByTagName("heading"):
                attr = _text(h, "_attribute")
                if attr:
                    form["headings"].append(attr)
            for sec in el.getElementsByTagName("section"):
                columns = []
                for col in sec.getElementsByTagName("column"):
                    attr = _text(col, "_attribute")
                    size_raw = _text(col, "size")
                    size = int(size_raw) if size_raw.isdigit() else 0
                    longname = _text(col, "_longname") or attr
                    columns.append({"attribute": attr, "size": size, "longname": longname})
                form["sections"].append({
                    "role":    sec.getAttribute("role"),
                    "type":    sec.getAttribute("type"),
                    "title":   sec.getAttribute("title"),
                    "columns": columns,
                })
            dom.unlink()
            return form
        dom.unlink()
    return None


# ---------------------------------------------------------------------------
# PDF generation helpers
# ---------------------------------------------------------------------------

def _sanitize(text):
    """Convert arbitrary text to a valid PDF field name."""
    return re.sub(r"[^A-Za-z0-9_]", "_", text).strip("_") or "field"


MIN_COL_W = 20   # pt — minimum usable column width


def _col_widths(columns, available_w):
    """Return a list of point widths proportional to each column's <size>."""
    sizes = [c["size"] for c in columns]
    total = sum(sizes)
    if total > 0 and all(s > 0 for s in sizes):
        return [available_w * s / total for s in sizes]
    n = len(columns) or 1
    return [available_w / n] * len(columns)


def _required_avail_w(columns):
    """
    Return the minimum available_w so every proportional column >= MIN_COL_W.
    Used to expand the page rather than squish columns.
    """
    sizes = [c["size"] for c in columns]
    pos = [s for s in sizes if s > 0]
    if not pos:
        return 0
    return MIN_COL_W * sum(sizes) / min(pos)


def _wrap_text(text, max_width, canv, font, size):
    """Break *text* into lines that fit within *max_width* points."""
    words = text.split()
    lines, line = [], ""
    for word in words:
        candidate = (line + " " + word).strip()
        if canv.stringWidth(candidate, font, size) <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines or [""]


def _find_logo():
    """Return a path to the Gramps logo PNG, or None if not found."""
    candidates = [
        os.path.join(SCRIPT_DIR, "gramps-logo.png"),
        os.path.join(SCRIPT_DIR, "gramps.png"),
    ]
    import sys
    for prefix in (sys.prefix, sys.exec_prefix):
        candidates.append(os.path.join(prefix, "share", "gramps", "images", "gramps.png"))
    try:
        from gramps.gen.const import IMAGE_DIR
        candidates.append(os.path.join(IMAGE_DIR, "gramps.png"))
    except ImportError:
        pass
    return next((p for p in candidates if os.path.exists(p)), None)


def _draw_branding_header(canv, pw, y):
    """
    Draw the Gramps branding block at the current y position.
    Returns the new y cursor position after the block and divider.
    """
    logo_path = _find_logo()
    brand_top = y - 2

    if logo_path:
        img = ImageReader(logo_path)
        iw, ih = img.getSize()
        img_h = 24
        img_w = iw * img_h / ih  # preserve aspect ratio
        canv.drawImage(img, MARGIN, brand_top - img_h, width=img_w, height=img_h, mask="auto")
    else:
        # Text fallback: "Gramps" in dark green
        canv.setFont("Helvetica-Bold", 16)
        canv.setFillColorRGB(0.24, 0.47, 0.24)
        canv.drawString(MARGIN, brand_top - 16, "Gramps")
        canv.setFillColorRGB(0, 0, 0)

    # Right side: tagline + URL
    canv.setFont("Helvetica", 9)
    canv.drawRightString(pw - MARGIN, brand_top - 9, "Gramps Genealogy Software")
    canv.setFont("Helvetica", 8)
    canv.setFillColorRGB(0.10, 0.32, 0.65)
    canv.drawRightString(pw - MARGIN, brand_top - 20, "https://gramps-project.org")
    canv.setFillColorRGB(0, 0, 0)

    y -= BRANDING_HEIGHT
    canv.setLineWidth(0.5)
    canv.line(MARGIN, y, pw - MARGIN, y)
    y -= 5
    return y


def _draw_column_headers(canv, columns, col_widths, x0, y_top):
    """
    Draw column headers above a data grid, bottom-aligned within each column.
    Each column is clipped to its own width so text never bleeds into neighbours.
    Returns the y coordinate of the bottom of the header block.
    """
    header_h = HEADER_LINES * (HEADER_SIZE + 1) + 2
    for col_info, cw in zip(columns, col_widths):
        lines = _wrap_text(col_info["attribute"], cw - 2, canv, "Helvetica-Bold", HEADER_SIZE)
        display = lines[-HEADER_LINES:]

        # Clip this column so long words cannot bleed into the next column.
        canv.saveState()
        clip = canv.beginPath()
        clip.rect(x0, y_top - header_h, cw - 1, header_h)
        canv.clipPath(clip, stroke=0, fill=0)

        # Bottom-aligned, top-to-bottom reading order:
        # draw the last display line at the bottom, work upward.
        y = y_top - header_h + 2
        for line in reversed(display):
            canv.setFont("Helvetica-Bold", HEADER_SIZE)
            canv.drawString(x0 + 1, y, line)
            y += HEADER_SIZE + 1

        canv.restoreState()
        x0 += cw
    return y_top - header_h


def _add_row_fields(canv, columns, col_widths, x0, y, role, row_suffix):
    """Add one row of AcroForm text fields and return the y of the next row."""
    cx = x0
    for col_info, cw in zip(columns, col_widths):
        fname = _sanitize(f"{role}_{col_info['attribute']}_{row_suffix}")
        canv.acroForm.textfield(
            name=fname,
            tooltip=col_info["longname"],
            x=cx,
            y=y - FIELD_HEIGHT,
            width=cw - 1,
            height=FIELD_HEIGHT,
            fontName="Helvetica",
            fontSize=FIELD_SIZE,
            borderWidth=0.5,
        )
        cx += cw
    return y - ROW_HEIGHT


# ---------------------------------------------------------------------------
# Main PDF generator
# ---------------------------------------------------------------------------

def _required_page_height(form, rows):
    """Return the page height (in points) needed to render all sections with *rows* data rows."""
    h = 2 * MARGIN
    h += BRANDING_HEIGHT + 5
    h += TITLE_SIZE + 4 + 5
    h += INSTR_SIZE + 3 + 5
    n_hr = (len(form["headings"]) + HEADING_PER_ROW - 1) // HEADING_PER_ROW
    if n_hr:
        h += n_hr * ROW_HEIGHT + 3 + 5
    header_block = HEADER_LINES * (HEADER_SIZE + 1) + 2 + 1
    for sec in form["sections"]:
        if not sec["columns"]:
            continue
        h += LABEL_SIZE + 1 + 3        # section title
        h += header_block              # column headers
        h += (rows if sec["type"] == "multi" else 1) * ROW_HEIGHT
        h += SECTION_GAP + 3
    return h


def generate_form_pdf(form, rows, output_path):
    """
    Render *form* as a blank fillable PDF and save it to *output_path*.

    Args:
        form:        dict returned by :func:`load_form`
        rows:        number of data rows for ``multi``-type sections
        output_path: destination file path (will be created/overwritten)
    """
    sections = form["sections"]
    max_multi_cols = max(
        (len(s["columns"]) for s in sections if s["type"] == "multi"),
        default=0,
    )
    base_pw, base_ph = rl_landscape(A4) if max_multi_cols > 4 else A4

    # Expand width so every column is at least MIN_COL_W points wide.
    needed_avail = max(
        (_required_avail_w(s["columns"]) for s in sections
         if s["type"] == "multi" and s["columns"]),
        default=0,
    )
    base_avail = base_pw - 2 * MARGIN
    pw = base_pw if needed_avail <= base_avail else needed_avail + 2 * MARGIN
    avail_w = pw - 2 * MARGIN

    # Expand height so all requested rows fit without truncation.
    ph = max(base_ph, _required_page_height(form, rows))

    page_size = (pw, ph)
    c = canvas.Canvas(output_path, pagesize=page_size)
    c.setTitle("Gramps " + form["title"])
    c.setAuthor("Gramps Genealogy Software")
    c.setSubject("Gramps genealogy form")

    y = ph - MARGIN  # current top-of-cursor (points from bottom)

    # ── Branding header ────────────────────────────────────────────────────
    y = _draw_branding_header(c, pw, y)

    # ── Title ──────────────────────────────────────────────────────────────
    c.setFont("Helvetica-Bold", TITLE_SIZE)
    c.drawString(MARGIN, y - TITLE_SIZE, "Gramps " + form["title"])
    if form.get("date"):
        c.setFont("Helvetica", 9)
        c.drawRightString(pw - MARGIN, y - TITLE_SIZE + 1, form["date"])
    y -= TITLE_SIZE + 4

    c.setLineWidth(0.5)
    c.line(MARGIN, y, pw - MARGIN, y)
    y -= 5

    # ── Instructions ───────────────────────────────────────────────────────
    c.setFont("Helvetica-Oblique", INSTR_SIZE)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(
        MARGIN, y - INSTR_SIZE,
        "Fill in each field below, save the completed form, "
        "then return it to the sender or import it directly into Gramps.",
    )
    c.setFillColorRGB(0, 0, 0)
    y -= INSTR_SIZE + 3
    c.setLineWidth(0.3)
    c.line(MARGIN, y, pw - MARGIN, y)
    y -= 5

    # ── Heading fields (form metadata) ─────────────────────────────────────
    if form["headings"]:
        heading_w = avail_w / HEADING_PER_ROW
        col = 0
        row_top = y
        for i, heading in enumerate(form["headings"]):
            hx = MARGIN + col * heading_w
            label = heading + ":"
            lw = c.stringWidth(label, "Helvetica", LABEL_SIZE) + 2
            # Label
            c.setFont("Helvetica", LABEL_SIZE)
            c.drawString(hx, row_top - LABEL_SIZE, label)
            # Field
            field_w = heading_w - lw - 2
            if field_w >= 20:
                c.acroForm.textfield(
                    name=f"heading_{i}",
                    tooltip=heading,
                    x=hx + lw,
                    y=row_top - FIELD_HEIGHT,
                    width=field_w,
                    height=FIELD_HEIGHT,
                    fontName="Helvetica",
                    fontSize=FIELD_SIZE,
                    borderWidth=0.5,
                )
            col += 1
            if col >= HEADING_PER_ROW:
                col = 0
                row_top -= ROW_HEIGHT
        heading_rows = (len(form["headings"]) + HEADING_PER_ROW - 1) // HEADING_PER_ROW
        y -= heading_rows * ROW_HEIGHT + 3

        c.setLineWidth(0.3)
        c.line(MARGIN, y, pw - MARGIN, y)
        y -= 5

    # ── Sections ───────────────────────────────────────────────────────────
    for sec_idx, section in enumerate(sections):
        role    = section["role"]
        stype   = section["type"]
        title   = section["title"] or role
        columns = section["columns"]
        if not columns:
            continue

        # Ensure we have room for at least the section title + header + one row
        min_needed = LABEL_SIZE + 4 + HEADER_LINES * (HEADER_SIZE + 1) + ROW_HEIGHT
        if y - min_needed < MARGIN:
            y = new_page()

        # Section title
        c.setFont("Helvetica-Bold", LABEL_SIZE + 1)
        c.drawString(MARGIN, y - (LABEL_SIZE + 1), title)
        y -= LABEL_SIZE + 1 + 3

        cws = _col_widths(columns, avail_w)

        # ── family: Groom + Bride split ─────────────────────────────────
        if stype == "family":
            parts = title.split("/", 1)
            side_labels = (parts[0].strip(), parts[1].strip() if len(parts) > 1 else "")
            half_w = (avail_w - 4) / 2
            side_x = [MARGIN, MARGIN + half_w + 4]
            side_keys = ["Groom", "Bride"]

            for s_label, sx, sk in zip(side_labels, side_x, side_keys):
                side_cws = _col_widths(columns, half_w)
                # Side sub-title
                c.setFont("Helvetica-Bold", LABEL_SIZE)
                c.drawString(sx, y - LABEL_SIZE, s_label or sk)
                # Column headers
                header_bot = _draw_column_headers(c, columns, side_cws, sx, y - LABEL_SIZE - 2)
            y = header_bot - 1

            # One data row per side
            for sx, sk in zip(side_x, side_keys):
                side_cws = _col_widths(columns, half_w)
                _add_row_fields(c, columns, side_cws, sx, y, f"{role}_{sk}", "1")
            y -= ROW_HEIGHT

        # ── person: single data row ─────────────────────────────────────
        elif stype == "person":
            y = _draw_column_headers(c, columns, cws, MARGIN, y) - 1
            y = _add_row_fields(c, columns, cws, MARGIN, y, role, "1")

        # ── multi: N data rows ──────────────────────────────────────────
        else:
            y = _draw_column_headers(c, columns, cws, MARGIN, y) - 1
            for row_i in range(1, rows + 1):
                y = _add_row_fields(c, columns, cws, MARGIN, y, role, str(row_i))

        # Section divider
        y -= SECTION_GAP
        if sec_idx < len(sections) - 1 and y > MARGIN + 10:
            c.setLineWidth(0.2)
            c.line(MARGIN, y, pw - MARGIN, y)
            y -= 3

    # Hidden field that lets the importer identify which form template was used.
    c.acroForm.textfield(
        name="_form_id",
        value=form["id"],
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
        description="Generate a blank fillable PDF from a Gramps Form XML definition."
    )
    parser.add_argument("form_id", nargs="?", help="Form ID, e.g. US1790")
    parser.add_argument("output",  nargs="?", help="Output PDF path (default: {form_id}.pdf)")
    parser.add_argument("--list",  action="store_true", help="List all available form IDs")
    parser.add_argument("--rows",  type=int, default=None,
                        help="Rows for multi-type sections (default: 30, or prompted)")
    args = parser.parse_args()

    if args.list:
        for fid, title in list_forms():
            print(f"{fid:<14}  {title}")
        return

    # interactive controls whether we prompt the user for missing values
    interactive = args.form_id is None

    form_id = args.form_id
    if not form_id:
        forms = list_forms()
        if not forms:
            print("No form definitions found.", file=sys.stderr)
            sys.exit(1)
        print("Available forms:\n")
        for i, (fid, title) in enumerate(forms, 1):
            print(f"  {i:3}.  {fid:<14}  {title}")
        choice = input("\nEnter a number or form ID: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(forms):
            form_id = forms[int(choice) - 1][0]
        else:
            form_id = choice

    form = load_form(form_id)
    if form is None:
        print(f"Form '{form_id}' not found.  Use --list to see available forms.",
              file=sys.stderr)
        sys.exit(1)

    rows = args.rows
    if rows is None:
        has_multi = any(s["type"] == "multi" for s in form["sections"])
        if has_multi and interactive:
            try:
                raw = input("Number of data rows [30]: ").strip()
                rows = int(raw) if raw else 30
            except (ValueError, EOFError):
                rows = 30
        else:
            rows = 30  # default for both multi (non-interactive) and person/family

    output = args.output or f"{form_id}.pdf"
    generate_form_pdf(form, rows, output)
    print(f"Generated: {output}")


if __name__ == "__main__":
    main()
