# encoding:utf-8
from gi.repository import Gtk
from gramps.gen.plug import Gramplet
from gramps.gen.lib import Source, Citation, Attribute, Span, Date, Repository, RepoRef
from gramps.gen.db import DbTxn

import re
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
        bild = match.group("bild")
        page = match.group("page") or f"Bild {bild}"
        full_aid = match.group("full_aid")
        aid = full_aid.split(".")[0]
        nad_base = match.group("nad")

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
        r'^(?P<archive>.+?)\s+(?:kyrkoarkiv|stadsarkiv),'
        r'(?P<series>[^,]+),\s*'
        r'(?P<nad>SE/\w+/\d+/[^,]+)\s*'
        r'\((?P<years>\d{4}(?:-\d{4})?)\),\s*'
        r'bildid[^_]*_(?P<bildid>\d+)'
        r'(?:,\s*sida\s+(?P<page>\d+))?',
        re.IGNORECASE
    )

    match = pattern.search(text)
    if not match:
        return {}

    archive = match.group("archive").strip()
    series = match.group("series").strip()
    nad = match.group("nad").strip()
    years = match.group("years")
    bild = match.group("bildid").lstrip("0")
    page = match.group("page") or f"Bild {bild}"

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
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Enter ArkivDigital reference string")
        vbox.pack_start(self.entry, False, False, 0)

        # Button
        self.button = Gtk.Button(label="Create Source & Citation")
        self.button.connect("clicked", self.on_create_clicked)
        vbox.pack_start(self.button, False, False, 0)

        # Status label
        self.status_label = Gtk.Label(label="")
        vbox.pack_start(self.status_label, False, False, 0)

        return vbox
    
    def get_or_create_repository(self, name):
        for handle in self.dbstate.db.get_repository_handles():
            repo = self.dbstate.db.get_repository_from_handle(handle)
            if repo.get_name() == name:
                return handle

        repo = Repository()
        repo.set_name(name)
        self.dbstate.db.add_repository(repo)
        return repo.get_handle()

    def on_create_clicked(self):
        text = self.entry.get_text().strip()
        if not text:
            self.status_label.set_text("Please enter a reference string.")
            return

        parsed = parse_ref(text)
        if not parsed:
            self.status_label.set_text("Could not parse the reference string.")
            return

        try:
            with DbTxn("Create Source and Citation", self.dbstate.db) as trans:
                # Source
                src = Source()
                src.set_title(parsed["abr"])
                src.set_publication_info(parsed["years"])
                
                if parsed["AID"]:
                    AID = Attribute()
                    AID.set_type("AID")
                    AID.set_value(parsed["AID"])
                    src.add_attribute(AID)
                
                NAD = Attribute()
                NAD.set_type("NAD")
                NAD.set_value(parsed["NAD"])
                src.add_attribute(NAD)
                
                repo_ref = RepoRef()
                repo_handle = self.get_or_create_repository(parsed["provider"])
                repo_ref.set_reference_handle(repo_handle)
                src.add_repo_reference(repo_ref)
                
                src_handle = self.dbstate.db.add_source(src, trans)

                # Citation
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
                
                if parsed["full_AID"]:
                    AID = Attribute()
                    AID.set_type("AID")
                    AID.set_value(parsed["full_AID"])
                    cit.add_attribute(AID)
                    cit.set_reference_handle(src_handle)
                
                cit_handle = self.dbstate.db.add_citation(cit, trans)

            
            self.status_label.set_text(
                f"Created Source ({src.get_gramps_id()}) and Citation ({cit.get_gramps_id()})."
            )

        except Exception as e:
            self.status_label.set_text(f"Error: {str(e)}")
