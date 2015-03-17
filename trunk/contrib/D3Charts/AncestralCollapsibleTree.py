#
# AncestralCollapsibleTree - a plugin for GRAMPS, the GTK+/GNOME based
#       genealogy program that creates an Ancestor Chart Map based on
#       the D3.js Collapsible Tree Layout scheme.
#
# Copyright (C) 2014  Matt Keenan <matt.keenan@gmail.com>
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

# version 0.1

# The idea behind this plugin is to create an ancestral tree chart that can
# be interacted with via clicking on an individual to either collapse or expand
# ancestors for that individual. The chart is SVG and uses D3.js layout engine.

"""Reports/Web Pages/Ancestral Collapsible Tree"""

#------------------------------------------------------------------------
#
# python modules
#
#------------------------------------------------------------------------
import copy
import io
import os
import shutil
import sys

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale, conv_to_unicode
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

#------------------------------------------------------------------------
#
# gramps modules
#
#------------------------------------------------------------------------
from gramps.gen.display.name import displayer as global_name_display
from gramps.gen.errors import ReportError
from gramps.gen.lib import ChildRefType
from gramps.gen.plug.menu import (ColorOption, NumberOption, PersonOption,
                                  EnumeratedListOption, DestinationOption,
                                  StringOption)
from gramps.gen.config import config
from gramps.gen.plug.report import Report
from gramps.gen.plug.report import MenuReportOptions

#------------------------------------------------------------------------
#
# AncestralCollapsibleTreeReport
#
#------------------------------------------------------------------------
class AncestralCollapsibleTreeReport(Report):
    """
    Ancestral Collapsible Tree Report class
    """
    def __init__(self, database, options, user):
        """
        Create the AncestralCollapsibleTree object that produces the
        Ancestral Collapsible Tree report.

        The arguments are:

        database        - the GRAMPS database instance
        options         - instance of the Options class for this report
        user            - a gen.user.User() instance

        This report needs the following parameters (class variables)
        that come in the options class.

        max_gen       - Maximum number of generations to include.
        name_format   - Preferred format to display names
        male_bg       - Background color for males
        female_bg     - Background color for females
        exp_male_bg   - Background color for expandable males
        exp_female_bg - Background color for expandable females
        dest_path     - Destination Path
        dest_file     - Destination HTML filename
        """
        Report.__init__(self, database, options, user)

        self.map = {}

        menu = options.menu
        self.max_gen = menu.get_option_by_name('maxgen').get_value()
        self.male_bg = menu.get_option_by_name('male_bg').get_value()
        self.female_bg = menu.get_option_by_name('female_bg').get_value()
        self.exp_male_bg = menu.get_option_by_name('exp_male_bg').get_value()
        self.exp_female_bg = \
            menu.get_option_by_name('exp_female_bg').get_value()
        self.dest_path = conv_to_unicode(
            menu.get_option_by_name('dest_path').get_value(), 'utf8')
        self.dest_file = conv_to_unicode(
            menu.get_option_by_name('dest_file').get_value(), 'utf8')
        self.destprefix, self.destext = \
            os.path.splitext(os.path.basename(self.dest_file))
        self.destjson = conv_to_unicode(
            os.path.join(self.dest_path, "json", "%s.json" % (self.destprefix)))
        self.destjs = conv_to_unicode(
            os.path.join(self.dest_path, "js", "%s.js" % (self.destprefix)))
        self.desthtml = conv_to_unicode(
            os.path.join(self.dest_path, os.path.basename(self.dest_file)))

        pid = menu.get_option_by_name('pid').get_value()
        self.center_person = database.get_person_from_gramps_id(pid)
        if (self.center_person == None) :
            raise ReportError(_("Person %s is not in the Database") % pid )

        # Copy the global NameDisplay so that we don't change application
        # defaults.
        self._name_display = copy.deepcopy(global_name_display)
        name_format = menu.get_option_by_name("name_format").get_value()
        if name_format != 0:
            self._name_display.set_default_format(name_format)

    def pad_str(self, num_spaces):
        """
        Utility method to retrieve string with specific number of spaces
        """
        pad_str = ""
        for i in range(0, num_spaces):
            pad_str = pad_str + " "
        return pad_str

    def get_gender_str(self, person):
        """
        Return gender string of male/female/unknown
        """
        if person.get_gender() == 0:
            return "female"
        elif person.get_gender() == 1:
            return "male"
        else:
            return "unknown"

    def json_filter(self, person_handle, generation=1):
        """
        Recursable JSON generation method. Processing each parent in a
        recursive nature
        """
        # check for end of the current recursion level. This happens
        # if the person handle is None, or if the max_gen is hit
        if not person_handle or generation > self.max_gen:
            return

        # retrieve the Person instance from the database from the
        # passed person_handle and find the parents from the list.
        # Since this report is for natural parents (birth parents),
        # we have to handle that parents may not
        person = self.database.get_person_from_handle(person_handle)

        gen_pad = (generation-1) * 2

        name = self._name_display.display(person)
        self.json_fp.write('%s{\n' % (self.pad_str(gen_pad)))
        self.json_fp.write('%s"name": "%s",\n' %
            (self.pad_str(gen_pad+1), name.replace('"', "'")))
        self.json_fp.write('%s"gender": "%s",\n' %
            (self.pad_str(gen_pad+1), self.get_gender_str(person)))

        # Get Birth/Death dates if they exist
        birth_year = 0
        birth_ref = person.get_birth_ref()
        if birth_ref and birth_ref.ref:
            birth_event = self.database.get_event_from_handle(birth_ref.ref)
            if birth_event:
                birth_year = birth_event.get_date_object().get_year()

        death_year = 0
        death_ref = person.get_death_ref()
        if death_ref and death_ref.ref:
            death_event = self.database.get_event_from_handle(death_ref.ref)
            if death_event:
                death_year = death_event.get_date_object().get_year()

        self.json_fp.write('%s"born": "%s",\n' %
            (self.pad_str(gen_pad+1),
            str(birth_year) if birth_year != 0 else ""))
        self.json_fp.write('%s"died": "%s",\n' %
            (self.pad_str(gen_pad+1),
            str(death_year) if death_year != 0 else ""))

        self.json_fp.write('%s"gramps_id": "%s"' %
            (self.pad_str(gen_pad+1), str(person.get_gramps_id())))

        father_handle = None
        mother_handle = None
        for family_handle in person.get_parent_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)

            # filter the child_ref_list to find the reference that matches
            # the passed person. There should be exactly one, but there is
            # nothing that prevents the same child in the list multiple times.

            ref = [ c for c in family.get_child_ref_list()
                    if c.get_reference_handle() == person_handle]
            if ref:
                # If the father_handle is not defined and the relationship is
                # BIRTH, then we have found the birth father. Same applies to
                # the birth mother. If for some reason, we have multiple
                # people defined as the birth parents, we will select based on
                # priority in the list

                if not father_handle and \
                   ref[0].get_father_relation() == ChildRefType.BIRTH:
                    father_handle = family.get_father_handle()
                if not mother_handle and \
                   ref[0].get_mother_relation() == ChildRefType.BIRTH:
                    mother_handle = family.get_mother_handle()

        # Recursively call the function. It is okay if the handle is None,
        # since routine handles a handle of None
        if (not father_handle and not mother_handle) or \
            generation == self.max_gen:
            self.json_fp.write('\n')
            self.json_fp.write('%s}' % (self.pad_str(gen_pad)))
        else:
            self.json_fp.write(',\n')
            self.json_fp.write('%s"children": [\n' %
                (self.pad_str(gen_pad+1)))
            
            self.json_filter(father_handle, generation+1)

            if father_handle and mother_handle:
                self.json_fp.write(',\n')
            elif mother_handle:
                self.json_fp.write('\n')

            self.json_filter(mother_handle, generation+1)
            self.json_fp.write('\n')

            self.json_fp.write('%s]\n' % (self.pad_str(gen_pad+1)))
            self.json_fp.write('%s}' % (self.pad_str(gen_pad)))

    def write_report(self):
        """
        The routine the actually creates the report. At this point, the document
        is opened and ready for writing.
        """
        name = self._name_display.display(self.center_person)
        title = "Ancestral Collapsible Tree for " + name
        try:
            with io.open(self.desthtml, 'w', encoding='utf8') as fp:
                # Generate HTML File
                outstr = '<!DOCTYPE html>\n' + \
                    '<html>\n' + \
                    '  <head>\n' + \
                    '    <title>' + title + '</title>\n' + \
                    '    <meta http-equiv="Content-Type" ' + \
                    'content="text/html;charset=utf-8"/>\n' + \
                    '    <script type="text/javascript" ' + \
                    'src="js/d3/d3.min.js"></script>\n' + \
                    '    <script type="text/javascript" ' + \
                    'src="js/jquery/jquery-2.0.3.min.js"></script>\n' + \
                    '    <link type="text/css" rel="stylesheet" ' + \
                    'href="css/collapsibletree.css"/>\n' + \
                    '  </head>\n' + \
                    '  <body>\n' + \
                    '    <div id="body">\n' + \
                    '      <div id="start">\n' + \
                    '       <h1>' + title + '</h1>\n' + \
                    '      </div>\n' + \
                    '      <div id="chart">\n' + \
                    '      </div>\n' + \
                    '      <div id="end">\n' + \
                    '       <h3>Click people to expand/collapse : \n' + \
                    '        <svg width="80" height="20">\n' + \
                    '         <g>\n' + \
                    '          <rect x="0" y="0" width="80" height="20" style="fill:%s;stroke-width:1;stroke:#BBBBBB" />\n' % (self.exp_male_bg) + \
                    '          <image x="2" y="4" xlink:href="images/male.png" height="12" width="12"></image>\n' + \
                    '          <text x="15" y="15" font-vamily="Verdana" font-size="10" fill="black">Has Children</text>\n' + \
                    '         </g>\n' + \
                    '        </svg> \n' + \
                    '        <svg width="80" height="20">\n' + \
                    '         <g>\n' + \
                    '           <rect x="0" y="0" width="80" height="20" style="fill:%s;stroke-width:1;stroke:#BBBBBB" />\n' % (self.male_bg) + \
                    '          <image x="2" y="4" xlink:href="images/male.png" height="12" width="12"></image>\n' + \
                    '          <text x="15" y="15" font-vamily="Verdana" font-size="10" fill="black">No Children</text>\n' + \
                    '         </g>\n' + \
                    '        </svg> \n' + \
                    '        <svg width="80" height="20">\n' + \
                    '         <g>\n' + \
                    '           <rect x="0" y="0" width="80" height="20" style="fill:%s;stroke-width:1;stroke:#BBBBBB" />\n' % (self.exp_female_bg) + \
                    '          <image x="2" y="4" xlink:href="images/female.png" height="12" width="12"></image>\n' + \
                    '          <text x="15" y="15" font-vamily="Verdana" font-size="10" fill="black">Has Children</text>\n' + \
                    '         </g>\n' + \
                    '        </svg> \n' + \
                    '        <svg width="80" height="20">\n' + \
                    '         <g>\n' + \
                    '           <rect x="0" y="0" width="80" height="20" style="fill:%s;stroke-width:1;stroke:#BBBBBB" />\n' % (self.female_bg) + \
                    '          <image x="2" y="4" xlink:href="images/female.png" height="12" width="12"></image>\n' + \
                    '          <text x="15" y="15" font-vamily="Verdana" font-size="10" fill="black">No Children</text>\n' + \
                    '         </g>\n' + \
                    '        </svg>\n' + \
                    '       </h3>\n' + \
                    '      </div>\n' + \
                    '    </div>\n' + \
                    '    <div id="testString">\n' + \
                    '    </div>\n' + \
                    '    <script type="text/javascript" ' + \
                    'src="js/%s.js"></script>\n' % (self.destprefix) + \
                    '  </body>\n' + \
                    '</html>\n'
                fp.write(outstr)

        except IOError as msg:
            ErrorDialog(_("Failed writing %s: %s") % (self.desthtml, str(msg)))
            return

        # Create required directory structure
        try:
            if not os.path.exists(os.path.join(self.dest_path, "css")):
                os.mkdir(os.path.join(self.dest_path, "css"))
            if not os.path.exists(os.path.join(self.dest_path, "images")):
                os.mkdir(os.path.join(self.dest_path, "images"))
            if not os.path.exists(os.path.join(self.dest_path, "js")):
                os.mkdir(os.path.join(self.dest_path, "js"))
            if not os.path.exists(os.path.join(self.dest_path, "js", "d3")):
                os.mkdir(os.path.join(self.dest_path, "js", "d3"))
            if not os.path.exists(os.path.join(self.dest_path, "js", "jquery")):
                os.mkdir(os.path.join(self.dest_path, "js", "jquery"))
            if not os.path.exists(os.path.join(self.dest_path, "json")):
                os.mkdir(os.path.join(self.dest_path, "json"))
        except OSError as why:
            ErrorDialog(_("Failed to create directory structure : %s") % (why))
            return

        try:
            # Copy/overwrite css/images/js files
            plugin_dir = os.path.dirname(__file__)
            shutil.copy(os.path.join(plugin_dir, "css", "collapsibletree.css"),
                os.path.join(self.dest_path, "css"))
            shutil.copy(os.path.join(plugin_dir, "images", "male.png"),
                os.path.join(self.dest_path, "images"))
            shutil.copy(os.path.join(plugin_dir, "images", "female.png"),
                os.path.join(self.dest_path, "images"))
            shutil.copy(
                os.path.join(plugin_dir, "images", "texture-noise.png"),
                os.path.join(self.dest_path, "images"))
            shutil.copy(os.path.join(plugin_dir, "js", "d3", "d3.min.js"),
                os.path.join(self.dest_path, "js", "d3"))
            shutil.copy(
                os.path.join(
                    plugin_dir, "js", "jquery", "jquery-2.0.3.min.js"),
                os.path.join(self.dest_path, "js", "jquery"))
        except OSError as why:
            ErrorDialog(_("Failed to copy web files : %s") % (why))
            return

        # Generate <dest>.js based on colors and initial
        # generations to display
        try:
            with io.open(self.destjs, 'w', encoding='utf8') as fp:
                fp.write('var m = [20, 50, 20, 100],\n')
                fp.write(' w = 4000 - m[1] - m[3],\n')
                fp.write(' h = 4000 - m[0] - m[2],\n')
                fp.write(' i = 0,\n')
                fp.write(' root,\n')
                fp.write(' strAdjust = 25,\n')
                fp.write(' rectHeight = 15,\n')
                fp.write(' rectWidths = [0];\n\n')
                fp.write('var tree = d3.layout.tree()\n')
                fp.write(' .size([h, w]);\n\n')
                fp.write('var diagonal = d3.svg.diagonal().' +
                    'projection(function (d) {\n')
                fp.write('  return [d.y, d.x];\n')
                fp.write(' });\n\n')
                fp.write('var vis = d3.select("#chart").' +
                    'append("svg:svg")\n')
                fp.write(' .attr("width", w + m[1] + m[3])\n')
                fp.write(' .attr("height", h + m[0] + m[2])\n')
                fp.write(' .append("svg:g")\n')
                fp.write(' .attr("transform", "translate(" + m[3] +' +
                    ' "," + m[0] + ")");\n\n')
                out_str = 'd3.json("json/%s.json", ' % (self.destprefix)
                fp.write(out_str + 'function(json) {\n')
                fp.write(' var testString = ' +
                    'document.getElementById("testString");\n\n')
                fp.write(' root = json;\n')
                fp.write(' root.x0 = h / 2;\n')
                fp.write(' root.y0 = 0;\n\n')
                fp.write(' function toggleAll(d) {\n')
                fp.write('  if (d.children) {\n')
                fp.write('   d.children.forEach(toggleAll);\n')
                fp.write('   toggle(d);\n')
                fp.write('  }\n')
                fp.write(' }\n\n')
                fp.write(' if (root.children) {\n')
                fp.write('  // Initialize the display to show a ' +
                    'few nodes.\n')
                fp.write('  root.children.forEach(toggleAll);\n\n')
                fp.write('  if (root.children[0]) {\n')
                fp.write('   toggle(root.children[0]);\n\n')
                fp.write('   if (root.children[0].children) {\n')
                fp.write('    if (root.children[0].children[0]) {\n')
                fp.write('     toggle(root.children[0].' +
                    'children[0]);\n\n')
                fp.write('     if (root.children[0].children[0].' +
                    'children) {\n')
                fp.write('      if (root.children[0].children[0].' +
                    'children[0]) {\n')
                fp.write('       toggle(root.children[0].children[0].' +
                    'children[0]);\n')
                fp.write('      }\n')
                fp.write('      if (root.children[0].children[0].' +
                    'children[1]) {\n')
                fp.write('       toggle(root.children[0].children[0].' +
                    'children[1]);\n')
                fp.write('      }\n')
                fp.write('     }\n')
                fp.write('    }\n')
                fp.write('    if (root.children[0].children[1]) {\n')
                fp.write('     toggle(root.children[0].' +
                    'children[1]);\n\n')
                fp.write('     if (root.children[0].children[1].' +
                    'children) {\n')
                fp.write('      if (root.children[0].children[1].' +
                    'children[0]) {\n')
                fp.write('       toggle(root.children[0].children[1].' +
                    'children[0]);\n')
                fp.write('      }\n')
                fp.write('      if (root.children[0].children[1].' +
                    'children[1]) {\n')
                fp.write('       toggle(root.children[0].children[1].' +
                    'children[1]);\n')
                fp.write('      }\n')
                fp.write('     }\n')
                fp.write('    }\n')
                fp.write('   }\n')
                fp.write('  }\n\n')
                fp.write('  if (root.children[1]) {\n')
                fp.write('   toggle(root.children[1]);\n\n')
                fp.write('   if (root.children[1].children) {\n')
                fp.write('    if (root.children[1].children[0]) {\n')
                fp.write('     toggle(root.children[1].' +
                    'children[0]);\n')
                fp.write('     if (root.children[1].children[0].' +
                    'children) {\n')
                fp.write('      if (root.children[1].children[0].' +
                    'children[0]) {\n')
                fp.write('       toggle(root.children[1].children[0].' +
                    'children[0]);\n')
                fp.write('      }\n')
                fp.write('      if (root.children[1].children[0].' +
                    'children[1]) {\n')
                fp.write('       toggle(root.children[1].children[0].' +
                    'children[1]);\n')
                fp.write('      }\n')
                fp.write('     }\n')
                fp.write('    }\n\n')
                fp.write('    if (root.children[1].children[1]) {\n')
                fp.write('     toggle(root.children[1].' +
                    'children[1]);\n\n')
                fp.write('     if (root.children[1].children[1].' +
                    'children) {\n')
                fp.write('      if (root.children[1].children[1].' +
                    'children[0]) {\n')
                fp.write('       toggle(root.children[1].children[1].' +
                    'children[0]);\n')
                fp.write('      }\n')
                fp.write('      if (root.children[1].children[1].' +
                    'children[1]) {\n')
                fp.write('       toggle(root.children[1].children[1].' +
                    'children[1]);\n')
                fp.write('      }\n')
                fp.write('     }\n')
                fp.write('    }\n')
                fp.write('   }\n')
                fp.write('  }\n')
                fp.write(' }\n\n')
                fp.write(' var calcRectWidths = function ' +
                    '(level, n) {\n')
                fp.write('  testString.innerHTML = n.name;\n')
                fp.write('  strHeight = (testString.clientHeight + ' +
                    'strAdjust);\n')
                fp.write('  strWidth = (testString.clientWidth + ' +
                    'strAdjust);\n\n')
                fp.write('  if (rectWidths[level] < strWidth) {\n')
                fp.write('   rectWidths[level] = strWidth;\n')
                fp.write('  }\n\n')
                fp.write('  if (n.children && n.children.length > 0) ' +
                    '{\n')
                fp.write('   if (rectWidths.length <= (level + 1)) ' +
                    '{\n')
                fp.write('    rectWidths.push(0);\n')
                fp.write('   }\n')
                fp.write('   n.children.forEach (function (d) {\n')
                fp.write('     calcRectWidths(level+1, d);\n')
                fp.write('   });\n')
                fp.write('  }\n')
                fp.write('  if (n._children && n._children.' +
                    'length > 0) {\n')
                fp.write('   if (rectWidths.length <= (level + 1)) ' +
                    '{\n')
                fp.write('    rectWidths.push(0);\n')
                fp.write('   }\n')
                fp.write('   n._children.forEach (function (d) {\n')
                fp.write('     calcRectWidths(level+1, d);\n')
                fp.write('   });\n')
                fp.write('  }\n')
                fp.write(' };\n')
                fp.write(' calcRectWidths(0, root);\n\n')
                fp.write(' update(root);\n')
                fp.write('});\n\n')
                fp.write('function update(source) {\n')
                fp.write(' var strHeight = 0,\n')
                fp.write('  strWidth = 0,\n')
                fp.write('  duration = d3.event && d3.event.altKey ? ' +
                    '1000 : 500,\n')
                fp.write('  totalPersons = 0,\n')
                fp.write('  newHeight = 0,\n')
                fp.write('  newWidth = 0,\n')
                fp.write('  heightItems = 0,\n')
                fp.write('  totalPersons = 0,\n')
                fp.write('  levelWidth = [1];\n\n')
                fp.write(' var calcDepthVisible = function (level, ' +
                    'n) {\n')
                fp.write('  // Dynamically determien height/width ' +
                    'of canvas based on\n')
                fp.write('  // Depth currently displayed\n')
                fp.write('  totalPersons = totalPersons + 1;\n')
                fp.write('  if (n.children && n.children.length > 0)' +
                    ' {\n')
                fp.write('   if (levelWidth.length <= (level + 1)) ' +
                    '{\n')
                fp.write('    levelWidth.push(0);\n')
                fp.write('   }\n')
                fp.write('   levelWidth[level+1] += n.children.' +
                    'length;\n\n')
                fp.write('   n.children.forEach( function (d) {\n')
                fp.write('    calcDepthVisible(level+1, d);\n')
                fp.write('   });\n')
                fp.write('  }\n')
                fp.write(' };\n\n')
                fp.write(' calcDepthVisible(0, root);\n')
                fp.write(' switch (levelWidth.length) {\n')
                fp.write('  case 0 :\n')
                fp.write('   heightItems = 3;\n')
                fp.write('   break;\n')
                fp.write('  case 1 :\n')
                fp.write('   heightItems = 3;\n')
                fp.write('   break;\n')
                fp.write('  case 2:\n')
                fp.write('   heightItems = 3;\n')
                fp.write('   break;\n')
                fp.write('  case 3:\n')
                fp.write('   heightItems = 7;\n')
                fp.write('   break;\n')
                fp.write('  case 4:\n')
                fp.write('   heightItems = 15;\n')
                fp.write('   break;\n')
                fp.write('  case 5:\n')
                fp.write('   heightItems = 25;\n')
                fp.write('   break;\n')
                fp.write('  default:\n')
                fp.write('   heightItems = levelWidth.length * 5;\n')
                fp.write('   break;\n')
                fp.write(' }\n\n')
                fp.write(' if (totalPersons < heightItems) {\n')
                fp.write('  heightItems = totalPersons;\n')
                fp.write(' }\n\n')
                fp.write(' newWidth = levelWidth.length * 150;\n\n')
                fp.write(' if (newWidth > ($(window).width()-170)) ' +
                    '{\n')
                fp.write('  newWidth = $(window).width()-170;\n')
                fp.write(' }\n\n')
                fp.write(' newHeight = heightItems * 50;\n')
                fp.write(' if (newHeight < 180) {\n')
                fp.write('  newHeight = 180;\n')
                fp.write(' }\n')
                fp.write(' tree.size([newHeight, newWidth]);\n\n')
                fp.write(' // Compute the new tree layout.\n')
                fp.write(' var nodes = tree.nodes(root).reverse();' +
                    '\n\n')
                fp.write(' // Update the nodes\n')
                fp.write(' var node = vis.selectAll("g.node").' +
                    'data(nodes, function(d) {\n')
                fp.write('      return d.id || (d.id = ++i);\n')
                fp.write('  });\n\n')
                fp.write(' // Enter any new nodes at the parents ' +
                    'previous position.\n')
                fp.write(' var nodeEnter = node.enter().' +
                    'append("svg:g")\n')
                fp.write('  .attr("class", "node")\n')
                fp.write('  .attr("transform", function(d) {\n')
                fp.write('    return "translate(" + source.y0 + "," ' +
                    '+ source.x0 + ")";\n')
                fp.write('   })\n')
                fp.write('  .on("click", function(d) { toggle(d); ' +
                    'update(d); });\n\n')
                fp.write(' nodeEnter.append("svg:rect")\n')
                fp.write('  .attr("width", function(d) {\n')
                fp.write('    return rectWidths[d.depth];\n')
                fp.write('   })\n')
                fp.write('  .attr("height", rectHeight*2)\n')
                fp.write('  .attr("x", function(d) {\n')
                fp.write('    return (-rectWidths[d.depth]/2);\n')
                fp.write('   })\n')
                fp.write('  .attr("y", -rectHeight)\n')
                fp.write('  .style("fill", function(d) {\n')
                fp.write('    if (d.gender == "male") {\n')
                fp.write('     return d._children ? "%s" : "%s";\n' %
                    (self.exp_male_bg, self.male_bg))
                fp.write('    } else if (d.gender == "female") {\n')
                fp.write('     return d._children ? "%s" : "%s";\n' %
                    (self.exp_female_bg, self.female_bg))
                fp.write('    } else {\n')
                fp.write('     return d._children ? ' +
                    '"lightsteelblue" : "#fff";\n')
                fp.write('    }\n')
                fp.write('   });\n\n')
                fp.write(' nodeEnter.append("svg:image")\n')
                fp.write('  .attr("xlink:href", function (d) {\n')
                fp.write('    return d.gender == "male" ?\n')
                fp.write('     "images/male.png" : ' +
                    '"images/female.png";\n')
                fp.write('   })\n')
                fp.write('  .attr("height", 12)\n')
                fp.write('  .attr("width", 12)\n')
                fp.write('  .attr("y", -rectHeight + 4)\n')
                fp.write('  .attr("x", function(d) {\n')
                fp.write('    return ((-rectWidths[d.depth]/2)+2);\n')
                fp.write('   });\n\n')
                fp.write(' nodeEnter.append("svg:text")\n')
                fp.write('  .attr("x", function(d) { return +5; })\n')
                fp.write('  .attr("dy", "-.12em")\n')
                fp.write('  .attr("text-anchor", "middle")\n')
                fp.write('  .call(wrap)\n')
                fp.write('  .style("fill-opacity", 1e-6);\n\n')
                fp.write(' // Transition nodes to their new ' +
                    'position.\n')
                fp.write(' var nodeUpdate = node.transition()\n')
                fp.write('  .duration(duration)\n')
                fp.write('  .attr("transform", function(d) {\n')
                fp.write('    return "translate(" + d.y + "," + ' +
                    'd.x + ")";\n')
                fp.write('   });\n\n')
                fp.write(' nodeUpdate.select("rect")\n')
                fp.write('  .attr("width", function(d) {\n')
                fp.write('    return rectWidths[d.depth];\n')
                fp.write('   })\n')
                fp.write('  .attr("height", rectHeight*2)\n')
                fp.write('  .attr("x", function(d) {\n')
                fp.write('    return (-rectWidths[d.depth]/2);\n')
                fp.write('   })\n')
                fp.write('  .attr("y", -rectHeight)\n')
                fp.write('  .style("fill", function(d) {\n')
                fp.write('    if (d.gender == "male") {\n')
                fp.write('     return d._children ? "%s" : "%s";\n' %
                    (self.exp_male_bg, self.male_bg))
                fp.write('    } else if (d.gender == "female") {\n')
                fp.write('     return d._children ? "%s" : "%s";\n' %
                    (self.exp_female_bg, self.female_bg))
                fp.write('    } else {\n')
                fp.write('     return d._children ? ' +
                    '"lightsteelblue" : "#fff";\n')
                fp.write('    }\n')
                fp.write('   });\n\n')
                fp.write(' nodeUpdate.select("text")\n')
                fp.write('  .style("fill-opacity", 1);\n\n')
                fp.write(' // Transition exiting nodes to the ' +
                    'parents new position.\n')
                fp.write(' var nodeExit = node.exit().transition()\n')
                fp.write('  .duration(duration)\n')
                fp.write('  .attr("transform", function(d) {\n')
                fp.write('    return "translate(" + source.y + "," ' +
                    '+ source.x + ")";\n')
                fp.write('   })\n')
                fp.write('  .remove();\n\n')
                fp.write(' nodeExit.select("rect")\n')
                fp.write('  .attr("width", function(d) {\n')
                fp.write('    return rectWidths[d.depth];\n')
                fp.write('   })\n')
                fp.write('  .attr("height", rectHeight*2)\n')
                fp.write('  .attr("x", function(d) {\n')
                fp.write('    return (-rectWidths[d.depth]/2);\n')
                fp.write('   })\n')
                fp.write('  .attr("y", -rectHeight);\n\n')
                fp.write(' nodeExit.select("text")\n')
                fp.write('  .style("fill-opacity", 1e-6);\n\n')
                fp.write(' // Update the links\n')
                fp.write(' var link = vis.selectAll("path.link")\n')
                fp.write('  .data(tree.links(nodes), function(d) ' +
                    '{ return d.target.id; });\n\n')
                fp.write(' // Enter any new links at the parents ' +
                    'previous position.\n')
                fp.write(' link.enter().insert("svg:path", "g")\n')
                fp.write('  .attr("class", "link")\n')
                fp.write('  .attr("d", function(d) {\n')
                fp.write(' var o = {x: source.x0, y: source.y0};\n')
                fp.write('    return diagonal({source: o, target: o}' +
                    ');\n')
                fp.write('   })\n')
                fp.write('  .transition()\n')
                fp.write('  .duration(duration)\n')
                fp.write('  .attr("d", diagonal);\n\n')
                fp.write(' // Transition links to their new ' +
                    'position.\n')
                fp.write(' link.transition()\n')
                fp.write('  .duration(duration)\n')
                fp.write('  .attr("d", diagonal);\n\n')
                fp.write(' // Transition exiting nodes to the ' +
                    'parents new position.\n')
                fp.write(' link.exit().transition()\n')
                fp.write('  .duration(duration)\n')
                fp.write('  .attr("d", function(d) {\n')
                fp.write('    var o = {x: source.x, y: source.y};\n')
                fp.write('    return diagonal({source: o, target: ' +
                    'o});\n')
                fp.write('   })\n')
                fp.write('  .remove();\n\n')
                fp.write(' // Stash the old positions for ' +
                    'transition.\n')
                fp.write(' nodes.forEach(function(d) {\n')
                fp.write('  d.x0 = d.x;\n')
                fp.write('  d.y0 = d.y;\n')
                fp.write(' });\n')
                fp.write('}\n\n')
                fp.write('function wrap(text) {\n')
                fp.write(' text.each(function () {\n')
                fp.write('  var txt = d3.select(this),\n')
                fp.write('   line1 = txt[0][0].__data__.name,\n')
                fp.write('   line2 = "(" + txt[0][0].__data__.born ' +
                    '+ " - " + txt[0][0].__data__.died + ")",\n')
                fp.write('   y = text.attr("y"),\n')
                fp.write('   x = text.attr("x"),\n')
                fp.write('   dy = parseFloat(text.attr("dy")),\n')
                fp.write('   tspan = txt.text(null).append("tspan").' +
                    'attr("x", x).attr("y", y).attr("dy", dy + "em");\n')
                fp.write('\n')
                fp.write('   tspan.text(line1);\n')
                fp.write('   tspan = txt.append("tspan").attr("x", ' +
                    'x).attr("y", y).attr("dy", 1*1.1+dy+"em").text(line2);\n')
                fp.write('  \n')
                fp.write(' });\n')
                fp.write('}\n\n')
                fp.write('// Toggle children.\n')
                fp.write('function toggle(d) {\n')
                fp.write(' if (d.children) {\n')
                fp.write('  d._children = d.children;\n')
                fp.write('  d.children = null;\n')
                fp.write(' } else {\n')
                fp.write('  d.children = d._children;\n')
                fp.write('  d._children = null;\n')
                fp.write(' }\n')
                fp.write('}\n')

        except IOError as msg:
            ErrorDialog(_("Failed writing %s: %s") % (self.destjs, str(msg)))
            return

        # Genearte json data file to be used
        try:
            with io.open(self.destjson, 'w', encoding='utf8') as self.json_fp:
                generation = 0

                # Call json_folter to build the json file of people in the
                # database that match the ancestry.
                self.json_filter(self.center_person.get_handle(), 1)

        except IOError as msg:
            ErrorDialog(_("Failed writing %s: %s") % (self.destjson, str(msg)))
            return

#------------------------------------------------------------------------
#
# AncestralCollapsibleTreeOptions
#
#------------------------------------------------------------------------
class AncestralCollapsibleTreeOptions(MenuReportOptions):

    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, dbase):
        self._dbase = dbase
        MenuReportOptions.__init__(self, name, dbase)

    def validate_gen(self):
        """
        Validate Max generation > 0
        """
        maxgen = self.maxgen.get_value()
        if maxgen < 1:
            self.maxgen.set_value(1)

    def add_menu_options(self, menu):
        """
        Add options to the menu for the ancestral collapsible tree report.
        """
        category_name = _("Ancestral Collapsible Tree Options")

        pid = PersonOption(_("Center Person"))
        pid.set_help(_("The center person for the report"))
        menu.add_option(category_name, "pid", pid)

        pid = menu.get_option_by_name('pid').get_value()
        center_person = self._dbase.get_person_from_gramps_id(
            menu.get_option_by_name('pid').get_value())
        if center_person :
            name_str = global_name_display.display_formal(center_person)
        else:
            name_str = ""

        # We must figure out the value of the first option before we can
        # create the EnumeratedListOption
        fmt_list = global_name_display.get_name_format()
        name_format = EnumeratedListOption(_("Name format"), 0)
        name_format.add_item(0, _("Default"))
        for num, name, fmt_str, act in fmt_list:
            name_format.add_item(num, name)
        name_format.set_help(_("Select the format to display names"))
        menu.add_option(category_name, "name_format", name_format)

        self.maxgen = NumberOption(_("Include Generations"), 10, 1, 100)
        self.maxgen.set_help(_("The number of generations to include in the " +
            "report"))
        menu.add_option(category_name, "maxgen", self.maxgen)
        self.maxgen.connect('value-changed', self.validate_gen)

        male_bg = ColorOption(_("Male Background Color"), "#ffffff")
        male_bg.set_help(_("RGB-color for male box background."))
        menu.add_option(category_name, "male_bg", male_bg)

        exp_male_bg = ColorOption(_("Male Expandable Background Color"),
            "#B4C4D9")
        exp_male_bg.set_help(_("RGB-color for male expandable box background."))
        menu.add_option(category_name, "exp_male_bg", exp_male_bg)

        female_bg = ColorOption(_("Female Background"), "#ffffff")
        female_bg.set_help(_("RGB-color for female box background."))
        menu.add_option(category_name, "female_bg", female_bg)

        exp_female_bg = ColorOption(_("Female Expandable Background"),
            "#F0D5D7")
        exp_female_bg.set_help(_("RGB-color for female expandable box " +
            "background."))
        menu.add_option(category_name, "exp_female_bg", exp_female_bg)

        dest_path = DestinationOption(_("Destination"),
            config.get('paths.website-directory'))
        dest_path.set_help(_("The destination path for generated files."))
        dest_path.set_directory_entry(True)
        menu.add_option(category_name, "dest_path", dest_path)

        dest_file = StringOption(_("Filename"), "AncestralCollapsible.html")
        dest_file.set_help(_("The destination file name for html content."))
        menu.add_option(category_name, "dest_file", dest_file)
