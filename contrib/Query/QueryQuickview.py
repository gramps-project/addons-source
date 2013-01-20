#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2007  Donald N. Allingham
# Copyright (C) 2007-2008  Brian G. Matherly
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

"""
Run a query on the tables
"""

from gramps.gen.simple import SimpleAccess, SimpleDoc
from gramps.gui.plug.quick import QuickTable
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.get_addon_translator(__file__).gettext
import gramps.gen.datehandler
import gramps.gen.lib

class DBI(object):
    def __init__(self, database, document):
        self.database = database
        self.document = document

        self.data = {
            "people": 
            ("person", {"given_name": "person.get_primary_name().get_first_name()",
                        "surname": "person.get_primary_name().get_surname()",
                        "suffix": "person.get_primary_name().get_suffix()",
                        "title": "person.get_primary_name().get_title()",
                        "birth_date": "self.sdb.birth_date_obj(person)",
                        "death_date": "self.sdb.death_date_obj(person)",
                        "gender": "self.sdb.gender(person)",
                        "birth_place": "self.sdb.birth_place(person)",
                        "death_place": "self.sdb.death_place(person)",
                        "change": "person.get_change_display()",
                        "marker": "person.marker.string",
                        }),
            "families": ("family", {}),
            "sources": ("source", {}),
            "events": ("event", {}),
            }

    def parse(self, query):
        # select col1, col2 from table where exp;
        # select * from table where exp;
        # delete from table where exp;
        self.query = query
        state = "START"
        substate = None
        subdepth = {"(": 0, "[": 0}
        data = None
        i = 0
        self.columns = []
        self.command = None
        self.where = None
        self.table = None
        self.name = None
        while i < len(query):
            c = query[i]
            #print "STATE:", state, c, substate
            if substate:
                if substate == "IN-EXP":
                    data += c
                    if c in ['(']:
                        subdepth["("] += 1
                    elif c in ['[']:
                        subdepth["["] += 1
                    elif c in [']']:
                        subdepth["["] -= 1
                    elif c in [')']:
                        subdepth["("] -= 1
                    if not any(subdepth.values()):
                        substate = None
                elif substate == "IN-QUOTE":
                    if c in ['"']:
                        substate = None
                    data += c
            elif state == "START":
                if c in [' ', '\n', '\t']: # pre white space
                    pass # skip it
                else:
                    state = "COMMAND"
                    data = c
            elif state == "COMMAND":
                if c in [' ', '\n', '\t']: # ending white space
                    self.command = data.lower()
                    data = ''
                    state = "AFTER-COMMAND"
                else:
                    data += c
            elif state == "AFTER-COMMAND":
                if c in [' ', '\n', '\t']: # pre white space
                    pass
                else:
                    state = "COL_OR_FROM"
                    i -= 1
            elif state == "COL_OR_FROM":
                if c in ['"']:
                    substate = "IN-QUOTE"
                    data += c
                elif c in ['(']:
                    substate = "IN-EXP"
                    data += c
                    subdepth["("] += 1
                elif c in ['[']:
                    substate = "IN-EXP"
                    data += c
                    subdepth["["] += 1
                elif c in [' ', '\n', '\t',  ',']: # end white space or comma
                    if data.upper() == "FROM":
                        data = ''
                        state = "PRE-GET-TABLE"
                    else:
                        if data:
                            self.columns.append(data)
                        data = ''
                        state = "AFTER-COMMAND"
                else:
                    data += c
            elif state == "PRE-GET-TABLE":
                if c in [' ', '\n', '\t']: # pre white space
                    pass
                else:
                    state = "GET-TABLE"
                    i -= 1
            elif state == "GET-TABLE":
                if c in [' ', '\n', '\t', ';']: # end white space or colon
                    self.table = data.lower()
                    self.name = self.data[self.table][0]
                    data = ''
                    state = "PRE-GET-WHERE"
                else:
                    data += c
            elif state == "PRE-GET-WHERE":
                if c in [' ', '\n', '\t']: # pre white space
                    pass
                else:
                    state = "GET-WHERE"
                    i -= 1
            elif state == "GET-WHERE":
                if c in [' ', '\n', '\t']: # end white space
                    if data.upper() != "WHERE":
                        raise AttributeError("expecting WHERE got '%s'" % data)
                    else:
                        data = ''
                        state = "GET-EXP"
                else:
                    data += c
            elif state == "GET-EXP":
                self.where = query[i:]
                self.where = self.where.strip()
                if self.where.endswith(";"):
                    self.where = self.where[:-1]
                i = len(query)
            else:
                raise AttributeError("unknown state: '%s'" % state)
            i += 1
        if self.table is None:
            raise AttributeError("malformed query: no table in '%s'\n" % self.query)

    def close(self):
        #try:
        #    self.progress.close()
        #except:
        pass

    def eval(self):
        self.sdb = SimpleAccess(self.database)
        self.stab = QuickTable(self.sdb)
        self.select = 0
        self.process_table()
        if self.select > 0:
            self.sdoc = SimpleDoc(self.document)
            self.sdoc.title(self.query)
            self.sdoc.paragraph("\n")
            self.sdoc.paragraph("%d rows processed.\n" % self.select)
            self.stab.write(self.sdoc)
            self.sdoc.paragraph("")
        return _("[%d rows processed]") % self.select

    def get_columns(self, table):
        retval = self.data[table][1].keys()
        retval.sort()
        return [self.name] + retval

    def process_table(self):
        for col_name in self.columns[:]: # copy
            if col_name == "*":
                self.columns.remove('*')
                self.columns.extend( self.get_columns(self.table))
        self.stab.columns(*map(lambda s: s.replace("_", " ").title(),
                               self.columns))
        if self.table == "people":
            self.do_query(self.sdb.all_people())
        elif self.table == "families":
            self.do_query(self.sdb.all_families())
        elif self.table == "events":
            self.do_query(self.sdb.all_events())
        elif self.table == "sources":
            self.do_query(self.sdb.all_sources())
        else:
            raise AttributeError, ("no such table: '%s'" % self.table)

    def make_env(self, **kwargs):
        """
        An environment with which to eval rows.
        """
        retval= {
            _("Date"): gramps.gen.lib.date.Date,
            _("Today"): gramps.gen.lib.date.Today(),
            }
        # Fixme: make these lazy, for delayed lookup
        #retval.update(self.data[self.table][1])
        retval.update(kwargs) 
        return retval

    def do_query(self, items):
        count = 0
        for item in items:
            count += 1
            row = []
            sorts = []
            env = self.make_env(col=row)
            env[self.name] = item
            for col in self.columns:
                col_name = col
                if col in self.data[self.table][1]:
                    col = self.data[self.table][1][col]
                if col == "":
                    continue
                else:
                    try:
                        env[col_name] = eval(col, env)
                    except:
                        env[col_name] = "" 
                row.append(env[col_name])
            if self.where:
                try:
                    result = eval(self.where, env)
                except:
                    result = False
            else:
                result = True
            if result:
                self.select += 1
                if self.command == "select":
                    self.stab.row(*row)
                    for (col, value) in sorts:
                        self.stab.row_sort_val(col, value)
                elif self.command == "delete":
                    #self.database.active = person
                    #trans = self.database.transaction_begin()
                    #active_name = _("Delete Person (%s)") % self.sdb.name(person)
                    #gramps.gen.utils.delete_person_from_database(self.database, person, trans)
                    ## FIXME: delete familes, events, notes, resources, etc, if possible
                    #self.database.transaction_commit(trans, active_name)
                    pass
                else:
                    raise AttributeError("unknown command: '%s'", self.command)


def run(database, document, query):
    """
    Run the query
    """
    retval = ""
    dbi = DBI(database, document)
    try:
        q = dbi.parse(query)
    except AttributeError, msg:
        return msg
    try:
        retval = dbi.eval()
    except AttributeError, msg:
        # dialog?
        retval = msg
    dbi.close()
    return retval

