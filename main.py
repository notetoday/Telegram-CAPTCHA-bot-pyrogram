# !/usr/bin/env python3
# -*- coding: UTF-8 -*-
import asyncio
import json
import logging
import threading
import time
import datetime
from configparser import ConfigParser

from pyrogram import (Client, filters)
from pyrogram.errors import ChatAdminRequired, ChannelPrivate, MessageNotModified, RPCError, BadRequest
from pyrogram.types import (InlineKeyboardMarkup, User, Message, ChatPermissions, CallbackQuery,
                            ChatMemberUpdated)
from Timer import Timer
from challenge.math import Math
from challenge.recaptcha import ReCAPTCHA
from dbhelper import DBHelper
from challengedata import ChallengeData
from waitress import serve

db = DBHelper()

_start_message = "YABE!"
# _challenge_scheduler = sched.scheduler(time, sleep)
_current_challenges = ChallengeData()
_cch_lock = threading.Lock()
_config = dict()
admin_operate_filter = filters.create(lambda _, __, query: query.data.split(" ")[0] in ["+", "-"])

'''
读 只 读 配 置
'''
cf = ConfigParser()  # 启用ConfigParser读取那些启动后即不会再被更改的数据，如BotToken等
cf.read("auth.ini", encoding="utf-8")
_admin_user = cf.getint("bot", "admin")
_token = cf.get("bot", "token")
_api_id = cf.getint("bot", "api_id")
_api_hash = cf.get("bot", "api_hash")
_channel = cf.getint("bot", "channel")
logging.basicConfig(level=logging.INFO)


# 设置一下日志记录，能够在诸如 systemctl status captchabot 这样的地方获得详细输出。

def start_web(client: Client):
    import web
    port = cf.getint('web', 'flask_port')
    host = cf.get('web', 'flask_host')
    web.app.secret_key = cf.get('web', 'flask_secret_key')
    web.client = client
    web._current_challenges = _current_challenges
    web._config = _config
    web._channel = _channel
    if cf.getboolean('web', 'development'):
        web.app.env = 'development '
        web.app.run(host=host, port=port)
    else:
        serve(web.app, host=host, port=port)


def load_config():
    global _config
    with open("config.json", encoding="utf-8") as f:
        _config = json.load(f)


def save_config():
    with open("config.json", "w", encoding='utf8') as f:
        json.dump(_config, f, indent=4, ensure_ascii=False)


def get_group_config(chat_id):
    try:
        int(chat_id)
    except ValueError:
        return None
    file_config = _config.get(chat_id, _config["*"])
    db_config = db.get_group_config(chat_id, 'all')
    if db_config is None:
        return file_config
    else:
        final_config = {**file_config, **db_config}
        return final_config


def _update(app):
    @app.on_message(filters.edited)
    async def edited(client, message):
        pass

    # avoid event handler called twice or more by edit

    @app.on_message(filters.command("reload") & filters.private)
    async def reload_cfg(client: Client, message: Message):
        _me: User = await client.get_me()
        logging.info(message.text)
        if message.from_user.id == _admin_user:
            save_config()
            load_config()
            await message.reply("配置已成功重载。")
        else:
            logging.info("Permission denied, admin user in config is:" + str(_admin_user))
            pass

    @app.on_message(filters.group or filters.service)
    # delete service message and message send from pending validation user
    async def delete_service_message(client: Client, message: Message):
        if message.service:
            if message.service == "new_chat_members" or message.service == "left_chat_member":
                await message.delete()
                return
            else:
                return
        if not _current_challenges.data:
            # 如果当前没有验证任务，就不用判断了
            return
        if not message.from_user:
            # 频道发言不判断
            return
        await asyncio.sleep(2)  # 延迟2秒再判断
        chat_id, user = message.chat.id, message.from_user
        logging.info(f"Chat: {chat_id} User: {user.id} Message: {message.text} Current Challenges: {_current_challenges}")  # for debug
        if _current_challenges.is_duplicate(user.id, chat_id):
            await message.delete()
            await client.send_message(chat_id=_channel,
                                      text=_config["msg_message_deleted"].format(
                                          targetuserid=str(user.id),
                                          messageid=str(message.message_id),
                                          groupid=str(chat_id),
                                          grouptitle=str(message.chat.title),
                                      ),
                                      parse_mode="Markdown",
                                      )
            return

    @app.on_message(filters.command("help") & filters.group)
    async def helping_cmd(client: Client, message: Message):
        _me: User = await client.get_me()
        logging.info(message.text)
        await message.reply(_config["msg_self_introduction"],
                            disable_web_page_preview=True)

    @app.on_message(filters.command("ping") & filters.private)
    async def ping_command(client: Client, message: Message):
        await message.reply("poi~")

    @app.on_message(filters.command("test"))
    async def test_command(client: Client, message: Message):
        new_config = get_group_config(message.chat.id)
        print(new_config)

    @app.on_message(filters.command("start") & filters.private)
    async def start_command(client: Client, message: Message):
        user_id = message.from_user.id
        if len(message.command) != 2:
            await message.reply(_start_message)
            return
        try:
            from_chat_id = int(message.command[1])
        except ValueError:
            await message.reply(_start_message)
            return

        if from_chat_id >= 0:
            await message.reply(_start_message)
            return
        ch_id, challenge_data = _current_challenges.get_by_user_and_chat_id(user_id, from_chat_id)

        if challenge_data is None or ch_id is None:
            await message.reply("这不是你的验证数据，请确认是否点击了正确的按钮")
            return
        else:
            challenge, target_id, timeout_event = challenge_data

        await message.reply("点击下方按钮完成验证，您需要一个浏览器来完成它\n\n"
                            "隐私提醒: \n"
                            "当您打开验证页面时，我们和 Cloudflare 将不可避免的获得您访问使用的 IP 地址，即使我们并不记录它\n"
                            "Google 将获得您的信息， 详见 [Privacy Policy](https://policies.google.com/privacy)\n"
                            "如果您不想被记录，请返回群组，在超时时间内找到并联系群组管理员，您会在超时时间后被自动移出群组",
                            reply_markup=InlineKeyboardMarkup(challenge.generate_auth_button()))

    @app.on_message(filters.command("leave") & filters.private)
    async def leave_command(client: Client, message: Message):
        chat_id = message.text.split()[-1]
        if message.from_user.id == _admin_user:
            try:
                await client.send_message(int(chat_id),
                                          _config["msg_leave_msg"])
                await client.leave_chat(int(chat_id), True)
            except RPCError:
                await message.reply("指令出错了！可能是bot不在参数所在群里。")
            else:
                await message.reply("已离开群组: `" + chat_id + "`",
                                    parse_mode="Markdown")
                _me: User = await client.get_me()
                try:
                    await client.send_message(
                        int(_channel),
                        _config["msg_leave_group"].format(
                            groupid=chat_id,
                        ),
                        parse_mode="Markdown")
                except Exception as e:
                    logging.error(str(e))
        else:
            pass

    @app.on_message(filters.command("clean") & filters.private)
    async def clean_database(client: Client, message: Message):
        if message.from_user.id == _admin_user:
            failed_count = success_count = 0
            deleted_user = []
            user_id_list = db.get_all_user_ids()
            estimated_time = datetime.timedelta(seconds=int(len(user_id_list) / 4))
            await message.reply("开始整理数据库，请稍等...\n预计需要时间:{}".format(estimated_time))
            for x in user_id_list:
                try:
                    user = await client.get_users(x)
                except BadRequest:
                    failed_count += 1
                    continue
                if user.is_deleted:
                    deleted_user.append((user.id,))
                    # 因为 db 用的是 executemany ，得传一个 tuple 进去，所以必须得这么写，不知道有没有更好的方法
                    success_count += 1
            db.delete_user(deleted_user)
            await message.reply(
                "已成功清除{}个已经删号的用户，共有{}个用户信息获取失败。".format(success_count, failed_count))
        else:
            logging.info("Permission denied, admin user in config is:" + str(_admin_user))
            return

    @app.on_message(filters.command("faset") & filters.group)
    async def set_config(client: Client, message: Message):
        if message.from_user is None:
            await message.reply("请从个人账号发送指令。")
            return
        chat_id = message.chat.id
        group_config = get_group_config(chat_id)
        user_id = message.from_user.id
        admins = await client.get_chat_members(chat_id, filter="administrators")
        help_message = "使用方法:\n" \
                       "/faset [配置项] [值]\n\n" \
                       "配置项:\n" \
                       "`challenge_failed_action`: 验证失败的动作，值为 `ban` 封禁或 `kick` 踢出\n" \
                       "`challenge_timeout_action`: 验证超时的动作，值为 `ban` 封禁或 `kick` 踢出\n" \
                       "`challenge_timeout`: 验证超时时间，单位为秒\n" \
                       "`challenge_type`: 验证方法，当前可用为数学题 `math` 或 `reCAPTCHA` 谷歌验证码\n" \
                       "`enable_global_blacklist`: 是否启用全局黑名单，值为 `1` 启用或 `0` 禁用\n" \
                       "`enable_third_party_blacklist`: 是否启用第三方黑名单，值为 `true` 或 `false`\n\n" \
                       "例如: \n" \
                       "`/faset challenge_type reCAPTCHA`\n\n" \
                       "PS: 当前仅有 challenge_type 有效，其他配置项开发中。"
        if not any([
            admin.user.id == user_id and
            (admin.status == "creator" or admin.can_restrict_members)
            for admin in admins
        ]):
            await message.reply(group_config["msg_permission_denied"])
            return

        args = message.text.split(" ", maxsplit=3)
        if len(args) != 3:
            await message.reply(help_message)
            return
        key = args[1]
        value = args[2]
        if db.set_group_config(chat_id, key, value):
            await message.reply("配置项设置成功")
        else:
            await message.reply("配置项设置失败, 请输入 /fasset 查看帮助")

    @app.on_chat_member_updated()
    async def challenge_user(client: Client, message: ChatMemberUpdated):
        # 过滤掉非用户加群消息和频道新用户消息，同时确保 form_user 这个参数不是空的
        if not bool(message.new_chat_member) or bool(message.old_chat_member) or message.chat.type == "channel":
            return
        # 过滤掉管理员 ban 掉用户产生的加群消息 (Durov 这什么 jb api 赶紧分遗产了)
        if message.from_user.id != message.new_chat_member.user.id and not message.new_chat_member.user.is_self:
            return

        target = message.new_chat_member.user
        group_config = get_group_config(message.chat.id)
        chat_id = message.chat.id
        user_id = target.id

        # 黑名单部分----------------------------------------------------------------------------------------------------
        if group_config["enable_global_blacklist"]:
            current_time = int(time.time())
            last_try = db.get_last_try(target.id)
            since_last_attempt = current_time - last_try
            if db.get_user_status(target.id) == 1 and since_last_attempt - 60 > group_config[
                "global_timeout_user_blacklist_remove"]:
                await client.ban_chat_member(chat_id, target.id)
                await client.unban_chat_member(chat_id, target.id)
                db.update_last_try(current_time, target.id)
                db.try_count_plus_one(target.id)
                try_count = int(db.get_try_count(target.id))
                try:
                    await client.send_message(_channel,
                                              text=_config["msg_failed_auto_kick"].format(
                                                  targetuserid=str(target.id),
                                                  targetusername=str(target.username),
                                                  targetfirstname=str(target.first_name),
                                                  targetlastname=str(target.last_name),
                                                  groupid=str(chat_id),
                                                  grouptitle=str(message.chat.title),
                                                  lastattempt=str(
                                                      time.strftime('%Y-%m-%d %H:%M %Z', time.gmtime(last_try))),
                                                  sincelastattempt=str(datetime.timedelta(seconds=since_last_attempt)),
                                                  trycount=str(try_count)
                                              ))
                except Exception as e:
                    logging.error(str(e))
                return
            else:
                db.whitelist(target.id)

        # 入群验证部分--------------------------------------------------------------------------------------------------
        # 这里做一个判断让当出 bug 的时候不会重复弹出一车验证消息
        if _current_challenges.is_duplicate(user_id, chat_id):
            logging.error('重复的验证，用户id：{}, 群组 id {}'.format(user_id, chat_id))
            return

        # 禁言用户 ----------------------------------------------------------------------------------------------------
        if message.from_user.id != target.id:
            if target.is_self:
                try:
                    await client.send_message(
                        message.chat.id, group_config["msg_self_introduction"])
                    _me: User = await client.get_me()
                    try:
                        await client.send_message(
                            int(_channel),
                            _config["msg_into_group"].format(
                                groupid=str(message.chat.id),
                                grouptitle=str(message.chat.title),
                            ),
                            parse_mode="Markdown",
                        )
                    except Exception as e:
                        logging.error(str(e))
                except ChannelPrivate:
                    return
            return
        try:
            await client.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=target.id,
                permissions=ChatPermissions(can_send_messages=False))
        except ChatAdminRequired:
            return
        except RPCError:
            await client.send_message(
                message.chat.id,
                "当前群组不是超级群组，Bot 无法工作，可能是成员过少。\n请尝试添加更多用户，或者禁言一个用户，让 Telegram 将该群转换为超级群组")
            return
        # reCAPTCHA 验证 ----------------------------------------------------------------------------------------------

        if group_config['challenge_type'] == 'reCAPTCHA':
            challenge = ReCAPTCHA()
            timeout = group_config["challenge_timeout"]
            reply_message = await client.send_message(
                message.chat.id,
                group_config["msg_challenge_recaptcha"].format(target=target.first_name,
                                                               target_id=target.id,
                                                               timeout=timeout, ),
                reply_markup=InlineKeyboardMarkup(
                    challenge.generate_button(group_config, chat_id)),
            )
            challenge.message = reply_message
        else:  # 验证码验证 -------------------------------------------------------------------------------------------
            challenge = Math()
            timeout = group_config["challenge_timeout"]
            reply_message = await client.send_message(
                message.chat.id,
                group_config["msg_challenge_math"].format(target=target.first_name,
                                                          target_id=target.id,
                                                          timeout=timeout,
                                                          challenge=challenge.qus()),
                reply_markup=InlineKeyboardMarkup(
                    challenge.generate_button(group_config)),
            )

        # 开始计时 -----------------------------------------------------------------------------------------------------
        challenge_id = "{chat}|{msg}".format(chat=message.chat.id, msg=reply_message.message_id)
        timeout_event = Timer(
            challenge_timeout(client, message, reply_message.message_id),
            timeout=group_config["challenge_timeout"],
        )
        _current_challenges[challenge_id] = (challenge, message.from_user.id, timeout_event)

    @app.on_callback_query(admin_operate_filter)
    async def admin_operate_callback(client: Client, callback_query: CallbackQuery):
        query_data = str(callback_query.data)
        query_id = callback_query.id
        chat_id = callback_query.message.chat.id
        user_id = callback_query.from_user.id
        msg_id = callback_query.message.message_id
        chat_title = callback_query.message.chat.title
        user_username = callback_query.from_user.username
        user_first_name = callback_query.from_user.first_name
        user_last_name = callback_query.from_user.last_name
        group_config = get_group_config(chat_id)

        # 获取验证信息-----------------------------------------------------------------------------------------------

        ch_id = "{chat}|{msg}".format(chat=chat_id, msg=msg_id)
        challenge_data = _current_challenges.get(ch_id)

        if challenge_data is None:
            logging.error("challenge not found, challenge_id: {}".format(ch_id))
            return
        else:
            challenge, target_id, timeout_event = challenge_data

        # 响应管理员操作------------------------------------------------------------------------------------------------

        if query_data in ["+", "-"]:
            admins = await client.get_chat_members(chat_id,
                                                   filter="administrators")
            if not any([
                admin.user.id == user_id and
                (admin.status == "creator" or admin.can_restrict_members)
                for admin in admins
            ]):
                await client.answer_callback_query(
                    query_id, group_config["msg_permission_denied"])
                return
            _current_challenges.delete(ch_id)
            timeout_event.stop()
            if query_data == "+":
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
                    await client.answer_callback_query(
                        query_id, group_config["msg_bot_no_permission"])
                    return

                await client.edit_message_text(
                    chat_id,
                    msg_id,
                    group_config["msg_approved"].format(user=user_first_name),
                    reply_markup=None,
                )
                _me: User = await client.get_me()
                try:
                    await client.send_message(
                        int(_channel),
                        _config["msg_passed_admin"].format(
                            targetuserid=str(target_id),
                            groupid=str(chat_id),
                            grouptitle=str(chat_title),
                        ),
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logging.error(str(e))
            else:
                try:
                    await client.ban_chat_member(chat_id, target_id)
                except ChatAdminRequired:
                    await client.answer_callback_query(
                        query_id, group_config["msg_bot_no_permission"])
                    return
                await client.edit_message_text(
                    chat_id,
                    msg_id,
                    group_config["msg_refused"].format(user=user_first_name),
                    reply_markup=None,
                )
                _me: User = await client.get_me()
                try:
                    await client.send_message(
                        int(_channel),
                        _config["msg_failed_admin"].format(
                            targetuserid=str(target_id),
                            groupid=str(chat_id),
                            grouptitle=str(chat_title),
                        ),
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logging.error(str(e))
            await client.answer_callback_query(query_id)
            return

    @app.on_callback_query()
    async def challenge_answer_callback(client: Client, callback_query: CallbackQuery):
        query_data = str(callback_query.data)
        query_id = callback_query.id
        chat_id = callback_query.message.chat.id
        user_id = callback_query.from_user.id
        msg_id = callback_query.message.message_id
        chat_title = callback_query.message.chat.title
        user_username = callback_query.from_user.username
        user_first_name = callback_query.from_user.first_name
        user_last_name = callback_query.from_user.last_name
        group_config = get_group_config(chat_id)

        # 获取验证信息-----------------------------------------------------------------------------------------------

        ch_id = "{chat}|{msg}".format(chat=chat_id, msg=msg_id)

        challenge_data = _current_challenges.get(ch_id)

        if challenge_data is None:
            logging.error("challenge not found, challenge_id: {}".format(ch_id))
            return
        else:
            challenge, target_id, timeout_event = challenge_data

        # 让捣蛋的一边玩去 ---------------------------------------------------------------------------------

        if user_id != target_id:
            await client.answer_callback_query(
                query_id, group_config["msg_challenge_not_for_you"])
            return None
        timeout_event.stop()

        # 分析的没错的话这里应该是先给用户解开再根据回答对错处理 -----------------------------------------------------------

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

        correct = str(challenge.ans()) == query_data
        if correct:
            try:
                await client.edit_message_text(
                    chat_id,
                    msg_id,
                    group_config["msg_challenge_passed"],
                    reply_markup=None)
            except MessageNotModified as e:
                await client.send_message(int(_channel),
                                          'Bot 运行时发生异常: `' + str(e) + "`")
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
        else:
            try:
                await client.edit_message_text(
                    chat_id,
                    msg_id,
                    group_config["msg_challenge_failed"],
                    reply_markup=None,
                )
                try:
                    await client.send_message(
                        int(_channel),
                        _config["msg_failed_answer"].format(
                            targetuserid=str(target_id),
                            groupid=str(chat_id),
                            grouptitle=str(chat_title),
                        ),
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logging.error(str(e))
            except ChatAdminRequired:
                return

            if group_config["challenge_failed_action"] == "ban":
                await client.ban_chat_member(chat_id, user_id)
            else:
                # kick
                await client.ban_chat_member(chat_id, user_id)
                await client.unban_chat_member(chat_id, user_id)

            if group_config["delete_failed_challenge"]:
                Timer(
                    client.delete_messages(chat_id, msg_id),
                    group_config["delete_failed_challenge_interval"],
                )
        if group_config["delete_passed_challenge"]:
            Timer(
                client.delete_messages(chat_id, msg_id),
                group_config["delete_passed_challenge_interval"],
            )

    async def challenge_timeout(client: Client, message, reply_id):
        chat_id = message.chat.id
        from_id = message.from_user.id
        chat_title = message.chat.title
        user_username = message.from_user.username
        user_first_name = message.from_user.first_name
        user_last_name = message.from_user.last_name
        group_config = get_group_config(chat_id)
        _current_challenges.delete("{chat}|{msg}".format(chat=chat_id,
                                                         msg=reply_id))

        # TODO try catch
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=reply_id,
            text=group_config["msg_challenge_failed"],
            reply_markup=None,
        )

        await client.send_message(chat_id=_channel,
                                  text=_config["msg_failed_timeout"].format(
                                      targetuserid=str(from_id),
                                      targetusername=str(user_username),
                                      targetfirstname=str(user_first_name),
                                      targetlastname=str(user_last_name),
                                      groupid=str(chat_id),
                                      grouptitle=str(chat_title)
                                  ))

        if group_config["challenge_timeout_action"] == "ban":
            await client.ban_chat_member(chat_id, from_id)
        elif group_config["challenge_timeout_action"] == "kick":
            await client.ban_chat_member(chat_id, from_id)
            await client.unban_chat_member(chat_id, from_id)
        else:
            pass

        if group_config["delete_failed_challenge"]:
            Timer(
                client.delete_messages(chat_id, reply_id),
                group_config["delete_failed_challenge_interval"],
            )

        if group_config["enable_global_blacklist"]:
            current_time = int(time.time())
            db.new_blacklist(current_time, from_id)


def _main():
    db.setup()
    global _channel, _start_message, _config
    load_config()
    _start_message = _config["msg_start_message"]
    _proxy_ip = _config["proxy_addr"].strip()
    _proxy_port = _config["proxy_port"].strip()
    if _proxy_ip and _proxy_port:
        _app = Client("bot",
                      bot_token=_token,
                      api_id=_api_id,
                      api_hash=_api_hash,
                      proxy=dict(hostname=_proxy_ip, port=int(_proxy_port)))
    else:
        _app = Client("bot",
                      bot_token=_token,
                      api_id=_api_id,
                      api_hash=_api_hash)
    try:

        # start web
        tt = threading.Thread(
            target=start_web, name="WebThread", args=(_app,))
        tt.daemon = True
        logging.info('Starting webapi ....')
        tt.start()

        # start bot
        _update(_app)
        _app.run()
    except KeyboardInterrupt:
        quit()
    except Exception as e:
        logging.error(e)
        _main()


if __name__ == "__main__":
    _main()
