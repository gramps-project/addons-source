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


#-------------------------------------------------------------------------
#
# Test sets
#
#-------------------------------------------------------------------------


default_options = {
    'name' : "DynamicWeb",
    'archive': True,
    'archive_file': "archive.zip",
    # "filter", self.__filter)
    # "pid", self.__pid)
    # 'name_format': 0,
    # 'short_name_format': 0,
    'template': 0,
    'copyright': 0,
    'incpriv': True,
    'inc_notes': True,
    'inc_sources': True,
    'inc_addresses': True,
    'living': INCLUDE_LIVING_VALUE,
    'yearsafterdeath': 30,
    'inc_repositories': True,
    'inc_gallery': True,
    'copy_media': True,
    'print_notes_type': True,
    'inc_places': True,
    'placemappages': True,
    'familymappages': True,
    'mapservice': "Google",
    'encoding': "UTF-8",
    'inc_families': True,
    'inc_events': True,
    'showbirth': True,
    'showdeath': True,
    'showmarriage': True,
    'showpartner': True,
    'showparents': True,
    'showallsiblings': True,
    # 'birthorder': False,
    'bkref_type': True,
    'inc_gendex': True,
    'graphgens': 10,
    'svg_tree_type': DEFAULT_SVG_TREE_TYPE,
    'svg_tree_shape': DEFAULT_SVG_TREE_SHAPE,
    'svg_tree_color1': "#EF2929",
    'svg_tree_color2': "#3D37E9",
    'svg_tree_color_dup': "#888A85",
    'headernote': "_header1",
    'footernote': "_footer1",
    'custom_note_0': "_custom1",
    'custom_menu_0': False,
    'pages_number': len(PAGES_NAMES) - NB_CUSTOM_PAGES + 1,
}
default_options.update({
    ('page_name_%i' % i): p[1]
    for (i, p) in enumerate(PAGES_NAMES)
})
default_options.update({
    ('page_content_%i' % i): i
    for i in range(len(PAGES_NAMES) - NB_CUSTOM_PAGES + 1)
})


report_list = [
{
    'title': "Example using template '%s'" % WEB_TEMPLATE_LIST[0][1],
    'link': "person.html?igid=I0044",
    'environ': {
        'LANGUAGE': "en_US",
        'LANG': "en_US.UTF-8",
    },
    'options': {
        'template': 0,
    },
    'procedures': [
        {
            'what': "General test",
            'path': "person.html?igid=I0044",
        },
        {
            'what': "Links, images, and search input in custom page",
            'path': "custom_1.html",
        },
        {
            'what': "All possible citations are referenced",
            'path': "source.html?sgid=S0001",
        },
        {
            'what': "GENDEX file",
            'path': "gendex.txt",
        },
        {
            'what': "Contents ZIP of archive",
            'path': "archive.zip",
        },
    ]
},
{
    'title':  "Example using template '%s'" % WEB_TEMPLATE_LIST[1][1],
    'link': "person.html?igid=I0044",
    'environ': {
        'LANGUAGE': "en_US",
        'LANG': "en_US.UTF-8",
    },
    'options': {
        'template': 1,
        'archive_file': "archive.tgz",
    },
    'procedures': [
        {
            'what': "General test (Mainz template)",
            'path': "person.html?igid=I0044",
        },
        {
            'what': "Contents of TGZ archive",
            'path': "archive.tgz",
        },
    ]
},
{
    'title':  "Example using template '%s', french translation and OpenStreetMap" % WEB_TEMPLATE_LIST[0][1],
    'link': "person.html?igid=I0044",
    'environ': {
        'LANGUAGE': "fr_FR",
        'LANG': "fr_FR.UTF-8",
    },
    'options': {
        'template': 0,
        'mapservice': "OpenStreetMap",
    },
    'procedures': [
        {
            'what': "French translation test",
            'path': "person.html?igid=I0044",
        },
        {
            'what': "OpenStreetMap test",
            'path': "place.html?pgid=P1678",
        },
        {
            'what': "OpenStreetMap test in families",
            'path': "family.html?fgid=F0017",
        },
    ]
},
{
    'title': "Example using template '%s', without media copy, without note types" % WEB_TEMPLATE_LIST[0][1],
    'link': "person.html?igid=I0044",
    'environ': {
        'LANGUAGE': "en_US",
        'LANG': "en_US.UTF-8",
    },
    'options': {
        'template': 0,
        'copy_media': False,
        'print_notes_type': False,
        'custom_menu_0': True,
    },
    'procedures': [
        {
            'what': "No media copy",
            'path': "media.html?mgid=O0010",
        },
        {
            'what': "Notes type are not printed",
            'path': "person.html?igid=I0044",
        },
        {
            'what': "Search works both in menu and in page",
            'path': "custom_1.html",
        },
    ]
},
{
    'title':  "Example with minimal features (without private data, notes, sources, addresses, gallery, places, families, events)",
    'link': "person.html?igid=I0044",
    'environ': {
        'LANGUAGE': "en_US",
        'LANG': "en_US.UTF-8",
    },
    'options': {
        'template': 0,
        'incpriv': False,
        'inc_notes': False,
        'inc_sources': False,
        'inc_addresses': False,
        'inc_repositories': False,
        'inc_gallery': False,
        'inc_places': False,
        'inc_families': False,
        'inc_events': False,
        'pages_number': 5,
        'page_content_0': PAGE_PERSON,
        'page_name_0': PAGES_NAMES[PAGE_PERSON][1],
        'page_content_1': PAGE_SURNAMES,
        'page_name_1': PAGES_NAMES[PAGE_SURNAMES][1],
        'page_content_2': PAGE_PERSON_INDEX,
        'page_name_2': PAGES_NAMES[PAGE_PERSON_INDEX][1],
        'page_content_3': PAGE_FAMILY_INDEX,
        'page_name_3': PAGES_NAMES[PAGE_FAMILY_INDEX][1],
        'page_content_4': PAGE_CUSTOM,
        'page_name_4': PAGES_NAMES[PAGE_CUSTOM][1],
    },
    'procedures': [
        {
            'what': "Test with minimal features (without private data, notes, sources, repositories, addresses, gallery, places, families, events)",
            'path': "person.html?igid=I0044",
        },
        {
            'what': "Test that addresses are not printed",
            'path': "person.html?igid=I0044",
        },
    ]
},
]

test_list = [
{
    'environ': {
        'LANGUAGE': "en_US",
        'LANG': "en_US.UTF-8",
    },
    'options': {
        'title': 'Basic test',
        "filter": 3, # Ancestors
        "pid": "I0044", # Lewis Anderson Zieliński
    },
},
]


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
        self.plugin_path = os.path.dirname(__file__)
        # Create results directory
        self.results_path = os.path.join(self.plugin_path, "reports")
        self.results_path = os.path.abspath(self.results_path)
        if (not os.path.isdir(self.results_path)): os.mkdir(self.results_path)
        # Get plugin version
        self.plugvers = self.plugin_version()

        # Check if plugin exists
        user_plugin_path = os.path.join(USER_PLUGINS, "DynamicWeb")
        self.assertTrue(os.path.exists(user_plugin_path), "%s does not exist" % user_plugin_path)

        # Check if dynamicweb_example database needs to be imported
        process = subprocess.Popen(
            [sys.executable, os.path.join(self.gramps_path, "Gramps.py"), "-l"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result_str, err_str = process.communicate("")
        result_str = result_str.decode()
        err_str = err_str.decode()
        self.assertFalse("Traceback (most recent call last):" in err_str, err_str)
        if (re.search(r'with name "dynamicweb_example"', result_str)):
            # dynamicweb_example already imported
            return
        # Change the mediapath in the example database
        ex_path_orig = os.path.join(self.gramps_path, "example", "gramps", "example.gramps")
        ex_path_orig = os.path.abspath(ex_path_orig)
        media_path = os.path.join(self.gramps_path, "example", "gramps")
        media_path = os.path.abspath(media_path)
        ex_path = os.path.join(self.plugin_path, "reports", "example.gramps")
        ex_path = os.path.abspath(ex_path)
        f_in = codecs.open(ex_path_orig, "r", encoding = "UTF-8")
        f_out = codecs.open(ex_path, "w", encoding = "UTF-8")
        for line in f_in:
            line = re.sub(
                r"<mediapath>.*</mediapath>",
                r"<mediapath>%s</mediapath>" % media_path,
                line)
            f_out.write(line)
        f_in.close()
        f_out.close()
        # Import example database
        os.chdir(self.gramps_path)
        process = subprocess.Popen(
            [sys.executable, os.path.join(self.gramps_path, "Gramps.py"), "-y", "-C", "dynamicweb_example", "-i", ex_path],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result_str, err_str = process.communicate("")
        result_str = result_str.decode()
        err_str = err_str.decode()
        # self.assertFalse("Traceback (most recent call last):" in err_str, err_str)
        # (commented out because PIL not installed in Travis environment)


    def do_export(self, report_num, report_set):
        report_name = "report_%03i" % report_num
        # Build the test title and path
        title = ",".join([
            (key + "=" + (str(report_set['options'][key]) if isinstance(report_set['options'][key], (int, bool)) else report_set['options'][key]))
            for key in sorted(report_set['options'].keys())
        ])
        title = re.sub("[^a-zA-Z_0-9]", ".", title)
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
        process = subprocess.Popen(
            [sys.executable, os.path.join(self.gramps_path, "Gramps.py"), "-q", "-O", "dynamicweb_example", "-a", "report", "-p", param],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result_str, err_str = process.communicate("")
        result_str = result_str.decode()
        err_str = err_str.decode()
        # self.assertFalse("Traceback (most recent call last):" in err_str, err_str)
        # (commented out because PIL not installed in Travis environment)
        self.assertFalse("Unknown report name." in err_str, err_str)

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
        process = subprocess.Popen(
            [sys.executable, os.path.join(self.gramps_path, "Gramps.py"), "-q", "-O", "dynamicweb_example", "-a", "report", "-p", param],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result_str, err_str = process.communicate("")
        result_str = result_str.decode()
        err_str = err_str.decode()
        # self.assertFalse("Traceback (most recent call last):" in err_str, err_str)
        # (commented out because PIL not installed in Travis environment)
        self.assertFalse("Unknown report name." in err_str, err_str)


    def plugin_version(self):
        # Get the plugin version
        filenames = glob.glob(os.path.join(self.plugin_path, "*gpr.py"))
        self.plugvers = "?"
        if (len(filenames) != 1): return()
        filename = filenames[0]
        fp = open(filename, "r")
        for line in fp:
            if ((line.lstrip().startswith("version")) and ("=" in line)):
                line, stuff = line.rsplit(",", 1)
                line = line.rstrip()
                pos = line.index("version")
                var, gtv = line[pos:].split('=', 1)
                self.plugvers = gtv.strip()[1:-1]
                break
        fp.close()


    #-------------------------------------------------------------------------
    # Export example reports
    #-------------------------------------------------------------------------
    # This test is slow (several minutes)
    # In order to exclude it, run nosetests with options: -a '!slow'
    @nose.plugins.attrib.attr('slow')
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
