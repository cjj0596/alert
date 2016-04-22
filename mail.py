#!/usr/bin/env python3
#-*- coding: utf-8 -*-

MAIL_LIST="mail.list"
TIME_FMTs="%a, %d %b %Y %H:%M:%S %z"
TIME_FMTz="%d %b %Y %H:%M:%S %z"
TIME_FMTg="%Y-%m-%d %H:%M:%S"

last_mail_id=None #由本模块维护
config=None




import logging, logging.config, os, hashlib,\
    poplib, json, time, sys, socket, ast

from datetime import datetime
from email.parser import Parser
from email.header import decode_header
from email.utils import parseaddr



# 使用本模块前需前先初始化,在这修改即可
def init(cf):
    global last_mail_id,config
    config=cf
    poplib._MAXLINE=2*20480 # 邮件大小，一般够用
    last_mail_id=None
    if os.path.isfile('lastMailId'):
        with open('lastMailId', 'r') as f:
            tmp=f.readline()
            last_mail_id=tmp if tmp else None

# 递归解析content为str
def getcontent(msg):
    if msg.is_multipart():
        for x in msg.get_payload():
            ret=getcontent(x)
            if ret:
                return ret
    elif msg.get_content_type()=='text/plain':
        content=msg.get_payload(decode=True) # 编成byte 
        return content.decode(guesscharset(msg)).replace('\r\n','\n').strip()  # 以utf-8展示
    else:
        return None

# 猜测/获取编码
def guesscharset(msg):
    charset = msg.get_charset()
    if charset is None:
        content_type = msg.get('Content-Type', '').lower()
        pos = content_type.find('charset=')
        if pos>=0:
            tmp=content_type[pos+8:].strip()
            tmp=tmp[1:] if tmp[0]=='"' else tmp
            charset=''
            for c in tmp:
                if c.isdigit() or c.isalpha() or c=='-':
                    charset+=c 
                else:
                    break
        else:
            charset='utf-8'
    return charset

# 解析header为str
def getheader(msg):
    # 发送人
    fro=msg['From']
    sender, addr= parseaddr(fro)
    header='{"From": "%s" ,'% addr 
    # 主题
    sub=getMsgSub(msg)
    header+='"Subject": "%s"}'% sub 
    return header

def getSender(msg):
    fro=msg['From']
    sender, addr= parseaddr(fro)
    sender=str2utf8(sender)
    return sender

# header时间格式化
def timeStandardize(s):
    if len(s)>31:
        s=s[0:31].strip()
    if s.find(',')>0:
        t=datetime.strptime(s, TIME_FMTs)
    else:
        t=datetime.strptime(s, TIME_FMTz)
    return t.strftime(TIME_FMTg)

# 处理header编码
def str2utf8(s):
    val, cset= decode_header(s)[0]
    return val.decode(cset) if type(val)==bytes else val

# 获取消息ID
def getMsgId(msg):
    return msg['Message-ID']

# 获取消息时间，并转为str
def getMsgDate(msg):
    date=msg['Date']
    try:
        return timeStandardize(date)
    except: #时间格式未识别，强切成当前时间
        return time.time().strftime(TIME_FMTg)

# 获取主题
def getMsgSub(msg):
    return str2utf8(msg['Subject'])

# 用于推送时的邮件判重
def gethash(msg):
    ret=''
    for c in msg[1]:
        if c=='\n' or c=='\r': # 去换行
            continue
        #elif c.isdigit():
        #    ret+='a' # 数字替换
        else:
            ret+=c
    return hashlib.md5(ret.encode('utf-8')).hexdigest()

# 用于接收时的邮件判重(简单的)
def getMD5(msg):
    _msg=getheader(msg)+getcontent(msg)
    return hashlib.md5(_msg.encode('utf-8')).hexdigest()

# 计算文本编码后所占长度
def sizeoftext(text):
    codetext=text.encode('utf-8')
    return len(codetext)
    
# 切成可发送长度
def cut_text(text, length=2000):
    L, R= 0, len(text)
    while L<R:
        mid=R-int((R-L+1)/2)
        if sizeoftext(text[:mid])>length:
            R=mid
        else:
            L=mid+1
    return text[:R]


# 连接邮箱服务器 
def connect():
    global config
    server=poplib.POP3_SSL(config['pop3_server'], config['pop3_ssl_port'], timeout=120)
    #server.set_debuglevel(0) # 若调试则为1
    try:
        server.user(config['user'])
        server.pass_(config['passwd'])
    except poplib.error_proto:
        logging.error('fail to auth')
        return None
    except socket.timeout:
        logging.warning('socket timeout')
        return None
    return server


# 将箱子中的邮件处理出来，这是generator
def nextmsg(box):
    global last_mail_id,data
    mails=list()
    for msg in reversed(box):
        # subject存盘
        #with open(MAIL_LIST, 'a+') as f:
        #    f.write('%s\t%s\n'% (getMsgDate(msg), getMsgSub(msg)))
        data=[]
        header=getheader(msg)
        data.append(json.loads(header))
        content=getcontent(msg)
        data.append(content)
        #if content==None:
        #    content='this email content cannot be parse'
        #ret=ret if sizeoftext(ret)<2000 else cut_text(ret)
        yield data
        last_mail_id=getMD5(msg)
        with open('lastMailId', 'w') as f:
            f.write('%s'% last_mail_id)
    return True


# 扫描信箱,限制扫描数量
def checkbox(last=100):
    global last_mail_id
    server=connect()
    if not server:
        return None
    cnt, siz= server.stat()  
    #logging.info('message count: %s ， mailbox size: %s' % (cnt, siz))
    box, down= list(), max(cnt-last, 0)+1
    for x in reversed(range(down, cnt+1)): # 倒序提取最新消息
        lines=server.retr(x)[1]
        try:    # 注:默认忽略未识别的编码
            msg_content = b'\r\n'.join(lines).decode('utf-8') 
        except:  
            logging.warning('got a email that contains unknown code.' )
            continue
        msg=Parser().parsestr(msg_content) 
        if last_mail_id==getMD5(msg):
            break
        box.append(msg)
    return box






if __name__=="__main__":
    pass





