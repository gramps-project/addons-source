# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2014 Pierre Bélissent
#
# This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with this program; if not, write to the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# $Id: $

"""
Dynamic Web Report testing script

This script tests the dynamic web report,
With the database /example/gramps/example.gramps,
And with various options.

The tests import the file "example/gramps/example.gramps" into the dynamicweb_example database.
The dynamicweb_example database is created if necessary, but *not* overwritten if it exists.
"""

from __future__ import print_function
import copy, re, os, os.path, subprocess, sys, traceback, locale, shutil, time, glob, json
import unittest, nose.plugins.attrib


from gramps.gen.const import ROOT_DIR, USER_PLUGINS, USER_HOME
from .dynamicweb import *
from .dynamicweb import _


# Check if plugin exists
user_plugin_path = os.path.join(USER_PLUGINS, "DynamicWeb")
assert os.path.exists(user_plugin_path), "%s does not exist" % user_plugin_path
sys.path.append(user_plugin_path)

from .report_sets import *


#-------------------------------------------------------------------------
#
# DynamicWebTests class
#
#-------------------------------------------------------------------------

class DynamicWebTests(unittest.TestCase):

    def setUp(self):

        # Get paths
        self.gramps_path = os.path.join(ROOT_DIR, "..")
        self.assertTrue(os.path.exists(self.gramps_path), "%s does not exist" % self.gramps_path)
        # Create results directory
        self.results_path = os.path.join(user_plugin_path, "reports")
        self.results_path = os.path.abspath(self.results_path)
        if (not os.path.isdir(self.results_path)): os.mkdir(self.results_path)
        # Get plugin version
        self.plugvers = plugin_version(user_plugin_path)

        # Check if dynamicweb_example database needs to be imported
        (result_str, err_str) = self.call([sys.executable, os.path.join(self.gramps_path, "Gramps.py"), "-l"])
        if (re.search(r'with name "dynamicweb_example"', result_str)):
            # dynamicweb_example already imported
            return
        # Import example database
        ex_path = os.path.join(self.gramps_path, "example", "gramps", "example.gramps")
        (result_str, err_str) = self.call(
            [sys.executable, os.path.join(self.gramps_path, "Gramps.py"), "-y", "-C", "dynamicweb_example", "-i", ex_path])


    def call(self, cmd):
        print(" ".join(cmd))
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result_str, err_str = process.communicate("")
        result_str = result_str.decode()
        err_str = err_str.decode()
        print(result_str)
        print(sys.stderr, err_str)
        # self.assertFalse("Traceback (most recent call last):" in err_str)
        # (commented out because PIL not installed in Travis environment)
        return(result_str, err_str)


    def do_export(self, report_num, report_set):
        report_name = "report_%03i" % report_num
        # Build the test title and path
        title = report_set['title']
        target = os.path.join(self.results_path, report_name)

        # Clean-up reports and tests files
        if (os.path.exists(target)): shutil.rmtree(target)

        # Build the report options form the default options + the test set options
        o = copy.deepcopy(default_options)
        o.update(report_set['options'])
        o.update({
            'title': title,
            'target': target,
            'archive_file': os.path.join(target, os.path.basename(o['archive_file'])),
        })
        param = ",".join([
            (key + "=" + (str(value) if isinstance(value, (int, bool)) else value))
            for (key, value) in o.items()
        ])

        # Setup environment variables
        os.environ.update(report_set['environ'])

        # Call GRAMPS CLI
        if (sys.version_info[0] < 3):
            param = param.encode()
        os.chdir(self.gramps_path)
        (result_str, err_str) = self.call(
            [sys.executable, os.path.join(self.gramps_path, "Gramps.py"), "-q", "-O", "dynamicweb_example", "-a", "report", "-p", param])
        self.assertFalse("Unknown report name." in err_str)

        # Update index pages
        if (report_set['link']):
            p = report_name + "/" + report_set['link']
            self.html_index += "<li><a href='%s'>%s</a></li>" % (p, report_set['title'])
        for procedure in report_set['procedures']:
            p = report_name + "/" + procedure['path']
            self.html_procedures += "<li>%s<br><a href='%s'>%s</a></li>" % (procedure['what'], p, p)


    def do_case(self, test_num, test_set):
        test_name = "test_%03i" % test_num
        target = os.path.join(self.results_path, test_name)

        # Clean-up reports and tests files
        if (os.path.exists(target)): shutil.rmtree(target)

        # Build the report options form the default options + the test set options
        o = copy.deepcopy(default_options)
        o.update(test_set['options'])
        o.update({
            'target': target,
            'archive_file': os.path.join(target, os.path.basename(o['archive_file'])),
        })
        param = ",".join([
            (key + "=" + (str(value) if isinstance(value, (int, bool)) else value))
            for (key, value) in o.items()
        ])

        # Setup environment variables
        os.environ.update(test_set['environ'])

        # Call GRAMPS CLI
        if (sys.version_info[0] < 3):
            param = param.encode()
        os.chdir(self.gramps_path)
        (result_str, err_str) = self.call(
            [sys.executable, os.path.join(self.gramps_path, "Gramps.py"), "-q", "-O", "dynamicweb_example", "-a", "report", "-p", param])
        self.assertFalse("Unknown report name." in err_str)



    #-------------------------------------------------------------------------
    # Export example reports
    #-------------------------------------------------------------------------
    # This test is slow (several minutes)
    # In order to exclude it, run nosetests with options: -a '!slow'
    @nose.plugins.attrib.attr('slow')
    @nose.plugins.attrib.attr('report')
    def test_export(self):
        index = os.path.join(self.results_path, "index.html")
        procedures = os.path.join(self.results_path, "procedures.html")
        # Clean-up reports and tests files
        if (os.path.exists(index)): os.remove(index)
        if (os.path.exists(procedures)): os.remove(procedures)

        # Initialize index pages
        self.html_index = """
            <!DOCTYPE html>
            <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
            <head lang="en">
            <title>GRAMPS dynamic web pages report test index</title>
            <meta charset="UTF-8" />
            </head>
            <body>
            <p>List of the web pages examples generated by the GRAMPS dynamic web pages report:</p>
            <ul>
        """
        self.html_procedures = """
            <!DOCTYPE html>
            <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
            <head lang="en">
            <title>GRAMPS dynamic web pages report test procedures</title>
            <meta charset="UTF-8" />
            </head>
            <body>
            <p><a href='index.html'>List of the web pages examples generated by the GRAMPS dynamic web pages report</a></p>
            <p>List of the test procedures for the GRAMPS dynamic web pages report:</p>
            <ul>
        """

        for (report_num, report_set) in enumerate(report_list):
            self.do_export(report_num, report_set)

        # Generate index pages
        self.html_index += """
            </ul>
            <p><a href='procedures.html'>GRAMPS dynamic web pages report tests index</a></p>
            <p><small>Generated by the report %s version %s for GRAMPS version %s</small></p>
            </body>
            </html>
        """ % (default_options['name'], self.plugvers, VERSION)
        f = codecs.open(index, "w", encoding = "UTF-8", errors="xmlcharrefreplace")
        f.write(self.html_index)
        f.close()
        self.html_procedures += """
            </ul>
            <p><small>Generated by the report %s version %s for GRAMPS version %s</small></p>
            </body>
            </html>
        """ % (default_options['name'], self.plugvers, VERSION)
        f = codecs.open(procedures, "w", encoding = "UTF-8", errors="xmlcharrefreplace")
        f.write(self.html_procedures)
        f.close()


    #-------------------------------------------------------------------------
    # Basic tests
    #-------------------------------------------------------------------------
    def test_basic(self):
        self.do_case(0, test_list[0])

        # Check list of exported files
        filenames = os.listdir(os.path.join(self.results_path, "test_000"))
        for filename in [
            "data",
            "image",
            "thumb",
            "archive.zip",
            "dwr_conf.js",
            "gendex.txt",
            "address.html",
            "custom_1.html",
            "families.html",
            "family.html",
            "media.html",
            "medias.html",
            "person.html",
            "persons.html",
            "place.html",
            "places.html",
            "repositories.html",
            "repository.html",
            "search.html",
            "source.html",
            "sources.html",
            "surname.html",
            "surnames2.html",
            "surnames.html",
            "tree_svg_conf.html",
            "tree_svg_full.html",
            "tree_svg.html",
            "tree_svg_save.html",
        ]:
            self.assertIn(filename, filenames, "%s was not generated" % filename)

        # Check size of exported JSON files
        for (filename, prefix, expected_size) in [
            ("dwr_db_indi.js", r"I *= *", 7),
            ("dwr_db_fam.js", r"F *= *", 5),
            ("dwr_db_sour.js", r"S *= *", 4),
            ("dwr_db_media.js", r"M *= *", 4),
            ("dwr_db_repo.js", r"R *= *", 3),
            ("dwr_db_place.js", r"P *= *", 16),
        ]:
            path = os.path.join(self.results_path, "test_000", filename)
            jf = codecs.open(path, "r", encoding = "UTF-8")
            s = jf.read()
            s = re.sub(r"^\s*//.*$", "", s, flags = re.MULTILINE) # remove JS comments
            s = re.sub(prefix, "", s)
            jdata = json.loads(s)
            self.assertEqual(len(jdata), expected_size,
                "%s JSON data does not have the expected size (%i instead of %i)" % (path, len(jdata), expected_size))

        # Checks to be added:
        # Re-export and check that unchanged files are not overwritten
        # etc.


##############################################################

if __name__ == '__main__':
    unittest.main()
