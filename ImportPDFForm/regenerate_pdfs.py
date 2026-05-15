#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regenerate all fillable PDFs into ImportPDFForm/pdfs/.

Usage::

    python3 ImportPDFForm/regenerate_pdfs.py           # all forms + pedigrees
    python3 ImportPDFForm/regenerate_pdfs.py --rows 20 # override row count
    python3 ImportPDFForm/regenerate_pdfs.py --forms-only
    python3 ImportPDFForm/regenerate_pdfs.py --pedigrees-only
"""

import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from generate_pdf import list_forms, load_form, generate_form_pdf
from generate_pedigree_pdf import generate_pedigree_pdf

OUTPUT_DIR = os.path.join(SCRIPT_DIR, "pdfs")
DEFAULT_ROWS = 30
PEDIGREE_GENERATIONS = range(1, 6)


def regenerate_forms(rows):
    forms = list_forms()
    ok = failed = 0
    for form_id, title in forms:
        form = load_form(form_id)
        if form is None:
            print(f"  SKIP  {form_id}  (load failed)")
            continue
        output = os.path.join(OUTPUT_DIR, f"{form_id}.pdf")
        try:
            generate_form_pdf(form, rows, output)
            print(f"  OK    {form_id}  ({title})")
            ok += 1
        except Exception as exc:
            print(f"  FAIL  {form_id}  {exc}")
            failed += 1
    return ok, failed


def regenerate_pedigrees():
    ok = failed = 0
    for gen in PEDIGREE_GENERATIONS:
        output = os.path.join(OUTPUT_DIR, f"Pedigree{gen}.pdf")
        try:
            generate_pedigree_pdf(gen, output)
            print(f"  OK    Pedigree{gen}  ({gen} generation{'s' if gen != 1 else ''})")
            ok += 1
        except Exception as exc:
            print(f"  FAIL  Pedigree{gen}  {exc}")
            failed += 1
    return ok, failed


def main():
    parser = argparse.ArgumentParser(description="Regenerate all PDFs in ImportPDFForm/pdfs/")
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS,
                        help=f"Data rows for multi-type sections (default: {DEFAULT_ROWS})")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--forms-only", action="store_true",
                       help="Only regenerate census/event form PDFs")
    group.add_argument("--pedigrees-only", action="store_true",
                       help="Only regenerate pedigree PDFs")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    total_ok = total_failed = 0

    if not args.pedigrees_only:
        print("Generating form PDFs...")
        ok, failed = regenerate_forms(args.rows)
        total_ok += ok
        total_failed += failed

    if not args.forms_only:
        print("Generating pedigree PDFs...")
        ok, failed = regenerate_pedigrees()
        total_ok += ok
        total_failed += failed

    print(f"\n{total_ok} generated, {total_failed} failed  →  {OUTPUT_DIR}")
    if total_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
