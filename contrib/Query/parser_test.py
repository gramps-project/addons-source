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
from gramps.gen.merge.diff import import_as_dict, Struct
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
    def test_parser1(self):
        self.do_test(
            "select * from person;",
            table="person",
            columns=["*"],
            action="SELECT",
            values=[],
            where=None,
        )

    def test_parser2(self):
        self.do_test(
            "\n\tselect\t*\tfrom\ttable\n;",
            table="table",
            columns=["*"],
            action="SELECT",
            values=[],
            where=None,
        )

    def test_parser3(self):
        self.do_test(
            "from person select *;",
            table="person",
            columns=["*"],
            action="SELECT",
            values=[],
            where=None,
        )
        
    def test_parser4(self):
        self.do_test(
            "select * from family where x == 1;",
            table="family",
            columns=["*"],
            where="x == 1",
            action="SELECT",
        )
        
    def test_parser5(self):
        self.do_test(
            "select a, b, c from table;",
            table="table",
            columns=["a", "b", "c"],
            action="SELECT",
        )
        
    def test_parser6(self):
        self.do_test(
            "from table select a, b, c;",
            table="table",
            columns=["a", "b", "c"],
            action="SELECT",
        )
        
    def test_parser7(self):
        self.do_test(
            "select a.x.y[0], b.f[5], c[0] from table;",
            table="table",
            columns=["a.x.y[0]", "b.f[5]", "c[0]"],
            action="SELECT",
        )
        
    def test_parser8(self):
        self.do_test(
            "select a.x.y[0] as X, b.f[5] as apple, c[0] from table;",
            table="table",
            aliases={"a.x.y[0]":"X", "b.f[5]": "apple"},
            columns=["a.x.y[0]", "b.f[5]", "c[0]"],
            action="SELECT",
        )
        
    def test_parser9(self):
        self.do_test(
            "from table select a.x.y[0] as X, b.f[5] as apple, c[0];",
            table="table",
            aliases={"a.x.y[0]":"X", "b.f[5]": "apple"},
            columns=["a.x.y[0]", "b.f[5]", "c[0]"],
            action="SELECT",
        )
        
    def test_parser10(self):
        self.do_test(
            "delete from table where test in col[0];",
            table="table",
            where="test in col[0]",
            action ="DELETE",
        )
        
    def test_parser11(self):
        self.do_test(
            "delete from table where ',' in a.b.c;",
            table="table",
            where="',' in a.b.c",
            action ="DELETE",
        )
        
    def test_parser12(self):
        self.do_test(
            "update table set a=1, b=2 where test is in col[0];",
            table="table",
            where="test is in col[0]",
            setcolumns=["a", "b"],
            values=["1", "2"],
            action="UPDATE",
        )
        
    def test_parser13(self):
        self.do_test(
            "select gramps_id, primary_name.first_name, primary_name.surname_list[0].surname from person;",
            table="person",
            where=None,
            columns=["gramps_id", "primary_name.first_name", "primary_name.surname_list[0].surname"],
            action="SELECT",
        )
        
    def test_parser14(self):
        self.do_test(
            "from person select gramps_id, primary_name.first_name, primary_name.surname_list[0].surname;",
            table="person",
            where=None,
            columns=["gramps_id", "primary_name.first_name", "primary_name.surname_list[0].surname"],
            action="SELECT",
        )

    def test_parser15(self):
        self.do_test(
            "select primary_name.first_name from person",
            table="person",
            where=None,
            columns=["primary_name.first_name"],
            action="SELECT",
        )

    def test_parser16(self):
        self.do_test(
            'update person SET primary_name.first_name = "12" where primary_name.first_name == "Emma";',
            table="person",
            where='primary_name.first_name == "Emma"',
            setcolumns=["primary_name.first_name"],
            values=[repr("12")],
            action="UPDATE",
            )

    def test_parser17(self):
        self.do_test(
            'update person SET primary_name.first_name=12 where primary_name.first_name == "Emma";',
            table="person",
            where='primary_name.first_name == "Emma"',
            setcolumns=["primary_name.first_name"],
            values=["12"],
            action="UPDATE",
        )
        
    def test_parser18(self):
        self.do_test(
            "UPDATE person SET private = (False or True) "
            "from person "
            "where primary_name.first_name == 'XXX';", 
            table="person",
            where="primary_name.first_name == 'XXX'", 
            setcolumns=["private"],
            values=["(False or True)"],
        )

    def test_parser19(self):
        self.do_test(
            "SELECT * from person LIMIT 5",
            table="person",
            limit=(0,5),
            where=None,
            columns=["*"],
        )

    def test_parser20(self):
        self.do_test(
            "SELECT * from person LIMIT 10, 20",
            table="person",
            limit=(10,20),
            where=None,
            columns=["*"],
        )

    def test_parser21(self):
        self.do_test(
            "UPDATE person SET private = (False or False) "
            "from person "
            "where primary_name.first_name == 'XXX';", 
            table="person",
            where="primary_name.first_name == 'XXX'", 
            setcolumns=["private"],
            values=["(False or False)"],
        )

class Table:
    def __init__(self):
        self.data = []

    def row(self, *items):
        self.data.append(items)

class StructTest(unittest.TestCase):
    DB = import_as_dict(os.environ["GRAMPS_RESOURCES"] + "/example/gramps/data.gramps", User())

    def __init__(self, *args, **kwargs):
        self.dbi = DBI(StructTest.DB, None) # no document here
        self.dbi.sdb = SimpleAccess(StructTest.DB)
        self.pcount = len(StructTest.DB._tables["Person"]["handles_func"]())
        unittest.TestCase.__init__(self, *args, **kwargs)

    def runTest(self): # for python -i
        pass

    def test_struct1(self):
        with StructTest.DB._tables["Person"]["cursor_func"]() as cursor:
            for handle, person in cursor:
                p = StructTest.DB._tables["Person"]["class_func"](person)
                if p and len(p.parent_family_list) > 0:
                    person_with_parents = p
                    break
        to_struct = person_with_parents.to_struct()
        struct = Struct(to_struct, StructTest.DB)
        self.assertTrue(len(struct.parent_family_list) > 0,
                        "Size not correct: %s is not > than %s" % (len(struct.parent_family_list), 
                                                                   0))

        self.assertTrue(struct.parent_family_list[0].private == False,
                        "Inproper value of private: %s != %s" % (struct.parent_family_list[0].private,
                                                                 False))

    def test_struct2(self):
        with StructTest.DB._tables["Person"]["cursor_func"]() as cursor:
            for handle, person in cursor:
                p = StructTest.DB._tables["Person"]["class_func"](person)
                if p and len(p.event_ref_list) > 0:
                    person_with_events = p
                    break
        to_struct = person_with_events.to_struct()
        struct = Struct(to_struct, StructTest.DB)
        self.assertTrue(len(struct.event_ref_list) > 0,
                        "Size not correct: %s is not > than %s" % (len(struct.event_ref_list), 
                                                                   0))

        self.assertTrue(struct.event_ref_list[0] is not None,
                        "not None: %s is not %s" % (struct.event_ref_list[0],
                                                    None))

        self.assertTrue(struct.event_ref_list[0].ref.description == "Birth of Janis Elaine Green",
                        ".ref.description: %s != %s" % (struct.event_ref_list[0].ref.description,
                                                        "Birth of Janis Elaine Green"))


class SelectTest(unittest.TestCase):
    DB = import_as_dict(os.environ["GRAMPS_RESOURCES"] + "/example/gramps/data.gramps", User())

    def __init__(self, *args, **kwargs):
        self.dbi = DBI(SelectTest.DB, None) # no document here
        self.dbi.sdb = SimpleAccess(SelectTest.DB)
        self.pcount = len(SelectTest.DB._tables["Person"]["handles_func"]())
        self.john_count = 0
        with SelectTest.DB._tables["Person"]["cursor_func"]() as cursor:
            for handle, person in cursor:
                name = SelectTest.DB._tables["Person"]["class_func"](person).get_primary_name()
                if name and "John" in name.first_name:
                    self.john_count += 1
        unittest.TestCase.__init__(self, *args, **kwargs)
    
    def runTest(self): # for python -i
        pass

    def do_test(self, test, string, count):
        self.dbi.parse(string)
        table = Table()
        self.dbi.process_table(table)
        self.assertTrue(len(table.data) == count,
                        "Test #%d, Selected %d records from example.gramps; should have been %d: '%s'" % (
                            test, len(table.data), count, string))

    def test_select1(self):
        self.do_test(1, "select * from person;", self.pcount)

    def test_select2(self):
        self.do_test(2, "select primary_name.first_name "
                     "from person "
                     "where 'John' in primary_name.first_name;", 
                     self.john_count)

    def test_select3(self):
        self.do_test(3, "update person SET primary_name.first_name='XXX' "
                     "where 'John' in primary_name.first_name;", 
                     self.john_count)

    def test_select4(self):
        self.do_test(4, "select primary_name.first_name "
                     "from person "
                     "where primary_name.first_name == 'XXX';", 
                     self.john_count)

    def test_select5(self):
        self.do_test(5, "UPDATE person SET private = (False or False) "
                     "from person "
                     "where primary_name.first_name == 'XXX';", 
                     self.john_count)

    def test_select6(self):
        self.do_test(6, "select private, primary_name "
                     "from person "
                     "where primary_name.first_name == 'XXX' and private;", 
                     0)

    def test_select7(self):
        self.do_test(7, "SELECT private, primary_name "
                     "FROM person "
                     "where primary_name.first_name == 'XXX' and not private;", 
                     self.john_count)

    def test_select8(self):
        self.do_test(8, "UPDATE person SET private = (False or True) "
                     "from person "
                     "where primary_name.first_name == 'XXX';", 
                     self.john_count)

    def test_select9(self):
        self.do_test(9, "select private, primary_name "
                     "from person "
                     "where primary_name.first_name == 'XXX' and private;", 
                     self.john_count)

    def test_select10(self):
        self.do_test(10, "select private, primary_name "
                     "from person "
                     "where primary_name.first_name == 'XXX' and not private;", 
                     0)

    def test_select11(self):
        self.do_test(11,
            "SELECT * from person LIMIT 10, 20",
            10)

    def test_select12(self):
        self.do_test(12,
            "SELECT * from person LIMIT 5",
            5)
        
    def test_select13(self):
        self.do_test(13,
            "SELECT ROWNUM, random.random() from person LIMIT 5",
            5)

    def test_select14(self):
        self.do_test(14, "select * from person where not parent_family_list[0].private;", 38)

    def test_select15(self):
        self.do_test(15.1, "UPDATE person SET private=True WHERE not parent_family_list[0].private;", 38)
        self.do_test(15.2, "SELECT * from person WHERE private;", 38)
        self.do_test(15.3, "UPDATE person SET private=False;", 60)
        self.do_test(15.4, "UPDATE person SET private=False WHERE private;", 0)
        self.do_test(15.5, "UPDATE person SET private=True;", 60)
        self.do_test(15.6, "UPDATE person SET private=True where not private;", 0)

if __name__ == "__main__":
    unittest.main()
