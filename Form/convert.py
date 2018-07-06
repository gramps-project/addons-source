#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2015      Nick Hall
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

import sys
import xml.dom.minidom

if len(sys.argv) != 3:
    print ('Usage: python convert.py old_file new_file')
    sys.exit()

old_file = sys.argv[1]
new_file = sys.argv[2]

dom = xml.dom.minidom.parse(old_file)
out_file = open(new_file, 'w')

top = dom.getElementsByTagName('censuses')
out_file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
out_file.write('<forms>\n')

for census in top[0].getElementsByTagName('census'):
    id = census.attributes['id'].value
    date = census.attributes['date'].value
    title = census.attributes['title'].value
    out_file.write("    <form id='%s' type='Census' title='%s' date='%s'>\n" %
                   (id, title, date))

    headings = census.getElementsByTagName('heading')
    for heading in headings:
        attr = heading.getElementsByTagName('_attribute')
        attr_text = attr[0].childNodes[0].data
        out_file.write('        <heading>\n')
        out_file.write('            <_attribute>%s</_attribute>\n' % attr_text)
        out_file.write('        </heading>\n')

    out_file.write("        <section role='Primary' type='multiple'>\n")
    columns = census.getElementsByTagName('column')
    for column in columns:
        attr = column.getElementsByTagName('_attribute')
        size = column.getElementsByTagName('size')
        longname = column.getElementsByTagName('_longname')
        attr_text = attr[0].childNodes[0].data
        out_file.write('            <column>\n')
        out_file.write('                <_attribute>%s</_attribute>\n' %
                       attr_text)
        if size:
            size_text = size[0].childNodes[0].data
            out_file.write('                <size>%s</size>\n' % size_text)
        if longname:
            long_text = longname[0].childNodes[0].data
            out_file.write('                <_longname>%s</_longname>\n' %
                           long_text)
        out_file.write('            </column>\n')

    out_file.write("        </section>\n")
    out_file.write("    </form>\n")

out_file.write("</forms>\n")

dom.unlink()
out_file.close()
