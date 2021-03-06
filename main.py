# !/usr/bin/env python3
import time
import pdb
# -*- coding: UTF-8 -*-
import json
import logging
import threading
from configparser import ConfigParser

from pyrogram import Client, filters
from pyrogram.errors import ChatAdminRequired, ChannelPrivate, MessageNotModified
from pyrogram.methods.chats.get_chat_members import Filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, User, Message, ChatPermissions, CallbackQuery, \
    ChatMemberUpdated

from Timer import Timer
from challenge import Challenge
from pyrogram.handlers import chat_member_updated_handler

_app: Client = None
# _challenge_scheduler = sched.scheduler(time, sleep)
_current_challenges = dict()
_cch_lock = threading.Lock()
_config = dict()

_keys_config = dict()
'''
读 只 读 配 置
'''
# pdb.set_trace()
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
    with open("config.json", "w") as f:
        json.dump(_config, f, indent=4)


def load_keys_config():
    global _keys_config
    with open("keys.json", encoding="utf-8") as f:
        _keys_config = json.load(f)


def save_keys_config():
    with open("keys.json", "w") as f:
        json.dump(_keys_config, f, indent=4)


def _update(app):
    @app.on_message(filters.command("addkeys") & filters.private)
    async def addkeys(client: Client, message: Message):
        _me: User = await client.get_me()
        logging.info(message.text)
        if message.from_user.id == _admin_user:
            new_keys = message.text.split(" ")[1:]
            for key in new_keys:
                if key == "":
                    new_keys.remove("")
            new_keys_str = " ".join(new_keys)
            keys = _keys_config["keys"]
            keys.extend(new_keys)
            _keys_config["keys"] = keys
            save_keys_config()
            load_keys_config()
            await message.reply("成功添加 %s" % new_keys_str)
        else:
            logging.info(
                "Permission denied, admin user in config is:" + str(_admin_user))
            pass

    @app.on_message(filters.command("delkeys") & filters.private)
    async def addkeys(client: Client, message: Message):
        _me: User = await client.get_me()
        logging.info(message.text)
        if message.from_user.id == _admin_user:
            del_keys = message.text.split(" ")[1:]
            keys = _keys_config["keys"]
            deled_keys = []
            not_deled_keys = []
            for key in del_keys:
                try:
                    keys.remove(key)
                    deled_keys.append(key)
                except:
                    not_deled_keys.append(key)
            _keys_config["keys"] = keys
            save_keys_config()
            load_keys_config()
            deled_keys_str = " ".join(deled_keys)
            await message.reply("成功删除 %s" % deled_keys_str)
            if len(not_deled_keys) != 0:
                not_deled_keys_str = " ".join(not_deled_keys)
                await message.reply("删除失败 %s" % not_deled_keys_str)
        else:
            logging.info(
                "Permission denied, admin user in config is:" + str(_admin_user))
            pass

    @app.on_message(filters.command("showkeys") & filters.private)
    async def showkeys(client: Client, message: Message):
        _me: User = await client.get_me()
        logging.info(message.from_user.id)
        logging.info(message.text)
        if message.from_user.id == _admin_user:
            keys = _keys_config["keys"]
            keys_str = " ".join(keys)
            await message.reply(keys_str)
        else:
            logging.info(
                "Permission denied, admin user in config is:" + str(_admin_user))
            pass

    @app.on_message(filters.command("reload") & filters.private)
    async def reload_cfg(client: Client, message: Message):
        _me: User = await client.get_me()
        logging.info(message.text)
        if message.from_user.id == _admin_user:
            save_config()
            load_config()
            await message.reply("配置已成功重载。")
        else:
            logging.info(
                "Permission denied, admin user in config is:" + str(_admin_user))
            pass

    @app.on_message(filters.command("help") & filters.group)
    async def helping_cmd(client: Client, message: Message):
        _me: User = await client.get_me()
        logging.info(message.text)
        await message.reply(_config["*"]["msg_self_introduction"],
                            disable_web_page_preview=True)

    @app.on_message(filters.command("ping") & filters.private)
    async def ping_command(client: Client, message: Message):
        await message.reply("poi~")

    @app.on_message(filters.command("start") & filters.private)
    async def start_command(client: Client, message: Message):
        # pdb.set_trace()
        await message.reply(_start_message)

    @app.on_message(filters.command("leave") & filters.private)
    async def leave_command(client: Client, message: Message):
        chat_id = message.text.split()[-1]
        if message.from_user.id == _admin_user:
            try:
                await client.send_message(int(chat_id),
                                          _config["msg_leave_msg"])
                await client.leave_chat(int(chat_id), True)
            except:
                await message.reply("指令出错了！可能是bot不在参数所在群里。")
            else:
                await message.reply("已离开群组: `" + chat_id + "`",
                                    parse_mode="Markdown")
                _me: User = await client.get_me()
                try:
                    await client.send_message(
                        int(_channel),
                        _config["msg_leave_group"].format(
                            botid=str(_me.id),
                            groupid=chat_id,
                        ),
                        parse_mode="Markdown")
                except Exception as e:
                    logging.error(str(e))
        else:
            pass

    @app.on_chat_member_updated()
    async def on_chat_member_change(client, chat_member_updated: ChatMemberUpdated):
        # 被踢的可能会重复进，这时候会有老人数据。但新人新数据不可能是空
        if chat_member_updated.new_chat_member is None:
            return
        await on_handler_new_people(client, chat_member_updated)

    async def on_handler_new_people(client, message):
        target = message.from_user
        first_name = target.first_name
        last_name = target.last_name
        user_name = str(first_name) + str(last_name)
        chat_id = message.chat.id
        user_id = message.from_user.id
        # msg_id = message.message_id
        # msg_id = message.date
        if message.from_user.id != target.id:
            if target.is_self:
                group_config = _config.get(str(message.chat.id), _config["*"])
                try:
                    await client.send_message(
                        message.chat.id, group_config["msg_self_introduction"])
                    _me: User = await client.get_me()
                    try:
                        await client.send_message(
                            int(_channel),
                            _config["msg_into_group"].format(
                                botid=str(_me.id),
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

        def get_flag(user_name):
            keys = _keys_config["keys"]
            for k in keys:
                if k in user_name:
                    return True
            return False

        if get_flag(user_name):
            await client.kick_chat_member(chat_id, user_id)
            # await client.delete_messages(chat_id, msg_id)
        else:
            group_config = _config.get(str(message.chat.id), _config["*"])
            challenge = Challenge()

            def generate_challenge_button(e):
                choices = []
                answers = []
                for c in e.choices():
                    answers.append(
                        InlineKeyboardButton(str(c),
                                             callback_data=bytes(
                                                 str(c), encoding="utf-8")))
                choices.append(answers)
                return choices + [[
                    InlineKeyboardButton(group_config["msg_approve_manually"],
                                         callback_data=b"+"),
                    InlineKeyboardButton(group_config["msg_refuse_manually"],
                                         callback_data=b"-"),
                ]]

            timeout = group_config["challenge_timeout"]
            reply_message = await client.send_message(
                message.chat.id,
                group_config["msg_challenge"].format(target=target.first_name,
                                                     target_id=target.id,
                                                     timeout=timeout,
                                                     challenge=challenge.qus()),
                # reply_to_message_id=msg_id,
                reply_markup=InlineKeyboardMarkup(
                    generate_challenge_button(challenge)),
            )
            _me: User = await client.get_me()
            chat_id = message.chat.id
            chat_title = message.chat.title
            target = message.from_user.id
            timeout_event = Timer(
                challenge_timeout(client, message.chat.id, message.from_user.id,
                                  reply_message.message_id),
                timeout=group_config["challenge_timeout"],
            )
            _cch_lock.acquire()
            _current_challenges["{chat}|{msg}".format(
                chat=message.chat.id,
                msg=reply_message.message_id)] = (challenge, message.from_user.id,
                                                  timeout_event)
            _cch_lock.release()

    @app.on_message(filters.left_chat_member)
    async def delete_left_messages(client: Client, message: Message):
        chat_id = message.chat.id
        msg_id = message.message_id
        await client.delete_messages(chat_id, msg_id)

    # 重复触发，这个先注掉
    # @app.on_message(filters.new_chat_members)
    # async def delete_left_messages(client: Client, message: Message):
    #     chat_id = message.chat.id
    #     msg_id = message.message_id
    #     await on_handler_new_people(client, message)

    @app.on_callback_query()
    async def challenge_callback(client: Client,
                                 callback_query: CallbackQuery):
        query_data = str(callback_query.data)
        query_id = callback_query.id
        chat_id = callback_query.message.chat.id
        user_id = callback_query.from_user.id
        msg_id = callback_query.message.message_id
        chat_title = callback_query.message.chat.title
        user_name = callback_query.from_user.first_name
        group_config = _config.get(str(chat_id), _config["*"])
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

            ch_id = "{chat}|{msg}".format(chat=chat_id, msg=msg_id)
            _cch_lock.acquire()
            # target: int = None
            timeout_event: None
            challenge, target, timeout_event = _current_challenges.get(
                ch_id, (None, None, None))
            if ch_id in _current_challenges:
                # 预防异常
                del _current_challenges[ch_id]
            _cch_lock.release()
            timeout_event.stop()
            if query_data == "+":
                try:
                    await client.restrict_chat_member(
                        chat_id,
                        target,
                        permissions=ChatPermissions(
                            can_send_messages=True,
                            can_send_media_messages=True,
                            can_send_stickers=True,
                            can_send_animations=True,
                            can_send_games=True,
                            can_use_inline_bots=True,
                            can_add_web_page_previews=True,
                            can_send_polls=True,
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
                    group_config["msg_approved"].format(user=user_name),
                    reply_markup=None,
                )
                _me: User = await client.get_me()
                try:
                    await client.send_message(
                        int(_channel),
                        _config["msg_passed_admin"].format(
                            botid=str(_me.id),
                            targetuser=str(target),
                            groupid=str(chat_id),
                            grouptitle=str(chat_title),
                        ),
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logging.error(str(e))
            else:
                try:
                    await client.kick_chat_member(chat_id, target)
                except ChatAdminRequired:
                    await client.answer_callback_query(
                        query_id, group_config["msg_bot_no_permission"])
                    return
                await client.edit_message_text(
                    chat_id,
                    msg_id,
                    group_config["msg_refused"].format(user=user_name),
                    reply_markup=None,
                )
                _me: User = await client.get_me()
                try:
                    await client.send_message(
                        int(_channel),
                        _config["msg_failed_admin"].format(
                            botid=str(_me.id),
                            targetuser=str(target),
                            groupid=str(chat_id),
                            grouptitle=str(chat_title),
                        ),
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logging.error(str(e))
            await client.answer_callback_query(query_id)
            return

        ch_id = "{chat}|{msg}".format(chat=chat_id, msg=msg_id)
        _cch_lock.acquire()
        challenge, target, timeout_event = _current_challenges.get(
            ch_id, (None, None, None))
        _cch_lock.release()
        if user_id != target:
            await client.answer_callback_query(
                query_id, group_config["msg_challenge_not_for_you"])
            return None
        timeout_event.stop()

        correct = str(challenge.ans()) == query_data
        if correct:
            try:
                await client.restrict_chat_member(
                    chat_id,
                    target,
                    permissions=ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_stickers=True,
                        can_send_animations=True,
                        can_send_games=True,
                        can_use_inline_bots=True,
                        can_add_web_page_previews=True,
                        can_send_polls=True,
                        can_change_info=True,
                        can_invite_users=True,
                        can_pin_messages=True))
            except ChatAdminRequired:
                pass
            try:
                await client.edit_message_text(
                    chat_id,
                    msg_id,
                    group_config["msg_challenge_passed"].format(
                        target=user_name,
                        target_id=user_id,
                        grouptitle=str(chat_title)),
                    reply_markup=None)
                _me: User = await client.get_me()
            except MessageNotModified as e:
                await client.send_message(int(_channel),
                                          'Bot 运行时发生异常: `' + str(e) + "`")
            try:
                await client.send_message(
                    _channel,
                    _config["msg_passed_answer"].format(
                        botid=str(_me.id),
                        targetuser=str(target),
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
                        _channel,
                        _config["msg_passed_mercy"].format(
                            botid=str(_me.id),
                            targetuser=str(target),
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
                            _channel,
                            _config["msg_failed_answer"].format(
                                botid=str(_me.id),
                                targetuser=str(target),
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
                    await client.kick_chat_member(chat_id, user_id)
                elif group_config["challenge_timeout_action"] == "kick":
                    # await client.kick_chat_member(chat_id, user_id)
                    # await client.unban_chat_member(chat_id, user_id)
                    pass
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

    async def challenge_timeout(client: Client, chat_id, from_id, reply_id):
        global _current_challenges
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
        try:
            await client.send_message(chat_id=_channel,
                                      text=_config["msg_failed_timeout"].format(
                                          botid=str(_me.id),
                                          targetuser=str(from_id),
                                          groupid=str(chat_id)))
        except Exception as e:
            logging.error(str(e))
        if group_config["challenge_timeout_action"] == "ban":
            await client.kick_chat_member(chat_id, from_id)
        elif group_config["challenge_timeout_action"] == "kick":
            # pdb.set_trace()
            # await client.kick_chat_member(chat_id, from_id)
            # await client.unban_chat_member(chat_id, from_id)
            pass
        else:
            pass

        if group_config["delete_failed_challenge"]:
            Timer(
                client.delete_messages(chat_id, reply_id),
                group_config["delete_failed_challenge_interval"],
            )


def _main():
    global _app, _channel, _start_message, _config, _keys_config
    load_config()
    load_keys_config()
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
