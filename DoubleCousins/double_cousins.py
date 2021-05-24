#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C)    2020 Matthias Kemmer
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
"""A text report listing double cousins."""
# ----------------------------------------------------------------------------
#
# Python modules
#
# ----------------------------------------------------------------------------
import itertools

# ----------------------------------------------------------------------------
#
# Gramps modules
#
# ----------------------------------------------------------------------------
from gramps.gen.plug.report import Report, MenuReportOptions
from gramps.gen.plug.menu import BooleanOption
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.plug.docgen import ParagraphStyle, FontStyle, PARA_ALIGN_CENTER
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# ----------------------------------------------------------------------------
#
# Report Class
#
# ----------------------------------------------------------------------------
class DoubleCousins(Report):
    """Create a text report listing double (first) cousins."""

    def __init__(self, database, options, user):
        Report.__init__(self, database, options, user)

        self.options = options
        self.menu = options.menu
        self.db = database
        self.persons = dict()
        self.double_cousins = set()
        self.get_persons()
        self.search_double_cousins()

    def get_persons(self):
        """Get all persons with known parents and grandparents."""
        for person_h in self.db.iter_person_handles():
            parents = self.get_parents(person_h)
            if parents:
                father_h = parents[0]
                mother_h = parents[1]
                paternal = self.get_parents(father_h)
                maternal = self.get_parents(mother_h)
                if paternal and maternal:
                    grandparents = (*paternal, *maternal)
                    self.persons[person_h] = (parents, grandparents)

    def search_double_cousins(self):
        """Search all persons for double cousin relationship."""
        dct = self.persons
        items = list(iter(dct))
        combo = itertools.combinations(items, 2)
        for pers1, pers2 in combo:
            if True not in [pers in dct[pers2][0] for pers in dct[pers1][0]]:
                if all([pers in dct[pers2][1] for pers in dct[pers1][1]]):
                    self.double_cousins.add((pers1, pers2))

    def get_parents(self, person_h):
        """Return a tuple of parent handles of a person or None.

        Return tuple(father_h, mother_h) if person has a father and a mother
        and the relationship to them is birth. If not, return None.
        """
        person = self.db.get_person_from_handle(person_h)
        for family_h in person.get_parent_family_handle_list():
            family = self.db.get_family_from_handle(family_h)
            if family:
                father_h = family.get_father_handle()
                mother_h = family.get_mother_handle()
                if father_h and mother_h:
                    for child_ref in family.get_child_ref_list():
                        if child_ref.ref == person_h:
                            father_rel = child_ref.get_father_relation()
                            mother_rel = child_ref.get_mother_relation()
                            if father_rel == _("Birth") and \
                               mother_rel == _("Birth"):
                                return (father_h, mother_h)
        return None

    def write_report(self):
        """Write the text report."""
        self.doc.start_paragraph("Heading")
        self.doc.write_text(_("Double Cousins Report"))
        self.doc.end_paragraph()
        gid = self.menu.get_option_by_name("gid").get_value()

        # Double cousins info text
        if self.menu.get_option_by_name("info1").get_value():
            self.doc.start_paragraph("Default")
        # xgettext:no-python-format
            text = _("Double (first) cousins occur when two siblings of "
                     "family A marry two siblings of family B. "
                     "Their children are double cousins to each other and "
                     "share the same four grandparents instead of six "
                     "like normal first cousins. "
                     "Therefore they are genetically closer than normal "
                     "first cousins and share 25% of their DNA similar to "
                     "half-siblings instead of 12.5% like normal "
                     "first cousins.\n")
            self.doc.write_text(text)
            self.doc.end_paragraph()

        # Check if database has double cousins
        dc_num = len(self.double_cousins)
        if dc_num == 0:
            self.doc.start_paragraph("Default")
            self.doc.write_text(_("No double cousins were found in your"
                                  " database."))
            self.doc.end_paragraph()

        # list the double cousins
        counter = 1
        for dcousins in self.double_cousins:
            self.doc.start_paragraph("Default")
            person1 = self.db.get_person_from_handle(dcousins[0])
            person2 = self.db.get_person_from_handle(dcousins[1])
            id1 = " (%s)" % person1.get_gramps_id()
            id2 = " (%s)" % person2.get_gramps_id()
            name1 = name_displayer.display(person1)
            name2 = name_displayer.display(person2)
            self.doc.write_text("%d: %s%s & %s%s" %
                                (counter, name1, id1 if gid else '',
                                 name2, id2 if gid else ''))
            self.doc.end_paragraph()
            counter += 1


# ----------------------------------------------------------------------------
#
# Report Options Class
#
# ----------------------------------------------------------------------------
class ReportOptions(MenuReportOptions):
    """Report options for Media Report."""

    def __init__(self, name, dbase):
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):
        """Add the options to the report option menu."""
        self.info1 = BooleanOption(_("Show info text"), False)
        menu.add_option(_("Report Options"), "info1", self.info1)
        self.gid = BooleanOption(_("Show Gramps ID"), False)
        menu.add_option(_("Report Options"), "gid", self.gid)

    @staticmethod
    def make_default_style(default_style):
        """Define the default styling."""
        font = FontStyle()
        font.set(size=10)
        para = ParagraphStyle()
        para.set_font(font)
        default_style.add_paragraph_style("Default", para)

        font = FontStyle()
        font.set(size=16, bold=1)
        para.set_font(font)
        para.set_header_level(1)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_alignment(PARA_ALIGN_CENTER)
        default_style.add_paragraph_style("Heading", para)
