# -*- coding:utf-8 -*-

'''configuration'''

__author__='Jan'

import config_default

class Dict(dict):
	'''
	Simple dict but support access as x.y style.
	'''
	def __init__(self,names=(),values=(),**kw):
		super(Dict,self).__init__(**kw)
		for k,v in zip(names,values):
			self[k]=v #self[name]=value

	def __getattr__(self,key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(r"'Dict' object has no attribute '%s'" % key)

	def __setattr__(self,key,value):
		self[key]=value

def merge(defaults,override):
	r={}
	for k,v in defaults.items():#k:'db','session',v:dict
		if k in override:#'db'
			if isinstance(v,dict):
				r[k]=merge(v,override[k])#merge(defaults['db'],override['db'])=>'host'=> not isinstance(v,dict) r['host']='192.168.0.100'
			else:
				r[k]=override[k] #{'db':{'host':'192.168.0.100'}}
		else:
			r[k]=v
	return r #得到被覆盖后的dict

def toDict(d):
	D=Dict()
	for k,v in d.items():
		D[k]=toDict(v) if isinstance(v,dict) else v
	return D

configs=config_default.configs

try:
	import config_override
	configs=merge(configs,config_override.configs)
except ImportError:
	pass

myconfigs=toDict(configs) 