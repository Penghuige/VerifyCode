# encoding:utf-8

import json
import os
import random
import re
import time
from datetime import datetime, timedelta


import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
from common.log import logger
from plugins import *

# 这个文件用来实现功能：添加好友后进行判断，若发送邀请码且邀请码
# 正确，则能使用机器人的功能，若不正确则不行
# 刚加好友的时候能够获得一天试用，通过自身发送激活码来激活

@plugins.register(
    name="VerifyCode",
    desire_priority=998,
    hidden=False,
    desc="通过激活码与邀请码来获得机器人的使用权限。",
    version="0.9",
    author="Penghuige",
)
class VerifyCode(Plugin):
    def __init__(self):
        super().__init__()
        # 存放未被使用的邀请码 初始给了个root,邀请人为本身
        self.invitation_code = {}
        # 存放已被使用的邀请码，以邀请码为索引，存放用户ID、注册时间、有效期
        self.verify_code = {}
        # 存放已被激活的用户ID
        self.whitelist = []
        # 存放用户ID和邀请码的对应关系，每个用户对应一个邀请码
        self.user_id = {}
        try:
            # load config
            curdir = os.path.dirname(__file__)
            config_path = os.path.join(curdir, "config.json")
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                logger.info(f"[VerifyCode] 加载配置文件成功: {config}")

                self.initial_time = config["initial_time"]   
                self.hours_extension = config["hours_extension"]
                self.manager = config["manager"]

            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context

            logger.info("[VerifyCode] inited")
        except Exception as e:
            logger.warn("[VerifyCode] init failed, ignore or see")
            raise e
    
    def on_handle_context(self, e_context: EventContext):
        # 根据输入判断使用功能
        if e_context["context"].type not in [
            ContextType.TEXT,
            ContextType.ACCEPT_FRIEND
        ]:
            return 
        
        context = e_context['context']
        msg: ChatMessage = context['msg']
        isgroup = e_context["context"].get("isgroup")

        group_id = None
        if isgroup:
            # 是群信息，判断该群是否开启了激活码，这里的标识符是群名称，未找到群号
            group_id = e_context.econtext["context"]["self_display_name"]

        sender_id = e_context.econtext["context"]["receiver"]
        
        content = e_context["context"].content

        # 无邀请码时，初始化manager的为邀请码
        if not self.invitation_code:
            self.invitation_code[self.manager] = sender_id

        # 机器人向外新添加好友时
        if e_context["context"].type == ContextType.ACCEPT_FRIEND:
            reply = Reply()
            reply.type = ReplyType.TEXT
            temp_invitation = self.generate_invitation_code()
            reply.content = f"您已获得1天试用!\n激活码为：{temp_invitation}"
            self.invitation_code[temp_invitation] = sender_id
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS

        reply = Reply()
        reply.type = ReplyType.TEXT

        if (sender_id in self.whitelist or group_id in self.whitelist):
            # 当用户已经在白名单中时，仍可以查询有效期及申请邀请码
            # 或者群聊id已经在白名单时
            if not self.is_valid(sender_id):
                # 当激活码已过期,需要移出白名单，也可以选择不移除，继续在原验证码续费
                # 若要ignore，把return去掉就行
                reply.content = "您的试用已过期，请重新激活。"
                if(sender_id in self.whitelist):
                    self.whitelist.remove(sender_id)
                elif group_id and (group_id in self.whitelist):
                    self.whitelist.remove(group_id)
                if(sender_id in self.user_id):
                    self.user_id.pop(sender_id)
                elif group_id and (group_id in self.user_id):
                    self.user_id.pop(group_id)
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
                return
            if content == "查询有效期":
                # 查询有效期
                invitation_code = self.user_id[sender_id]
                # 获取邀请码的数据
                invitation_data = self.verify_code[invitation_code]
                # 计算有效期
                start_time = datetime.fromtimestamp(invitation_data["time"])
                duration = timedelta(seconds=invitation_data["duration"])
                expiry_date = start_time + duration
                # 返回有效期
                reply.content = f"您的试用有效期至{expiry_date.strftime('%Y年%m月%d日')}。"            
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
            elif content == "申请邀请码":
                # 生成邀请码
                # 要获取发送人的id
                invitation_code = self.apply_invitation(sender_id)
                reply.content = f"您的邀请码为{invitation_code}"
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
        elif content.startswith("激活码"):
            # 发送激活码 这里要辨别是不是正确的，不是就返回错误
            if self.verify_invitation(content):
                reply.content = "激活成功！"

                # 移入已使用邀请码
                invitation_code = content[4:]
                self.verify_code[invitation_code] = {"sender_id": sender_id, "time": time.time(), "duration": self.initial_time * 3600}
                
                # 添加白名单
                self.whitelist.append(sender_id)
                self.user_id[sender_id] = invitation_code

                # 加邀请人时间
                inviter = self.invitation_code[invitation_code]
                if self.user_id[inviter] in self.verify_code:
                    t = self.verify_code[self.user_id[inviter]]["duration"]
                    self.verify_code[self.user_id[inviter]]["duration"] = t + self.hours_extension * 3600

                # 移出未使用邀请码，
                self.invitation_code.pop(invitation_code)

                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
            else:
                reply.content = "激活码错误！"
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
        else:
            reply = Reply()
            reply.type = ReplyType.TEXT
            reply.content = "请发送正确的激活码来获取机器人的使用权限。"
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS


    def generate_invitation_code(self):
        # 生成随机的邀请码
        return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=random.randint(6, 10)))
    
    def apply_invitation(self, sender_id):
        # 申请邀请码
        invitation_code = self.generate_invitation_code()
        # 存储邀请码与邀请人
        self.invitation_code[invitation_code] = sender_id
        return invitation_code
    
    def verify_invitation(self, received_code):
        # 验证邀请码是否正确
        pattern = re.compile(r'^激活码[:：]\s*([A-Za-z0-9]+[A-Za-z0-9]$)')
        match = pattern.match(received_code)

        if match:
            user_code = match.group(1)
            if user_code in self.invitation_code:
                return True
            else:
                return False
        else:
            return False
        
    def is_valid(self, sender_id):
        # 判断这个人对应的激活码是否在持续时间内
        if sender_id in self.whitelist:
            invitation_data = self.verify_code[self.user_id[sender_id]]
            start_time = datetime.fromtimestamp(invitation_data["time"])
            duration = timedelta(seconds=invitation_data["duration"])
            expiry_date = start_time + duration
            if expiry_date > datetime.now():
                return True
            else:
                return False
        else:
            return False

            
    def get_help_text(self, **kwargs):
        help_text = (
            f'''
            通过激活码与邀请码来获得机器人的使用权限。\n
            若您是新用户，请输入“申请使用”后以“激活码：XXX”的形式激活。\n
            若您是老用户，可输入“查询有效期”来查询有效期或“申请邀请码”来生成你自己的邀请码\n
            若账号过期，请联系管理员以增加使用时间！\n
            成功邀请他人使用机器人后，您的使用时间会延长{self.hours_extension}小时！\n
            '''
        )
        return help_text