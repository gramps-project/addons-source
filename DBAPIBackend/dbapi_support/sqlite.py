import os
import sqlite3

sqlite3.paramstyle = 'qmark'

class Sqlite(object):
    def __init__(self, *args, **kwargs):
        self.connection = sqlite3.connect(*args, **kwargs)

    def execute(self, *args, **kwargs):
        self.cursor = self.connection.execute(*args, **kwargs)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def create(self, sql):
        try:
            self.connect.execute(sql)
        except:
            pass

    def close(self):
        self.connection.close()
