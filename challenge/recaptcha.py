from configparser import ConfigParser
from pyrogram.types import (InlineKeyboardButton, Message)
import requests
import json
import uuid
import random

cf = ConfigParser()
cf.read("auth.ini", encoding="utf-8")


class ReCAPTCHA:
    def __init__(self):
        self.site_key = cf.get("reCAPTCHA", "site_key")
        self.secret_key = cf.get("reCAPTCHA", "secret_key")
        self.recaptcha_id = str(uuid.uuid4().hex)  # 在用户启动 bot 后随机生成的一个 id, 用于 recaptcha 链接
        self.auth_url = cf.get("reCAPTCHA", "base_url") + "/recaptcha?challenge=" + str(self.recaptcha_id)
        self.bot_url = 'https://t.me/' + cf.get("bot", "username") + '?start='
        self.message = None

    def get_site_key(self):
        return self.site_key

    def get_secret_key(self):
        return self.secret_key

    def verify(self, captcha_response):
        """ Validating recaptcha response from google server
            Returns True captcha test passed for submitted form else returns False.
            https://techmonger.github.io/5/python-flask-recaptcha/
        """
        secret = self.secret_key
        payload = {'response': captcha_response, 'secret': secret}
        response = requests.post("https://www.google.com/recaptcha/api/siteverify", payload)
        response_text = json.loads(response.text)
        return response_text['success']

    def generate_button(self, group_config, chat_id):
        link_to_bot = [[InlineKeyboardButton(text="开始验证", url=self.bot_url + str(chat_id))]]
        return link_to_bot + [[
            InlineKeyboardButton(group_config["msg_approve_manually"],
                                 callback_data=b"+"),
            InlineKeyboardButton(group_config["msg_refuse_manually"],
                                 callback_data=b"-"),
        ]]

    def generate_auth_button(self):
        return [[InlineKeyboardButton(text="开始验证",
                                      url=self.auth_url)]]
