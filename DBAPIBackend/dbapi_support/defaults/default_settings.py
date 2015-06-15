#from dbapi_support.postgresql import Postgresql
#dbapi = Postgresql(dbname='mydb', user='postgres',
#                   host='localhost', password='PASSWORD')

from dbapi_support.sqlite import Sqlite
path_to_db = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                        'sqlite.db')  
dbapi = Sqlite(path_to_db)
