from pyrogram.errors import ChatAdminRequired, MessageNotModified
from pyrogram.types import ChatPermissions
import logging
from dbhelper import DBHelper
from flask import Flask, request, flash
from flask import render_template
from pyrogram import Client
from challengedata import ChallengeData

web = Flask(__name__)
client = Client('web')
_current_challenges = ChallengeData()
_config = dict()
db = DBHelper()
_channel = 0


@web.route("/")
def hello_world():
    if not client.is_connected:
        return '<h1>Not connected</h1>'
    return str(client.get_me())


@web.route("/recaptcha", methods=["GET", "POST"])
async def verify():
    if request.args.get('challenge') is None:
        return '<h1>Welcome pages</h1>'
    else:
        challenge_id = request.args.get('challenge')

    try:
        ch_id, challenge_data = _current_challenges.get_by_challenge_id(challenge_id)
    except TypeError:
        return '<h1>Challenge not found</h1>'

    if challenge_data is None or ch_id is None:
        return '<h1>Challenge not found</h1>'
    challenge, target_id, timeout_event = challenge_data

    chat_id = challenge.message.chat.id
    msg_id = challenge.message.message_id

    if chat_id != challenge.message.chat.id:
        return '<h1>Unknown error</h1>'
    group_config = _config.get(str(chat_id), _config["*"])
    chat_title = challenge.message.chat.title

    if request.method == "POST":
        captcha_response = request.form['g-recaptcha-response']
        if not challenge.verify(captcha_response):
            flash('Invalid reCAPTCHA status. Please try again.')
            return '<h1>Invalid reCAPTCHA status. Please try again.</h1>'
        else:
            timeout_event.stop()
            try:
                await client.restrict_chat_member(
                    chat_id,
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

            _current_challenges.delete(ch_id)

            try:
                await client.send_message(
                    int(_channel),
                    _config["msg_passed_answer"].format(
                        targetuserid=str(target_id),
                        groupid=str(chat_id),
                        grouptitle=str(chat_title),
                    ),
                    parse_mode="Markdown",
                )
            except Exception as e:
                logging.error(str(e))

            if group_config["delete_passed_challenge"]:
                await client.delete_messages(chat_id, msg_id)
            else:
                try:
                    await client.edit_message_text(
                        chat_id=chat_id,
                        message_id=msg_id,
                        text=group_config["msg_challenge_passed"],
                        reply_markup=None)
                except MessageNotModified as e:
                    await client.send_message(int(_channel),
                                              'Bot 运行时发生异常: `' + str(e) + "`")
            return '<h1>Success</h1>'
    else:
        return render_template('recaptcha.html', sitekey=challenge.site_key)


if __name__ == '__main__':
    web.run(port=8181, host="127.0.0.1")
