#
# AncestralFanChart - a plugin for GRAMPS, the GTK+/GNOME based
#       genealogy program that creates an Ancestor Chart Map based on
#       the D3.js Fan Chart Layout scheme.
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

# The idea behind this plugin is to create an ancestral fan chart that can
# be interacted with via clicking on an individual to either collapse or expand
# ancestors for that individual. The chart is SVG and uses D3.js layout engine.

"""Reports/Web Pages/Ancestral Fan Chart"""

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
from gramps.gui.dialog import ErrorDialog

#------------------------------------------------------------------------
#
# AncestralFanChartReport
#
#------------------------------------------------------------------------
class AncestralFanChartReport(Report):
    """
    Ancestral Fan Chart Report class
    """
    def __init__(self, database, options, user):
        """
        Create the Ancestral Fan Chart object that produces the
        Ancestral Fan Chart report.

        The arguments are:

        database        - the GRAMPS database instance
        options         - instance of the Options class for this report
        user            - a gen.user.User() instance

        This report needs the following parameters (class variables)
        that come in the options class.

        gen         - Maximum number of generations to include.
        name_format - Preferred format to display names
        pat_bg      - Background color for paternal ancestors
        mat_bg      - Background color for maternal ancestors
        dest_path   - Destination Path
        dest_file   - Destination HTML filename
        """
        Report.__init__(self, database, options, user)

        self.map = {}

        menu = options.menu
        self.max_ancestor = 1
        self.max_gen = menu.get_option_by_name('maxgen').get_value()
        self.pat_bg = menu.get_option_by_name('pat_bg').get_value()
        self.mat_bg = menu.get_option_by_name('mat_bg').get_value()
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

    def get_parent_handles(self, person_handle):
        """
        Retrieve father and mother handles for a person, if they exist
        """
        person = self.database.get_person_from_handle(person_handle)

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

        return (father_handle, mother_handle)
    

    def calc_max_ancestor(self, person_handle, generation=1):
        """
        Recursable filter on ancestors to calculate the maximum ancestor
        level for a person
        """
        if not person_handle:
            return

        if generation > self.max_ancestor:
            self.max_ancestor = generation

        # Get parent handles if they exist
        father_handle, mother_handle = self.get_parent_handles(person_handle)

        if father_handle:
            self.calc_max_ancestor(father_handle, generation+1)

        if mother_handle:
            self.calc_max_ancestor(mother_handle, generation+1)

    def dummy_filter(self, gender, generation=1):
        """
        Generate empty entries for this person to ensure all ancestor
        levels are equal.
        """
        
        gen_pad = (generation-1) * 2
        self.json_fp.write('%s{\n' % (self.pad_str(gen_pad)))
        self.json_fp.write('%s"name": "",\n' %
            (self.pad_str(gen_pad+1)))
        self.json_fp.write('%s"gender": "%s",\n' %
            (self.pad_str(gen_pad+1), gender))
        self.json_fp.write('%s"born": "",\n' %
            (self.pad_str(gen_pad+1)))
        self.json_fp.write('%s"died": "",\n' %
            (self.pad_str(gen_pad+1)))
        self.json_fp.write('%s"generation": "%s",\n' %
            (self.pad_str(gen_pad+1), str(generation)))

        if generation == self.max_ancestor or generation == self.max_gen:
            self.json_fp.write('%s"colour": "%s",\n' %
                (self.pad_str(gen_pad+1),
                self.pat_bg if self.fam_side == "paternal" else self.mat_bg))

        self.json_fp.write('%s"gramps_id": ""' %
            (self.pad_str(gen_pad+1)))

        if generation == self.max_gen or generation == self.max_ancestor:
            # No more levels required so close this person out.
            self.json_fp.write('\n')
            self.json_fp.write('%s}' % (self.pad_str(gen_pad)))
        elif generation < self.max_ancestor:
            # Need to generate some empty ancestors to satisfy max_ancestor
            self.json_fp.write(',\n')
            self.json_fp.write('%s"children": [\n' %
                (self.pad_str(gen_pad+1)))
            self.dummy_filter("male", generation+1)
            self.json_fp.write(',\n')
            self.dummy_filter("female", generation+1)
            self.json_fp.write('\n')
            self.json_fp.write('%s]\n' % (self.pad_str(gen_pad+1)))
            self.json_fp.write('%s}' % (self.pad_str(gen_pad)))

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

        self.json_fp.write('%s"generation": "%s",\n' %
            (self.pad_str(gen_pad+1), str(generation)))

        if generation == self.max_ancestor or generation == self.max_gen:
            self.json_fp.write('%s"colour": "%s",\n' %
                (self.pad_str(gen_pad+1),
                self.pat_bg if self.fam_side == "paternal" else self.mat_bg))

        self.json_fp.write('%s"gramps_id": "%s"' %
            (self.pad_str(gen_pad+1), str(person.get_gramps_id())))

        # Get parent handles if they exist
        father_handle, mother_handle = self.get_parent_handles(person_handle)

        # Recursively call the function. It is okay if the handle is None,
        # since routine handles a handle of None
        if (not father_handle and not mother_handle):
            if generation == self.max_gen or generation == self.max_ancestor:
                # No more levels required so close this person out.
                self.json_fp.write('\n')
                self.json_fp.write('%s}' % (self.pad_str(gen_pad)))
            elif generation < self.max_ancestor:
                # Need to generate some empty ancestors to satisfy max_ancestor
                self.json_fp.write(',\n')
                self.json_fp.write('%s"children": [\n' %
                    (self.pad_str(gen_pad+1)))
                if generation == 1:
                    self.fam_side = "paternal"
                self.dummy_filter("male", generation+1)
                self.json_fp.write(',\n')
                if generation == 1:
                    self.fam_side = "maternal"
                self.dummy_filter("female", generation+1)
                self.json_fp.write('\n')
                self.json_fp.write('%s]\n' % (self.pad_str(gen_pad+1)))
                self.json_fp.write('%s}' % (self.pad_str(gen_pad)))
        elif generation < self.max_gen and generation < self.max_ancestor:
            self.json_fp.write(',\n')
            self.json_fp.write('%s"children": [\n' %
                (self.pad_str(gen_pad+1)))
            
            if generation == 1:
                self.fam_side = "paternal"
            if father_handle:
                self.json_filter(father_handle, generation+1)
            else:
                self.dummy_filter("male", generation+1)

            self.json_fp.write(',\n')

            if generation == 1:
                self.fam_side = "maternal"
            if mother_handle:
                self.json_filter(mother_handle, generation+1)
            else:
                self.dummy_filter("female", generation+1)
            self.json_fp.write('\n')

            self.json_fp.write('%s]\n' % (self.pad_str(gen_pad+1)))
            self.json_fp.write('%s}' % (self.pad_str(gen_pad)))
        else:
            # No more levels required so close this person out.
            self.json_fp.write('\n')
            self.json_fp.write('%s}' % (self.pad_str(gen_pad)))

    def write_report(self):
        """
        The routine the actually creates the report. At this point, the document
        is opened and ready for writing.
        """
        name = self._name_display.display(self.center_person)
        title = "Ancestral Fan Chart for " + name
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
                    'href="css/fanchart.css"/>\n' + \
                    '  </head>\n' + \
                    '  <body>\n' + \
                    '    <div id="body">\n' + \
                    '      <div id="start">\n' + \
                    '       <h1>' + title + '</h1>\n' + \
                    '       <h3>Click to zoom!</h3>\n' + \
                    '      </div>\n' + \
                    '      <div id="chart">\n' + \
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
            shutil.copy(os.path.join(plugin_dir, "css", "fanchart.css"),
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

        # Generate <dest>.js based on colors and initial generations to
        # display
        try:
            with io.open(self.destjs, 'w', encoding='utf8') as fp:
                fp.write('var width = 1024;\n\n')
                fp.write('if (width > $(window).width()-25) {\n')
                fp.write(' width = $(window).width()-25;\n')
                fp.write('}\n\n')
                fp.write('var height = width,\n')
                fp.write(' radius = width / 2,\n')
                fp.write(' x = d3.scale.linear().range([0, 2 * ' +
                    'Math.PI]),\n')
                fp.write(' y = d3.scale.pow().exponent(1.3).' +
                    'domain([0, 1]).range([0, radius]),\n')
                fp.write(' padding = 5,\n')
                fp.write(' duration = 1000;\n\n')
                fp.write('var div = d3.select("#chart");\n\n')
                fp.write('var vis = div.append("svg")\n')
                fp.write(' .attr("width", width + padding * 2)\n')
                fp.write(' .attr("height", height + padding * 2)\n')
                fp.write(' .append("g")\n')
                fp.write(' .attr("transform", "translate(" +\n')
                fp.write('  [radius + padding, radius + padding] + ' +
                    '")");\n\n')
                fp.write('var partition = d3.layout.partition()\n')
                fp.write(' .sort(null)\n')
                fp.write(' .value(function(d) { return 5.8 - ' +
                    'd.depth; });\n\n')
                fp.write('var arc = d3.svg.arc()\n')
                fp.write(' .startAngle(function(d) {\n')
                fp.write('   return Math.max(0, Math.min(2 * ' +
                    'Math.PI, x(d.x)));\n')
                fp.write('  })\n')
                fp.write(' .endAngle(function(d) {\n')
                fp.write('   return Math.max(0, Math.min(2 * ' +
                    'Math.PI, x(d.x + d.dx)));\n')
                fp.write('  })\n')
                fp.write(' .innerRadius(function(d) { ' +
                    'return Math.max(0, d.y ? y(d.y) : d.y); })\n')
                fp.write(' .outerRadius(function(d) { ' +
                    'return Math.max(0, y(d.y + d.dy)); });\n\n')
                out_str = 'd3.json("json/%s.json", ' % (self.destprefix)
                fp.write(out_str + 'function(error, json) {\n')
                fp.write(' var nodes = partition.nodes({children: ' +
                    'json});\n')
                fp.write(' var path = vis.selectAll("path").' +
                    'data(nodes);\n')
                fp.write(' path.enter().append("path")\n')
                fp.write('  .attr("id", function(d, i) { ' +
                    'return "path-" + i; })\n')
                fp.write('  .attr("d", arc)\n')
                fp.write('  .attr("fill-rule", "evenodd")\n')
                fp.write('  .style("fill", colour)\n')
                fp.write('  .on("click", click);\n\n')
                fp.write(' var text = vis.selectAll("text").' +
                    'data(nodes);\n')
                fp.write(' var textEnter = text.enter().' +
                    'append("text")\n')
                fp.write('  .style("fill-opacity", 1)\n')
                fp.write('  .style("fill", function(d) {\n')
                fp.write('    return brightness(d3.rgb(colour(d))) ' +
                    '< 125 ? "#eee" : "#000";\n')
                fp.write('   })\n')
                fp.write('  .attr("text-anchor", function(d) {\n')
                fp.write('    return x(d.x + d.dx / 2) > Math.PI ? ' +
                    '"end" : "start";\n')
                fp.write('   })\n')
                fp.write('  .attr("dy", ".2em")\n')
                fp.write('  .attr("transform", function(d) {\n')
                fp.write('    var multiline = (d.name || "").' +
                    'split(" ").length > 1,\n')
                fp.write('     multangle = d.depth == 1 ? 90 : ' +
                    '180,\n')
                fp.write('     angle = x(d.x + d.dx / 2) * ' +
                    'multangle / Math.PI - 90,\n')
                fp.write('     rotate = angle + (multiline ? -.5 ' +
                    ': 0);\n')
                fp.write('    return "rotate(" + rotate + ")' +
                    'translate(" +\n')
                fp.write('     (y(d.y) + padding) + ")rotate(" +\n')
                fp.write('     (angle > 90 ? -180 : 0) + ")";\n')
                fp.write('   })\n')
                fp.write('  .on("click", click);\n\n')
                fp.write(' textEnter.append("tspan")\n')
                fp.write('  .attr("x", 0)\n')
                fp.write('  .text(function(d) { return d.depth ? ' +
                    'd.name.split(" ")[0] : ""; });\n\n')
                fp.write(' textEnter.append("tspan")\n')
                fp.write('  .attr("x", 0)\n')
                fp.write('  .attr("dy", "1em")\n')
                fp.write('  .text(function(d) {\n')
                fp.write('    return d.depth ? d.name.split(" ")[1] ' +
                    '|| "" : "";\n')
                fp.write('   });\n\n')
                fp.write(' textEnter.append("tspan")\n')
                fp.write('  .attr("x", 0)\n')
                fp.write('  .attr("dy", "1em")\n')
                fp.write('  .text(function(d) {\n')
                fp.write('    return d.depth ? d.name.split(" ")[2] ' +
                    '|| "" : "";\n')
                fp.write('   });\n\n')
                fp.write(' function click(d) {\n')
                fp.write('  path.transition().duration(duration).' +
                    'attrTween("d", arcTween(d));\n\n')
                fp.write('  var click_name = d.name;\n')
                fp.write('  var click_depth = d.depth;\n\n')
                fp.write('  // Somewhat of a hack as we rely on ' +
                    'arcTween updating the scales.\n')
                fp.write('  text.style("visibility", function(e) {\n')
                fp.write('     return isParentOf(d, e) ?\n')
                fp.write('      null : d3.select(this).' +
                    'style("visibility");\n')
                fp.write('    })\n')
                fp.write('   .transition()\n')
                fp.write('   .duration(duration)\n')
                fp.write('   .attrTween("text-anchor", function(d) ' +
                    '{\n')
                fp.write('     return function() {\n')
                fp.write('      return x(d.x + d.dx / 2) > Math.PI ' +
                    '? "end" : "start";\n')
                fp.write('     };\n')
                fp.write('    })\n')
                fp.write('   .attrTween("transform", function(d) {\n')
                fp.write('     var multiline = (d.name || "").' +
                    'split(" ").length > 1;\n')
                fp.write('     return function() {\n')
                fp.write('      var multangle = click_name == ' +
                    'd.name &&\n')
                fp.write('       click_depth == d.depth ? 90 : ' +
                    '180;\n')
                fp.write('      var angle = x(d.x + d.dx / 2) * ' +
                    'multangle / Math.PI - 90;\n')
                fp.write('      var rotate = angle + (multiline ? ' +
                    '-.5 : 0);\n')
                fp.write('      return "rotate(" + rotate + ")' +
                    'translate(" + (y(d.y) +\n')
                fp.write('       padding) + ")rotate(" +\n')
                fp.write('       (angle > 90 ? -180 : 0) + ")";\n')
                fp.write('     };\n')
                fp.write('    })\n')
                fp.write('   .style("fill-opacity", function(e) {\n')
                fp.write('     return isParentOf(d, e) ? 1 : 1e-6;\n')
                fp.write('    })\n')
                fp.write('   .each("end", function(e) {\n')
                fp.write('     d3.select(this).style("visibility",\n')
                fp.write('      isParentOf(d, e) ? null : "hidden");' +
                    '\n')
                fp.write('    });\n')
                fp.write(' }\n')
                fp.write('});\n\n')
                fp.write('function isParentOf(p, c) {\n')
                fp.write(' if (p === c) return true;\n')
                fp.write(' if (p.children) {\n')
                fp.write('  return p.children.some(function(d) {\n')
                fp.write('   return isParentOf(d, c);\n')
                fp.write('  });\n')
                fp.write(' }\n')
                fp.write(' return false;\n')
                fp.write('}\n\n')
                fp.write('function colour(d) {\n')
                fp.write(' if (d.children) {\n')
                fp.write('  // There is a maximum of two children!\n')
                fp.write('  var colours = d.children.map(colour),\n')
                fp.write('   a = d3.hsl(colours[0]),\n')
                fp.write('   b = d3.hsl(colours[1]);\n')
                fp.write('  // L*a*b* might be better here...\n')
                fp.write('  return d3.hsl((a.h + b.h) / 2, a.s * ' +
                    '1.2, a.l / 1.2);\n')
                fp.write(' }\n')
                fp.write(' return d.colour || "#fff";\n')
                fp.write('}\n\n')
                fp.write('// Interpolate the scales!\n')
                fp.write('function arcTween(d) {\n')
                fp.write(' var my = maxY(d),\n')
                fp.write('  xd = d3.interpolate(x.domain(), ' +
                    '[d.x, d.x + d.dx]),\n')
                fp.write('  yd = d3.interpolate(y.domain(), ' +
                    '[d.y, my]),\n')
                fp.write('  yr = d3.interpolate(y.range(), ' +
                    '[d.y ? 20 : 0, radius]);\n')
                fp.write(' return function(d) {\n')
                fp.write('  return function(t) {\n')
                fp.write('   x.domain(xd(t)); y.domain(yd(t)).' +
                    'range(yr(t)); return arc(d);\n')
                fp.write('  };\n')
                fp.write(' };\n')
                fp.write('}\n\n')
                fp.write('function maxY(d) {\n')
                fp.write(' return d.children ? Math.max.apply(Math, ' +
                    'd.children.map(maxY)) : d.y + d.dy;\n')
                fp.write('}\n\n')
                fp.write('// http://www.w3.org/WAI/ER/WD-AERT/' +
                    '#color-contrast\n')
                fp.write('function brightness(rgb) {\n')
                fp.write(' return rgb.r * .299 + rgb.g * .587 + ' +
                    'rgb.b * .114;\n')
                fp.write('}\n\n')
                fp.write('if (top != self) top.location.' +
                    'replace(location);\n')

        except IOError as msg:
            ErrorDialog(_("Failed writing %s: %s") % (self.destjs, str(msg)))
            return

        if self.get_gender_str(self.center_person) == "male":
            self.fam_side = "paternal"
        else:
            self.fam_side = "maternal"

        # Genearte json data file to be used
        try:
            with io.open(self.destjson, 'w', encoding='utf8') as self.json_fp:
                generation = 0

                # Calculate the maximum ancestor level, as all ancestor
                # lines need to be fleshed out to the maximum for an even
                # fan chart
                self.calc_max_ancestor(self.center_person.get_handle(), 1)

                # Generate json file of ancestors
                self.json_fp.write('[\n')
                self.json_filter(self.center_person.get_handle(), 1)
                self.json_fp.write(']')


        except IOError as msg:
            ErrorDialog(_("Failed writing %s: %s") % (self.destjson, str(msg)))
            return

#------------------------------------------------------------------------
#
# AncestralFanChartOptions
#
#------------------------------------------------------------------------
class AncestralFanChartOptions(MenuReportOptions):

    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, dbase):
        self._dbase = dbase
        self._maxgen = None
        MenuReportOptions.__init__(self, name, dbase)

    def validate_gen(self):
        """
        Validate Max generation > 0
        """
        if self._maxgen is not None:
            maxgen = self._maxgen.get_value()
            if maxgen < 1:
                self._maxgen.set_value(1)

    def add_menu_options(self, menu):
        """
        Add options to the menu for the ancestral fan chart report.
        """
        category_name = _("Ancestral Fan Chart Options")

        pid = PersonOption(_("Center Person"))
        pid.set_help(_("The center person for the report"))
        menu.add_option(category_name, "pid", pid)

        # We must figure out the value of the first option before we can
        # create the EnumeratedListOption
        fmt_list = global_name_display.get_name_format()
        name_format = EnumeratedListOption(_("Name format"), 0)
        name_format.add_item(0, _("Default"))
        for num, name, fmt_str, act in fmt_list:
            name_format.add_item(num, name)
        name_format.set_help(_("Select the format to display names"))
        menu.add_option(category_name, "name_format", name_format)

        self._maxgen = NumberOption(_("Include Generations"), 10, 1, 100)
        self._maxgen.set_help(_("The number of generations to include in " +
            "the report"))
        menu.add_option(category_name, "maxgen", self._maxgen)
        self._maxgen.connect('value-changed', self.validate_gen)

        pat_bg = ColorOption(_("Paternal Background Color"), "#ccddff")
        pat_bg.set_help(_("RGB-color for paternal box background."))
        menu.add_option(category_name, "pat_bg", pat_bg)

        mat_bg = ColorOption(_("Maternal Background"), "#ffb2a1")
        mat_bg.set_help(_("RGB-color for maternal box background."))
        menu.add_option(category_name, "mat_bg", mat_bg)

        dest_path = DestinationOption(_("Destination"),
            config.get('paths.website-directory'))
        dest_path.set_help(_("The destination path for generated files."))
        dest_path.set_directory_entry(True)
        menu.add_option(category_name, "dest_path", dest_path)

        dest_file = StringOption(_("Filename"), "AncestralFanchart.html")
        dest_file.set_help(_("The destination file name for html content."))
        menu.add_option(category_name, "dest_file", dest_file)
