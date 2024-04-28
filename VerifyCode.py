# encoding:utf-8

import json
import os
import random
import re
import time
from datetime import datetime, timedelta
import threading


import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage

from common.log import logger
from plugins import *
from plugins.godcmd import Godcmd

# 这个文件用来实现功能：添加好友后进行判断，若发送邀请码且邀请码
# 正确，则能使用机器人的功能，若不正确则不行
# 刚加好友的时候能够获得一天试用，通过自身发送激活码来激活

@plugins.register(
    name="VerifyCode",
    desire_priority=998,
    hidden=False,
    desc="通过激活码与邀请码来获得机器人的使用权限。",
    version="1.0",
    author="Penghuige",
)
class VerifyCode(Plugin):
    def __init__(self):
        super().__init__()
        # 存放未被使用的邀请码 初始给了个root,邀请人为本身
        self.invitation_code = {}
        # 存放邀请人对应的邀请码，每个人只能由一个邀请码
        self.inviter_code = {}
        # 存放已被使用的邀请码，以邀请码为索引，存放用户ID、注册时间、有效期
        self.verify_code = {}
        # 存放已被激活的用户ID
        self.whitelist = []
        # 存放用户ID和激活码的对应关系，每个用户对应一个激活码
        self.user_id = {}
        # 管理员
        self.admin = []
        # 存放申请激活码的人，防止重复激活
        self.request_id = []

        try:
            # load config
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                logger.info(f"[VerifyCode] 加载配置文件成功: {config}")

                self.initial_time = config["initial_time"]   
                self.hours_extension = config["hours_extension"]
                self.manager = config["manager"]
                self.save_time = config["save_time"]
                self.save_file = config["save_file"]

            if self.save_file:
                # 在程序开始时加载数据
                # 统一打开文件夹
                self.invitation_code = self.load_from_json('./plugins/VerifyCode/data/invitation_code.json', dict)
                self.inviter_code = self.load_from_json('./plugins/VerifyCode/data/inviter_code.json', dict)
                self.verify_code = self.load_from_json('./plugins/VerifyCode/data/verify_code.json', dict)
                self.whitelist = self.load_from_json('./plugins/VerifyCode/data/whitelist.json', list)
                self.user_id = self.load_from_json('./plugins/VerifyCode/data/user_id.json', dict)
                self.admin = self.load_from_json('./plugins/VerifyCode/data/admin.json', list)
                # 保存数据的线程
                self.save_thread = threading.Thread(target=self.save_data_periodically)
                # 这个线程在程序结束后会卡着，需要关掉
                self.save_thread.daemon = True
                self.save_thread.start()

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
        isgroup = e_context["context"].get("isgroup")
        
        
        group_id = None
        if isgroup:
            # 是群信息，判断该群是否开启了激活码，这里的标识符是群名称，未找到群号
            group_id = e_context.econtext["context"]["receiver"]
            sender_id = e_context.econtext["context"]["session_id"]
        else:
            sender_id = e_context.econtext["context"]["receiver"]
        
        content = e_context["context"].content

        # 无邀请码时，初始化manager的为邀请码
        if not self.invitation_code:
            self.invitation_code[self.manager] = sender_id

        reply = Reply()
        reply.type = ReplyType.TEXT
        
        # 以分隔符空格为分割，区分命令与参数
        cmd, *args = content.split(" ")

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
            if cmd == "申请激活码":
                # 生成邀请码
                # 要获取发送人的id
                # 仅有管理员才能申请邀请码
                if sender_id in self.admin:
                    duration = self.initial_time/24
                    if len(args) > 0:
                        # 申请args天 需要判断args是否是整数
                        if not args[0].isdigit():
                            reply.content = "请输入正确的天数！"
                            e_context["reply"] = reply
                            e_context.action = EventAction.BREAK_PASS
                            return
                        else:
                            duration = int(args[0])
                    invitation_code = self.apply_invitation(sender_id)
                    self.invitation_code[invitation_code].append(duration)
                    reply.content = f"您的邀请码为{invitation_code}"
                    e_context["reply"] = reply
                    e_context.action = EventAction.BREAK_PASS
                else:
                    reply.content = "您没有权限申请激活码，请申请邀请码！"
                    e_context["reply"] = reply
                    e_context.action = EventAction.BREAK_PASS
            elif cmd == "申请邀请码":
                duration = self.initial_time/24
                # 生成一个邀请码
                invitation_code = self.apply_invitation(sender_id)
                # 若原先他已经申请过一个邀请码，替换
                if sender_id in self.inviter_code:
                    self.invitation_code.pop(self.inviter_code[sender_id])
                self.inviter_code[sender_id] = invitation_code

                reply.content = f"您的邀请码为{invitation_code}"
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
            elif cmd == "查询有效期":
                # 查询有效期
                invitation_code = self.user_id[sender_id]
                # 获取邀请码的数据
                invitation_data = self.verify_code[invitation_code]
                # 计算有效期
                start_time = datetime.fromtimestamp(invitation_data["time"])
                duration = timedelta(seconds=invitation_data["duration"])
                expiry_date = start_time + duration
                # 返回有效期
                reply.content = f"您的有效期至{expiry_date.strftime('%Y年%m月%d日')}。"            
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
        elif cmd.startswith("激活码"):
            # 发送激活码 这里要辨别是不是正确的，不是就返回错误
            # 如果通过manager激活码激活的，直接加入管理员名单
            if self.verify_invitation(content):
                reply.content = "激活成功！"
                
                # 移入已使用邀请码
                invitation_code = content[4:]
                # 若该激活码有设定时间，按设定时间来，否则按初始时间来
                if isinstance(self.invitation_code[invitation_code], list) and len(self.invitation_code[invitation_code]) > 1:
                    duration = self.invitation_code[invitation_code][1]
                else:
                    duration = self.initial_time/24
                self.verify_code[invitation_code] = {"sender_id": sender_id, "time": time.time(), "duration": duration * 24 * 3600}
                # 添加白名单
                self.whitelist.append(sender_id)
                self.user_id[sender_id] = invitation_code

                # 加入管理员名单
                if invitation_code == self.manager:
                    self.admin.append(sender_id)
                    self.verify_code[invitation_code]["duration"] = 9999 * 24 * 3600

                # 给邀请人加时间
                inviter = self.invitation_code[invitation_code]
                # 如果inviter是列表，去第一项
                if isinstance(inviter, list):
                    inviter = inviter[0]
                if self.user_id[inviter] in self.verify_code:
                    t = self.verify_code[self.user_id[inviter]]["duration"]
                    self.verify_code[self.user_id[inviter]]["duration"] = t + self.hours_extension * 3600

                # 移出未使用邀请码
                self.invitation_code.pop(invitation_code)

                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
            else:
                reply.content = "激活码错误！"
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
        elif cmd == "申请试用":
            if sender_id in self.whitelist:
                reply.content = "您已经是正式用户了！"
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
            elif sender_id in self.request_id:
                reply.content = "您已经申请过试用了，请联系管理员以获得更多天数！"
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS

            # 发送一天试用激活码
            invitation_code = self.generate_invitation_code()
            reply.content = f"您已获得{self.initial_time/24}天试用!\n激活码为：{invitation_code}"
            self.invitation_code[invitation_code] = sender_id
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS
        else:
            reply = Reply()
            reply.type = ReplyType.TEXT
            reply.content = "请发送正确的激活码，或是输入“申请试用”来获取机器人的使用权限。"
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS


    def generate_invitation_code(self):
        # 生成随机的邀请码
        return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=random.randint(6, 10)))
    
    def apply_invitation(self, sender_id):
        # 申请邀请码
        invitation_code = self.generate_invitation_code()
        # 存储邀请码与邀请人
        self.invitation_code[invitation_code] = [sender_id]
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
若您是新用户，请输入“申请试用”后以“激活码：XXX”的形式激活。\n
若您是老用户，可输入“查询有效期”来查询有效期或“申请邀请码”来生成你自己的邀请码\n
若您是管理员，可输入“申请激活码 111”来生成111天（若空则为一天）的激活码\n
若账号过期，请联系管理员以增加使用时间！\n
成功邀请他人使用机器人后，您的使用时间会延长{self.hours_extension}小时！\n
            '''
        )
        return help_text
    
    def load_from_json(self, filename, expected_type):
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                if not isinstance(data, expected_type):
                    print(f"Warning: data in {filename} is not of type {expected_type.__name__}, creating a new one.")
                    data = expected_type()
                return data
        except FileNotFoundError:
            return expected_type()
        

    def save_to_json(self, data, filename):
        # 检查文件夹是否存在，如果不存在，创建它
        # 需要保存在与这个文件相同文件夹的data文件夹
        folder = os.path.dirname(filename)
        if not os.path.exists(folder):
            os.makedirs(folder)
        with open(filename, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
    def save_data_periodically(self):
        while True:
            # 在程序运行过程中保存数据
            self.save_to_json(self.invitation_code, './plugins/VerifyCode/data/invitation_code.json')
            self.save_to_json(self.inviter_code, './plugins/VerifyCode/data/inviter_code.json')
            self.save_to_json(self.verify_code, './plugins/VerifyCode/data/verify_code.json')
            self.save_to_json(self.whitelist, './plugins/VerifyCode/data/whitelist.json')
            self.save_to_json(self.user_id, './plugins/VerifyCode/data/user_id.json')
            self.save_to_json(self.admin, './plugins/VerifyCode/data/admin.json')

            # 等待一段时间
            time.sleep(self.save_time*60)  # 每小时保存一次数据