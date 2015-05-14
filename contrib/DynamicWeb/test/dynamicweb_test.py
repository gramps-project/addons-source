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

The script is to be launched from its directory

Arguments = [-i] [test numbers]

Usage examples:
- Import example database
	python dynamicweb_test.py -i
- Run tests 0 and 2
	python dynamicweb_test.py 0 2
- Run all tests
	python dynamicweb_test.py
"""

from __future__ import print_function
import copy, re, os, os.path, subprocess, sys, traceback, locale, shutil, time, glob

# os.environ["LANGUAGE"] = "en_US"
# os.environ["LANG"] = "en_US.UTF-8"

user_path = os.environ["GRAMPSHOME"]
if (not os.path.exists(user_path)): raise Exception("User path GRAMPSHOME not found")
plugin_path = ".."
sys.path.append(plugin_path)

gramps_path = os.environ["GRAMPS_RESOURCES"]
if (not os.path.exists(gramps_path)): raise Exception("Gramps path GRAMPS_RESOURCES not found")
sys.path.append(gramps_path)

from dynamicweb import *
from dynamicweb import _


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


test_list = [
{
	'title': "Example using template '%s'" % WEB_TEMPLATE_LIST[0][1],
	'level': 0,
	'link': "person.html?stxt=Garner%20von",
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
			'path': "person.html?stxt=Garner%20von",
		},
		{
			'what': "Links, images, and search input in custom page",
			'path': "custom_1.html",
		},
		{
			'what': "All possible citations are referenced",
			'path': "source.html?sdx=1",
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
	'level': 1,
	'link': "person.html?stxt=Garner%20von",
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
			'path': "person.html?stxt=Garner%20von",
		},
		{
			'what': "Contents of TGZ archive",
			'path': "archive.tgz",
		},
	]
},
{
	'title':  "Example using template '%s', french translation and OpenStreetMap" % WEB_TEMPLATE_LIST[0][1],
	'level': 1,
	'link': "person.html?stxt=Garner%20von",
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
			'path': "person.html?stxt=Garner%20von",
		},
		{
			'what': "OpenStreetMap test",
			'path': "places.html",
		},
		{
			'what': "OpenStreetMap test in families",
			'path': "families.html",
		},
	]
},
{
	'title': "Example using template '%s', without media copy, without note types" % WEB_TEMPLATE_LIST[0][1],
	'level': 2,
	'link': "person.html?stxt=Garner%20von",
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
			'what': "Media copy",
			'path': "medias.html",
		},
		{
			'what': "Notes type are not printed",
			'path': "person.html?stxt=Garner%20von",
		},
		{
			'what': "Search works both in menu and in page",
			'path': "custom_1.html",
		},
	]
},
{
	'title':  "Example with minimal features (without private data, notes, sources, addresses, gallery, places, families, events)",
	'level': 1,
	'link': "person.html?stxt=Garner%20von",
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
			'path': "person.html?stxt=Garner%20von",
		},
		{
			'what': "Test that addresses are not printed",
			'path': "person.html?stxt=Garner%20von",
		},
	]
},
]


def import_data():
	path = os.path.join(gramps_path, "example", "gramps", "example.gramps")
	path = os.path.abspath(path)
	print("=" * 80)
	print("Importing data \"%s\" in database \"dynamicweb_example\"" % path)
	print("=" * 80)
	os.chdir(gramps_path)
	subprocess.call([sys.executable, os.path.join(gramps_path, "Gramps.py"), "-y", "-C", "dynamicweb_example", "-i", path])


def main(test_nums):
	# Create results directory
	results_path = os.path.join(plugin_path, "test_results")
	results_path = os.path.abspath(results_path)
	if (not os.path.isdir(results_path)): os.mkdir(results_path)
	plugvers = plugin_version()

	# Initialize index pages
	html_index = """
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
	html_procedures = """
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
	
	for (test_num, test_set) in enumerate(test_list):
		if (test_num not in test_nums): continue
		test_name = "test_%03i" % test_num
		# Build the test title and path
		title = ",".join([
			(key + "=" + (str(test_set['options'][key]) if isinstance(test_set['options'][key], (int, bool)) else test_set['options'][key]))
			for key in sorted(test_set['options'].keys())
		])
		title = re.sub("[^a-zA-Z_0-9]", ".", title)
		print("=" * 80)
		print("%s:" % test_name)
		print("Exporting with options: %s" % title)
		print("=" * 80)
		target = os.path.join(results_path, test_name)
		
		# Build the report options form the default options + the test set options
		o = copy.deepcopy(default_options)
		o.update(test_set['options'])
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
		os.environ.update(test_set['environ'])
		
		# Call GRAMPS CLI
		if (sys.version_info[0] < 3):
			param = param.encode("UTF-8")
		os.chdir(gramps_path)
		# subprocess.call([sys.executable, os.path.join(gramps_path, "Gramps.py"), "-d", ".DynamicWeb", "-q", "-O", "dynamicweb_example", "-a", "report", "-p", param])
		subprocess.call([sys.executable, os.path.join(gramps_path, "Gramps.py"), "-q", "-O", "dynamicweb_example", "-a", "report", "-p", param])
		
		# Update index pages
		if (test_set['link']):
			p = test_name + "/" + test_set['link']
			html_index += "<li><a href='%s'>%s</a></li>" % (p, test_set['title'])
		for procedure in test_set['procedures']:
			p = test_name + "/" + procedure['path']
			html_procedures += "<li>%s<br><a href='%s'>%s</a></li>" % (procedure['what'], p, p)

	# Generate index pages
	html_index += """
		</ul>
		<p><a href='procedures.html'>GRAMPS dynamic web pages report tests index</a></p>
		<p><small>Generated by the report %s version %s for GRAMPS version %s</small></p>
		</body>
		</html>
	""" % (default_options['name'], plugvers, VERSION)
	f = codecs.open(os.path.join(results_path, "index.html"), "w", encoding = "UTF-8", errors="xmlcharrefreplace")
	f.write(html_index)
	f.close()
	html_procedures += """
		</ul>
		<p><small>Generated by the report %s version %s for GRAMPS version %s</small></p>
		</body>
		</html>
	""" % (default_options['name'], plugvers, VERSION)
	f = codecs.open(os.path.join(results_path, "procedures.html"), "w", encoding = "UTF-8", errors="xmlcharrefreplace")
	f.write(html_procedures)
	f.close()
	
	

##############################################################
# Plugin version

def plugin_version():
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


##############################################################
# Unbuffered screen output
# needed in some environments (cygwin for example)
# otherwise the print statements are not printed in the correct order

class Unbuffered(object):
	def __init__(self, stream):
		self.stream = stream
	def write(self, data):
		self.stream.write(data)
		self.stream.flush()
	def __getattr__(self, attr):
		return getattr(self.stream, attr)
		
sys.stdout = Unbuffered(sys.stdout)
sys.stderr = Unbuffered(sys.stderr)


##############################################################

if __name__ == '__main__':
	try:
		# Import database argument
		if (len(sys.argv) == 2 and sys.argv[1] == "-i"):
			import_data()
			sys.exit(0);
		# Tests numbers arguments
		test_nums = range(len(test_list))
		if (len(sys.argv) > 1):
			test_nums = [
				int(sys.argv[i])
				for i in range(1, len(sys.argv))
			]
		# Launch tests
		print("Performing tests: %s" % str(test_nums))
		main(test_nums)
	except Exception as ex:
		sys.stderr.write(str(ex))
		sys.stderr.write("\n")
		traceback.print_exc()
		sys.exit(1)
