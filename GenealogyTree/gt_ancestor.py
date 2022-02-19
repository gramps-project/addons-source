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
LaTeX Genealogy Tree ancestor report
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
from gramps.gen.plug.menu import PersonOption, NumberOption, BooleanOption

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
# AncestorTree
#
#------------------------------------------------------------------------
class AncestorTree(Report):
    """ Ancestor Tree report """

    def __init__(self, database, options, user):
        """
        Create LaTeX Genealogy Tree ancestor report.
        """
        Report.__init__(self, database, options, user)

        menu = options.menu
        get_option_by_name = menu.get_option_by_name
        get_value = lambda name: get_option_by_name(name).get_value()

        self._db = self.database

        self._pid = get_value('pid')
        self.max_generations = menu.get_option_by_name('maxgen').get_value()
        self.include_images = menu.get_option_by_name('images').get_value()
        self.set_locale(menu.get_option_by_name('trans').get_value())

    def write_report(self):
        """
        Inherited method; called by report() in _ReportDialog.py
        """
        if self._pid:
            person = self._db.get_person_from_gramps_id(self._pid)
            if person is None:
                raise ReportError(_("Person %s is not in the Database") %
                                  self._pid)
            family_handle = person.get_main_parents_family_handle()
            if family_handle:
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

                self.doc.start_tree(options)
                self.write_subgraph(0, 'parent', family_handle, person.handle)
                self.doc.end_tree()

    def write_subgraph(self, level, subgraph_type, family_handle, ghandle):
        if level > self.max_generations:
            return
        family = self._db.get_family_from_handle(family_handle)
        self.doc.start_subgraph(level, subgraph_type, family)
        for handle in (family.get_father_handle(), family.get_mother_handle()):
            if handle:
                parent = self._db.get_person_from_handle(handle)
                family_handle = parent.get_main_parents_family_handle()
                if family_handle:
                    self.write_subgraph(level+1, 'parent', family_handle,
                                        handle)
                else:
                    self.doc.write_node(self._db, level+1, 'p', parent, True)
        for childref in family.get_child_ref_list():
            child = self._db.get_person_from_handle(childref.ref)
            if childref.ref == ghandle:
                self.doc.write_node(self._db, level+1, 'g', child, True)
            else:
                self.doc.write_node(self._db, level+1, 'c', child, False)
        self.doc.end_subgraph(level)

#------------------------------------------------------------------------
#
# AncestorTreeOptions
#
#------------------------------------------------------------------------
class AncestorTreeOptions(MenuReportOptions):
    """
    Defines all of the controls necessary
    to configure the Ancestor Tree report.
    """
    def __init__(self, name, dbase):
        self.__pid = None
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):

        category_name = _("Report Options")

        self.__pid = PersonOption(_("Center Person"))
        self.__pid.set_help(_("The center person for the report"))
        menu.add_option(category_name, "pid", self.__pid)

        maxgen = NumberOption(_("Generations"), 10, 1, 100)
        maxgen.set_help(_("The number of generations to include in the tree"))
        menu.add_option(category_name, "maxgen", maxgen)

        images = BooleanOption(_("Include images"), False)
        images.set_help(_("Include images of people in the nodes."))
        menu.add_option(category_name, "images", images)

        locale_opt = stdoptions.add_localization_option(menu, category_name)
