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
        if self.database:
            for name in self.database.get_table_names():
                d = self.database._tables[name]["class_func"]().to_struct()
                self.data[name.lower()] = d.keys()

    def parse(self, query):
        self.query = query.strip()
        self.parser(self.lexer(self.query))

    def lexer(self, string):
        """
        Given a string, break into a list of Lexical Symbols
        """
        retval = []
        state = None
        current = ""
        stack = []
        i = 0
        while i < len(string):
            ch = string[i]
            #print("lex:", i, ch)
            if state == "in-double-quote":
                if ch == '"':
                    state = stack.pop()
                    retval.append(current)
                    current = ""
                else:
                    current += ch
            elif ch == '"':
                stack.append(state)
                state = "in-double-quote"
                current = ""
            elif ch == ",":
                if current:
                    retval.append(current)
                    current = ""
                else:
                    raise ValueError("invalid comma in expression at position %d" % i)
                retval.append(",")
            elif ch == "=":
                if current:
                    retval.append(current)
                    current = ""
                else:
                    raise ValueError("invalid equal-sign in expression at position %d" % i)
                retval.append("=")
            elif ch in [' ', '\t', '\n', ";"]: # break
                if current:
                    retval.append(current)
                    if current.upper() == "WHERE":
                        # HACK: get rest of string:
                        if string[-1] == ";":
                            retval.append(string[i + 1:-1])
                            i = len(string) - 2
                        else:
                            retval.append(string[i + 1:])
                            i = len(string) - 1
                    current = ""
                else:
                    pass # ignore whitespace
            else:
                current += ch
            i += 1
        #print("lexed:", retval)
        return retval

    def parser(self, lex):
        self.action = None
        self.table = None
        self.columns = []
        self.setcolumns = []
        self.values = []
        self.aliases = {}
        self.where = None
        self.index = 0
        while self.index in range(len(lex)):
            symbol = lex[self.index]
            if symbol.upper() == "FROM":
                # from table select *;
                if self.index < len(lex):
                    self.index += 1
                    self.table = lex[self.index]
            elif symbol.upper() == "SELECT":
                # select a, b from table;
                self.action = "SELECT"
                self.index += 1
                self.columns.append(lex[self.index])
                self.index += 1
                while self.index < len(lex) and lex[self.index] in [",", "as"]:
                    sep = lex[self.index]
                    if sep == ",":
                        self.index += 1
                        self.columns.append(lex[self.index])
                        self.index += 1
                    elif sep == "as":
                        self.index += 1 # alias
                        self.aliases[self.columns[-1]] = lex[self.index]
                        self.index += 1
                self.index -= 1
            elif symbol.upper() == "DELETE":
                # delete from table where item == 1;
                self.action = "DELETE"
                self.columns = ["*"] # for where clause
            elif symbol.upper() == "SET":
                # SET x=1, y=2
                self.index += 1
                self.setcolumns.append(lex[self.index]) # first column
                self.index += 1 # equal sign
                # =
                self.index += 1 # value
                self.values.append(lex[self.index])
                self.index += 1 # comma
                while self.index < len(lex) and lex[self.index] == ",":
                    self.index += 1 # next column
                    self.setcolumns.append(lex[self.index])
                    self.index += 1 # equal
                    # =
                    self.index += 1 # value
                    self.values.append(lex[self.index])
                    self.index += 1 # comma?
                self.index -= 1
            elif symbol.upper() == "LIMIT":
                pass # FIXME
            elif symbol.upper() == "WHERE":
                # how can we get all of Python expressions?
                # this assumes all by ;
                self.index += 1
                self.where = lex[self.index]
            elif symbol.upper() == "UPDATE":
                self.columns = ["*"] # for where clause
                # update table set x=1, y=2 where condition;
                self.action = "UPDATE"
                if self.index < len(lex):
                    self.index += 1
                    self.table = lex[self.index]
            self.index += 1

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
        self.stab.columns(*[column.replace("_", "__") for column in self.columns])
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
        with self.database.get_transaction_class()("QueryQuickview", self.database) as trans:
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
                    if self.action in ["DELETE", "UPDATE"]:
                        result = True
                    else:
                        result = any([col != "None" for col in row]) # are they all None?
                # If result, then append the row
                if result:
                    self.select += 1
                    if self.action == "SELECT":
                        if self.select < 50: # FIXME: use LIMIT
                            self.stab.row(*row)
                    elif self.action == "UPDATE":
                        # update table set col=val, col=val where expr;
                        self.stab.row(*row)
                        for i in range(len(self.setcolumns)):
                            s.setitem(self.setcolumns[i], self.values[i], trans=trans)
                    elif self.action == "DELETE":
                        self.stab.row(*row)
                        self.database.remove_from_database(item, trans)
                    else:
                        raise AttributeError("unknown command: '%s'", self.action)

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

