#!/usr/bin/env python3
#-*- coding:utf-8 -*-

import urllib, urllib.request
import time, json, logging

TK_URL="https://qyapi.weixin.qq.com/cgi-bin/gettoken"
POST_URL="https://qyapi.weixin.qq.com/cgi-bin/message/send"

token_stp=0
token=None
config=None


def setconfig(c):
	global config
	config=c
	get_token()


# 获取access token,更新全局时间戳
def get_token():
    global token_stp,token,config
    value={ 'corpid': config['corpid'],
            'corpsecret': config['corpsecret']
            }
    data=urllib.parse.urlencode(value)
    req=urllib.request.Request(TK_URL+ '?'+ data)
    with urllib.request.urlopen(req) as f:
        res=json.loads(f.read().decode('utf-8'))
        token=res['access_token'] if 'access_token' in res else None
        token_stp=time.time()
    return token

# 发送消息之前，请先检验token是否失效
def tk_timeout():
    last=time.time()-token_stp
    hours=(last+30)/3600 #时间差
    return True if hours>=2.0 else False

# 发送消息
def send_text(text, toparty=None, touser=None, agentid=0):
	global config
	if tk_timeout():
		get_token()
	value=dict()
	if toparty==None and touser==None:
		raise ValueError # 至少指定其一
	elif toparty:
		value['toparty']=toparty
	else:
		value['touser']=touser
	value['msgtype']='text'
	value['agentid']=agentid
	value['text']={'content': text}
	data=json.JSONEncoder(ensure_ascii=False).encode(value).encode('utf-8')
	suffix=urllib.parse.urlencode({'access_token': token})
	url=POST_URL+ '?'+ suffix
	req=urllib.request.Request(url, headers={'Content-Type':'application/json; charset=utf-8'})
	with urllib.request.urlopen(url, data) as f:
		res=json.loads(f.read().decode('utf-8'))
		if res['errcode']==0:
			return True 
		else:
			logging.error('send_text fail,error message:%s, code:[%s]'% (res['errmsg'],res['errcode']))
	return False 

# 持续性通知所有人times次
def alarm(text, times=6):
    global config
    if tk_timeout():
        get_token(config['corpid'], config['corpsecret'])
    ret=False
    wait=60
    for x in range(times):
        if entr.send_text(text, config, touser='@all'):
            ret=True
        time.sleep(wait)
        wait*=2
    return ret

if __name__=="__main__":
    pass

