import sqlite3
import logging


class DBHelper:
    def __init__(self, dbname="data.sqlite"):
        self.dbname = dbname
        self.conn = sqlite3.connect(dbname)

    def setup(self):
        stmt = ('''CREATE TABLE IF NOT EXISTS user
       (user_id int PRIMARY KEY     NOT NULL,
        last_try int default 0,
        blacklist  int  default 1 NOT NULL,
        try_count int default 1);''')
        try:
            self.conn.execute(stmt)
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(str(e))

    def get_user_status(self, user_id):
        stmt = "SELECT blacklist FROM user WHERE user_id == (?)"
        cur = self.conn.cursor()
        try:
            cur.execute(stmt, (user_id,))
            result = cur.fetchone()
        except sqlite3.Error as e:
            logging.error(str(e))
            return None
        if result is None:
            return 0
        else:
            return result[0]

    def get_last_try(self, user_id):
        stmt = "SELECT last_try FROM user WHERE user_id == (?)"
        cur = self.conn.cursor()
        try:
            cur.execute(stmt, (user_id,))
            result = cur.fetchone()
        except sqlite3.Error as e:
            logging.error(str(e))
            return None
        if result is None:
            return 0
        else:
            return result[0]

    def update_last_try(self, time, user_id):
        stmt = "UPDATE user SET last_try = (?) WHERE user_id == (?)"
        cur = self.conn.cursor()
        try:
            cur.execute(stmt, (time, user_id,))
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(str(e))

    def try_count_plus_one(self, user_id):
        stmt = "UPDATE user SET try_count = try_count + 1 WHERE user_id == (?)"
        cur = self.conn.cursor()
        try:
            cur.execute(stmt, (user_id,))
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(str(e))

    def new_blacklist(self, time, user_id):
        stmt = "INSERT OR REPLACE INTO user (last_try, user_id) VALUES (?,?)"
        try:
            self.conn.execute(stmt, (time, user_id,))
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(str(e))

    def blacklist(self, user_id):
        stmt = "UPDATE user SET blacklist = 1 where user_id == (?)"
        args = user_id
        try:
            self.conn.execute(stmt, (args,))
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(str(e))

    def whitelist(self, user_id):
        stmt = "UPDATE user SET blacklist = 0 where user_id == (?)"
        args = user_id
        try:
            self.conn.execute(stmt, (args,))
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(str(e))

    def get_try_count(self, user_id):
        stmt = "SELECT try_count FROM user WHERE user_id == (?)"
        cur = self.conn.cursor()
        try:
            cur.execute(stmt, (user_id,))
            result = cur.fetchone()
        except sqlite3.Error as e:
            logging.error(str(e))
            return None
        if result is None:
            return 0
        else:
            return result[0]

    def get_all_user_ids(self):
        stmt = "SELECT user_id FROM user"
        cur = self.conn.cursor()
        try:
            cur.execute(stmt)
            result = [i[0] for i in cur.fetchall()]
            # cur.fetchall() 是返回一个 tuples，只能用这个方法了转成 list 处理了，如果有更好的方法麻烦告诉我
        except sqlite3.Error as e:
            logging.error(str(e))
            return None
        if result is None:
            return 0
        else:
            return result

    def delete_user(self, user_id):
        stmt = "DELETE FROM user WHERE user_id = (?)"
        args = user_id
        try:
            self.conn.executemany(stmt, args)
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(str(e))
