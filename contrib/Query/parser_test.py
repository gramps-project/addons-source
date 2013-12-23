## PYTHONPATH=/PATHTO/gramps/master GRAMPS_RESOURCES=/PATHTO/gramps/master/ python parser_test.py

from QueryQuickview import DBI

import unittest

dbi = DBI(None, None)

def Parser(string):
    dbi.parse(string)
    return dbi

class ParseTest(unittest.TestCase):

    def do_test(self, p, **kwargs):
        for kw in kwargs:
            self.assertTrue(getattr(p, kw) == kwargs[kw],
                            "QUERY: %s %s, %s != %s" % (p.query,
                                                    kw, 
                                                    getattr(p, kw), 
                                                    kwargs[kw]))

    def test_parser(self):
        p = Parser("select * from table;")
        self.do_test(p, 
                     table="table",
                     columns=["*"],
                     action="SELECT",
                     values=[],
                     where=None,
                 )

        p = Parser("\n\tselect\t*\tfrom\ttable\n;")
        self.do_test(p, 
             table="table",
             columns=["*"],
             action="SELECT",
             values=[],
             where=None,
         )

        p = Parser("from table select *;")
        self.do_test(p, 
             table="table",
             columns=["*"],
             action="SELECT",
             values=[],
             where=None,
         )
        
        p=Parser("select * from table where x == 1;")
        self.do_test(p,
             table="table",
             columns=["*"],
             where="x == 1",
             action="SELECT",
         )
        
        p=Parser("select a, b, c from table;")
        self.do_test(p,
             table="table",
             columns=["a", "b", "c"],
             action="SELECT",
         )
        
        p=Parser("from table select a, b, c;")
        self.do_test(p,
             table="table",
             columns=["a", "b", "c"],
             action="SELECT",
         )
        
        p=Parser("select a.x.y.0, b.f.5, c.0 from table;")
        self.do_test(p,
             table="table",
             columns=["a.x.y.0", "b.f.5", "c.0"],
             action="SELECT",
         )
        
        p=Parser("select a.x.y.0 as X, b.f.5 as apple, c.0 from table;")
        self.do_test(p,
             table="table",
             aliases={"a.x.y.0":"X", "b.f.5": "apple"},
             columns=["a.x.y.0", "b.f.5", "c.0"],
             action="SELECT",
         )
        
        p=Parser("from table select a.x.y.0 as X, b.f.5 as apple, c.0;")
        self.do_test(p,
             table="table",
             aliases={"a.x.y.0":"X", "b.f.5": "apple"},
             columns=["a.x.y.0", "b.f.5", "c.0"],
             action="SELECT",
         )
        
        p=Parser("delete from table where test in col[0];")
        self.do_test(p,
             table="table",
             where="test in col[0]",
             action ="DELETE",
         )
        
        p=Parser("delete from table where ',' in a.b.c;")
        self.do_test(p,
             table="table",
             where="',' in a.b.c",
             action ="DELETE",
         )
        
        p=Parser("update table set a=1, b=2 where test is in col[0];")
        self.do_test(p,
             table="table",
             where="test is in col[0]",
             setcolumns=["a", "b"],
             values=["1", "2"],
             action="UPDATE",
         )

        p=Parser("select gramps_id, primary_name.first_name, primary_name.surname_list.0.surname from person;")
        self.do_test(p,
                     table="person",
                     where=None,
                     columns=["gramps_id", "primary_name.first_name", "primary_name.surname_list.0.surname"],
                     action="SELECT",
                 )

        p=Parser("from person select gramps_id, primary_name.first_name, primary_name.surname_list.0.surname;")
        self.do_test(p,
                     table="person",
                     where=None,
                     columns=["gramps_id", "primary_name.first_name", "primary_name.surname_list.0.surname"],
                     action="SELECT",
                 )

if __name__ == "__main__":
    unittest.main()
