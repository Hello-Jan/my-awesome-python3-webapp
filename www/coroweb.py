# -*- coding:utf-8 -*-

__author__='Jan'

import asyncio,os,inspect,logging,functools

from urllib import parse

from aiohttp import web

from apis import APIError

def get(path):
	'''
	Define decorator @get('/path')
	'''
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args,**kw):
			return func(*args,**kw)
		wrapper.__method__='GET'
		wrapper.__route__=path
		return wrapper
	return decorator

def post(path):
	'''
	Define decorator @post('/path') path是一个字符串。。。
	'''
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args,**kw):
			return func(*args,**kw)
		wrapper.__method__='POST'
		wrapper.__route__=path
		return wrapper
	return decorator

#拿到fn的没有默认值的命名关键字参数（*或*args后面的参数）
def get_required_kw_args(fn):#fn:def hello(name,request):   name=request.match_info['name']？？？
	args=[]
	params=inspect.signature(fn).parameters
	for name,param in params.items():
		if param.kind==inspect.Parameter.KEYWORD_ONLY and param.default==inspect.Parameter.empty:
			args.append(name)
	return tuple(args)

#拿到所有的命名关键字参数
def get_named_kw_args(fn):
	args=[]
	params=inspect.signature(fn).parameters
	for name,param in params.items():
		if param.kind==inspect.Parameter.KEYWORD_ONLY:
			args.append(name)
	return tuple(args)

#判断是否有命名关键字参数
def has_named_kw_args(fn):
	params=inspect.signature(fn).parameters
	for name,param in params.items():
		if param.kind==inspect.Parameter.KEYWORD_ONLY:
			return True

#判断是否有**kw
def has_var_kw_arg(fn):
	params=inspect.signature(fn).parameters
	for name,param in params.items():
		if param.kind==inspect.Parameter.VAR_KEYWORD:
			return True

#判断是否有名为'request'的参数。最后一个判断没看懂。。。。
def has_request_arg(fn):
	sig=inspect.signature(fn)
	params=sig.parameters
	found=False
	for name,param in params.items():
		if name=='request':
			found=True
			continue
		if found and (param.kind!=inspect.Parameter.VAR_POSITIONAL and param.kind!=inspect.Parameter.KEYWORD_ONLY and param.kind!=inspect.Parameter.VAR_KEYWORD):
			raise ValueError('request parameter must be the last named parameter in function:%s%s'% (fn.__name__,str(sig)))
	return found


class RequestHandler(object):

	def __init__(self,app,fn):#app=web.Application(loop=loop,...)
		self._app=app
		self._func=fn
		self._has_request_arg=has_request_arg(fn)
		self._has_var_kw_arg=has_var_kw_arg(fn)
		self._has_named_kw_args=has_named_kw_args(fn)
		self._named_kw_args=get_named_kw_args(fn)
		self._required_kw_args=get_required_kw_args(fn)

	async def __call__(self,request):
		kw=None
		if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:#如果fn有关键字参数或命名关键字参数：
			if request.method=='POST':#如果request是post，根据request.content_type的不同，采用不同方法获得request里的内容作为params，最后统一格式变成kw
				if not request.content_type:
					return web.HTTPBadRequest('Missing Content-Type.')
				ct=request.content_type.lower()
			if ct.startswith('application/json'):
				params=await request.json()
				if not isinstance(params,dict):
					return web.HTTPBadRequest('JSON body must be object.')
				kw=params
			elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
				params=await request.post()
				kw=dict(**params)
			else:
				return web.HTTPBadRequest('Unsupported Content_Type:%s'% request.content_type)
			if request.method=='GET':
				qs=request.query_string
				if qs:
					kw=dict()
					for k,v in parse.parse_qs(qs,True).items():#urllib.parse.parse_qs(qs, keep_blank_values=False, strict_parsing=False, encoding='utf-8', errors='replace')
						kw[k]=v[0]#v[0]是什么？9009001吧。得到{FuncNo:9009001,username:1}.print(urllib.parse.parse_qs("FuncNo=9009001&username=1"))  {'FuncNo': ['9009001'], 'username': ['1']}
		if kw is None: #fn 没有**kw和命名关键字参数
			kw=dict(**request.match_info)
		else:
			if not self._has_var_kw_arg and self._named_kw_args:#如果没有**kw,但有命名关键字参数
				#remove all unamed kw:
				copy=dict()
				for name in self._named_kw_args:
					if name in kw:
						copy[name]=kw[name]
				kw=copy
			#check named arg:
			for k,v in request.match_info.items():
				if k in kw:
					logging.warning('Duplicate arg name in named arg and kw args:%s'% k)#为什么?
				kw[k]=v#添加了一部分参数
		if self._has_request_arg:
			kw['request']=request
		#check required kw:
		if self._required_kw_args:
			for name in self._required_kw_args:
				if not name in kw:
					return web.HTTPBadRequest('Missing argument:%s'%name)
		logging.info('call with args:%s'%(str(kw)))
		try:
			r=await self._func(**kw)
			return r
		except APIError as e:
			return dict(error=e.error,data=e.data,message=e.message)


def add_static(app):#为什么要把app放参数里面？
	path=os.path.join(os.path.dirname(os.path.abspath('__file__')),'static')
	app.router.add_static('/static/',path)
	logging.info('add static %s => %s'%('/static/',path))

def add_route(app,fn):#为什么要把app放参数里面？
	method=getattr(fn,'__method__',None)
	path=getattr(fn,'__route__',None)
	if path is None or method is None:
		raise ValueError('@get or @post not defined in %s.'% str(fn))
	if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
		fn=asyncio.coroutine(fn)
	logging.info('add route %s %s => %s(%s)' % (method,path,fn.__name__,','.join(inspect.signature(fn).parameters.keys())))
	app.router.add_route(method,path,RequestHandler(app,fn))#在此处用RequestHandler封装原url函数，调用了函数，但该函数有类似于装饰器的middleware，会先执行middleware，再调用实例：Requesthandler(app,fn)(request) 

def add_routes(app,module_name):
	n=module_name.rfind('.')
	if n==(-1):#没找到'.'
		mod=__import__(module_name,globals(),locals())
	else:
		name=module_name[n+1:]
		mod=getattr(__import__(module_name[:n],globals,locals(),[name]),name)#当name是一个函数的时候，mod=module.name,相当于把函数赋给它。
	for attr in dir(mod):
		if attr.startswith('_'):
			continue
		fn=getattr(mod,attr)
		if callable(fn):
			method=getattr(fn,'__method__',None)
			path=getattr(fn,'__route__',None)
			if method and path:#排除'__'开头的属性和方法且要有method、path的方法才可以add_route
				add_route(app,fn)