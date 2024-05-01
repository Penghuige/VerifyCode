# VertifyCode邀请码插件

当你的群聊中有个自己搭建的COW机器人，却不想让别人使用怎么办？

VertifyCode是你的不二之选！🥳

该插件能够通过邀请码验证的功能，限制用户使用COW机器人。当你第一次与机器人聊天，需要输入从管理员/老用户/初始赠送的邀请码，以“激活码：XXX”的形式发送给机器人，就能成功获取机器人的使用权！当你激活该机器人后，你也成为老用户的一员了，可以通过输入“申请邀请码”来获取新的一个邀请码，当这个邀请码被激活时，你和新用户都能得到新的使用时间！

作为管理员，你不但可以申请邀请码，还能申请任意时间的激活码！输入"激活码:root"(root为程序默认的管理员激活码，可修改config中的manager进行自定义)以获得系统的管理员权限！

程序运行中会将数据自动存储到插件同文件夹下的data中，每次程序运行前将会读取，保证上次记录还在，可以在json文件中修改save_file的值来选择是否开启这个功能。同时，也可以输入“下载数据”来本地保存所有的json文件。

Enjoy this!

ChatGPT on Wechat(COW) 原项目地址：https://github.com/zhayujie/chatgpt-on-wechat

## 安装教程

根据你自己的需要，修改以下的配置/不修改，将config.json.template重命名为config.json后，将整个文件夹放入plugins文件夹，即可自动激活该插件！

**！！！别忘记删除注释！！！**

<img src=".\image\config1.png" alt="example1" style="zoom:50%;" />

## 使用示例

功能展示：

用户没有使用激活码激活时，将无法使用机器人。可进行申请试用生成一天的激活码。

<img src=".\image\example1.png" alt="example1" style="zoom:50%;" />

邀请码/验证码的申请/激活：

管理员可以申请激活码/邀请码，普通用户可以申请邀请码，邀请码仅能保存最后一次申请，而激活码不做限制。申请激活码后面可以加上天数作为有效时间，邀请码只能为一天（config中的initial_time可以修改）。

<img src=".\image\example3-2.png" alt="example3-2" style="zoom: 25%;" />

<img src=".\image\example3-3.png" alt="example3-3" style="zoom:50%;" />

群聊认证：

若管理员/已认证用户在群聊中召唤机器人，照样可以使用，未认证用户无法使用

<img src=".\image\example3-1.png" alt="example3-1" style="zoom: 33%;" />

邀请新用户获得使用时长：

老用户邀请新用户后可以增加自身一天（可自定义，在config中修改）时长。

<img src=".\image\example3-5.png" alt="example3-5" style="zoom:50%;" />

<img src=".\image\example3-6.png" alt="example3-6" style="zoom:50%;" />



下载data数据（仅管理员）：

<img src=".\image\example4.png" alt="example4" style="zoom:50%;" />