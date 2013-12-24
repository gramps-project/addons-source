#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2013  Doug Blank <doug.blank@gmail.com>
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

## PYTHONPATH=/PATHTO/gramps/master GRAMPS_RESOURCES=/PATHTO/gramps/master/ python parser_test.py

from QueryQuickview import DBI
from gramps.gen.merge.diff import import_as_dict
from gramps.cli.user import User
from gramps.gen.simple import SimpleAccess

import unittest
import os

class ParseTest(unittest.TestCase):
    def do_test(self, string, **kwargs):
        p = DBI(None, None)
        p.parse(string)
        for kw in kwargs:
            self.assertTrue(getattr(p, kw) == kwargs[kw],
                            "QUERY: '%s' checking '%s', %s != %s" % (
                                p.query,
                                kw, 
                                getattr(p, kw), 
                                kwargs[kw]))
    def test_parser(self):
        self.do_test(
            "select * from person;",
            table="person",
            columns=["*"],
            action="SELECT",
            values=[],
            where=None,
        )

        self.do_test(
            "\n\tselect\t*\tfrom\ttable\n;",
            table="table",
            columns=["*"],
            action="SELECT",
            values=[],
            where=None,
        )

        self.do_test(
            "from person select *;",
            table="person",
            columns=["*"],
            action="SELECT",
            values=[],
            where=None,
        )
        
        self.do_test(
            "select * from family where x == 1;",
            table="family",
            columns=["*"],
            where="x == 1",
            action="SELECT",
        )
        
        self.do_test(
            "select a, b, c from table;",
            table="table",
            columns=["a", "b", "c"],
            action="SELECT",
        )
        
        self.do_test(
            "from table select a, b, c;",
            table="table",
            columns=["a", "b", "c"],
            action="SELECT",
        )
        
        self.do_test(
            "select a.x.y.0, b.f.5, c.0 from table;",
            table="table",
            columns=["a.x.y.0", "b.f.5", "c.0"],
            action="SELECT",
        )
        
        self.do_test(
            "select a.x.y.0 as X, b.f.5 as apple, c.0 from table;",
            table="table",
            aliases={"a.x.y.0":"X", "b.f.5": "apple"},
            columns=["a.x.y.0", "b.f.5", "c.0"],
            action="SELECT",
        )
        
        self.do_test(
            "from table select a.x.y.0 as X, b.f.5 as apple, c.0;",
            table="table",
            aliases={"a.x.y.0":"X", "b.f.5": "apple"},
            columns=["a.x.y.0", "b.f.5", "c.0"],
            action="SELECT",
        )
        
        self.do_test(
            "delete from table where test in col[0];",
            table="table",
            where="test in col[0]",
            action ="DELETE",
        )
        
        self.do_test(
            "delete from table where ',' in a.b.c;",
            table="table",
            where="',' in a.b.c",
            action ="DELETE",
        )
        
        self.do_test(
            "update table set a=1, b=2 where test is in col[0];",
            table="table",
            where="test is in col[0]",
            setcolumns=["a", "b"],
            values=["1", "2"],
            action="UPDATE",
        )
        
        self.do_test(
            "select gramps_id, primary_name.first_name, primary_name.surname_list.0.surname from person;",
            table="person",
            where=None,
            columns=["gramps_id", "primary_name.first_name", "primary_name.surname_list.0.surname"],
            action="SELECT",
        )
        
        self.do_test(
            "from person select gramps_id, primary_name.first_name, primary_name.surname_list.0.surname;",
            table="person",
            where=None,
            columns=["gramps_id", "primary_name.first_name", "primary_name.surname_list.0.surname"],
            action="SELECT",
        )

        self.do_test(
            "select primary_name.first_name from person",
            table="person",
            where=None,
            columns=["primary_name.first_name"],
            action="SELECT",
        )

        self.do_test(
            'update person SET primary_name.first_name = "12" where primary_name.first_name == "Emma";',
            table="person",
            where='primary_name.first_name == "Emma"',
            setcolumns=["primary_name.first_name"],
            values=[repr("12")],
            action="UPDATE",
            )

        self.do_test(
            'update person SET primary_name.first_name=12 where primary_name.first_name == "Emma";',
            table="person",
            where='primary_name.first_name == "Emma"',
            setcolumns=["primary_name.first_name"],
            values=["12"],
            action="UPDATE",
        )
        
        self.do_test(
            "UPDATE person SET private = (False or True) "
            "from person "
            "where primary_name.first_name == 'XXX';", 
            table="person",
            where="primary_name.first_name == 'XXX'", 
            setcolumns=["private"],
            values=["False or True"],
        )

        self.do_test(
            "SELECT * from person LIMIT 5",
            table="person",
            limit=(1,5),
            where=None,
            columns=["*"],
        )

        self.do_test(
            "SELECT * from person LIMIT 10, 20",
            table="person",
            limit=(10,20),
            where=None,
            columns=["*"],
        )

class Table:
    def __init__(self):
        self.data = []

    def row(self, *items):
        self.data.append(items)

class SelectTest(unittest.TestCase):
    DB = import_as_dict(os.environ["GRAMPS_RESOURCES"] + "/example/gramps/example.gramps", User())
    
    def runTest(self):
        pass

    def do_test(self, string, count=None):
        dbi = DBI(SelectTest.DB, None) # no document here
        dbi.sdb = SimpleAccess(SelectTest.DB)
        dbi.parse(string)
        table = Table()
        dbi.process_table(table)
        if count is not None:
            self.assertTrue(len(table.data) == count,
                            "Selected %d records from example.gramps; should have been %d: '%s'" % (
                                len(table.data), count, string))
        return dbi

    def test_select(self):
        count = len(SelectTest.DB._tables["Person"]["handles_func"]())
        self.do_test("select * from person;", count)

        count = 0
        with SelectTest.DB._tables["Person"]["cursor_func"]() as cursor:
            for handle, person in cursor:
                name = SelectTest.DB._tables["Person"]["class_func"](person).get_primary_name()
                if name and "John" in name.first_name:
                    count += 1

        self.do_test("select primary_name.first_name "
                     "from person "
                     "where 'John' in primary_name.first_name;", 
                     count)

        self.do_test("update person SET primary_name.first_name='XXX' "
                     "where 'John' in primary_name.first_name;", 
                     count)

        self.do_test("select primary_name.first_name "
                     "from person "
                     "where primary_name.first_name == 'XXX';", 
                     count)

        self.do_test("UPDATE person SET private = (False or False) "
                     "from person "
                     "where primary_name.first_name == 'XXX';", 
                     count)

        self.do_test("select private, primary_name "
                     "from person "
                     "where primary_name.first_name == 'XXX' and private;", 
                     0)

        self.do_test("select private, primary_name "
                     "from person "
                     "where primary_name.first_name == 'XXX' and not private;", 
                     count)

        self.do_test("UPDATE person SET private = (False or True) "
                     "from person "
                     "where primary_name.first_name == 'XXX';", 
                     count)

        self.do_test("select private, primary_name "
                     "from person "
                     "where primary_name.first_name == 'XXX' and private;", 
                     count)

        self.do_test("select private, primary_name "
                     "from person "
                     "where primary_name.first_name == 'XXX' and not private;", 
                     0)

        self.do_test(
            "SELECT * from person LIMIT 10, 20",
            10)

        self.do_test(
            "SELECT * from person LIMIT 5",
            5)
        
if __name__ == "__main__":
    unittest.main()
