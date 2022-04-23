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
        challenge_failed_action TEXT,
        challenge_timeout_action TEXT,
        challenge_timeout INTEGER,
        challenge_type TEXT,
        enable_global_blacklist INTEGER,
        enable_third_party_blacklist INTEGER
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

    def get_group_config(self, group_id, field: str = 'all'):
        """
        获取群配置，默认返回所有配置，可以指定返回某个配置
        field: 值为 challenge_failed_action,
        challenge_timeout_action,
        challenge_timeout,
        challenge_type,
        enable_global_blacklist,
        enable_third_party_blacklist

        return: 如果指定了 field，返回指定的配置，否则返回所有配置

        """

        stmt = "SELECT * FROM group_config WHERE group_id == (?)"
        args = group_id
        cur = self.conn.cursor()
        try:
            cur.execute(stmt, (args,))
            result = cur.fetchone()
            if result is None:
                return None
            elif field == 'challenge_failed_action':
                return result[1]
            elif field == 'challenge_timeout_action':
                return result[2]
            elif field == 'challenge_timeout':
                return result[3]
            elif field == 'challenge_type':
                return result[4]
            elif field == 'enable_global_blacklist':
                return result[5]
            elif field == 'enable_third_party_blacklist':
                return result[6]
            elif field == 'all':
                group_config = {'challenge_failed_action': result[1], 'challenge_timeout_action': result[2],
                                'challenge_timeout': result[3], 'challenge_type': result[4],
                                'enable_global_blacklist': result[5], 'enable_third_party_blacklist': result[6]}
                # remove None value
                null_key = [i for i in group_config if group_config[i] is None]
                for key in null_key:
                    group_config.pop(key)
                return group_config
            else:
                return None
        except sqlite3.Error as e:
            logging.error(str(e))
            return None

    def new_group_config(self, group_id):
        stmt = "INSERT OR REPLACE INTO group_config (group_id) VALUES (?)"
        args = (group_id,)
        try:
            self.conn.execute(stmt, args)
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(str(e))
            return False

    def set_group_config(self, group_id, key, value):
        if self.get_group_config(group_id) is None:
            self.new_group_config(group_id)

        value_type = 'str'

        if key == 'challenge_failed_action':
            if value != 'ban' and value != 'kick':
                return False
            stmt = "UPDATE group_config SET challenge_failed_action = (?) WHERE group_id = (?)"
        elif key == 'challenge_timeout_action':
            if value != 'ban' and value != 'kick' and value != 'mute':
                return False
            stmt = "UPDATE group_config SET challenge_timeout_action = (?) WHERE group_id = (?)"
        elif key == 'challenge_timeout':
            stmt = "UPDATE group_config SET challenge_timeout = (?) WHERE group_id = (?)"
            value_type = 'int'
        elif key == 'challenge_type':
            if value != 'math' and value != 'reCAPTCHA':
                return False
            stmt = "UPDATE group_config SET challenge_type = (?) WHERE group_id = (?)"
        elif key == 'enable_global_blacklist':
            stmt = "UPDATE group_config SET enable_global_blacklist = (?) WHERE group_id = (?)"
            value_type = 'bool'
        elif key == 'enable_third_party_blacklist':
            stmt = "UPDATE group_config SET enable_third_party_blacklist = (?) WHERE group_id = (?)"
            value_type = 'bool'
        else:
            return False

        if value_type == 'int':
            try:
                value = int(value)
            except ValueError:
                return False
        if value_type == 'bool':
            try:
                value = int(value)
                print(value)
                if value != 0 and value != 1:
                    return False
            except ValueError:
                return False

        args = (value, group_id)
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
