#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2017-2018 Nick Hall
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

"""
LaTeX Genealogy Tree sandclock report
"""

#------------------------------------------------------------------------
#
# python modules
#
#------------------------------------------------------------------------
from functools import partial

#------------------------------------------------------------------------
#
# Set up logging
#
#------------------------------------------------------------------------
import logging
LOG = logging.getLogger(".Tree")

#------------------------------------------------------------------------
#
# Gramps module
#
#------------------------------------------------------------------------
from gramps.gen.errors import ReportError
from gramps.gen.plug.report import Report
from gramps.gen.plug.report import MenuReportOptions
from gramps.gen.plug.report import stdoptions
from gramps.gen.plug.menu import PersonOption, FamilyOption, NumberOption, BooleanOption

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

#------------------------------------------------------------------------
#
# SandclockTree
#
#------------------------------------------------------------------------

_PERSON_RPT_NAME = 'gt_sandclock'
_FAMILY_RPT_NAME = 'gt_sandclock_family'

class SandclockTree(Report):
    """ Sandclock Tree report """

    def __init__(self, database, options, user):
        """
        Create LaTeX Genealogy Tree sandclock report.
        """
        Report.__init__(self, database, options, user)

        menu = options.menu
        get_option_by_name = menu.get_option_by_name
        get_value = lambda name: get_option_by_name(name).get_value()

        self._person_report = options.name.split(",")[0] == _PERSON_RPT_NAME
        self._db = self.database

        self._pid = get_value('pid')
        self.max_up = menu.get_option_by_name('genup').get_value()
        self.max_down = menu.get_option_by_name('gendown').get_value()
        self.include_siblings = menu.get_option_by_name('siblings').get_value()
        self.include_images = menu.get_option_by_name('images').get_value()
        self.compact = menu.get_option_by_name('compact').get_value()
        self.set_locale(menu.get_option_by_name('trans').get_value())

    def write_report(self):
        """
        Inherited method; called by report() in _ReportDialog.py
        """
        if self._pid:
            if self._person_report:
                person = self._db.get_person_from_gramps_id(self._pid)
                if person is None:
                    raise ReportError(_("Person %s is not in the Database") %
                                      self._pid)
            else:
                family = self._db.get_family_from_gramps_id(self._pid)
                if family is None:
                    raise ReportError(_("Family %s is not in the Database") %
                                      self._pid)

            self.doc.start_tree(self._build_tree_options())
            if self._person_report:
                family_handle = person.get_main_parents_family_handle()
                if family_handle:
                    self.subgraph_up(0, 'sandclock', family_handle, person.handle)
            else:
                self.doc.start_subgraph(0, 'sandclock', family)
                self.subgraph_up_parents(0, family)
                for childref in family.get_child_ref_list():
                    child = self._db.get_person_from_handle(childref.ref)
                    family_handles = child.get_family_handle_list()
                    if len(family_handles) > 0:
                        self.subgraph_down(1, 'child', family_handles, child.handle)
                    else:
                        self.doc.write_node(self._db, 1, 'c', child, False)
                self.doc.end_subgraph(0)
            self.doc.end_tree()

    def _build_tree_options(self):
        """Assemble the option list for ``\\genealogytree[...]``.

        Kept separate from ``write_report`` so the option-construction
        logic can be unit-tested without driving a full report run.
        """
        options = ['pref code={\\underline{#1}}',
                   'list separators hang',
                   'place text={\\newline}{}']

        if self.include_images:
            images = ('if image defined={'
                      'add to width=25mm,right=25mm,\n'
                      'underlay={\\begin{tcbclipinterior}'
                      '\\path[fill overzoom image=\\gtrDBimage]\n'
                      '([xshift=-24mm]interior.south east) '
                      'rectangle (interior.north east);\n'
                      '\\end{tcbclipinterior}},\n'
                      '}{},')
            box = 'box={halign=left,\\gtrDBsex,%s\n}' % images
        else:
            box = 'box={halign=left,\\gtrDBsex}'

        options.append(box)

        if self.compact:
            # Mantis 10512 / SNoiraud's 2018-12-20 note: the default
            # `database` template lays out sandclock trees so widely
            # that large trees clip off the page.  `database pole
            # reduced` gives ~4x more space per page at the cost of
            # denser per-node formatting.  Appended last so it
            # overrides any node-spacing defaults set by treedoc.py's
            # built-in keys earlier in the parameter list.
            options.append('template=database pole reduced')

        return options

    def subgraph_up_parents(self, level, family):
        for handle in (family.get_father_handle(), family.get_mother_handle()):
            if handle:
                parent = self._db.get_person_from_handle(handle)
                family_handle = parent.get_main_parents_family_handle()
                if family_handle and level < self.max_up:
                    self.subgraph_up(level+1, 'parent', family_handle,
                                     handle)
                else:
                    self.doc.write_node(self._db, level+1, 'p', parent, True)

    def subgraph_up(self, level, subgraph_type, family_handle, ghandle):
        if level > self.max_up:
            return
        family = self._db.get_family_from_handle(family_handle)
        self.doc.start_subgraph(level, subgraph_type, family)
        self.subgraph_up_parents(level, family)
        for childref in family.get_child_ref_list():
            child = self._db.get_person_from_handle(childref.ref)
            if childref.ref == ghandle:
                if subgraph_type != 'sandclock':
                    self.doc.write_node(self._db, level+1, 'g', child, True)
            elif self.include_siblings:
                self.doc.write_node(self._db, level+1, 'c', child, False)

        if self._person_report and subgraph_type == 'sandclock':
            person = self._db.get_person_from_handle(ghandle)
            family_handles = person.get_family_handle_list()
            if len(family_handles) > 0:
                self.subgraph_down(0, 'child', family_handles, person.handle)

        self.doc.end_subgraph(level)

    def subgraph_down(self, level, subgraph_type, family_handles, ghandle):
        if level >= self.max_down:
            return
        family = self._db.get_family_from_handle(family_handles[0])
        self.doc.start_subgraph(level, subgraph_type, family)
        for handle in family_handles[1:]:
            self.subgraph_down(level+1, 'union', [handle], ghandle)
        for handle in (family.get_father_handle(), family.get_mother_handle()):
            if handle:
                parent = self._db.get_person_from_handle(handle)
                if handle == ghandle:
                    if subgraph_type == 'child':
                        self.doc.write_node(self._db, level+1, 'g', parent,
                                            False)
                else:
                    self.doc.write_node(self._db, level+1, 'p', parent, True)
        for childref in family.get_child_ref_list():
            child = self._db.get_person_from_handle(childref.ref)
            family_handles = child.get_family_handle_list()
            if len(family_handles) > 0:
                if level+1 >= self.max_down:
                    self.doc.write_node(self._db, level+1, 'c', child, True)
                else:
                    self.subgraph_down(level+1, 'child', family_handles,
                                       childref.ref)
            else:
                self.doc.write_node(self._db, level+1, 'c', child, True)
        self.doc.end_subgraph(level)

#------------------------------------------------------------------------
#
# SandclockTreeOptions
#
#------------------------------------------------------------------------
class SandclockTreeOptions(MenuReportOptions):
    """
    Defines all of the controls necessary
    to configure the Ancestor Tree report.
    """
    def __init__(self, name, dbase):
        self.__pid = None
        self.name = name
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):

        category_name = _("Report Options")

        if self.name.split(",")[0] == _PERSON_RPT_NAME:
            self.__pid = PersonOption(_("Center Person"))
            self.__pid.set_help(_("The center person for the report"))
            menu.add_option(category_name, "pid", self.__pid)
        else:
            self.__pid = FamilyOption(_("Center Family"))
            self.__pid.set_help(_("The center family for the report"))
            menu.add_option(category_name, "pid", self.__pid)

        genup = NumberOption(_("Generations up"), 10, 0, 100)
        genup.set_help(_("The number of generations to include in the tree"))
        menu.add_option(category_name, "genup", genup)

        gendown = NumberOption(_("Generations down"), 10, 0, 100)
        gendown.set_help(_("The number of generations to include in the tree"))
        menu.add_option(category_name, "gendown", gendown)

        siblings = BooleanOption(_("Include siblings"), True)
        siblings.set_help(_("Include siblings of ancestors."))
        menu.add_option(category_name, "siblings", siblings)

        images = BooleanOption(_("Include images"), False)
        images.set_help(_("Include images of people in the nodes."))
        menu.add_option(category_name, "images", images)

        compact = BooleanOption(_("Compact tree layout"), False)
        compact.set_help(_(
            "Use the genealogytree 'database pole reduced' template, "
            "which packs more generations per page. Useful for large "
            "sandclock trees that otherwise clip off the rendered page."
        ))
        menu.add_option(category_name, "compact", compact)

        locale_opt = stdoptions.add_localization_option(menu, category_name)
