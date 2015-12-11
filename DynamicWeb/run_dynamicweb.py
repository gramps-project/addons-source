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
Dynamic Web Report generation script

This script produces the dynamic web report examples,
With the database /example/gramps/example.gramps,
And with various options.

The script is to be launched from its directory

Arguments = [-i] [report numbers]

Usage examples:
- Import example database
    python run_dynamicweb.py -i
- Run reports 0 and 2
    python run_dynamicweb.py 0 2
- Run all reports
    python run_dynamicweb.py
"""

from __future__ import print_function
import copy, re, os, os.path, subprocess, sys, traceback, locale, shutil, time, glob

# os.environ["LANGUAGE"] = "en_US"
# os.environ["LANG"] = "en_US.UTF-8"

# user_path = os.environ["GRAMPSHOME"]
# if (not os.path.exists(user_path)): raise Exception("User path GRAMPSHOME not found")
plugin_path = "."

gramps_path = os.environ["GRAMPS_RESOURCES"]
if (not os.path.exists(gramps_path)): raise Exception("Gramps path GRAMPS_RESOURCES not found")
sys.path.insert(1, gramps_path)

if sys.version_info[0] < 3:
    reload(sys)
    sys.setdefaultencoding('utf8')
from dynamicweb import *
from dynamicweb import _
from report_sets import *




def import_data():
    path = os.path.join(gramps_path, "example", "gramps", "example.gramps")
    path = os.path.abspath(path)
    print("=" * 80)
    print("Importing data \"%s\" in database \"dynamicweb_example\"" % path)
    print("=" * 80)
    os.chdir(gramps_path)
    subprocess.call([sys.executable, os.path.join(gramps_path, "Gramps.py"), "-y", "-C", "dynamicweb_example", "-i", path])


def main(report_nums):
    # Create results directory
    results_path = os.path.join(plugin_path, "reports")
    results_path = os.path.abspath(results_path)
    if (not os.path.isdir(results_path)): os.mkdir(results_path)
    plugvers = plugin_version(plugin_path)

    # Initialize index pages
    html_index = html_index_0
    html_procedures = html_procedures_0

    for (report_num, report_set) in enumerate(report_list):
        if (report_num not in report_nums): continue
        report_name = "report_%03i" % report_num
        # Build the report title and path
        title = report_set['title']
        print("=" * 80)
        print("%s:" % report_name)
        print("Exporting with options: %s" % title)
        print("=" * 80)
        target = os.path.join(results_path, report_name)

        # Build the report options form the default options + the report set options
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
            param = param.encode("UTF-8")
        os.chdir(gramps_path)
        # subprocess.call([sys.executable, os.path.join(gramps_path, "Gramps.py"), "-d", ".DynamicWeb", "-q", "-O", "dynamicweb_example", "-a", "report", "-p", param])
        subprocess.call([sys.executable, os.path.join(gramps_path, "Gramps.py"), "-q", "-O", "dynamicweb_example", "-a", "report", "-p", param])

        # Update index pages
        p = report_name + "/" + report_set['link']
        html_index += "<li><a href='%s'>%s</a></li>" % (p, report_set['title'])
        for procedure in report_set['procedures']:
            p = report_name + "/" + procedure['path']
            html_procedures += "<li>%s<br><a href='%s'>%s</a></li>" % (procedure['what'], p, p)

    for (test_num, test_set) in enumerate(test_list):
        if ((test_num + len(report_list)) not in report_nums): continue
        test_name = "test_%03i" % test_num
        # Build the test title and path
        title = test_set['title']
        print("=" * 80)
        print("%s:" % test_name)
        print("Exporting with options: %s" % title)
        print("=" * 80)
        target = os.path.join(results_path, test_name)
        
        # Build the test options form the default options + the test set options
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
        subprocess.call([sys.executable, os.path.join(gramps_path, "Gramps.py"), "-q", "-O", "dynamicweb_example", "-a", "report", "-p", param])
            
    # Generate index pages
    html_index += html_index_1 % (default_options['name'], plugvers, VERSION)
    f = codecs.open(os.path.join(results_path, "index.html"), "w", encoding = "UTF-8", errors="xmlcharrefreplace")
    f.write(html_index)
    f.close()
    html_procedures += html_procedures_1 % (default_options['name'], plugvers, VERSION)
    f = codecs.open(os.path.join(results_path, "procedures.html"), "w", encoding = "UTF-8", errors="xmlcharrefreplace")
    f.write(html_procedures)
    f.close()



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
        # Reports numbers arguments
        report_nums = range(len(report_list) + len(test_list))
        if (len(sys.argv) > 1):
            report_nums = [
                int(sys.argv[i])
                for i in range(1, len(sys.argv))
            ]
        # Launch reports generation
        print("Exporting reports: %s" % str(report_nums))
        main(report_nums)
    except Exception as ex:
        sys.stderr.write(str(ex))
        sys.stderr.write("\n")
        traceback.print_exc()
        sys.exit(1)
