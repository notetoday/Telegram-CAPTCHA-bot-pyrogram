import threading

from challenge.math import Math
from challenge.recaptcha import ReCAPTCHA


class ChallengeData:
    def __init__(self):
        self.data = dict()
        self.t_lock = threading.Lock()

    def __setitem__(self, key, value):
        with self.t_lock:
            self.data[key] = value

    def __getitem__(self, item: str):
        with self.t_lock:
            value = self.data.get(item)
        return value

    def __str__(self):
        output = []
        with self.t_lock:
            count = len(self.data)
            output.append("ChallengeCount: " + str(count))
            for ch_id, challenge_data in self.data.items():
                output.append("验证 ID：{}".format(ch_id))
                output.append("验证数据：{}".format(str(challenge_data)) + "\n")
        return str(output)

    def delete(self, data):
        with self.t_lock:
            deleted = self.data.pop(data, None)
        return deleted

    def get(self, ch_id):
        with self.t_lock:
            challenge_data = self.data.get(ch_id)
        return challenge_data

    def get_by_user_and_chat_id(self, user_id, chat_id):
        with self.t_lock:
            for ch_id, challenge_data in self.data.items():
                challenge_chat_id = int(ch_id.split("|")[0])
                if user_id == challenge_data[1] and chat_id == challenge_chat_id:
                    return ch_id, challenge_data
            return None, None

    def get_by_challenge_id(self, challenge_id: str):
        """
        Get all data by challenge id
        :param challenge_id: recaptcha challengeid
        :return: tuple(key, value)
        """
        with self.t_lock:
            for ch_id, challenge_data in self.data.items():
                if isinstance(challenge_data[0], ReCAPTCHA):
                    if challenge_id == challenge_data[0].recaptcha_id:
                        break
            else:
                return None
            challenge_data = self.data.get(ch_id)
        return ch_id, challenge_data

    def is_duplicate(self, user_id: int, chat_id: int):
        """
        检查当前用户在当前群是否有未完成的订阅，用来防止奇怪的原因重复发送多次验证
        :param user_id 目标用户 id
        :param chat_id 目标群组 id
        :return: True 重复 / False 不重复
        """
        with self.t_lock:
            for ch_id, v in self.data.items():
                challenge_chat_id = int(ch_id.split("|")[0])
                if challenge_chat_id == chat_id and user_id == v[1]:
                    return True
        return False
