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
LaTeX Genealogy Tree descendant report
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
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext

#------------------------------------------------------------------------
#
# GrandparentTree
#
#------------------------------------------------------------------------
class GrandparentTree(Report):
    """ Grandparent descendant report """

    def __init__(self, database, options, user):
        """
        Create LaTeX Genealogy Tree grandparent descendant report.
        """
        Report.__init__(self, database, options, user)

        menu = options.menu
        get_option_by_name = menu.get_option_by_name
        get_value = lambda name: get_option_by_name(name).get_value()

        self._db = self.database

        self._pid = get_value('pid')
        self.max_generations = menu.get_option_by_name('maxgen').get_value()
        self.shift = menu.get_option_by_name('shift').get_value()
        self.include_images = menu.get_option_by_name('images').get_value()
        self.set_locale(menu.get_option_by_name('trans').get_value())
        self.g1_handle = None
        self.g2_handle = None

    def write_report(self):
        """
        Inherited method; called by report() in _ReportDialog.py
        """
        person = self._db.get_person_from_gramps_id(self._pid)
        handle = person.get_main_parents_family_handle()
        if handle:
            family = self._db.get_family_from_handle(handle)

            self.f_handle = family.get_father_handle()
            if self.f_handle:
                father = self._db.get_person_from_handle(self.f_handle)
                handle1 = father.get_main_parents_family_handle()
                if handle1:
                    family1 = self._db.get_family_from_handle(handle1)
                    self.g1_handle = (family1.get_father_handle() or
                                      family1.get_mother_handle())

            self.m_handle = family.get_mother_handle()
            if self.m_handle:
                mother = self._db.get_person_from_handle(self.m_handle)
                handle2 = mother.get_main_parents_family_handle()
                if handle2:
                    family2 = self._db.get_family_from_handle(handle2)
                    self.g2_handle = (family2.get_father_handle() or
                                      family2.get_mother_handle())

        if self.g1_handle is None or self.g2_handle is None:
            raise ReportError(_('Person %s does not have both a paternal '
                                'and a maternal grandparent') % self._pid)

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

        options = ['pref code={\\underline{#1}}',
                   'list separators hang',
                   'place text={\\newline}{}',
                   box,
                   'id suffix=@a']

        self.doc.start_tree(options)
        self.write_subgraph(0, 'child', [handle1], self.g1_handle)
        self.doc.end_tree()

        link = 'set position=%s@b at %s@a' % (father.gramps_id,
                                              father.gramps_id)

        options = ['pref code={\\underline{#1}}',
                   'list separators hang',
                   'place text={\\newline}{}',
                   box,
                   'id suffix=@b',
                   link]
        self.doc.start_tree(options)
        self.write_subgraph(0, 'child', [handle2], self.g2_handle)
        self.doc.end_tree()

    def write_subgraph(self, level, subgraph_type, family_handles, ghandle):
        if level >= self.max_generations:
            return
        family = self._db.get_family_from_handle(family_handles[0])
        if ghandle == self.g1_handle:
            options = ['pivot shift=%smm' % self.shift]
        elif ghandle == self.g2_handle:
            options = ['pivot shift=%smm' % -self.shift]
        else:
            options = None
        self.doc.start_subgraph(level, subgraph_type, family, options)
        for handle in family_handles[1:]:
            self.write_subgraph(level+1, 'union', [handle], ghandle)
        for handle in (family.get_father_handle(), family.get_mother_handle()):
            if handle:
                parent = self._db.get_person_from_handle(handle)
                if handle == ghandle:
                    if subgraph_type == 'child':
                        self.doc.write_node(self._db, level+1, 'g', parent,
                                            False)
                else:
                    self.doc.write_node(self._db, level+1, 'p', parent, True)

        children = [ref.ref for ref in family.get_child_ref_list()]
        if self.f_handle in children:
            children.remove(self.f_handle)
            children.append(self.f_handle)
        if self.m_handle in children:
            children.remove(self.m_handle)
            children.insert(0, self.m_handle)

        for child_handle in children:
            child = self._db.get_person_from_handle(child_handle)
            family_handles = child.get_family_handle_list()
            if len(family_handles) > 0:
                family_handles = child.get_family_handle_list()
                self.write_subgraph(level+1, 'child', family_handles,
                                    child_handle)
            else:
                self.doc.write_node(self._db, level+1, 'c', child, True)
        self.doc.end_subgraph(level)


#------------------------------------------------------------------------
#
# GrandparentTreeOptions
#
#------------------------------------------------------------------------
class GrandparentTreeOptions(MenuReportOptions):
    """
    Defines all of the controls necessary
    to configure the Descendant Tree report.
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

        shift = NumberOption(_("Grandparent family spacing"), 0, 0, 50)
        shift.set_help(_("Extra spacing of grandparent families (mm)"))
        menu.add_option(category_name, "shift", shift)

        images = BooleanOption(_("Include images"), False)
        images.set_help(_("Include images of people in the nodes."))
        menu.add_option(category_name, "images", images)

        locale_opt = stdoptions.add_localization_option(menu, category_name)
