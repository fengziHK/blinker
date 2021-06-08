#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 树莓派利用WOL和OPENSSH实现开关机。 针对WIN10, 电脑需要openssh！
# 直接拿去用需要改5处，1，密匙，2，局域网电脑的固定IP，3，电脑ssh用户名，4，电脑ssh密码 5，电脑的MAC地址

from Blinker import Blinker, BlinkerButton, BlinkerNumber, BlinkerMIOT
from Blinker.BlinkerConfig import *
from Blinker.BlinkerDebug import *
from wakeonlan import send_magic_packet
import paramiko
import time
import subprocess

auth = '8b56d9ab3ce0'  # 1,点灯app上获得的密匙

BLINKER_DEBUG.debugAll()

Blinker.mode("BLINKER_WIFI")
Blinker.miotType('BLINKER_MIOT_OUTLET')
Blinker.begin(auth)

staticip = "192.168.0.102"  # 2,电脑局域网固定IP，用于检测电脑开关状态以及利用SSH关机，改为你的设置
pcusr = 'test'  # 3,电脑ssh用户名
pcpw = '123'  # 4,电脑ssh密码

pcmac = '00.0C.29.BF.E7.04'  # 5,MAC地址，改成你自己电脑网卡的

button1 = BlinkerButton("btn-pc2")  # 数据键，在App里设置一个一样的开关，类型为 '开关按键'，图标用滑动开关，其他随意，文本可为空
cmd1 = "timeout 0.1 ping -c 1 " + staticip  # 电脑开关检测就是一个局域网内的ping，超时我设置为100ms，貌似太短或太长小爱都容易出错
lockbutton1 = False

oState = ''

def miotPowerState(state):
    ''' '''

    global oState

    BLINKER_LOG('need set power state: ', state)

    oState = state
    BlinkerMIOT.powerState(state)
    BlinkerMIOT.print()
# 小爱控制的实际部分放在上报状态之后，因为电脑开机实际时间很长，小爱等久了她会以为没开
    if state == 'true':
        button1_callback('on')
    elif state == 'false':
        button1_callback('off')

def miotQuery(queryCode):
    ''' '''

    global oState

# 问小爱电脑开了吗，ping一次获得电脑实际状态
    if subprocess.call(cmd1, shell=True)==0:
        oState = 'true'
    else:
        oState = 'false'

    BLINKER_LOG('MIOT Query codes: ', queryCode)

    if queryCode == BLINKER_CMD_QUERY_ALL_NUMBER :
        BLINKER_LOG('MIOT Query All')
        BlinkerMIOT.powerState(oState)
        BlinkerMIOT.print()
    elif queryCode == BLINKER_CMD_QUERY_POWERSTATE_NUMBER :
        BLINKER_LOG('MIOT Query Power State')
        BlinkerMIOT.powerState(oState)
        BlinkerMIOT.print()
    else :
        BlinkerMIOT.powerState(oState)
        BlinkerMIOT.print()

# 关机部分用paramiko的sshclient，不用密码的话可以改用密匙，具体查阅paramiko用法
def shutdownpc():

    global staticip
    global pcusr
    global pcpw

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(staticip, username=pcusr, password=pcpw)
    stdin, stdout, stderr = client.exec_command('shutdown -s -f -c "小爱将在10秒内关闭这个电脑" -t 10')  

    if client is not None:
        client.close()
        del client, stdin, stdout, stderr

# 开关键，集成了开关功能，状态报告给小爱，开关过程中的运行保护，开关后状态的更新。
def button1_callback(state):
    """ """
    global lockbutton1
    global oState
    global pcmac
    dtimeout = 60  # 开关机超时默认60秒

    if lockbutton1==False:
        BLINKER_LOG('get button state: ', state)
        if state=='on':
            if subprocess.call(cmd1, shell=True)==0:
                oState = 'true'
                Blinker.print("检测到电脑已开,按钮状态已更新")
                button1.text('已开机')
                button1.print(state)
            else:
                Blinker.print("发送开机指令...")
                oState = 'true'
                lockbutton1 = True
                tic = time.perf_counter()
                toc = time.perf_counter()
                send_magic_packet(pcmac)  # 发魔术包开机
                while subprocess.call(cmd1, shell=True)!=0 and toc-tic<dtimeout+2:
                    time.sleep(2)
                    toc = time.perf_counter()
                if toc-tic >= dtimeout:
                    Blinker.print("开机超时!")
                    button1.text('已关机')
                    button1.print('off')
                else:
                    button1.text('已开机')
                    button1.print(state)
                lockbutton1 = False
        elif state=='off':
            if subprocess.call(cmd1, shell=True)==0:
                Blinker.print("发送关机指令...")
                oState = 'false'
                lockbutton1 = True
                tic = time.perf_counter()
                toc = time.perf_counter()
                shutdownpc()  # 关机
                while subprocess.call(cmd1, shell=True)==0 and toc-tic<dtimeout+2:
                    time.sleep(2)
                    toc = time.perf_counter()
                if toc-tic >= dtimeout:
                    Blinker.print("关机超时!")
                    button1.text('已开机')
                    button1.print('on')
                else:
                    button1.text('已关机')
                    button1.print(state)
                lockbutton1 = False
            else:
                oState = 'false'
                Blinker.print("检测到电脑已关闭,按钮状态已更新")
                button1.text('已关机')
                button1.print(state)
    else:
        Blinker.print("正在开机或关机中..")

# 心跳加入了电脑状态检测，更新按钮
def heartbeat_callback():

    global oState

    if subprocess.call(cmd1, shell=True)==0:
        oState = 'true'
        button1.text('已开机')
        button1.print("on")
    else:
        oState = 'false'
        button1.text('已关机')
        button1.print("off")

button1.attach(button1_callback)
Blinker.attachHeartbeat(heartbeat_callback)

BlinkerMIOT.attachPowerState(miotPowerState)
BlinkerMIOT.attachQuery(miotQuery)

if __name__ == '__main__':

    while True:
        Blinker.run()