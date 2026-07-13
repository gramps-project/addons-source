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
#

register(
    TOOL,
    id="generate_pdf_forms",
    name=_("Generate PDF Forms"),
    description=_(
        "Generate blank fillable PDF forms: census/event forms or "
        "Ahnentafel pedigree charts."
    ),
    version = '1.0.5',
    gramps_target_version="6.1",
    status=STABLE,
    fname="generatepdfform.py",
    authors=["Douglas S. Blank"],
    authors_email=["doug.blank@gmail.com"],
    category=TOOL_UTILS,
    toolclass="GeneratePDFForm",
    optionclass="GeneratePDFFormOptions",
    tool_modes=[TOOL_MODE_GUI],
    requires_mod=["reportlab"],
    depends_on=["Form Gramplet"],
    help_url="Addon:PDFForms",
)

register(
    IMPORT,
    id="import_pdf",
    name=_("Import Fillable PDF Forms"),
    description=_(
        "Import genealogy data from a PDF form. " 
        "Send the PDF template to others to fill out and return."
    ),
    version = '1.0.5',
    gramps_target_version="6.1",
    status=STABLE,
    fname="importpdf.py",
    import_function="importData",
    extension="pdf",
    requires_mod=["pypdf"],
    depends_on=["Form Gramplet"],
    help_url="Addon:PDFForms",
)
