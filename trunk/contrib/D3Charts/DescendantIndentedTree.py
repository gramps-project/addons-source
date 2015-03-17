#
# DescendantIndentedTree - a plugin for GRAMPS, the GTK+/GNOME based
#       genealogy program that creates an Ancestor Chart Map based on
#       the D3.js Indented Tree Layout scheme.
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

# version 0.1

# The idea behind this plugin is to create an descendants tree chart that can
# be interacted with via clicking on an individual to either collapse or expand
# descendants for that individual. The chart is SVG using D3.js layout engine.

"""Reports/Web Pages/Descendant Indented Tree"""

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
                                  StringOption, BooleanOption)
from gramps.gen.plug.report import Report
from gramps.gen.plug.report import utils as ReportUtils
from gramps.gen.plug.report import MenuReportOptions
from gramps.gen.utils.db import (get_birth_or_fallback, get_death_or_fallback,
                                 get_marriage_or_fallback,
                                 get_divorce_or_fallback)
from gramps.gen.config import config
from gramps.gen.datehandler import get_date
from gramps.gen.sort import Sort

#------------------------------------------------------------------------
#
# PrintSimple
#   Simple numbering system
#
#------------------------------------------------------------------------
class PrintSimple():
    def __init__(self, dups):
        self.dups = dups
        self.num = {0:1}

    def number(self, level):
        if self.dups:
            # Just show original simple numbering
            to_return = "%d." % level
        else:
            to_return = str(level)
            if level > 1:
                to_return += "-" + str(self.num[level-1])
            to_return += "."

            self.num[level] = 1
            self.num[level-1] = self.num[level-1] + 1

        return to_return
    
    
#------------------------------------------------------------------------
#
# PrintVlliers
#   de_Villiers_Pama numbering system
#
#------------------------------------------------------------------------
class PrintVilliers():
    def __init__(self):
        self.pama = 'abcdefghijklmnopqrstuvwxyz'
        self.num = {0:1}
    
    def number(self, level):
        to_return = self.pama[level-1]
        if level > 1:
            to_return += str(self.num[level-1])
        to_return += "."
        
        self.num[level] = 1
        self.num[level-1] = self.num[level-1] + 1

        return to_return
    

#------------------------------------------------------------------------
#
# PrintMeurgey
#   Meurgey_de_Tupigny numbering system
#
#------------------------------------------------------------------------
class PrintMeurgey():
    def __init__(self):
        self.childnum = [""]
    
    def number(self, level):
        if level == 1:
            dash = ""
        else:
            dash = "-"
            if len(self.childnum) < level:
                self.childnum.append(1)
        
        to_return = (ReportUtils.roman(level) + dash +
                     str(self.childnum[level-1]) + ".")

        if level > 1:
            self.childnum[level-1] += 1
        
        return to_return

#------------------------------------------------------------------------
#
# Printinfo
#
#------------------------------------------------------------------------
class Printinfo():
    """
    A base class used to help make the individual numbering system classes.
    This class must first be initialized with set_class_vars
    """
    def __init__(self, database, numbering, showmarriage, showdivorce,\
                 name_display):
        #classes
        self._name_display = name_display
        self.database = database
        self.numbering = numbering
        #variables
        self.showmarriage = showmarriage
        self.showdivorce = showdivorce
        self.json_fp = None

    def set_json_fp(self, json_fp):
        self.json_fp = json_fp

    def get_date_place(self,event):
        if event:
            year = event.get_date_object().get_year()
            date = get_date(event)
            place_handle = event.get_place_handle()
            if place_handle:
                places = self.database.get_place_from_handle(
                    place_handle).get_title().split(',')
                
                if places:
                    place = places[0]
                    return("%(event_abbrev)s %(date)s %(place)s" % {
                        'event_abbrev': event.type.get_abbreviation(),
                        'date' : date,
                        'place' : place,
                        })
            else:
                return("%(event_abbrev)s %(date)s" % {
                    'event_abbrev': event.type.get_abbreviation(),
                    'date' : date
                    })
        return ""

    def dump_string(self, person, level, family=None):
        gen_pad = (level-1) * 2

        born = self.get_date_place(get_birth_or_fallback(self.database, person))
        died = self.get_date_place(get_death_or_fallback(self.database, person))

        self.json_fp.write('%s"born": "%s",\n' %
            (self.pad_str(gen_pad+1), str(born)))
        self.json_fp.write('%s"died": "%s",\n' %
            (self.pad_str(gen_pad+1), str(died)))

        if family and self.showmarriage:
            marriage = self.get_date_place(
                get_marriage_or_fallback(self.database,
                                                              family))
            self.json_fp.write('%s"marriage": "%s",\n' %
                (self.pad_str(gen_pad+1), str(marriage)))
            
        if family and self.showdivorce:
            divorce = self.get_date_place(
                get_divorce_or_fallback(self.database, family))
            self.json_fp.write('%s"divorce": "%s",\n' %
                (self.pad_str(gen_pad+1), str(divorce)))

        self.json_fp.write('%s"gender": "%s"' %
            (self.pad_str(gen_pad+1), self.get_gender_str(person)))

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

    def print_person(self, level, person):
        display_num = self.numbering.number(level)
        name = self._name_display.display(person)
        gen_pad = (level-1) * 2

        self.json_fp.write('%s"display_num": "%s",\n' %
            (self.pad_str(gen_pad+1), str(display_num)))
        self.json_fp.write('%s"name": "%s",\n' %
            (self.pad_str(gen_pad+1), name.replace('"', "'")))
        self.json_fp.write('%s"spouse": "%s",\n' %
            (self.pad_str(gen_pad+1), "false"))
        self.dump_string(person, level)
        return display_num
    
    def print_spouse(self, level, spouse_handle, family_handle):
        #Currently print_spouses is the same for all numbering systems.
        gen_pad = (level-1) * 2

        if spouse_handle:
            spouse = self.database.get_person_from_handle(spouse_handle)
            name = self._name_display.display(spouse)

            self.json_fp.write('%s"display_num": "%s",\n' %
                (self.pad_str(gen_pad+1), "sp."))
            self.json_fp.write('%s"name": "%s",\n' %
                (self.pad_str(gen_pad+1), name.replace('"', "'")))
            self.json_fp.write('%s"spouse": "%s",\n' %
                (self.pad_str(gen_pad+1), "true"))
            self.dump_string(spouse, level, family_handle)
        else:

            name = "Unknown"
            self.json_fp.write('%s"display_num": "%s",\n' %
                (self.pad_str(gen_pad+1), "sp."))
            self.json_fp.write('%s"name": "%s",\n' %
                (self.pad_str(gen_pad+1), name.replace('"', "'")))
            self.json_fp.write('%s"spouse": "%s"\n' %
                (self.pad_str(gen_pad+1), "true"))

    def print_reference(self, level, person, display_num):
        #Person and their family have already been printed so
        #print reference here
        if person:
            gen_pad = (level-1) * 2
            sp_name = self._name_display.display(person)
            name = _("See %(reference)s : %(spouse)s" %
                    {'reference': display_num, 'spouse': sp_name})
            self.json_fp.write('%s{\n' % (self.pad_str(gen_pad)))
            self.json_fp.write('%s"display_num": "%s",\n' %
                (self.pad_str(gen_pad+1), "sp."))
            self.json_fp.write('%s"name": "%s",\n' %
                (self.pad_str(gen_pad+1), name.replace('"', "'")))
            self.json_fp.write('%s"spouse": "%s"\n' %
                (self.pad_str(gen_pad+1), "true"))

#------------------------------------------------------------------------
#
# RecurseDown
#
#------------------------------------------------------------------------
class RecurseDown():
    """
    A simple object to recurse from a person down through their descendants
    
    The arguments are:
    
    max_generations: The max number of generations
    database:  The database object
    objPrint:  A Printinfo derived class that prints person
               information on the report
    """
    def __init__(self, max_generations, database, objPrint, dups, marrs, divs):
        self.max_generations = max_generations
        self.database = database
        self.objPrint = objPrint
        self.dups = dups
        self.marrs = marrs
        self.divs = divs
        self.person_printed = {}

    def pad_str(self, num_spaces):
        """
        Utility method to retrieve string with specific number of spaces
        """
        pad_str = ""
        for i in range(0, num_spaces):
            pad_str = pad_str + " "
        return pad_str
    
    def recurse(self, level, person, curdepth):
        gen_pad = (level-1) * 2
        person_handle = person.get_handle()
        self.objPrint.json_fp.write('%s{\n' % (self.pad_str(gen_pad)))
        display_num = self.objPrint.print_person(level, person)

        if curdepth is None:
            ref_str = display_num
        else:
            ref_str = curdepth + " " + display_num

        if person_handle not in self.person_printed:
            self.person_printed[person_handle] = ref_str

        if len(person.get_family_handle_list()) > 0:
            self.objPrint.json_fp.write(',\n%s"children": [\n' %
                (self.pad_str(gen_pad)))

        family_num = 0
        for family_handle in person.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)
            family_num += 1

            spouse_handle = ReportUtils.find_spouse(person, family)

            if not self.dups and spouse_handle in self.person_printed:
                # Just print a reference
                spouse = self.database.get_person_from_handle(spouse_handle)
                if family_num > 1:
                    self.objPrint.json_fp.write(',%s{\n' % (self.pad_str(gen_pad)))
                else:
                    self.objPrint.json_fp.write('%s{\n' % (self.pad_str(gen_pad)))
                self.objPrint.print_reference(level, spouse,
                    self.person_printed[spouse_handle])
                self.objPrint.json_fp.write('%s}\n' % (self.pad_str(gen_pad)))
            else:
                if family_num > 1:
                    self.objPrint.json_fp.write(',%s{\n' % (self.pad_str(gen_pad)))
                else:
                    self.objPrint.json_fp.write('%s{\n' % (self.pad_str(gen_pad)))
                self.objPrint.print_spouse(level, spouse_handle, family)

                if spouse_handle:
                    spouse_num = _("%s sp." % (ref_str))
                    self.person_printed[spouse_handle] = spouse_num

                if level >= self.max_generations:
                    self.objPrint.json_fp.write('%s}\n%s]\n' %
                        (self.pad_str(gen_pad), (self.pad_str(gen_pad))))
                    continue

                childlist = family.get_child_ref_list()[:]
                first_child = True
                for child_ref in childlist:
                    if first_child:
                        first_child = False
                        self.objPrint.json_fp.write(',\n%s"children": [\n' %
                            (self.pad_str(gen_pad+1)))
                    else:
                        self.objPrint.json_fp.write(',')
                    child = self.database.get_person_from_handle(child_ref.ref)
                    self.recurse(level+1, child, ref_str)

                if not first_child:
                    self.objPrint.json_fp.write('\n%s]\n' %
                        (self.pad_str(gen_pad+1)))

                self.objPrint.json_fp.write('%s}\n' % (self.pad_str(gen_pad)))

        if len(person.get_family_handle_list()) > 0:
            self.objPrint.json_fp.write('%s]\n%s}\n' %
                (self.pad_str(gen_pad), self.pad_str(gen_pad)))
        else:
            self.objPrint.json_fp.write('\n%s}\n' % (self.pad_str(gen_pad)))

#------------------------------------------------------------------------
#
# DescendantIndentedTreeReport
#
#------------------------------------------------------------------------
class DescendantIndentedTreeReport(Report):
    """
    Descendant Indented Tree Report class
    """
    def __init__(self, database, options, user):
        """
        Create the Descendant Indented Tree object that produces the
        Descendant Indented Tree report.

        The arguments are:

        database        - the GRAMPS database instance
        options         - instance of the Options class for this report
        user            - a gen.user.User() instance

        This report needs the following parameters (class variables)
        that come in the options class.

        max_gen       - Maximum number of generations to include.
        name_format   - Preferred format to display names
        numbering     - numbering system to use
        dups          - Whether to include duplicate descendant trees
        marrs         - Whether to include Marriage Info
        divs          - Whether to include Divorce Info
        dest_path     - Destination Path
        dest_file     - Destination HTML filename
        parent_bg     - Background color for expanded rows
        more_bg       - Background color expandable rows
        no_more_bg    - Background color non-expandable rows
        """
        Report.__init__(self, database, options, user)

        self.map = {}

        menu = options.menu
        self.max_gen = menu.get_option_by_name('max_gen').get_value()
        self.parent_bg = menu.get_option_by_name('parent_bg').get_value()
        self.more_bg = menu.get_option_by_name('more_bg').get_value()
        self.no_more_bg = menu.get_option_by_name('no_more_bg').get_value()
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

        sort = Sort(self.database)
        self.by_birthdate = sort.by_birthdate_key
    
        #Initialize the Printinfo class    
        self.dups = menu.get_option_by_name('dups').get_value()
        numbering = menu.get_option_by_name('numbering').get_value()
        if numbering == "Simple":
            obj = PrintSimple(self.dups)
        elif numbering == "de Villiers/Pama":
            obj = PrintVilliers()
        elif numbering == "Meurgey de Tupigny":
            obj = PrintMeurgey()
        else:
            raise AttributeError("no such numbering: '%s'" % self.numbering)

        self.marrs = menu.get_option_by_name('marrs').get_value()
        self.divs = menu.get_option_by_name('divs').get_value()

        # Copy the global NameDisplay so that we don't change application
        # defaults.
        self._name_display = copy.deepcopy(global_name_display)
        name_format = menu.get_option_by_name("name_format").get_value()
        if name_format != 0:
            self._name_display.set_default_format(name_format)

        self.objPrint = Printinfo(database, obj, self.marrs,
                                  self.divs, self._name_display)

    def write_report(self):
        """
        The routine the actually creates the report. At this point, the document
        is opened and ready for writing.
        """
        name = self._name_display.display(self.center_person)
        title = "Descendant Indented Tree for " + name
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
                    'href="css/indentedtree.css"/>\n' + \
                    '  </head>\n' + \
                    '  <body>\n' + \
                    '    <div id="body">\n' + \
                    '      <div id="start">\n' + \
                    '       <h1>' + title + '</h1>\n' + \
                    '      </div>\n' + \
                    '      <div id="chart">\n' + \
                    '      </div>\n' + \
                    '      <div id="end">\n' + \
                    '       <h3>Click people to expand/collapse</h3>\n' + \
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
            shutil.copy(os.path.join(plugin_dir, "css", "indentedtree.css"),
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
                fp.write('var margin = {top: 30, right: 20, bottom: ' +
                    '30, left: 20},\n')
                fp.write(' width = 1024 - margin.left - ' +
                    'margin.right,\n')
                fp.write(' textMargin = 5.5,\n')
                fp.write(' barHeight = 20,\n')
                fp.write(' i = 0,\n')
                fp.write(' duration = 400,\n')
                fp.write(' root;\n\n')
                fp.write('var tree = d3.layout.tree().' +
                    'nodeSize([0, 20]);\n\n')
                fp.write('var diagonal = d3.svg.diagonal().' +
                    'projection(function(d) {\n')
                fp.write(' return [d.y, d.x];\n')
                fp.write('});\n\n')
                fp.write('var svg = d3.select("body").' +
                    'append("svg")\n')
                fp.write(' .attr("width", width + margin.left + ' +
                    'margin.right).append("g")\n')
                fp.write(' .attr("transform", "translate(" + ' +
                    'margin.left + "," + margin.top + ")");\n\n')
                out_str='d3.json("json/%s.json", ' % (self.destprefix)
                fp.write(out_str + 'function(error, descendant) {\n')
                fp.write(' descendant.x0 = 0;\n')
                fp.write(' descendant.y0 = 0;\n')
                fp.write(' update(root = descendant);\n')
                fp.write('});\n\n')
                fp.write('function update(source) {\n')
                fp.write(' // Compute the flattened node list. ' +
                    'TODO use d3.layout.hierarchy.\n')
                fp.write(' var strWidth = 0;\n')
                fp.write(' var nodes = tree.nodes(root);\n')
                fp.write(' var height = Math.max(500, nodes.length *' +
                    ' barHeight +\n')
                fp.write('  margin.top + margin.bottom);\n\n')
                fp.write(' d3.select("svg").transition().' +
                    'duration(duration).attr("height", height);\n\n')
                fp.write(' d3.select(self.frameElement).' +
                    'transition().duration(duration)\n')
                fp.write('  .style("height", height + "px");\n\n')
                fp.write(' // Compute the "layout".\n')
                fp.write(' nodes.forEach(function(n, i) {\n')
                fp.write('  // Set X Co-ordinate for each node\n')
                fp.write('  n.x = i * barHeight;\n')
                fp.write(' });\n\n')
                fp.write(' // Update the nodes\n')
                fp.write(' var node = svg.selectAll("g.node")\n')
                fp.write('  .data(nodes, function(d) { return ' +
                    'd.id || (d.id = ++i); });\n\n')
                fp.write(' var nodeEnter = node.enter().' +
                    'append("g")\n')
                fp.write('  .attr("class", "node")\n')
                fp.write('  .attr("transform", function(d) {\n')
                fp.write('    return "translate(" + source.y0 + ' +
                    '"," + source.x0 + ")";\n')
                fp.write('   })\n')
                fp.write('  .style("opacity", 1e-6);\n\n')
                fp.write(' // Enter any new nodes at the parents ' +
                    'previous position.\n')
                fp.write(' nodeEnter.append("rect")\n')
                fp.write('  .attr("y", -barHeight / 2)\n')
                fp.write('  .attr("height", barHeight)\n')
                fp.write('  .attr("width", function(n) { return ' +
                    'width - n.y;})\n')
                fp.write('  .style("fill", color)\n')
                fp.write('  .on("click", click);\n\n')
                fp.write(' nodeEnter.append("text")\n')
                fp.write('  .attr("dy", 3.5)\n')
                fp.write('  .attr("dx", textMargin)\n')
                fp.write('  .text(function(d) {\n' +
                    '    var ret_str = d.display_num' +
                    ' + " " + d.name + " (" + d.born + " - " + d.died + ")";' +
                    '    if (d.display_num == "sp.") {\n' +
                    '     if (d.marriage !== undefined && d.marriage.length > 0) {\n' +
                    '      ret_str = ret_str + ", " + d.marriage;\n' +
                    '     }\n' +
                    '     if (d.divorve !== undefined && d.divorce.length > 0) {\n' +
                    '      ret_str = ret_str + ", " + d.divorce;\n' +
                    '     }\n' +
                    '    }\n' +
                    '    return ret_str;\n' +
                    '   });\n\n')
                fp.write(' // Transition nodes to their new ' +
                    'position.\n')
                fp.write(' nodeEnter.transition()\n')
                fp.write('  .duration(duration)\n')
                fp.write('  .attr("transform", function(d) {\n')
                fp.write('    return "translate(" + d.y + "," + ' +
                    'd.x + ")";\n')
                fp.write('   })\n')
                fp.write('  .style("opacity", 1);\n\n')
                fp.write(' node.transition()\n')
                fp.write('  .duration(duration)\n')
                fp.write('  .attr("transform", function(d) {\n')
                fp.write('    return "translate(" + d.y + "," + ' +
                    'd.x + ")";\n')
                fp.write('   })\n')
                fp.write('  .style("opacity", 1)\n')
                fp.write('  .select("rect")\n')
                fp.write('  .style("fill", color);\n\n')
                fp.write(' // Transition exiting nodes to the ' +
                    'parents new position.\n')
                fp.write(' node.exit().transition()\n')
                fp.write('  .duration(duration)\n')
                fp.write('  .attr("transform", function(d) {\n')
                fp.write('    return "translate(" + source.y + "," ' +
                    '+ source.x + ")";\n')
                fp.write('   })\n')
                fp.write('  .style("opacity", 1e-6)\n')
                fp.write('  .remove();\n\n')
                fp.write(' // Update the links\n')
                fp.write(' var link = svg.selectAll("path.link")\n')
                fp.write('  .data(tree.links(nodes), function(d) { ' +
                    'return d.target.id; });\n\n')
                fp.write(' // Enter any new links at the parents ' +
                    'previous position.\n')
                fp.write(' link.enter().insert("path", "g")\n')
                fp.write('  .attr("class", "link")\n')
                fp.write('  .attr("d", function(d) {\n')
                fp.write('    var o = {x: source.x0, y: ' +
                    'source.y0};\n')
                fp.write('    return diagonal({source: o, target: ' +
                    'o});\n')
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
                fp.write('// Toggle children on click.\n')
                fp.write('function click(d) {\n')
                fp.write(' if (d.children) {\n')
                fp.write('  d._children = d.children;\n')
                fp.write('  d.children = null;\n')
                fp.write(' } else {\n')
                fp.write('  d.children = d._children;\n')
                fp.write('  d._children = null;\n')
                fp.write(' }\n')
                fp.write(' update(d);\n')
                fp.write('}\n\n')
                fp.write('function color(d) {\n')
                fp.write(' return d._children ? "' + self.more_bg +
                    '" : d.children ? "' + self.parent_bg + '" : "' +
                    self.no_more_bg + '";\n')
                fp.write(' return d._children ? "#3182bd" : ' +
                    'd.children ? "#c6dbef" : "#fd8d3c";\n')
                fp.write('}\n')

        except IOError as msg:
            ErrorDialog(_("Failed writing %s: %s") % (self.destjs, str(msg)))
            return

        # Genearte json data file to be used
        try:
            with io.open(self.destjson, 'w', encoding='utf8') as self.json_fp:
                generation = 1
                self.objPrint.set_json_fp(self.json_fp)
                recurse = RecurseDown(self.max_gen, self.database,
                                      self.objPrint, self.dups, self.marrs,
                                      self.divs)
                recurse.recurse(generation, self.center_person, None)

        except IOError as msg:
            ErrorDialog(_("Failed writing %s: %s") % (self.destjson, str(msg)))
            return

#------------------------------------------------------------------------
#
# DescendantIndentedTreeOptions
#
#------------------------------------------------------------------------
class DescendantIndentedTreeOptions(MenuReportOptions):

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
        max_gen = self.max_gen.get_value()
        if max_gen < 1:
            self.max_gen.set_value(1)

    def add_menu_options(self, menu):
        """
        Add options to the menu for the descendant indented tree report.
        """
        category_name = _("Descendant Indented Tree Options")

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

        numbering = EnumeratedListOption(_("Numbering system"), "Simple")
        numbering.set_items([
                ("Simple",      _("Simple numbering")),
                ("de Villiers/Pama", _("de Villiers/Pama numbering")),
                ("Meurgey de Tupigny", _("Meurgey de Tupigny numbering"))])
        numbering.set_help(_("The numbering system to be used"))
        menu.add_option(category_name, "numbering", numbering)

        self.max_gen = NumberOption(_("Include Generations"), 10, 1, 100)
        self.max_gen.set_help(_("The number of generations to include in the " +
            "report"))
        menu.add_option(category_name, "max_gen", self.max_gen)
        self.max_gen.connect('value-changed', self.validate_gen)

        marrs = BooleanOption(_('Show marriage info'), False)
        marrs.set_help(_("Whether to show marriage information in the report."))
        menu.add_option(category_name, "marrs", marrs)

        divs = BooleanOption(_('Show divorce info'), False)
        divs.set_help(_("Whether to show divorce information in the report."))
        menu.add_option(category_name, "divs", divs)

        dups = BooleanOption(_('Show duplicate trees'), True)
        dups.set_help(_("Whether to show duplicate family trees in the " +
            "report."))
        menu.add_option(category_name, "dups", dups)

        parent_bg = ColorOption(_("Expanded Row Background Color"), "#c6dbef")
        parent_bg.set_help(_("RGB-color for expanded row background."))
        menu.add_option(category_name, "parent_bg", parent_bg)

        more_bg = ColorOption(_("Expandable Background Color"),
            "#3182bd")
        more_bg.set_help(_("RGB-color for expandable row background."))
        menu.add_option(category_name, "more_bg", more_bg)

        no_more_bg = ColorOption(_("Non-Expandable Background Color"),
            "#fd8d3c")
        no_more_bg.set_help(_("RGB-color for non-expandable row " +
            "background."))
        menu.add_option(category_name, "no_more_bg", no_more_bg)

        dest_path = DestinationOption(_("Destination"),
            config.get('paths.website-directory'))
        dest_path.set_help(_("The destination path for generated files."))
        dest_path.set_directory_entry(True)
        menu.add_option(category_name, "dest_path", dest_path)

        dest_file = StringOption(_("Filename"), "DescendantIndentedTree.html")
        dest_file.set_help(_("The destination file name for html content."))
        menu.add_option(category_name, "dest_file", dest_file)
