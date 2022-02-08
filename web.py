from pyrogram.errors import ChatAdminRequired
from pyrogram.types import ChatPermissions

from dbhelper import DBHelper
from flask import Flask, request, flash
from flask import render_template
from pyrogram import Client
import threading

web = Flask(__name__)
client = Client('web')
_current_recaptcha = dict()
db = DBHelper()
_cch_lock = threading.Lock()


@web.route("/")
def hello_world():
    global client
    if not client.is_connected:
        return '<h1>Not connected</h1>'
    return str(client.get_me())


@web.route("/recaptcha", methods=["GET", "POST"])
def verify():
    if request.args.get('challenge') is None:
        return '<h1>Welcome pages</h1>'

    _cch_lock.acquire()
    challenge_data = _current_recaptcha.get(request.args.get('challenge'))
    _cch_lock.release()

    if not challenge_data:
        return '<h1>Challenge not found</h1>'
    else:
        challenge, target_id, timeout_event = challenge_data

    if request.method == "POST":
        print(request.form)
        captcha_response = request.form['g-recaptcha-response']
        if not challenge.verify(captcha_response):
            flash('Invalid reCAPTCHA status. Please try again.')
            return '<h1>Invalid reCAPTCHA status. Please try again.</h1>'
        else:
            timeout_event.stop()
            try:
                client.restrict_chat_member(
                    challenge.chat_id,
                    target_id,
                    permissions=ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_other_messages=True,
                        can_send_polls=True,
                        can_add_web_page_previews=True,
                        can_change_info=True,
                        can_invite_users=True,
                        can_pin_messages=True))
            except ChatAdminRequired:
                pass
            return '<h1>Success</h1>'
    else:
        print(request.args.get('challenge'))
        print('current challenges:', _current_recaptcha)
        return render_template('recaptcha.html', sitekey=challenge.site_key)


if __name__ == '__main__':
    web.run(port=8181, host="127.0.0.1")
