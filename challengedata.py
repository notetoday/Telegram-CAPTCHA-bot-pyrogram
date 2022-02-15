import threading


class ChallengeData:
    def __init__(self):
        self.data = dict()
        self.t_lock = threading.Lock()

    def __setitem__(self, key, value):
        self.t_lock.acquire()
        self.data[key] = value
        self.t_lock.release()

    def __getitem__(self, item: str):
        self.t_lock.acquire()
        value = self.data.get(item)
        self.t_lock.release()
        return value

    def __str__(self):
        output = []
        self.t_lock.acquire()
        count = len(self.data)
        output.append("ChallengeCount: " + str(count))
        for ch_id, challenge_data in self.data.items():
            output.append("验证 ID：{}".format(ch_id))
            output.append("验证数据：{}".format(challenge_data) + "\n")
        self.t_lock.release()
        return str(output)

    def delete(self, data):
        self.t_lock.acquire()
        deleted = self.data.pop(data, None)
        self.t_lock.release()
        return deleted

    def get(self, ch_id):
        self.t_lock.acquire()
        challenge_data = self.data.get(ch_id)
        self.t_lock.release()
        return challenge_data

    def get_by_user_and_chat_id(self, user_id, chat_id):
        self.t_lock.acquire()
        for ch_id, challenge_data in self.data.items():
            challenge_chat_id = int(ch_id.split("|")[0])
            if user_id == challenge_data[1] and chat_id == challenge_chat_id:
                self.t_lock.release()
                return ch_id, challenge_data
        self.t_lock.release()
        return None, None

    def get_by_challenge_id(self, challenge_id: str):
        """
        Get all data by challenge id
        :param challenge_id: recaptcha challengeid
        :return: tuple(key, value)
        """
        self.t_lock.acquire()
        for ch_id, value in self.data.items():
            if challenge_id == value[0].recaptcha_id:
                break
        else:
            self.t_lock.release()
            return None
        challenge_data = self.data.get(ch_id)
        self.t_lock.release()
        return ch_id, challenge_data

    def is_duplicate(self, user_id: int, chat_id: int):
        """
        检查当前用户在当前群是否有未完成的订阅，用来防止奇怪的原因重复发送多次验证
        :param user_id 目标用户 id
        :param chat_id 目标群组 id
        :return: True 重复 / False 不重复
        """
        self.t_lock.acquire()
        for ch_id, v in self.data.items():
            challenge_chat_id = int(ch_id.split("|")[0])
            if challenge_chat_id == chat_id and user_id == v[1]:
                self.t_lock.release()
                return True
        self.t_lock.release()
        return False
