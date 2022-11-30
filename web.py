from pyrogram.errors import ChatAdminRequired, MessageNotModified
from pyrogram.types import ChatPermissions
import logging
from dbhelper import DBHelper
from flask import Flask, request, flash
from flask import render_template
from pyrogram import Client
from challengedata import ChallengeData

app = Flask(__name__)
client = None
_current_challenges = ChallengeData()
_config = dict()
db = DBHelper()
_channel = 0


@app.route("/")
def root():
    return render_template('index.html')


@app.route("/recaptcha", methods=["GET", "POST"])
async def verify():
    # 测试模板用-----------------------------------------------------
    # return render_template('recaptcha.html', sitekey=114514)
    # 测试模板用-----------------------------------------------------

    if request.args.get('challenge') is None:
        flash("没有这条验证数据！", "error")
        return render_template('result.html')
    else:
        challenge_id = request.args.get('challenge')
    try:
        ch_id, challenge_data = _current_challenges.get_by_challenge_id(challenge_id)
    except TypeError:
        flash("没有这条验证数据！", "error")
        return render_template('result.html')

    if challenge_data is None or ch_id is None:
        flash("没有这条验证数据！", "error")
        return render_template('result.html')

    challenge, target_id, timeout_event = challenge_data
    chat_id = challenge.message.chat.id
    msg_id = challenge.message.id

    if chat_id != challenge.message.chat.id:
        flash("未知错误！", "error")
        return render_template('result.html')
    group_config = _config.get(str(chat_id), _config["*"])
    chat_title = challenge.message.chat.title

    if request.method == "POST":
        captcha_response = request.form['g-recaptcha-response']
        if not challenge.verify(captcha_response):
            flash('验证状态异常，请再试一次！', 'error')
            return render_template('recaptcha.html', sitekey=challenge.site_key)
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
                    ))
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
            flash('您已通过验证，欢迎加入本群！如果仍然无法发言，请重启 Telegram 客户端。')
            return render_template('result.html')
    else:
        return render_template('recaptcha.html', sitekey=challenge.site_key)


if __name__ == '__main__':
    app.debug = True
    app.env = 'debug'
    app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'
    app.run(port=5000, host="127.0.0.1")
