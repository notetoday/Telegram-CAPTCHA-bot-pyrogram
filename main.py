# !/usr/bin/env python3
# -*- coding: UTF-8 -*-
import json
import logging
import threading
import time
import datetime
import re
from configparser import ConfigParser

from pyrogram import (Client, filters)
from pyrogram.errors import ChatAdminRequired, ChannelPrivate, MessageNotModified, RPCError, BadRequest
from pyrogram.types import (InlineKeyboardMarkup, User, Message, ChatPermissions, CallbackQuery,
                            ChatMemberUpdated)

from Timer import Timer
from challenge.math import Challenge

from dbhelper import DBHelper

db = DBHelper()

_start_message = "YABE!"
# _challenge_scheduler = sched.scheduler(time, sleep)
_current_challenges = dict()
_cch_lock = threading.Lock()
_config = dict()
'''
读 只 读 配 置
'''
cf = ConfigParser()  # 启用ConfigParser读取那些启动后即不会再被更改的数据，如BotToken等
cf.read("auth.ini")
_admin_user = cf.getint("bot", "admin")
_token = cf.get("bot", "token")
_api_id = cf.getint("bot", "api_id")
_api_hash = cf.get("bot", "api_hash")
_channel = cf.getint("bot", "channel")
logging.basicConfig(level=logging.INFO)


# 设置一下日志记录，能够在诸如 systemctl status captchabot 这样的地方获得详细输出。


def load_config():
    global _config
    with open("config.json", encoding="utf-8") as f:
        _config = json.load(f)


def save_config():
    with open("config.json", "w", encoding='utf8') as f:
        json.dump(_config, f, indent=4, ensure_ascii=False)


def _update(app):
    @app.on_message(filters.edited)
    async def edited( client, message):
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

    @app.on_message(filters.command("help") & filters.group)
    async def helping_cmd(client: Client, message: Message):
        _me: User = await client.get_me()
        logging.info(message.text)
        await message.reply(_config["msg_self_introduction"],
                            disable_web_page_preview=True)

    @app.on_message(filters.command("ping") & filters.private)
    async def ping_command(client: Client, message: Message):
        await message.reply("poi~")

    @app.on_message(filters.command("start") & filters.private)
    async def start_command(client: Client, message: Message):
        await message.reply(_start_message)

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
            await message.reply("已成功清除{}个已经删号的用户，共有{}个用户信息获取失败。".format(success_count, failed_count))
        else:
            logging.info("Permission denied, admin user in config is:" + str(_admin_user))
            return

    @app.on_message(filters.command("regexadd") & filters.group)
    async def add_regex(client: Client, message: Message):
        group_config = _config.get(str(message.chat.id), _config["*"])
        chat_id = message.chat.id
        if message.from_user is None:
            await message.reply("请从个人账号发送指令。")
            return
        user_id = message.from_user.id
        admins = await client.get_chat_members(chat_id, filter="administrators")
        help_message = "使用方法:\n /regexadd [规则描述] [动作] [匹配类型] [正则表达式]" \
                       "\n\n参数使用空格分开\n规则描述: 对于这条规则的简短描述" \
                       "\n\n动作: 匹配到规则后的动作，值为 `ban` 永久封禁或 `kick` 踢出" \
                       "\n\n匹配类型: 值为 `username` 用户名或 `name` 用户名字" \
                       "\n\n正则表达式: Perl 正则表达式" \
                       "\n例如:" \
                       "\n /regexadd 封禁恶意用户 ban username ^[a-zA-Z0-9_]{5,20}$" \
                       "\n\n(这例子是 Github Copilot 自动写的，我压根就不会写正则) "

        if not any([
            admin.user.id == user_id and
            (admin.status == "creator" or admin.can_restrict_members)
            for admin in admins
        ]):
            await message.reply(group_config["msg_permission_denied"])
            return

        args = message.text.split(" ", maxsplit=4)
        if len(args) != 5:
            await message.reply(help_message)
            return
        description = args[1]
        action = args[2]
        match_type = args[3]
        regex = args[4].encode("utf-8")
        if action not in ["ban", "kick"] or match_type not in ["username", "name"]:
            await message.reply(help_message)
            return
        result = db.new_regex(chat_id, regex, match_type, action, description)
        if result:
            await message.reply("已添加规则：\n" + description)
        else:
            await message.reply("添加失败，超出本群正则表达式数量限制")
        return

    @app.on_message(filters.command("regexdel") & filters.group)
    async def del_regex(client: Client, message: Message):
        chat_id = message.chat.id
        if message.from_user is None:
            await message.reply("请从个人账号发送指令。")
            return
        user_id = message.from_user.id
        group_config = _config.get(str(chat_id), _config["*"])
        admins = await client.get_chat_members(chat_id, filter="administrators")
        help_message = "使用方法:\n" \
                       "/regexdel [规则 ID]\n\n不知道规则 ID 可以使用 /regexlist 查看"

        if not any([
            admin.user.id == user_id and
            (admin.status == "creator" or admin.can_restrict_members)
            for admin in admins
        ]):
            await message.reply(group_config["msg_permission_denied"])
            return

        args = message.text.split(" ", maxsplit=2)
        if len(args) != 2:
            await message.reply(help_message)
            return
        regex_id = args[1]
        result = db.delete_regex(regex_id, chat_id)
        if result:
            await message.reply("规则删除成功")
        else:
            await message.reply("规则删除失败，可能规则不属于这个群组")
        return

    @app.on_message(filters.command("regexlist") & filters.group)
    async def del_regex(client: Client, message: Message):
        chat_id = message.chat.id
        if message.from_user is None:
            await message.reply("请从个人账号发送指令。")
            return
        user_id = message.from_user.id
        group_config = _config.get(str(chat_id), _config["*"])
        admins = await client.get_chat_members(chat_id, filter="administrators")

        if not any([
            admin.user.id == user_id and
            (admin.status == "creator" or admin.can_restrict_members)
            for admin in admins
        ]):
            await message.reply(group_config["msg_permission_denied"])
            return

        regex_rules = db.get_regex(chat_id)
        regex_list = ""
        for regex_rule in regex_rules:
            rid = regex_rule[0]
            regex = regex_rule[2].decode("utf-8")
            match = regex_rule[3]
            action = regex_rule[4]
            description = regex_rule[5]
            regex_list += "ID: `{rid}`" \
                          "\n正则表达式: `{regex}`" \
                          "\n匹配: `{match}`" \
                          "\n动作: `{action}`" \
                          "\n备注：`{description}`" \
                          "\n- - - - - - - - - - " \
                          "\n".format(rid=rid, regex=regex, match=match, action=action, description=description)
        if regex_list == "":
            await message.reply("这个群组没有规则")
        else:
            await message.reply(regex_list)

    @app.on_chat_member_updated()
    async def challenge_user(client: Client, message: ChatMemberUpdated):
        # 过滤掉非用户加群消息和频道新用户消息，同时确保 form_user 这个参数不是空的
        if not bool(message.new_chat_member) or bool(message.old_chat_member) or message.chat.type == "channel":
            return
        # 过滤掉管理员 ban 掉用户产生的加群消息 (Durov 这什么 jb api 赶紧分遗产了)
        if message.from_user.id != message.new_chat_member.user.id:
            return

        target = message.new_chat_member.user
        group_config = _config.get(str(message.chat.id), _config["*"])
        chat_id = message.chat.id
        user_id = target.id

        # 黑名单部分----------------------------------------------------------------------------------------------------

        if group_config["global_timeout_user_kick"]:
            current_time = int(time.time())
            last_try = db.get_last_try(target.id)
            since_last_attempt = current_time - last_try
            if db.get_user_status(target.id) == 1 and since_last_attempt > group_config[
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

        # 正则匹配部分--------------------------------------------------------------------------------------------------

        if target.last_name:
            name = target.first_name + target.last_name
        else:
            name = target.first_name
        regex_rules = db.get_regex(chat_id)
        if regex_rules:
            for regex_rule in regex_rules:
                rid = regex_rule[0]
                regex = regex_rule[2].decode("utf-8")
                match = regex_rule[3]
                action = regex_rule[4]
                match_result = False
                if match == 'username' and target.username:
                    if re.search(regex, target.username):
                        match_result = True
                if match == 'name':
                    if re.search(regex, name):
                        match_result = True
                if match_result:
                    try:
                        if action == 'kick':
                            await client.ban_chat_member(chat_id=chat_id, user_id=user_id)
                            await client.unban_chat_member(chat_id=chat_id, user_id=user_id)
                        if action == 'ban':
                            await client.ban_chat_member(chat_id=chat_id, user_id=user_id)
                        await client.send_message(
                            _channel,
                            text=_config["msg_failed_regex"].format(
                                targetuserid=str(target.id),
                                targetusername=str(target.username),
                                targetfirstname=str(target.first_name),
                                targetlastname=str(target.last_name),
                                regexid=str(rid),
                                regex=str(regex),
                                groupid=str(chat_id),
                                grouptitle=str(message.chat.title)
                            ))
                    except RPCError as e:
                        logging.error(str(e))
                    return

        # 入群验证部分--------------------------------------------------------------------------------------------------

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
        challenge = Challenge()

        timeout = group_config["challenge_timeout"]
        reply_message = await client.send_message(
            message.chat.id,
            group_config["msg_challenge"].format(target=target.first_name,
                                                 target_id=target.id,
                                                 timeout=timeout,
                                                 challenge=challenge.qus()),
            reply_markup=InlineKeyboardMarkup(
                challenge.generate_button(group_config)),
        )
        _me: User = await client.get_me()
        timeout_event = Timer(
            challenge_timeout(client, message, reply_message.message_id),
            timeout=group_config["challenge_timeout"],
        )
        _cch_lock.acquire()
        _current_challenges["{chat}|{msg}".format(
            chat=message.chat.id,
            msg=reply_message.message_id)] = (challenge, message.from_user.id,
                                              timeout_event)
        _cch_lock.release()

    @app.on_callback_query()
    async def challenge_callback(client: Client,
                                 callback_query: CallbackQuery):
        query_data = str(callback_query.data)
        query_id = callback_query.id
        chat_id = callback_query.message.chat.id
        user_id = callback_query.from_user.id
        msg_id = callback_query.message.message_id
        chat_title = callback_query.message.chat.title
        user_username = callback_query.from_user.username
        user_first_name = callback_query.from_user.first_name
        user_last_name = callback_query.from_user.last_name
        group_config = _config.get(str(chat_id), _config["*"])

        # 获取验证信息-----------------------------------------------------------------------------------------------

        ch_id = "{chat}|{msg}".format(chat=chat_id, msg=msg_id)
        _cch_lock.acquire()
        # target: int = None
        challenge, target_id, timeout_event = _current_challenges.get(ch_id)
        _cch_lock.release()
        if not challenge or not target_id or not timeout_event:
            logging.error("challenge not found, challenge_id: {}".format(ch_id))
            return

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
            if ch_id in _current_challenges:
                # 预防异常
                del _current_challenges[ch_id]
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

        correct = str(challenge.ans()) == query_data
        if correct:
            try:
                await client.edit_message_text(
                    chat_id,
                    msg_id,
                    group_config["msg_challenge_passed"],
                    reply_markup=None)
                _me: User = await client.get_me()
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
            if not group_config["use_strict_mode"]:
                await client.edit_message_text(
                    chat_id,
                    msg_id,
                    group_config["msg_challenge_mercy_passed"],
                    reply_markup=None,
                )
                _me: User = await client.get_me()
                try:
                    await client.send_message(
                        int(_channel),
                        _config["msg_passed_mercy"].format(
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
                    # await client.restrict_chat_member(chat_id, target)
                    _me: User = await client.get_me()
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

                if group_config["challenge_timeout_action"] == "ban":
                    await client.ban_chat_member(chat_id, user_id)
                elif group_config["challenge_timeout_action"] == "kick":
                    await client.ban_chat_member(chat_id, user_id)
                    await client.unban_chat_member(chat_id, user_id)
                elif group_config["challenge_timeout_action"] == "mute":
                    await client.restrict_chat_member(
                        chat_id,
                        user_id,
                        permissions=ChatPermissions(can_send_messages=False))

                else:
                    pass

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
        global _current_challenges
        chat_id = message.chat.id
        from_id = message.from_user.id
        chat_title = message.chat.title
        user_username = message.from_user.username
        user_first_name = message.from_user.first_name
        user_last_name = message.from_user.last_name
        _me: User = await client.get_me()
        group_config = _config.get(str(chat_id), _config["*"])

        _cch_lock.acquire()
        del _current_challenges["{chat}|{msg}".format(chat=chat_id,
                                                      msg=reply_id)]
        _cch_lock.release()

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

        if group_config["global_timeout_user_kick"]:
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
        _update(_app)
        _app.run()
    except KeyboardInterrupt:
        quit()
    except Exception as e:
        logging.error(e)
        _main()


if __name__ == "__main__":
    _main()
