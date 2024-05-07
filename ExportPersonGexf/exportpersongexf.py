#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2024      Nick Hall
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

"Export people to GEXF"

#------------------------------------------------------------------------
#
# Set up logging
#
#------------------------------------------------------------------------
import logging
from collections import abc
from html import escape
import uuid
log = logging.getLogger(".ExportGEXF")

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from gramps.gen.display.name import displayer as _nd
from gramps.gen.lib import Person

from gramps.gen.plug.utils import OpenFileOrStdout

from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext

#-------------------------------------------------------------------------
#
# Support Functions
#
#-------------------------------------------------------------------------
def exportData(database, filename, user, option_box=None):
    """Function called by Gramps to export data in GrampsML format."""
    writer = GEXFWriter(database, filename, option_box, user)
    try:
        writer.export_data()
    except EnvironmentError as msg:
        user.notify_error(_("Could not create %s") % filename, str(msg))
        return False
    except:
        # Export shouldn't bring Gramps down.
        user.notify_error(_("Could not create %s") % filename)
        return False
    return True

SEX = {Person.MALE: _('Male'),
       Person.FEMALE: _('Female'),
       Person.OTHER: _('Other'),
       Person.UNKNOWN: _('Unknown')
       }

#-------------------------------------------------------------------------
#
# GEXFWriter class
#
#-------------------------------------------------------------------------
class GEXFWriter:
    """Class to create a file with data in GEXF format."""

    def __init__(self, database, filename, option_box=None, user=None):
        self.db = database
        self.filename = filename
        self.user = user
        self.filehandle = None
        self.option_box = option_box
        if isinstance(self.user.callback, abc.Callable):  # is really callable
            self.update = self.update_real
        else:
            self.update = self.update_empty

        if option_box:
            self.option_box.parse_options()
            self.db = option_box.get_filtered_database(self.db)

        self.count = 0
        self.total = 0
        self.edges = []

    def update_empty(self):
        """Progress can't be reported."""
        pass

    def update_real(self):
        """Report progress."""
        self.count += 1
        newval = int(100*self.count/self.total)
        if newval != self.oldval:
            self.user.callback(newval)
            self.oldval = newval

    def writeln(self, text):
        # print (text + '\n')
        self.filehandle.write(text + '\n')

    def export_data(self):
        with OpenFileOrStdout(self.filename, encoding='utf-8',
                              errors='strict', newline='') as self.filehandle:
            if self.filehandle:
                self.count = 0
                self.oldval = 0
                self.total = self.db.get_number_of_people()
                self.write_header()
                for handle in self.db.get_person_handles():
                    self.write_person(handle)
                    self.update()
                self.write_edges()
                self.write_footer()
        return True

    def write_person(self, person_handle):
        person = self.db.get_person_from_handle(person_handle)
        if person:
            data = {'label': _nd.display(person),
                    'gramps_id': person.gramps_id,
                    'sex': SEX[person.gender]}
            self.write_node(person.handle, data)

            # Parents
            for family_handle in person.get_parent_family_handle_list():
                family = self.db.get_family_from_handle(family_handle)
                if family.mother_handle:
                    kind = _('Mother')
                    data = {}
                    self.add_edge(person_handle, family.mother_handle, kind, data)
                if family.father_handle:
                    kind = _('Father')
                    data = {}
                    self.add_edge(person_handle, family.father_handle, kind, data)
                if family.mother_handle and family.father_handle:
                    kind = _('Spouse')
                    data = {}
                    self.add_edge(family.mother_handle, family.father_handle, kind, data)

            # Associations
            for person_ref in person.get_person_ref_list():
                kind = person_ref.get_relation()
                data = {}
                self.add_edge(person_handle, person_ref.ref, kind, data)

    def write_header(self):
        self.writeln('<?xml version="1.0" encoding="UTF-8"?>')
        self.writeln('<gexf xmlns="http://www.gexf.net/1.2draft"')
        self.writeln('      xmlns:xsi="http://www.w3.org/2001/XMLSchema−instance"')
        self.writeln('      xsi:schemaLocation="http://www.gexf.net/1.2draft')
        self.writeln('                          http://www.gexf.net/1.2draft/gexf.xsd"')
        self.writeln('      version="1.2">')

        self.writeln('<meta lastmodifieddate="2024−05−07">')
        self.writeln('  <creator>Gramps</creator>')
        self.writeln('</meta>')

        self.writeln('<attributes class="node">')
        #self.write_attr(['Label', 'string', 'node', 'label'])
        self.write_attr(['Gramps ID', 'string', 'node', 'gramps_id'])
        self.write_attr(['Sex', 'string', 'node', 'sex'])
        self.writeln('</attributes>')

        self.writeln('<attributes class="edge">')
        #self.write_attr(['Relation', 'string', 'edge', 'relation'])
        self.writeln('</attributes>')

        self.writeln('<graph defaultedgetype="undirected">')

    def write_attr(self, attr):
        key_str = '<attribute id="{}" title="{}" type="{}"/>'
        self.writeln(key_str.format(attr[3], attr[0], attr[1]))

    def write_node(self, node_id, data):
        label = ''
        if 'label' in data:
            label = escape(data['label'])
            del data['label']
        self.writeln('<node id="{}" label="{}">'.format(node_id, label))
        self.write_data(data)
        self.writeln('</node>')

    def add_edge(self, source, target, kind, data):
        self.edges.append((source, target, kind, data))

    def write_edges(self):
        for source, target, kind, data in self.edges:
            self.write_edge(source, target, kind, data)

    def write_edge(self, source, target, kind, data):
        edge_id = uuid.uuid4()
        edge_str = '<edge id="{}" source="{}" target="{}" kind="{}" label="{}">'
        self.writeln(edge_str.format(edge_id, source, target, kind, kind))
        self.write_data(data)
        self.writeln('</edge>')

    def write_data(self, data):
        self.writeln('<attvalues>')
        for key, value in data.items():
            if value:
                self.writeln('<attvalue for="{}" value="{}"/>'.format(key, escape(value)))
        self.writeln('</attvalues>')

    def write_footer(self):
        self.writeln('</graph>')
        self.writeln('</gexf>')
