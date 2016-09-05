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
Dynamic Web Report test sets

Used for: testing and generating report examples
"""


import glob, os.path

# Do not use relative imports
# (this file is included in several environments)
from dynamicweb import *
from dynamicweb import _
from gramps.gen.proxy import LivingProxyDb


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
    'incl_private': True,
    'inc_notes': True,
    'inc_sources': True,
    'inc_addresses': True,
    'living_people': INCLUDE_LIVING_VALUE,
    'years_past_death': 30,
    'inc_repositories': True,
    'inc_gallery': True,
    'copy_media': True,
    'print_notes_type': True,
    'inc_places': True,
    'placemappages': True,
    'familymappages': True,
    'mapservice': "Google",
    'googlemapkey': "",
    'tabbed_panels': False,
    'encoding': "UTF-8",
    'inc_families': True,
    # 'inc_events': True,
    'index_surnames_type': "0",
    'index_persons_type': "1",
    'index_families_type': "1",
    'index_sources_type': "1",
    'index_places_type': "1",
    'showdates': True,
    'showpartner': True,
    'showparents': True,
    'showallsiblings': True,
    # 'birthorder': False,
    'bkref_type': True,
    'entries_shown': "1",
    'inc_gendex': True,
    'inc_pageconf': True,
    'inc_change_time': True,
    'hide_gid': False,
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
    'pages_number': len(PAGES_NAMES) + 1,
}


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
        'tabbed_panels': True,
        'hide_gid': False,
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
    'title':  "Example using template '%s' French translation and OpenStreetMap" % WEB_TEMPLATE_LIST[0][1],
    'link': "person.html?igid=I0044",
    'environ': {
        'LANGUAGE': "fr_FR",
        'LANG': "fr_FR.UTF-8",
    },
    'options': {
        'template': 0,
        'mapservice': "OpenStreetMap",
        'tabbed_panels': True,
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
    'title': "Example using template '%s' without media copy without note types" % WEB_TEMPLATE_LIST[0][1],
    'link': "person.html?igid=I0044",
    'environ': {
        'LANGUAGE': "en_US",
        'LANG': "en_US.UTF-8",
    },
    'options': {
        'template': 0,
        'copy_media': False,
        'print_notes_type': False,
        'sourceauthor': True,
        'custom_menu_0': True,
        'inc_families': False,
        'living': LivingProxyDb.MODE_EXCLUDE_ALL,
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
    'title': "Example with minimal features (without private data notes sources addresses gallery places families events)",
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
        # 'inc_events': False,
        'living': LivingProxyDb.MODE_EXCLUDE_ALL,
        'inc_pageconf': False,
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
    'title': 'Basic test',
    'environ': {
        'LANGUAGE': "en_US",
        'LANG': "en_US.UTF-8",
    },
    'options': {
        "filter": 3, # Ancestors
        "pid": "I0044", # Lewis Anderson Zieliński
    },
},
]


html_index_0 = """
    <!DOCTYPE html>
    <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
    <head lang="en">
    <title>Gramps dynamic web pages report test index</title>
    <meta charset="UTF-8" />
    </head>
    <body>
    <p>List of the web pages examples generated by the Gramps dynamic web pages report:</p>
    <ul>
"""
html_procedures_0 = """
    <!DOCTYPE html>
    <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
    <head lang="en">
    <title>Gramps dynamic web pages report test procedures</title>
    <meta charset="UTF-8" />
    </head>
    <body>
    <p><a href='index.html'>List of the web pages examples generated by the Gramps dynamic web pages report</a></p>
    <p>List of the test procedures for the Gramps dynamic web pages report:</p>
    <ul>
"""
html_index_1 = """
    </ul>
    <p><a href='procedures.html'>Gramps dynamic web pages report tests index</a></p>
    <p><small>Generated by the report %s version %s for Gramps version %s</small></p>
    </body>
    </html>
"""
html_procedures_1 = """
    </ul>
    <p><small>Generated by the report %s version %s for Gramps version %s</small></p>
    </body>
    </html>
"""


##############################################################
# Plugin version

def plugin_version(plugin_path):
	filenames = glob.glob(os.path.join(plugin_path, "*gpr.py"))
	plugvers = "?"
	if (len(filenames) != 1): return(plugvers)
	filename = filenames[0]
	fp = open(filename, "r")
	for line in fp:
		if ((line.lstrip().startswith("version")) and ("=" in line)):
			line, stuff = line.rsplit(",", 1)
			line = line.rstrip()
			pos = line.index("version")
			var, gtv = line[pos:].split('=', 1)
			plugvers = gtv.strip()[1:-1]
			break
	fp.close()
	return(plugvers)

