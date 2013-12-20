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

from __future__ import print_function

from gramps.gen.simple import SimpleAccess, SimpleDoc
from gramps.gui.plug.quick import QuickTable
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
import gramps.gen.datehandler
import gramps.gen.lib
from gramps.gen.merge.diff import Struct

def groupings(string):
    groups = []
    current_type = None
    for c in string:
        if (not c.isdigit()) and current_type == "alpha":
            groups[-1].append(c)
        elif c.isdigit() and current_type == "numeric":
            groups[-1].append(c)
        else:
            if c.isdigit():
                current_type = "numeric"
            else:
                current_type = "alpha"
            groups.append([c])
    retval = []
    for group in groups:
        if group[0].isdigit():
            retval.append("".join(group).zfill(10))
        else:
            retval.append("".join(group).zfill(5))
    return (retval)


class DBI(object):
    def __init__(self, database, document):
        self.database = database
        self.document = document

        self.data = {}
        for name in self.database.get_table_names():
            d = self.database._tables[name]["class_func"]().to_struct()
            self.data[name.lower()] = d.keys()

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
            #print(state, substate, c)
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
                    if self.command == "delete":
                        state = "PRE-GET-UPDATE-TABLE"
                    else:
                        state = "AFTER-COMMAND"
                else:
                    data += c
            elif state == "PRE-GET-UPDATE-TABLE":
                if c in [' ', '\n', '\t']: # pre white space
                    pass
                else:
                    state = "GET-UPDATE-TABLE"
                    substate = ""
                    i -= 1
            elif state == "GET-UPDATE-TABLE":
                if c in [' ', '\n', '\t']: # pre white space
                    state = "GET-SET"
                    self.table = substate
                else:
                    substate += c
            elif state == "GET-SET":
                if c in [' ', '\n', '\t']: # pre white space
                    pass
                else:
                    substate += c.upper()
                    if substate == "SET":
                        state = "GET-SET-PAIRS"
                        substate = ""
            elif state == "GET-SET-PAIRS":
                if c in [' ', '\n', '\t']: # pre white space
                    pass
                else:
                    substate += c
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
                    self.name = data.lower()
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
        retval = self.data[table]
        return retval # [self.name] + retval

    def process_table(self):
        for col_name in self.columns[:]: # copy
            if col_name == "*":
                self.columns.remove('*')
                self.columns.extend( self.get_columns(self.table))
        self.stab.columns(*self.columns)
        if self.table == "person":
            self.do_query(self.sdb.all_people())
        elif self.table == "family":
            self.do_query(self.sdb.all_families())
        elif self.table == "event":
            self.do_query(self.sdb.all_events())
        elif self.table == "source":
            self.do_query(self.sdb.all_sources())
        else:
            raise AttributeError("no such table: '%s'" % self.table)

    def make_env(self, **kwargs):
        """
        An environment with which to eval rows.
        """
        retval= {
            _("Date"): gramps.gen.lib.date.Date,
            _("Today"): gramps.gen.lib.date.Today(),
            "groupings": groupings,
            }
        retval.update(kwargs) 
        return retval

    def do_query(self, items):
        for item in items:
            row = []
            row_env = []
            sorts = [] # [[0, "groupings(gramps_id)"]]
            # col[0] in where will return first column of selection:
            env = self.make_env(col=row_env) 
            struct = item.to_struct()
            s = Struct(struct, self.database)
            for col in self.columns:
                value = s[col] # col is path
                row.append(str(value))
                # for where eval:
                # get top-level name:
                col_top = col.split(".")[0]
                # set in environment:
                env[col_top] = getattr(s, col_top)
                # allow col[#] reference:
                row_env.append(s[col])
            # Should we include this row?
            if self.where:
                try:
                    result = eval(self.where, env)
                except:
                    print("Error in where clause:", self.where)
                    result = False
            else:
                result = True
            # If result, then append the row
            if result:
                self.select += 1
                if self.command == "select":
                    if self.select < 50:
                        self.stab.row(*row)
                        #for (col, value) in sorts:
                        #    self.stab.row_sort_val(col, eval(value, env))
                elif self.command == "update":
                    # update table set col=val, col=val where expr;
                    pass
                elif self.command == "delete":
                    #self.database.active = person
                    #trans = self.database.transaction_begin()
                    #active_name = _("Delete Person (%s)") % self.sdb.name(person)
                    #db.delete_person_from_database(self.database, person, trans)
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
    except AttributeError as msg:
        return msg
    try:
        retval = dbi.eval()
    except AttributeError as msg:
        # dialog?
        retval = msg
    dbi.close()
    return retval

