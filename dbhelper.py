import sqlite3
import logging


class DBHelper:
    def __init__(self, dbname="data.sqlite"):
        self.dbname = dbname
        self.conn = sqlite3.connect(dbname)

    def setup(self):
        stmt = ('''
        CREATE TABLE IF NOT EXISTS user
        (
        user_id INTEGER PRIMARY KEY NOT NULL,
        last_try INTEGER default 0,
        blacklist  INTEGER  default 1 NOT NULL,
        try_count INTEGER default 1
        );
        
        CREATE TABLE IF NOT EXISTS group_config
        (
        group_id INTEGER PRIMARY KEY NOT NULL,
        captcha_failed_action TEXT,
        captcha_timeout_action TEXT,
        captcha_timeout INTEGER,
        enable_global_blacklist INTEGER,
        enable_regex INTEGER,
        enable_third_party_blacklist INTEGER
        );
        
        CREATE TABLE IF NOT EXISTS regex
        (
        id INTEGER PRIMARY KEY AUTOINCREMENT NULL,
        group_id INTEGER NOT NULL,
        regex BLOB NOT NULL,
        match TEXT NOT NULL,
        action TEXT NOT NULL,
        description TEXT NOT NULL
        );
        ''')
        try:
            self.conn.executescript(stmt)
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

    def new_regex(self, group_id, regex, match, action, description):
        if self.regex_count(group_id) >= 10:
            return False
        stmt = "INSERT OR REPLACE INTO regex (group_id, regex, match, action, description) VALUES (?,?,?,?,?)"
        args = (group_id, regex, match, action, description)
        try:
            self.conn.execute(stmt, args)
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(str(e))
        return True

    def get_regex(self, group_id):
        stmt = "SELECT * FROM regex WHERE group_id == (?)"
        args = group_id
        cur = self.conn.cursor()
        try:
            cur.execute(stmt, (args,))
            result = cur.fetchall()
        except sqlite3.Error as e:
            logging.error(str(e))
            return None
        return result

    def regex_count(self, group_id):
        stmt = "SELECT COUNT(*) FROM regex WHERE group_id == (?)"
        args = group_id
        cur = self.conn.cursor()
        try:
            cur.execute(stmt, (args,))
            result = cur.fetchone()[0]
        except sqlite3.Error as e:
            logging.error(str(e))
            return None
        return result

    def delete_regex(self, rid, group_id):
        stmt = "DELETE FROM regex WHERE id = (?) and group_id = (?)"
        args = (rid, group_id)
        cur = self.conn.cursor()
        try:
            cur.execute(stmt, args)
            rows = cur.rowcount
            self.conn.commit()
            if rows == 0:
                return False
            else:
                return True
        except sqlite3.Error as e:
            logging.error(str(e))
            return None

    def get_group_config(self, group_id):
        stmt = "SELECT * FROM group_config WHERE group_id == (?)"
        args = group_id
        cur = self.conn.cursor()
        try:
            cur.execute(stmt, (args,))
            result = cur.fetchone()
        except sqlite3.Error as e:
            logging.error(str(e))
            return None

    def new_group_config(self, group_id):
        stmt = "INSERT OR REPLACE INTO group_config (group_id) VALUES (?)"
        args = (group_id,)
        try:
            self.conn.execute(stmt, (args,))
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(str(e))
            return None

    def set_group_config(self, group_id, key, value):
        if self.get_group_config(group_id) is None:
            self.new_group_config(group_id)
        stmt = "UPDATE group_config SET " + key + " = ? WHERE group_id == ?"
        args = (value, group_id)
        try:
            self.conn.execute(stmt, (args,))
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(str(e))
