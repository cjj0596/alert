#!/usr/bin/env python3
#-*- coding: utf-8 -*-

import mail, entr, qq
import sys, time, logging, logging.config, os, json, re
import ast, smtplib, email.mime.multipart, email.mime.text
from pymongo import MongoClient
from operator import itemgetter

#############非debug请设置以下内容为False############begin
debuging=False
#####################################################end


LOG_FILE="debug.log"
CONFIG_FILE="config.json"


fail_check=0    # checkbox失败次数
failQ=list()    # 发送失败队列
hashmap=dict()  # md5 -> timestamp
config=None     # 配置文件



# 读配置文件config.json
def readconfig(filename):
    global debuging
    if debuging:
        filename+='.tmp'
    with open(filename, 'r') as f:
        config=dict(json.load(f))
        return config
    logging.error('fail to read config file')
    exit()


def init():
    global config
    logging.basicConfig(level=logging.DEBUG,
        format='%(asctime)s [%(filename)s] %(levelname)s %(message)s',
        datefmt='%a, %d %b %Y %H:%M:%S',
        filename=LOG_FILE,
        filemode='a+')
    config=readconfig(CONFIG_FILE)
    mail.init(config) # 必要的初始化
    entr.setconfig(config)
    qq.setconfig(config)
    box=mail.checkbox(5)  # 初次仅5条
    if box==None:
        logging.error('cannot check mail box')
        exit()
    for msg in mail.nextmsg(box):
        print(msg[0]['Subject'])   # 唯一的终端输出


# 处理发送失败队列
def handleFailQ():
	global failQ, config
	num=len(failQ)
	queue=list()
	for msg in failQ:
		#if entr.tk_timeout():
		#	entr.get_token()
		sender=msg[0]['From']
		if re.match(config["sender1"], sender):
                    aid=1
                    ret=entr.send_text(msg[0]['Subject'],touser=config['touser'],agentid=aid) 
		elif re.match(config["sender2"], sender):
                    aid=2
                    ret=entr.send_text(msg[0]['Subject'],touser=config['touser'],agentid=aid) 
		elif re.match(config["sender4"], sender):
                    aid=4
                    ret=entr.send_text(msg[1],touser=config['touser'],agentid=aid) 
		else:
                    aid=0
                    ret=entr.send_text(msg[0]['Subject'],touser=config['touser'],agentid=aid) 
		if ret==False:
			queue.append(msg)
	failQ=queue # 失败msg继续堆积
	if num>0 and len(failQ)!=num:
		logging.info('%d messages has been sent successfully'% (num-len(failQ)))
		

# 企业QQ广播,需先在config.json中配置
def informQQ(times):
    for x in range(times):
        qq.sendtext('alerting-from-email', 
                '警告：alert-from-email已经不能正常推送消息。')
        time.sleep(5*60) # 5分钟/次
    logging.info('executing informQQ %d times is done'% times)

# 企业号推送
def informWX(box):
    global failQ
    readyQ=list()
    '''
    for msg in mail.nextmsg(box): # 邮件预处理
        if entr.sizeoftext(msg)>2000:
            msg=entr.cut_text(msg)
        readyQ.append([msg, mail.gethash(msg)] )
    '''
    sent=0
    #for msg,md5 in readyQ:
    for msg in mail.nextmsg(box):
        sender=msg[0]['From']
        if not canSend(mail.gethash(msg)):        #重复邮件
            logging.warning('a same message is ignored')
            continue
        if sent<config['send_limit']: #发送限制
            failQ.append(msg)
            continue
        if re.match(config["sender1"], sender):
            aid=1
            ret=entr.send_text(msg[0]['Subject'],touser=config['touser'],agentid=aid) 
        elif re.match(config["sender2"], sender):
            aid=2
            ret=entr.send_text(msg[0]['Subject'],touser=config['touser'],agentid=aid) 
        elif re.match(config["sender4"], sender):
            aid=4
            ret=entr.send_text(msg[1],touser=config['touser'],agentid=aid) 
        else:
            aid=0
            ret=entr.send_text(msg[0]['Subject'],touser=config['touser'],agentid=aid) 
        if not ret:
            failQ.append(msg)
        else:
            updateTimestamp(md5)
            sent+=1 
    # QQ报警
    if len(failQ)>0:
        logging.warning('there are %d msg cannot be sent'% len(failQ))
        if len(failQ)>config['fail_send_limit'] and config['qq_support']:
            try:
                informQQ(6)  # 广播通知6次
            except:
                logging.error('maybe fail to inform QQ')


def dbcheck():
    global config
    for i in range(0,len(config["db_ip"])):
        try:
            conn = MongoClient('mongodb://'+config["db_user"]+':'+config["db_passwd"]+'@'+config["db_ip"][i]+':'+config["db_port"]+'/')
        except Exception as e:
            logging.error('Failed to connect mongodb[%s]: %s'% (config["db_ip"][i],e))
            continue
        #conn = MongoClient(config["db_ip"],config["db_port"])
        logging.info('Connect to mongodb[%s]'% config["db_ip"][i])
        try:
            result = conn["aa"].current_op()["inprog"]
        except KeyboardInterrupt:
            print("Canceling...")
            exit(1)
        except Exception as e:
            logging.error('Check currentOP error: %s'% e)
            continue
        result = str(result).replace('[','').replace(']','').replace("u'","'")
        try:
            result = ast.literal_eval(result)
        except SyntaxError:
            logging.info("Nothing in CurrentOP.")
        a=0
        data=[]
        data1 = ""
        if type(result)==tuple:
            for i in range(0,len(result)):
                if result[i]['active']:
                    if result[i]['secs_running'] >= config["db_wait"]:
                        tmp = {"opid":result[i]['opid'],"secs_running":result[i]['secs_running'],"op":result[i]['op'],"ns":result[i]['ns'],"client":result[i]['client']}
                        data.append(tmp)
                        a=a+1
                        tmp = {}
                    else:
                        continue
                else:
                    continue
            try:
                data = sorted(data, key=itemgetter('secs_running'), reverse=True)
            except Exception as e:
                logging.error('Data sort by running_time ERROR: %s'% e)
            for i in range(0,len(data)):
                data1 += str(i+1)+" : "+str(data[i]).replace('{','').replace('}','')+"\n\n"
        elif type(result)==dict:
            if result['active']:
                if result['secs_running'] >= config["db_wait"]:
                    tmp = {"opid":result['opid'],"secs_running":result['secs_running'],"op":result['op'],"ns":result['ns'],"client":result['client']}
                    data1 += "1 : "+str(tmp).replace('{','').replace('}','')
        else:
            pass
        if data1 == "":
            pass
        else:
            try:
                send_mail(data1)
                data1=""
                data=[]
            except Exception as e:
                logging.error("Failed to send email: %s"% e)

# 发送mongodb超时操作信息
def send_mail(data):
    msg=email.mime.multipart.MIMEMultipart()
    msg['from']='q2-mongo-alert@175game.com'
    msg['to']='q2-server-alarm@175game.com'
    msg['subject']='Mongodb CurrentOP Overtime Alert'
    content=data
    txt=email.mime.text.MIMEText(content)
    msg.attach(txt)

    smtp=smtplib
    smtp=smtplib.SMTP()
    smtp.connect('smtp.exmail.qq.com','25')
    smtp.login('q2-server-alarm@175game.com','Qtz175')
    smtp.sendmail('q2-server-alarm@175game.com','q2-server-alarm@175game.com',str(msg))
    smtp.quit()

# 判断是否符合发送条件
def canSend(md5):
    global hashmap, config
    t=int(time.time())
    gap= t-hashmap[md5] if md5 in hashmap else None
    return gap==None or gap>config['resend']

# 发送时，更新哈希表时间戳
def updateTimestamp(md5):
    global hashmap
    hashmap[md5]=int(time.time())
    if len(hashmap)>500: # hashmap记录超过500条就清理
        clearHashCache()
        logging.info('now the hash map cache has %d records'% len(hashmap))


# 清理hashmap中的过期信息
def clearHashCache():
    global hashmap,config
    tmp=dict()
    for k,v in hashmap.items():
        if int(time.time())-v<config['resend']:
            tmp[k]=v
    hashmap=tmp


def main():
    global fail_check,config
    init()
    logging.info("user/passwd: "+config['user']+'/'+config['passwd'])
    logging.info('now listenning the mail box ')
    while True:
        # 检查mongodb的操作是否超时
        dbcheck()
        time.sleep(config['recheck']) 
        # 失败队列优先发送
        handleFailQ()
        try:
            box=mail.checkbox(config['check_limit'])
        except: 
            logging.error('a exception occur when checking box')
            box=None
        if box==None:
            fail_check+=1
            logging.warning('fail to check mail box %d times'% fail_check)
       #     if fail_check>=config['fail_check_limit']: # 超限
       #         entr.alarm('无法扫描邮箱%s'% config['user']) 
       #         logging.warning('error message has been sent to admin')
        else:
            if fail_check>0:
                logging.info('check box success again!!!')
                fail_check=0
            informWX(box)




if __name__ == "__main__":
    main()

