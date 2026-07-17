# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010  Doug Blank <doug.blank@gmail.com>
# Copyright (C) 2011  Nick Hall
# Copyright (C) 2011  Tim G L Lyons
# Copyright (C) 2024  Paul Womack (BugBear)
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

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------

from gi.repository import Gtk

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.plug import Gramplet

from gramps.gen.filters.rules import Rule
from gramps.gen.filters.rules.person import ProbablyAlive
from gramps.gen.lib.person import Person
from gramps.gen.lib import Date
from gramps.gen.datehandler import displayer
from gramps.gen.filters import GenericFilter
from gramps.gui import widgets
from gramps.gui.filters.sidebar import SidebarFilter

_ = glocale.translation.gettext


class _RegExpNameList(Rule):
    """Rule that checks for full or partial name matches"""

    labels = [_("Text:")]
    name = _("People with a name matching <text>")
    description = _(
        "Matches people's names containing a substring or "
        "matching a regular expression"
    )
    category = _("General filters")
    allow_regex = True

    def field_list(self, name):
        raise NotImplementedError

    def apply(self, db, person):
        for name in [person.primary_name] + person.alternate_names:
            for field in self.field_list(name):
                if self.match_substring(0, field):
                    return True
        else:
            return False


class RegExpPersonal(_RegExpNameList):
    def field_list(self, name):
        return [name.first_name, name.title, name.call, name.nick]


class RegExpFamily(_RegExpNameList):
    def field_list(self, name):
        return [name.get_surname(), name.suffix, name.famnick]


class _HasNamedRelation(Rule):
    labels = [_("Filter name:")]
    name = _("Children of name match")
    category = _("Family filters")
    description = _("Matches children of anybody with a given name")

    def __init__(self, arg, name_matcher, use_regex=False):
        super().__init__(arg, use_regex)
        self.name_matcher = name_matcher(arg, use_regex)

    def prepare(self, db, user):
        self.name_matcher.requestprepare(db, user)

    def reset(self):
        self.name_matcher.requestreset()

    def get_rel_list(self, db, person):
        raise NotImplementedError

    def get_spouse_list(self, db, person):
        handles = []
        for fam_id in person.family_list:
            fam = db.get_family_from_handle(fam_id)
            if fam:
                for spouse_id in [fam.father_handle, fam.mother_handle]:
                    if not spouse_id:
                        continue
                    if spouse_id == person.handle:
                        continue
                    handles.append(spouse_id)
        return handles

    def apply(self, db, person):
        for rel_id in self.get_rel_list(db, person):
            if rel_id:
                rel = db.get_person_from_handle(rel_id)
                if self.name_matcher.apply(db, rel):
                    return True
        return False


class _HasNamedParent(_HasNamedRelation):
    def get_parent_families(self, db, person):
        families = []
        for fam_id in person.parent_family_list:
            fam = db.get_family_from_handle(fam_id)
            if fam:
                families.append(fam)
        return families


class HasNamedFather(_HasNamedParent):
    def get_rel_list(self, db, person):
        return map(
            lambda fam: fam.get_father_handle(), self.get_parent_families(db, person)
        )


class HasNamedMother(_HasNamedParent):
    def get_rel_list(self, db, person):
        return map(
            lambda fam: fam.get_mother_handle(), self.get_parent_families(db, person)
        )


class IsSiblingofNamedSibling(_HasNamedRelation):
    def get_rel_list(self, db, person):
        handles = []
        fam_id = person.get_main_parents_family_handle()  # or all families, per above?
        fam = db.get_family_from_handle(fam_id) if fam_id else None
        if fam:
            for child_ref in fam.get_child_ref_list():
                if child_ref and child_ref.ref != person.handle:
                    handles.append(child_ref.ref)
        return handles


class HasNamedChild(_HasNamedRelation):
    def get_rel_list(self, db, person):
        handles = []
        for fam_id in person.family_list:
            fam = db.get_family_from_handle(fam_id)
            if fam:
                for child_ref in fam.get_child_ref_list():
                    if child_ref:
                        handles.append(child_ref.ref)
        return handles


class HasNamedSpouse(_HasNamedRelation):
    def get_rel_list(self, db, person):
        return self.get_spouse_list(db, person)


class HasName(_HasNamedRelation):
    def get_rel_list(self, db, person):
        if person.gender == Person.FEMALE and isinstance(
            self.name_matcher, RegExpFamily
        ):
            # for female surnames, we want to trawl the spouses surnames
            handles = self.get_spouse_list(db, person)
            handles.append(person.handle)
            return handles
        else:
            return [person.handle]


def extract_text(entry_widget):
    """
    Extract the text from the entry widget, strips off any extra spaces.
    """
    return str(entry_widget.get_text().strip())


# leverage to split the name into fore and aft
class SearchableNamePair:
    def __init__(self, label, rule_class):
        self.widget_personal = widgets.BasicEntry()
        self.widget_personal.set_placeholder_text(_("given"))
        self.widget_family = widgets.BasicEntry()
        self.widget_family.set_placeholder_text(_("surname"))
        self.label = label
        self.rule_class = rule_class

    def place(self, sidebar):
        # container.add_text_entry(self.label, self.widget_personal)
        # self.add_text_entry(container, self.label, self.widget_personal)
        # unrolled

        sidebar.grid.attach(widgets.BasicLabel(self.label), 1, sidebar.position, 1, 1)

        self.widget_personal.set_hexpand(True)
        sidebar.grid.attach(self.widget_personal, 2, sidebar.position, 1, 1)
        self.widget_personal.connect("key-press-event", sidebar.key_press)

        self.widget_family.set_hexpand(True)
        sidebar.grid.attach(self.widget_family, 3, sidebar.position, 1, 1)
        self.widget_family.connect("key-press-event", sidebar.key_press)
        sidebar.position += 1

    def clear(self):
        self.widget_personal.set_text("")
        self.widget_family.set_text("")

    def _add_to_filter(self, generic_filter, regex, widget, search_class):
        v = extract_text(widget)
        if v:
            rule = self.rule_class([v], search_class, use_regex=regex)
            generic_filter.add_rule(rule)

    def add_to_filter(self, generic_filter, regex):
        self._add_to_filter(generic_filter, regex, self.widget_personal, RegExpPersonal)
        self._add_to_filter(generic_filter, regex, self.widget_family, RegExpFamily)


# -------------------------------------------------------------------------
#
# PersonSidebarFilter class
#
# -------------------------------------------------------------------------
class PersonSidebarFilter(SidebarFilter):

    def __init__(self, dbstate, uistate, clicked):
        self.clicked_func = clicked
        self.sensitive_regex = False

        self.names = [
            SearchableNamePair(_("Person"), HasName),
            SearchableNamePair(_("Father"), HasNamedFather),
            SearchableNamePair(_("Mother"), HasNamedMother),
            SearchableNamePair(_("Spouse"), HasNamedSpouse),
            SearchableNamePair(_("Sibling 1"), IsSiblingofNamedSibling),
            SearchableNamePair(_("Sibling 2"), IsSiblingofNamedSibling),
            SearchableNamePair(_("Child 1"), HasNamedChild),
            SearchableNamePair(_("Child 2"), HasNamedChild),
        ]
        self.filter_alive = widgets.DateEntry(uistate, [])

        self.filter_regex = Gtk.CheckButton(label=_("Use regular expressions"))

        SidebarFilter.__init__(self, dbstate, uistate, "Person")

    def create_widget(self):
        exdate1 = Date()
        exdate2 = Date()
        exdate1.set(
            Date.QUAL_NONE,
            Date.MOD_RANGE,
            Date.CAL_GREGORIAN,
            (0, 0, 1800, False, 0, 0, 1900, False),
        )
        exdate2.set(
            Date.QUAL_NONE, Date.MOD_BEFORE, Date.CAL_GREGORIAN, (0, 0, 1850, False)
        )

        msg1 = displayer.display(exdate1)
        msg2 = displayer.display(exdate2)

        for w in self.names:
            w.place(self)

        self.add_text_entry(
            _("Probably Alive"),
            self.filter_alive,
            _("example: '%(msg1)s' or '%(msg2)s'") % {"msg1": msg1, "msg2": msg2},
        )
        self.add_regex_entry(self.filter_regex)

    def clear(self, obj):
        for w in self.names:
            w.clear()
        self.filter_alive.set_text("")

    def get_filter(self):
        """
        Extracts the text strings from the sidebar, and uses them to build up
        a new filter.
        """

        regex = self.filter_regex.get_active()

        # build a GenericFilter
        generic_filter = GenericFilter()
        for w in self.names:
            w.add_to_filter(generic_filter, regex)

        alive = extract_text(self.filter_alive)
        if alive:
            rule = ProbablyAlive([alive])
            generic_filter.add_rule(rule)

        return generic_filter


# -------------------------------------------------------------------------
#
# Filter class
#
# -------------------------------------------------------------------------
class Filter(Gramplet):
    """
    The base class for all filter gramplets.
    """

    FILTER_CLASS: type[SidebarFilter] | None = None

    def init(self):
        self.filter = self.FILTER_CLASS(
            self.dbstate, self.uistate, self.__filter_clicked
        )
        self.widget = self.filter.get_widget()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.widget)
        self.widget.show_all()

    def __filter_clicked(self):
        """
        Called when the filter apply button is clicked.
        """
        self.gui.view.generic_filter = self.filter.get_filter()
        self.gui.view.build_tree()


# -------------------------------------------------------------------------
#
# PersonFilter class
#
# -------------------------------------------------------------------------
class PersonRelationshipFilter(Filter):
    """
    A gramplet providing a Person Filter.
    """

    FILTER_CLASS = PersonSidebarFilter
