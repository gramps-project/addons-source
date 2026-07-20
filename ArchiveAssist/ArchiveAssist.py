# Copyright (C) 2026  Ludwig Tiston <help.ludwig@proton.me>
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
# along with this program; if not, see <https://www.gnu.org/licenses/>.

# Contains AI-generated code. Mostly used for regex and GUI.

from gi.repository import Gtk
from gramps.gen.plug import Gramplet
from gramps.gen.lib import Source, Citation, Attribute, Span, Date, Repository, RepoRef
from gramps.gen.db import DbTxn
import logging
import re

LOG = logging.getLogger(".ArchiveAssist")  # Add as class attr or global

# Example string Riksarkivet:
# Åby kyrkoarkiv, Husförhörslängder, SE/VALA/00460/A I/8 (1833-1840), bildid: C0029371_00018, sida 8

# Example string ArkivDigital:
# Högsrum (H) AI:6 (1861-1871) Bild 186 / sid 179 (AID: v22513.b186.s179, NAD: SE/VALA/00161)

# ------------------------
# Parser
# ------------------------
def parse_ref(text: str) -> dict:
    text = text.strip()

    # ---------- ArkivDigital ----------
    if "AID:" in text:
        pattern = re.compile(
            r'^(?P<abr>.+?\s[A-Z]+:\d+\s*\(.*?\))'
            r'.*?Bild\s+(?P<bild>\d+)'
            r'(?:\s*/\s*sid\s+(?P<page>\d+))?'
            r'.*?AID:\s*(?P<full_aid>v\d+\.b\d+(?:\.s\d+)?)'
            r'.*?NAD:\s*(?P<nad>SE/\w+/\d+)',
            re.IGNORECASE
        )

        match = pattern.search(text)
        if not match:
            return {}

        abr = match.group("abr").strip()
        bild = match.group("bild")  # photo
        page = match.group("page") or f"Bild {bild}"
        full_aid = match.group("full_aid")
        aid = full_aid.split(".")[0]  # ArkivDigital Identifier
        nad_base = match.group("nad") # Nationell ArkivDatabas

        # Extract series + volume from abr (AI:6, BII:2, etc.)
        book_ref = re.search(r'([A-Z]+):(\d+)', abr)
        if book_ref:
            series = book_ref.group(1)
            volume = book_ref.group(2)
            nad = f"{nad_base}/{series[0]} {series[1:]}/{volume}"
        else:
            nad = nad_base

        year_match = re.search(r'\((\d{4}\s*[-–]\s*\d{4})\)', abr)
        years = year_match.group(1) if year_match else ""

        return {
            "provider": "ArkivDigital",
            "abr": abr,
            "NAD": nad,
            "AID": aid,
            "full_AID": full_aid,
            "page": page,
            "years": years,
        }

    # ---------- Riksarkivet ----------
    pattern = re.compile(
        r'^(?P<archive>[^,]+),\s*'
        r'(?P<series>[^,]+),\s*'
        r'(?P<nad>[^\(]+)*'
        r'\((?P<years>\d{4}(?:-\d{4})?)\)\s*'
        r'(, bildid[^_]*_(?P<bildid>\d+))?'
        r'(?:,\s*sida\s+(?P<page>\d+))?',
        re.IGNORECASE
    )

    match = pattern.search(text)
    if not match:
        return {}

    archive = match.group("archive").strip()
    to_remove = ["kyrkoarkiv", "stadsarkiv"]
    for word in to_remove:
        archive = archive.replace(word, "")
    archive = archive.strip()
    series = match.group("series").strip()
    nad = match.group("nad").strip()
    years = match.group("years")
    bild = match.group("bildid")
    if bild:
        bild = bild.lstrip("0")
    page = match.group("page")
    if not page and bild:
        page = f"Bild {bild}"

    series_code = ':'.join(nad.split('/')[-2:]).replace(" ", "")
    abr = f"{archive} {series_code} ({years})"

    return {
        "provider": "Riksarkivet",
        "abr": abr,
        "NAD": nad,
        "AID": None,
        "full_AID": None,
        "page": page,
        "years": years,
    }

# ------------------------
# Gramplet class
# ------------------------
class ArchiveAssist(Gramplet):

    # I am bad at GUI. Double check...
    def init(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self.gui.WIDGET = self.build_gui()
        container = self.gui.get_container_widget()

        if self.gui.textview.get_parent() is not None:
            container.remove(self.gui.textview)

        container.add(self.gui.WIDGET)
        container.show_all()

    def build_gui(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_border_width(10)

        # Entry for ArkivDigital string
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        self.textview.set_pixels_above_lines(2)
        self.textview.set_pixels_below_lines(2)
        self.textview.get_buffer().set_text(
            "Enter ArkivDigital or Riksarkivet reference string here (multi-line OK)")
        scrolled.add(self.textview)
        scrolled.set_min_content_height(80)  # ~4 lines at default font
        vbox.pack_start(scrolled, True, True, 0)  # Expands to fill vbox height

        # Button
        self.button = Gtk.Button(label="Create Source & Citation")
        self.button.connect("clicked", self.on_create_clicked)
        vbox.pack_start(self.button, False, False, 0)

        # Status label
        self.status_label = Gtk.Label(label="")
        vbox.pack_start(self.status_label, False, False, 0)

        return vbox

    def get_or_create_repository(self, name, trans):
        for handle in self.dbstate.db.get_repository_handles():
            repo = self.dbstate.db.get_repository_from_handle(handle)
            if repo.get_name() == name:
                return handle

        repo = Repository()
        repo.set_name(name)
        handle = self.dbstate.db.add_repository(repo, trans)
        return handle

    def on_create_clicked(self, widget):
        buffer = self.textview.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        text = buffer.get_text(start, end, False).strip()
        if not text:
            self.status_label.set_text("Please enter a reference string.")
            return

        parsed = parse_ref(text)
        if not parsed:
            self.status_label.set_text("Could not parse the reference string.")
            return

        # Find existing Source (by title)
        src = None
        src_handle = None

        for handle in self.dbstate.db.get_source_handles():
            candidate = self.dbstate.db.get_source_from_handle(handle)
            for attr in candidate.get_attribute_list():
                if attr.get_type() == "NAD" and attr.get_value() == parsed["NAD"]:
                    src = candidate
                    src_handle = handle
                    break

            if src:
                break

        try:
            with DbTxn("Create Source and Citation", self.dbstate.db) as trans:

                # Source
                if src:
                    self.status_label.set_text(
                    f"Source with NAD '{parsed['NAD']}' already exists: {src.get_gramps_id()}"
                    )
                else:
                    src = Source()
                    src.set_title(parsed["abr"])
                    src.set_publication_info(parsed["years"])

                    # FIXED NAD attribute
                    nad_attr = Attribute()
                    nad_attr.set_type("NAD")
                    nad_attr.set_value(parsed["NAD"])
                    src.add_attribute(nad_attr)

                    # FIXED AID attribute (if present)
                    if parsed["AID"]:
                        aid_attr = Attribute()
                        aid_attr.set_type("AID")
                        aid_attr.set_value(parsed["AID"])
                        src.add_attribute(aid_attr)

                    # First add the Source WITHOUT repo refs
                    src_handle = self.dbstate.db.add_source(src, trans)

                    # Now add RepoRef AFTER the source exists
                    repo_ref = RepoRef()
                    repo_handle = self.get_or_create_repository(parsed["provider"], trans)
                    repo_ref.set_reference_handle(repo_handle)

                    src.add_repo_reference(repo_ref)

                    # Persist the updated Source with its RepoRef
                    self.dbstate.db.commit_source(src, trans)

                    # Citation
                    if parsed["page"]:
                        cit = Citation()
                        cit.set_confidence_level(2)
                        cit.set_page(parsed["page"])

                        years = parsed["years"]
                        cit_date = Date()
                        if years and "-" in years:
                            start_year, end_year = [y.strip() for y in years.split("-")]
                            cit_date.set(
                                modifier=Date.MOD_RANGE,
                                value=(0, 0, int(start_year), False, 0, 0, int(end_year), False))
                            cit.set_date_object(cit_date)

                        elif years:
                            cit_date.set_year(int(years.strip()))
                            cit.set_date_object(cit_date)

                        cit.set_reference_handle(src_handle)

                        if parsed["full_AID"]:
                            AID = Attribute()
                            AID.set_type("AID")
                            AID.set_value(parsed["full_AID"])
                            cit.add_attribute(AID)

                        cit_handle = self.dbstate.db.add_citation(cit, trans)

                        self.status_label.set_text(
                            f"Created Source ({src.get_gramps_id()}) and Citation ({cit.get_gramps_id()})."
                        )
                    else:
                        self.status_label.set_text(
                            f"Created Source ({src.get_gramps_id()}). No Citation created due to missing page info."
                        )

        except Exception as e:
            LOG.error("ArchiveAssist failed: %s", str(e), exc_info=True)
            self.status_label.set_text(
                "Failed to create Source/Citation. Check logs.")