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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""
Run a query on the tables
"""

from gramps.gen.simple import SimpleAccess, SimpleDoc
try:
    #quack
    from gramps.gui.plug.quick import QuickTable
except:
    # For testing framework
    class QuickTable(object):
        def __init__(self, database):
            self.db = database
            self.data = []
            self.column_labels = []
            self.links = []
        def rows(self, *cols, **kwargs):
            self.data.append(cols)
            self.links.append(kwargs.get("link", None))
        def columns(self, *cols):
            self.column_labels = cols[:]
        def write(self, document):
            pass

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
import gramps.gen.datehandler
import gramps.gen.lib
from gramps.gen.lib.handle import Handle
from gramps.gen.lib.primaryobj import PrimaryObject
from gramps.gen.lib.struct import Struct

import random
import re
import traceback
import itertools
import time

class Environment(dict):
    """
    Environment class for providing a specialized env
    so that eval(expr, env) will be able to find items
    in the struct.
    """
    def __init__(self, *args, **kwargs):
        """ Initialize environment as a regular dict """
        dict.__init__(self, *args, **kwargs)

    def __getitem__(self, key):
        """
        Try looking up the item in struct first, and if failing
        look in self (a dict).
        """
        try:
            return self.struct[key]
        except:
            if key in self:
                return dict.__getitem__(self, key)
            else:
                raise NameError("name '%s' is not defined" % key)

    def set_struct(self, struct):
        """
        Set the struct of the Environment.
        """
        self.struct = struct

class DBI(object):
    """
    The SQL-like interface to the database and document instances.
    """
    def __init__(self, database, document=None):
        self.database = database
        self.document = document
        self.data = {}
        self.select = 0
        self.flat = False
        self.raw = False
        if self.database:
            for name in ('Person', 'Family', 'Event', 'Place', 'Repository',
                         'Source', 'Citation', 'Media', 'Note', 'Tag'):
                d = self.database._tables[name]["class_func"]().to_struct()
                self.data[name.lower()] = d.keys()
        # The macros:
        self.shortcuts = {
            "SURNAME": "primary_name.surname_list[0].surname",
            "GIVEN": "primary_name.first_name",
        }

    def parse(self, query):
        """
        Parse the query.
        """
        self.query_text = query.replace("\n", " ").strip()
        lexed = self.lexer(self.query_text)
        #print(lexed)
        self.parser(lexed)
        for col_name in self.columns[:]: # copy
            if col_name == "*":
                self.columns.remove('*')
                # this is useful to see what _class it is:
                self.columns.extend(self.get_columns(self.table))
                # otherwise remove metadata:
                #self.columns.extend([col for col in self.get_columns(self.table) if not col.startswith("_"))

    def lexer(self, string):
        """
        Given a string, break into a list of chunks.
        """
        retval = []
        state = None
        current = ""
        stack = []
        i = 0
        # Handle macros:
        for key in self.shortcuts.keys():
            string = string.replace(key, self.shortcuts[key])
        # (some "expression" in ok)
        # func(some "expression" in (ok))
        # list[1][0]
        # [x for x in list]
        while i < len(string):
            ch = string[i]
            #print("lex:", i, ch, state, retval, current)
            if state == "in-double-quote":
                if ch == '"':
                    state = stack.pop()
                current += ch
            elif state == "in-single-quote":
                if ch == "'":
                    state = stack.pop()
                current += ch
            elif state == "in-expr":
                if ch == ")":
                    state = stack.pop()
                elif ch == "(":
                    stack.append("in-expr")
                current += ch
            elif state == "in-square-bracket":
                if ch == "]":
                    state = stack.pop()
                elif ch == "[":
                    stack.append("in-square-bracket")
                current += ch
            elif ch == '"':
                stack.append(state)
                state = "in-double-quote"
                current += ch
            elif ch == "'":
                stack.append(state)
                state = "in-single-quote"
                current += ch
            elif ch == "(":
                stack.append(state)
                state = "in-expr"
                current += "("
            elif ch == "[":
                stack.append(state)
                state = "in-square-bracket"
                current += "["
            elif ch == ",":
                if current:
                    retval.append(current)
                retval.append(",")
                current = ""
            elif ch == "=":
                if current:
                    retval.append(current)
                retval.append("=")
                current = ""
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
        if current:
            retval.append(current)
        #print("lexed:", retval)
        return retval

    def parser(self, lex):
        """
        Takes output of lexer, and sets the values.
        After parser, the DBI will be ready to process query.
        """
        self.action = None
        self.table = None
        self.columns = []
        self.setcolumns = []
        self.values = []
        self.aliases = {}
        self.limit = None
        self.where = None
        self.index = 0
        while self.index < len(lex):
            symbol = lex[self.index]
            if symbol.upper() == "FROM":
                # from table select *;
                self.index += 1
                if self.index < len(lex):
                    self.table = lex[self.index]
            elif symbol.upper() == "SELECT":
                # select a, b from table;
                self.action = "SELECT"
                self.index += 1
                self.columns.append(lex[self.index])
                self.index += 1
                while self.index < len(lex) and lex[self.index].upper() in [",", "AS"]:
                    sep = lex[self.index]
                    if sep == ",":
                        self.index += 1
                        self.columns.append(lex[self.index])
                        self.index += 1
                    elif sep.upper() == "AS":
                        self.index += 1 # alias
                        self.aliases[self.columns[-1]] = lex[self.index]
                        self.index += 1
                self.index -= 1
            elif symbol.upper() == "DELETE":
                # delete from table where item == 1;
                self.action = "DELETE"
                self.columns = ["gramps_id"]
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
                self.index += 1 # after LIMIT
                number = lex[self.index]
                self.index += 1 # maybe a comma
                if self.index < len(lex) and lex[self.index] == ",":
                    self.index += 1 # after ","
                    stop = lex[self.index]
                    self.limit = (int(number), int(stop))
                else:
                    self.limit = (0, int(number))
                    self.index -= 1
            elif symbol.upper() == "WHERE":
                # how can we get all of Python expressions?
                # this assumes all by ;
                self.index += 1
                self.where = lex[self.index]
            elif symbol.upper() == "UPDATE":
                # update table set x=1, y=2 where condition;
                # UPDATE gramps_id set tag_list = Tag("Betty") from person where  "Betty" in primary_name.first_name
                self.columns = ["gramps_id"]
                self.action = "UPDATE"
                if self.index < len(lex):
                    self.index += 1
                    self.table = lex[self.index]
            elif symbol.upper() == "FLAT":
                self.flat = True
            elif symbol.upper() == "EXPAND":
                self.flat = False
            elif symbol.upper() == "RAW":
                self.raw = True
            elif symbol.upper() == "NORAW":
                self.raw = False
            else:
                raise AttributeError("invalid SQL expression: '... %s ...'" % symbol)
            self.index += 1

    def close(self):
        """
        Close up any progress widgets or dialogs.
        """
        #try:
        #    self.progress.close()
        #except:
        pass

    def clean_titles(self, columns):
        """
        Take the columns and turn them into strings for the table.
        """
        retval = []
        for column in columns:
            if column in self.aliases:
                column = self.aliases[column]
            retval.append(column.replace("_", "__"))
        return retval

    def query(self, query):
        self.parse(query)
        self.select = 0
        start_time = time.time()
        class Table():
            results = []
            def row(self, *args, **kwargs):
                self.results.append([args, kwargs])
            def get_rows(self):
                return [list(item[0]) for item in self.results]
        table = Table()
        self.sdb = SimpleAccess(self.database)
        self.process_table(table) # a class that has .row(1, 2, 3, ...)
        print(_("{rows:d} rows processed in {secs} seconds.\n").format(rows=self.select, secs=time.time() - start_time)
        return table

    def eval(self):
        """
        Execute the query.
        """
        self.sdb = SimpleAccess(self.database)
        self.stab = QuickTable(self.sdb)
        self.select = 0
        start_time = time.time()
        self.process_table(self.stab) # a class that has .row(1, 2, 3, ...)
        if self.select > 0:
            self.stab.columns(*self.clean_titles(self.columns))
            self.sdoc = SimpleDoc(self.document)
            self.sdoc.title(self.query_text)
            self.sdoc.paragraph("\n")
            self.sdoc.paragraph("%d rows processed in %s seconds.\n" % (self.select, time.time() - start_time))
            self.stab.write(self.sdoc)
            self.sdoc.paragraph("")
        return _("{rows:d} rows processed in {secs} seconds.\n").format(rows=self.select, secs=time.time() - start_time)

    def get_columns(self, table):
        """
        Get the columns for the given table.
        """
        if self.database:
            retval = self.data[table.lower()]
            return retval # [self.name] + retval
        else:
            return ["*"]

    def process_table(self, table):
        """
        Given a table name, process the query on the elements of the
        table.
        """
        # 'Person', 'Family', 'Source', 'Citation', 'Event', 'Media',
        # 'Place', 'Repository', 'Note', 'Tag'
        # table: a class that has .row(1, 2, 3, ...)
        if self.table == "person":
            self.do_query(self.sdb.all_people(), table)
        elif self.table == "family":
            self.do_query(self.sdb.all_families(), table)
        elif self.table == "event":
            self.do_query(self.sdb.all_events(), table)
        elif self.table == "source":
            self.do_query(self.sdb.all_sources(), table)
        elif self.table == "tag":
            self.do_query(self.sdb.all_tags(), table)
        elif self.table == "citation":
            self.do_query(self.sdb.all_citations(), table)
        elif self.table == "media":
            self.do_query(self.sdb.all_media(), table)
        elif self.table == "place":
            self.do_query(self.sdb.all_places(), table)
        elif self.table == "repository":
            self.do_query(self.sdb.all_repositories(), table)
        elif self.table == "note":
            self.do_query(self.sdb.all_notes(), table)
        else:
            raise AttributeError("no such table: '%s'" % self.table)

    def get_tag(self, name):
        tag = self.database.get_tag_from_name(name)
        if tag is None:
            tag = gramps.gen.lib.Tag()
            tag.set_name(name)
            trans_class = self.database.get_transaction_class()
            with trans_class("QueryQuickview new Tag", self.database, batch=False) as trans:
                self.database.add_tag(tag, trans)
        return Handle("Tag", tag.handle)

    def make_env(self, **kwargs):
        """
        An environment with which to eval elements.
        """
        retval= Environment({
            _("Date"): gramps.gen.lib.date.Date,
            _("Today"): gramps.gen.lib.date.Today(),
            "random": random,
            "re": re,
            "db": self.database,
            "sdb": self.sdb,
            "lib": gramps.gen.lib,
            "_": _,
            "Tag": self.get_tag,
            })
        retval.update(__builtins__)
        retval.update(kwargs)
        return retval

    def stringify(self, value):
        """
        Turn the value into an appropriate string representation.
        """
        if self.raw:
            return value
        if isinstance(value, Struct):
            return self.stringify(value.struct)
        elif isinstance(value, (list, tuple)):
            if len(value) == 0 and not self.flat:
                return ""
            elif len(value) == 1 and not self.flat:
                return self.stringify(value[0])
            else:
                return "[%s]" % (", ".join(map(self.stringify, value)))
        elif isinstance(value, PrimaryObject):
            return value
        else:
            return str(value)

    def clean(self, values, names):
        """
        Given the values and names of columns, change the values
        into string versions for the display table.
        """
        if self.raw:
            return values
        retval = []
        for i in range(len(values)):
            if names[i].endswith("handle"):
                retval.append(repr(values[i].struct["handle"]))
            else:
                retval.append(self.stringify(values[i]))
        return retval

    def do_query(self, items, table):
        """
        Perform the query on the items in the named table.
        """
        # table: a class that has .row(1, 2, 3, ...)
        with self.database.get_transaction_class()("QueryQuickview", self.database, batch=True) as trans:
            ROWNUM = 0
            env = self.make_env()
            for item in items:
                if item is None:
                    continue
                row = []
                row_env = []
                # "col[0]" in WHERE clause will return first column of selection:
                env["col"] = row_env
                env["ROWNUM"] = ROWNUM
                env["object"] = item
                struct = Struct(item.to_struct(), self.database)
                env.set_struct(struct)
                for col in self.columns:
                    try:
                        value = eval(col, env)
                    except:
                        value = None
                    row.append(value)
                    # allow col[#] reference:
                    row_env.append(value)
                    # an alias?
                    if col in self.aliases:
                        env[self.aliases[col]] = value
                # Should we include this row?
                if self.where:
                    try:
                        result = eval(self.where, env)
                    except:
                        continue
                else:
                    if self.action in ["DELETE", "UPDATE"]:
                        result = True
                    else:
                        result = any([col != None for col in row]) # are they all None?
                # If result, then append the row
                if result:
                    if (self.limit is None) or (self.limit[0] <= ROWNUM < self.limit[1]):
                        if self.action == "SELECT":
                            if not self.flat:
                                # Join by rows:
                                products = []
                                columns = []
                                count = 0
                                for col in row:
                                    if ((isinstance(col, Struct) and isinstance(col.struct, list) and len(col.struct) > 0) or
                                        (isinstance(col, list) and len(col) > 0)):
                                        products.append(col)
                                        columns.append(count)
                                    count += 1
                                if len(products) > 0:
                                    current = self.clean(row, self.columns)
                                    for items in itertools.product(*products):
                                        for i in range(len(items)):
                                            current[columns[i]] = self.stringify(items[i])
                                        table.row(*current, link=(item.__class__.__name__, item.handle))
                                        self.select += 1
                                else:
                                    table.row(*self.clean(row, self.columns), link=(item.__class__.__name__, item.handle))
                                    self.select += 1
                            else:
                                table.row(*self.clean(row, self.columns), link=(item.__class__.__name__, item.handle))
                                self.select += 1
                        elif self.action == "UPDATE":
                            # update table set col=val, col=val where expr;
                            table.row(*self.clean(row, self.columns), link=(item.__class__.__name__, item.handle))
                            self.select += 1
                            for i in range(len(self.setcolumns)):
                                struct.setitem(self.setcolumns[i], eval(self.values[i], env), trans=trans)
                        elif self.action == "DELETE":
                            table.row(*self.clean(row, self.columns))
                            self.select += 1
                            self.database.remove_instance(item, trans)
                        else:
                            raise AttributeError("unknown command: '%s'", self.action)
                    ROWNUM += 1
                    if (self.limit is not None) and (ROWNUM >= self.limit[1]):
                        break

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

